"""F24: device commands only run after the user confirms a card, at most once per card revision."""

from app.core.models import CardCommand, DeviceInfo
from app.devices.provider import DeviceProvider


def describe(command: CardCommand, name: str) -> str:
    if command.command == "set_target_temp":
        return f"{name} set to {float(command.args['value']):g} °C"
    if command.command in ("power_off", "power_on"):
        return f"{name} turned {command.command.removeprefix('power_')}"
    if command.command == "restart":
        return f"{name} restarted"
    return f"{name}: {command.command} sent"


class CommandGate:
    def __init__(
        self, provider: DeviceProvider, infos: dict[str, DeviceInfo], real_devices: bool, allow_real: bool
    ) -> None:
        self._provider = provider
        self._infos = infos
        self._real_devices = real_devices
        self._allow_real = allow_real
        self._done: dict[str, str] = {}

    async def execute(self, command: CardCommand, idempotency_key: str) -> str:
        if idempotency_key in self._done:
            return self._done[idempotency_key]  # a double click must not send twice
        if self._real_devices and not self._allow_real:
            raise PermissionError("Device control is off. Set ALLOW_COMMANDS=true to control real devices.")
        if command.device_id not in self._infos:
            raise ValueError(f"Unknown device {command.device_id}")
        await self._provider.send_command(command.device_id, command.command, command.args)
        message = describe(command, self._infos[command.device_id].display_name)
        self._done[idempotency_key] = message
        return message
