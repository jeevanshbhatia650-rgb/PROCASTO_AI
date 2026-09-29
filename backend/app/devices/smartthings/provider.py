"""F23: real devices behind the same DeviceProvider contract as the simulator (DEVICE_PROVIDER=smartthings)."""

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
from app.devices.smartthings.oauth import OAuthFlow, Token
from app.devices.smartthings.signature import SignatureVerifier, http_key_fetcher
from app.devices.smartthings.webhook import WebhookHandler

log = logging.getLogger(__name__)
EventSink = Callable[[DeviceEvent], Awaitable[Any]]


class SmartThingsProvider:
    def __init__(
        self, settings: Settings, devices: list[DeviceInfo], sink: EventSink, clock: Clock,
        http: httpx.AsyncClient | None = None,
    ) -> None:  # fmt: skip
        self._http = http or httpx.AsyncClient()
        self._by_kind = {d.kind: d for d in devices}
        self._sink, self._clock = sink, clock
        self._public_url = settings.public_base_url.rstrip("/")
        self._client: SmartThingsClient | None = None
        self._bindings: dict[str, str] = {}  # SmartThings deviceId -> our device_id
        self.oauth = OAuthFlow(settings.smartthings_client_id, settings.smartthings_client_secret,
                               settings.smartthings_redirect_uri, self._http)  # fmt: skip
        self.webhook = WebhookHandler(
            SignatureVerifier(http_key_fetcher(self._http)), sink, self.device_for,
            target_url=f"{self._public_url}/webhooks/smartthings",
        )  # fmt: skip

    @property
    def connected(self) -> bool:
        return self._client is not None

    def devices(self) -> list[DeviceInfo]:
        return list(self._by_kind.values())

    def device_for(self, smartthings_id: str) -> str | None:
        return self._bindings.get(smartthings_id)

    async def start(self) -> None:
        log.info("SmartThings mode: open /auth/smartthings/login to connect your devices")

    async def stop(self) -> None:
        await self._http.aclose()

    async def connect(self, token: Token) -> dict[str, str]:
        """Binds one real washer, dryer and AC by their capabilities, loads their state, subscribes to events."""
        client = SmartThingsClient(token.access_token, self._http)
        bindings: dict[str, str] = {}
        for item in await client.devices():
            capabilities = {c["id"] for comp in item.get("components", []) for c in comp.get("capabilities", [])}
            kind = detect_kind(capabilities)
            info = self._by_kind.get(kind) if kind else None
            if info and info.device_id not in bindings.values():
                bindings[item["deviceId"]] = info.device_id
        self._client, self._bindings = client, bindings
        for smartthings_id, device_id in bindings.items():
            await self._load_status(client, smartthings_id, device_id)
            if token.installed_app_id and self._public_url:
                await client.subscribe(token.installed_app_id, smartthings_id)
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
            raise ValueError("SmartThings isn't connected yet. Open /auth/smartthings/login first.")
        smartthings_id = next((st for st, ours in self._bindings.items() if ours == device_id), None)
        if smartthings_id is None:
            raise ValueError(f"No SmartThings device is bound to {device_id}.")
        capability, name, arguments = to_smartthings(command, args)
        await self._client.command(smartthings_id, capability, name, arguments)
