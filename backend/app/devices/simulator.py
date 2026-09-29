"""F1: a simulated home. Ticks once a second and exposes 'break something' scenarios."""

import asyncio
import copy
import logging
import math
import random
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.ids import Clock
from app.core.models import DeviceEvent, DeviceInfo, DeviceKind
from app.devices.normalizer import normalize

log = logging.getLogger(__name__)

EventSink = Callable[[DeviceEvent], Awaitable[Any]]
SCENARIOS = ("washer_e3", "washer_done", "ac_spike", "dryer_done", "reset")
ROOM_TEMP_C = 22.0
RUN_POWER_W = {DeviceKind.WASHER: 450, DeviceKind.DRYER: 800}


def ac_power_for(target_c: float) -> int:
    """Rated 1.8 kW at 22 °C; each degree colder costs ~350 W (matches the AR12 manual)."""
    return int(1800 + (ROOM_TEMP_C - target_c) * 350)


class Simulator:
    def __init__(
        self,
        devices: list[DeviceInfo],
        initial: dict[str, dict[str, Any]],
        sink: EventSink,
        clock: Clock,
        seed: int = 7,
        tick_s: float = 1.0,
    ) -> None:
        self._infos = {d.device_id: d for d in devices}
        self._initial = copy.deepcopy(initial)
        self._state = copy.deepcopy(initial)
        self._sink = sink
        self._clock = clock
        self._rng = random.Random(seed)
        self._tick_s = tick_s
        self._seconds_left = self._initial_seconds()
        self._task: asyncio.Task[None] | None = None

    def devices(self) -> list[DeviceInfo]:
        return list(self._infos.values())

    async def start(self) -> None:
        for device_id, attrs in self._state.items():
            await self._emit(device_id, attrs)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._tick_s)
            await self.tick()

    async def tick(self) -> None:
        for device_id in self._state:
            await self._apply(device_id, self._tick_changes(device_id))

    def _tick_changes(self, device_id: str) -> dict[str, Any]:
        kind = self._infos[device_id].kind
        attrs = self._state[device_id]
        if kind == DeviceKind.AC:
            return self._tick_ac(attrs)
        if attrs["state"] != "RUNNING":
            # Water left in a stopped washer slowly cools toward room temperature.
            temp = attrs.get("temp_c")
            if temp is not None and temp > ROOM_TEMP_C:
                return {"temp_c": round(max(ROOM_TEMP_C, temp - 0.1), 1)}
            return {}
        self._seconds_left[device_id] = max(0.0, self._seconds_left[device_id] - self._tick_s)
        left = self._seconds_left[device_id]
        if left <= 0:
            return {"state": "DONE", "remaining_min": 0, "power_w": 0}
        noise = self._rng.uniform(-30, 30)
        return {"remaining_min": math.ceil(left / 60), "power_w": int(RUN_POWER_W[kind] + noise)}

    def _tick_ac(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["state"] != "COOLING":
            return {}
        target = attrs["target_temp_c"]
        temp = attrs["temp_c"]
        if temp != target:  # the room drifts 0.1 °C per tick toward the target
            temp = round(temp - 0.1 if temp > target else temp + 0.1, 1)
        noise = self._rng.uniform(-40, 40)
        return {"power_w": int(ac_power_for(target) + noise), "temp_c": temp}

    async def trigger(self, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}")
        if scenario == "reset":
            await self.reset()
        elif scenario == "washer_e3":
            # error_code first, so anyone reacting to state=ERROR already sees the code.
            await self._apply("washer-01", {"error_code": "E3", "state": "ERROR", "power_w": 0})
        elif scenario == "washer_done":
            self._seconds_left["washer-01"] = 0
            await self._apply("washer-01", {"error_code": None, "state": "DONE", "remaining_min": 0, "power_w": 0})
        elif scenario == "ac_spike":
            await self._apply("ac-01", {"target_temp_c": 18.0, "power_w": ac_power_for(18.0)})
        elif scenario == "dryer_done":
            await self._apply("dryer-01", {"state": "DONE", "remaining_min": 0, "power_w": 2})

    async def reset(self) -> None:
        self._seconds_left = self._initial_seconds()
        for device_id, attrs in self._initial.items():
            await self._apply(device_id, copy.deepcopy(attrs))

    async def send_command(self, device_id: str, command: str, args: dict[str, Any]) -> None:
        kind = self._infos[device_id].kind if device_id in self._infos else None
        if kind == DeviceKind.AC and command == "set_target_temp":
            value = float(args["value"])
            if not 16 <= value <= 30:
                raise ValueError("target temperature must be between 16 and 30 °C")
            await self._apply(device_id, {"target_temp_c": value, "power_w": ac_power_for(value)})
        elif kind == DeviceKind.AC and command in ("power_off", "power_on"):
            on = command == "power_on"
            power = ac_power_for(self._state[device_id]["target_temp_c"]) if on else 0
            await self._apply(device_id, {"state": "COOLING" if on else "OFF", "power_w": power})
        elif kind == DeviceKind.WASHER and command == "restart":
            self._seconds_left[device_id] = max(60.0, self._state[device_id]["remaining_min"] * 60.0)
            await self._apply(device_id, {"error_code": None, "state": "RUNNING", "temp_c": 40.0})
        else:
            raise ValueError(f"unsupported command {command!r} for {device_id!r}")

    async def _apply(self, device_id: str, changes: dict[str, Any]) -> None:
        changed = {k: v for k, v in changes.items() if self._state[device_id].get(k) != v}
        self._state[device_id].update(changed)
        await self._emit(device_id, changed)

    async def _emit(self, device_id: str, attrs: dict[str, Any]) -> None:
        for attribute, value in attrs.items():
            event = normalize(device_id, attribute, value, "simulator", self._clock.now())
            if event:
                await self._sink(event)

    def _initial_seconds(self) -> dict[str, float]:
        return {d: float(a.get("remaining_min", 0)) * 60 for d, a in self._initial.items()}
