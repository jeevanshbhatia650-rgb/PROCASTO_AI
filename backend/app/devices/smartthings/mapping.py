"""SmartThings capabilities -> PROCASTO attributes, and PROCASTO commands -> SmartThings commands.

Best effort for Samsung appliances: unmapped capabilities are ignored rather than guessed. Verified against the
public capability reference for the standard ones (switch, powerMeter, temperatureMeasurement,
thermostatCoolingSetpoint, airConditionerMode, washer/dryerOperatingState). Error codes vary by model and firmware,
so any attribute named errorCode (or a capability ending in errorAndAlarmState) is treated as the error code.
"""

import math
import re
from datetime import datetime
from typing import Any

from app.core.models import DeviceInfo, DeviceKind

MACHINE_STATE = {"run": "RUNNING", "stop": "IDLE", "pause": "PAUSED"}
COOLING_MODES = {"cool", "auto", "dry", "wind", "aiComfort"}
KIND_BY_CAPABILITY = {
    "washerOperatingState": DeviceKind.WASHER,
    "dryerOperatingState": DeviceKind.DRYER,
    "airConditionerMode": DeviceKind.AC,
}


def detect_kind(capabilities: set[str]) -> DeviceKind | None:
    return next((kind for cap, kind in KIND_BY_CAPABILITY.items() if cap in capabilities), None)


def discover_devices(items: list[dict[str, Any]], rooms: dict[str, str] | None = None) -> list[DeviceInfo]:
    """Show every authorized device, even when its capabilities are new to PROCASTO."""
    infos: list[DeviceInfo] = []
    used: set[str] = set()
    for item in items:
        device_id = item.get("deviceId")
        if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,64}", device_id) or device_id in used:
            continue
        used.add(device_id)
        capabilities = {c.get("id") for comp in item.get("components", []) for c in comp.get("capabilities", [])}
        kind = detect_kind(capabilities) or DeviceKind.OTHER
        label = item.get("label") or item.get("name") or kind.value.title()
        name = str(label)[:80]
        infos.append(
            DeviceInfo(
                device_id=device_id,
                kind=kind,
                model_id=str(item.get("modelName") or item.get("deviceTypeName") or "")[:80],
                family=kind.value,
                display_name=name,
                aliases=[kind.value] if kind != DeviceKind.OTHER else [],
                room=(rooms or {}).get(item.get("roomId"), "My home"),
            )
        )
    return infos


def _minutes_until(value: Any, now: datetime) -> int | None:
    try:
        finish = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, math.ceil((finish - now).total_seconds() / 60))


def map_attribute(capability: str, attribute: str, value: Any, now: datetime) -> list[tuple[str, Any]]:
    """One SmartThings attribute reading -> zero or more (attribute, value) pairs in our vocabulary."""
    if attribute == "machineState" and capability in ("washerOperatingState", "dryerOperatingState"):
        return [("state", MACHINE_STATE.get(str(value), str(value).upper()))]
    if attribute == "completionTime" and capability in ("washerOperatingState", "dryerOperatingState"):
        minutes = _minutes_until(value, now)
        return [("remaining_min", minutes)] if minutes is not None else []
    if (capability, attribute) == ("powerMeter", "power"):
        return [("power_w", value)]
    if (capability, attribute) == ("temperatureMeasurement", "temperature"):
        return [("temp_c", value)]
    if (capability, attribute) == ("thermostatCoolingSetpoint", "coolingSetpoint"):
        return [("target_temp_c", value)]
    if (capability, attribute) == ("switch", "switch") and value in ("on", "off"):
        return [("state", str(value).upper())]
    if (capability, attribute) == ("airConditionerMode", "airConditionerMode"):
        return [("state", "COOLING" if value in COOLING_MODES else str(value).upper())]
    if attribute == "errorCode" or capability.endswith("errorAndAlarmState"):
        code = None if value in (None, "", "none", "normal") else value
        return [("error_code", code)] + ([("state", "ERROR")] if code else [])
    return []


def to_smartthings(command: str, args: dict[str, Any]) -> tuple[str, str, list[Any]]:
    """Our confirmed CardCommand -> (capability, command, arguments)."""
    if command == "set_target_temp":
        return "thermostatCoolingSetpoint", "setCoolingSetpoint", [float(args["value"])]
    if command == "power_off":
        return "switch", "off", []
    if command == "power_on":
        return "switch", "on", []
    if command == "restart":
        return "washerOperatingState", "setMachineState", ["run"]
    raise ValueError(f"no SmartThings mapping for {command!r}")
