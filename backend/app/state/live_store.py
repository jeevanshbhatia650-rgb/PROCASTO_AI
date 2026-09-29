"""F4: revisioned live device state. Every applied event bumps the device's revision."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.bus import Bus
from app.core.ids import Clock
from app.core.models import DeviceEvent, DeviceInfo, DeviceSnapshot

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceChange:
    snapshot: DeviceSnapshot
    event: DeviceEvent
    previous: Any


class LiveStore:
    def __init__(self, devices: list[DeviceInfo], bus: Bus, clock: Clock) -> None:
        now = clock.now()
        self._snaps = {d.device_id: DeviceSnapshot(info=d, attributes={}, revision=0, updated_at=now) for d in devices}
        self._last_seen: dict[tuple[str, str], datetime] = {}
        self._bus = bus

    async def apply(self, event: DeviceEvent) -> DeviceSnapshot | None:
        """Returns the new snapshot, or None when the event is unknown or older than what we have."""
        snap = self._snaps.get(event.device_id)
        if snap is None:
            log.warning("event for unknown device %s", event.device_id)
            return None
        key = (event.device_id, event.attribute)
        last = self._last_seen.get(key)
        if last is not None and event.observed_at < last:
            return None  # out-of-order delivery: we already hold a newer reading
        self._last_seen[key] = event.observed_at
        previous = snap.attributes.get(event.attribute)
        new = snap.model_copy(
            update={
                "attributes": {**snap.attributes, event.attribute: event.value},
                "revision": snap.revision + 1,
                "updated_at": max(snap.updated_at, event.observed_at),
            }
        )
        self._snaps[event.device_id] = new
        await self._bus.publish("device.update", DeviceChange(new, event, previous))
        return new

    def get(self, device_id: str) -> DeviceSnapshot:
        return self._snaps[device_id]

    def revision(self, device_id: str) -> int:
        return self._snaps[device_id].revision

    def all(self) -> list[DeviceSnapshot]:
        return list(self._snaps.values())
