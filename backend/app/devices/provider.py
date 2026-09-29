"""The contract every device source implements (simulator today, SmartThings behind a flag)."""

from typing import Any, Protocol

from app.core.models import DeviceInfo


class DeviceProvider(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def devices(self) -> list[DeviceInfo]: ...

    async def send_command(self, device_id: str, command: str, args: dict[str, Any]) -> None: ...
