"""F23: a signed-in user's real devices behind the same DeviceProvider contract as the simulator."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.config import Settings
from app.core.ids import Clock
from app.core.models import DeviceEvent, DeviceInfo
from app.devices.normalizer import normalize
from app.devices.smartthings.client import SmartThingsClient
from app.devices.smartthings.mapping import detect_kind, map_attribute, to_smartthings
from app.devices.smartthings.oauth import Token

log = logging.getLogger(__name__)
EventSink = Callable[[DeviceEvent], Awaitable[Any]]


class SmartThingsProvider:
    """One user's real devices. Login and the webhook are server-wide and live elsewhere."""

    def __init__(
        self, settings: Settings, devices: list[DeviceInfo], sink: EventSink, clock: Clock, http: httpx.AsyncClient
    ) -> None:
        self._http = http  # shared by the whole server, which closes it
        self._infos = {d.device_id: d for d in devices}
        self._by_kind = {d.kind: d for d in devices}
        self._sink, self._clock = sink, clock
        self._public_url = settings.public_base_url.rstrip("/")
        self._client: SmartThingsClient | None = None
        self._bindings: dict[str, str] = {}  # SmartThings deviceId -> our device_id

    @property
    def connected(self) -> bool:
        return self._client is not None

    def devices(self) -> list[DeviceInfo]:
        return list(self._infos.values())

    def device_for(self, smartthings_id: str) -> str | None:
        return self._bindings.get(smartthings_id)

    async def start(self) -> None:
        pass  # connect() already loaded the devices

    async def stop(self) -> None:
        pass

    async def connect(self, token: Token, listed: list[dict[str, Any]] | None = None) -> dict[str, str]:
        """Binds every discovered device, loads its state, and subscribes to events."""
        client = SmartThingsClient(token.access_token, self._http)
        bindings: dict[str, str] = {}
        for item in listed if listed is not None else await client.devices():
            capabilities = {c["id"] for comp in item.get("components", []) for c in comp.get("capabilities", [])}
            kind = detect_kind(capabilities)
            info = self._infos.get(item.get("deviceId")) or (self._by_kind.get(kind) if kind else None)
            if info and info.device_id not in bindings.values():
                bindings[item["deviceId"]] = info.device_id
        self._client, self._bindings = client, bindings
        for smartthings_id, device_id in bindings.items():
            try:
                await self._load_status(client, smartthings_id, device_id)
                if token.installed_app_id and self._public_url:
                    await client.subscribe(token.installed_app_id, smartthings_id)
            except httpx.HTTPError as exc:
                log.warning("SmartThings device %s status or subscription failed: %s", smartthings_id, exc)
        if not self._public_url:
            log.warning("PUBLIC_BASE_URL is empty: device states load once, but live events can't reach this server")
        return bindings

    async def _load_status(self, client: SmartThingsClient, smartthings_id: str, device_id: str) -> None:
        now = self._clock.now()
        for capability, attributes in (await client.status(smartthings_id)).items():
            for attribute, reading in attributes.items():
                value = reading.get("value") if isinstance(reading, dict) else None
                for name, mapped in map_attribute(capability, attribute, value, now):
                    event = normalize(device_id, name, mapped, "smartthings", now)
                    if event:
                        await self._sink(event)

    async def send_command(self, device_id: str, command: str, args: dict[str, Any]) -> None:
        if self._client is None:
            raise ValueError("SmartThings isn't connected yet.")
        smartthings_id = next((st for st, ours in self._bindings.items() if ours == device_id), None)
        if smartthings_id is None:
            raise ValueError(f"No SmartThings device is bound to {device_id}.")
        capability, name, arguments = to_smartthings(command, args)
        await self._client.command(smartthings_id, capability, name, arguments)
