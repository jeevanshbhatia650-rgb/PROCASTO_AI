"""F3: every device source (simulator, SmartThings) goes through here to become a DeviceEvent."""

import logging
import re
from datetime import datetime
from typing import Any, Literal

from app.core.ids import new_id
from app.core.models import DeviceEvent

log = logging.getLogger(__name__)

KNOWN_ATTRIBUTES = ("state", "remaining_min", "power_w", "error_code", "temp_c", "target_temp_c")
_CODE_RE = re.compile(r"^([A-Za-z]{1,2})\s?(\d{1,2})$")
_EMPTY = (None, "", "none", "None", "null")


def normalize_error_code(value: Any) -> str | None:
    """'e 3', 'E3', ' E3 ' -> 'E3'. Empty-ish values mean no error."""
    if value in _EMPTY:
        return None
    text = str(value).strip()
    match = _CODE_RE.match(text)
    return f"{match.group(1).upper()}{match.group(2)}" if match else text.upper()


def coerce(attribute: str, value: Any) -> Any:
    if attribute == "state":
        return str(value).strip().upper()
    if attribute == "error_code":
        return normalize_error_code(value)
    if attribute in ("remaining_min", "power_w"):
        return int(round(float(value)))
    return round(float(value), 1)  # temp_c, target_temp_c


def normalize(
    device_id: str,
    attribute: str,
    value: Any,
    source: Literal["simulator", "smartthings"],
    observed_at: datetime,
) -> DeviceEvent | None:
    """Returns None (and logs) for attributes we don't track or values we can't read."""
    if attribute not in KNOWN_ATTRIBUTES:
        return None
    try:
        clean = coerce(attribute, value)
    except (TypeError, ValueError):
        log.warning("dropping unreadable %s=%r from %s for %s", attribute, value, source, device_id)
        return None
    return DeviceEvent(
        event_id=new_id("ev"),
        device_id=device_id,
        attribute=attribute,
        value=clean,
        observed_at=observed_at,
        source=source,
    )
