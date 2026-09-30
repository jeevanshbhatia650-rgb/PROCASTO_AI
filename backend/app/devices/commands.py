"""F24: device commands only run after the user confirms a card, at most once per card revision."""

import logging
from collections import OrderedDict
from collections.abc import Callable

from app.core.models import CardCommand, DeviceInfo
from app.devices.provider import DeviceProvider

log = logging.getLogger(__name__)
REMEMBERED_COMMANDS = 200


class CommandError(Exception):
    """The device (or its cloud) didn't take the command. Nothing changed."""


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
        self._done: OrderedDict[str, str] = OrderedDict()
        self.on_done: Callable[[CardCommand], None] = lambda command: None  # e.g. teach the Preference agent

    async def execute(self, command: CardCommand, idempotency_key: str) -> str:
        if idempotency_key in self._done:
            return self._done[idempotency_key]  # a double click must not send twice
        if self._real_devices and not self._allow_real:
            raise PermissionError("Device control is off. Set ALLOW_COMMANDS=true to control real devices.")
        if command.device_id not in self._infos:
            raise ValueError(f"Unknown device {command.device_id}")
        name = self._infos[command.device_id].display_name
        try:
            await self._provider.send_command(command.device_id, command.command, command.args)
        except (ValueError, PermissionError):
            raise  # already a clear, user-facing reason
        except Exception as exc:  # network, timeout, cloud error: report it, keep the session alive
            log.warning("%s to %s failed: %s", command.command, command.device_id, type(exc).__name__)
            raise CommandError(f"The {name} didn't respond, so nothing was changed. Try again in a moment.") from exc
        message = describe(command, name)
        self._done[idempotency_key] = message
        self.on_done(command)
        while len(self._done) > REMEMBERED_COMMANDS:
            self._done.popitem(last=False)
        return message
