"""F23: the SmartThings webhook. PING echoes its challenge; every other lifecycle must carry a valid signature."""

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.models import DeviceEvent
from app.devices.normalizer import normalize
from app.devices.smartthings.mapping import map_attribute
from app.devices.smartthings.signature import SignatureError, SignatureVerifier

log = logging.getLogger(__name__)
EventSink = Callable[[DeviceEvent], Awaitable[Any]]
MAX_BODY_BYTES = 256 * 1024


def _when(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def device_events(payload: dict[str, Any], device_for: Callable[[str], str | None]) -> list[DeviceEvent]:
    """EVENT lifecycle -> normalized DeviceEvents for the devices we're bound to."""
    out: list[DeviceEvent] = []
    for item in payload.get("eventData", {}).get("events", []):
        if item.get("eventType") != "DEVICE_EVENT":
            continue
        raw = item.get("deviceEvent", {})
        device_id = device_for(str(raw.get("deviceId", "")))
        if device_id is None:
            continue
        when = _when(item.get("eventTime"))
        for attribute, value in map_attribute(
            raw.get("capability", ""), raw.get("attribute", ""), raw.get("value"), when
        ):
            event = normalize(device_id, attribute, value, "smartthings", when)
            if event:
                out.append(event)
    return out


class WebhookHandler:
    def __init__(
        self,
        verifier: SignatureVerifier,
        sink: EventSink,
        device_for: Callable[[str], str | None],
        target_url: str,
    ) -> None:
        self._verifier, self._sink, self._device_for = verifier, sink, device_for
        self._target_url = target_url

    async def handle(self, method: str, path: str, headers: Mapping[str, str], body: bytes) -> tuple[int, dict]:
        if len(body) > MAX_BODY_BYTES:
            return 413, {"error": "payload too large"}
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400, {"error": "invalid JSON"}
        lifecycle = payload.get("lifecycle") if isinstance(payload, dict) else None
        if lifecycle == "PING":
            return 200, {"pingData": {"challenge": payload.get("pingData", {}).get("challenge")}}
        try:
            await self._verifier.verify(method, path, headers, body)
        except SignatureError as exc:
            log.warning("rejected an unsigned or forged SmartThings request: %s", exc)
            return 401, {"error": "unauthorized"}
        if lifecycle == "CONFIRMATION":
            # Same as the official SDK: log it, never fetch a URL a request handed us.
            url = payload.get("confirmationData", {}).get("confirmationUrl")
            log.warning("SmartThings wants this webhook confirmed. Open this URL once in a browser: %s", url)
            return 200, {"targetUrl": self._target_url}
        if lifecycle == "EVENT":
            for event in device_events(payload, self._device_for):
                await self._sink(event)
            return 200, {"eventData": {}}
        log.info("ignoring SmartThings lifecycle %s", lifecycle)
        return 200, {}
