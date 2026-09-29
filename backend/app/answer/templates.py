"""F17: deterministic card text. Every number on a card comes from here, never from the LLM."""

import re
from dataclasses import dataclass
from typing import Any

from app.core.models import DeviceKind

_RATED = re.compile(r"rated[^.]*?(\d+(?:\.\d+)?)\s*kW\b", re.IGNORECASE)
AC_COMFORT_TARGET_C = 24.0


@dataclass(frozen=True)
class CardText:
    title: str
    body: str
    speakable: str
    severity: str = "info"
    steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandSpec:
    command: str
    args: dict[str, Any]
    label: str


def fmt_power(watts: float | None) -> str:
    if watts is None:
        return "unknown power"
    return f"{watts / 1000:.1f} kW" if watts >= 1000 else f"{int(watts)} W"


def spoken_power(watts: float | None) -> str:
    if watts is None:
        return "an unknown amount of power"
    return f"{watts / 1000:.1f} kilowatts" if watts >= 1000 else f"{int(watts)} watts"


def fmt_temp(celsius: float | None) -> str:
    return "?" if celsius is None else f"{celsius:g} °C"


def spoken_name(name: str) -> str:
    return name if name.isupper() else name.lower()  # "AC" stays spelled out for text-to-speech


def rated_kw(text: str) -> float | None:
    match = _RATED.search(text)
    return float(match.group(1)) if match else None


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def status_text(name: str, kind: DeviceKind, attrs: dict[str, Any]) -> CardText:
    state, code, power = attrs.get("state", "UNKNOWN"), attrs.get("error_code"), attrs.get("power_w")
    said = spoken_name(name)
    if state == "ERROR" or code:
        left = attrs.get("remaining_min")
        body = f"It was {left} min from done. Power is {fmt_power(power)}." if left else f"Power is {fmt_power(power)}."
        return CardText(f"{name} stopped · Error {code}", body, f"The {said} stopped with error {code}.", "error")
    if kind == DeviceKind.AC:
        target, temp = attrs.get("target_temp_c"), attrs.get("temp_c")
        if state == "OFF":
            return CardText(f"{name} is off", f"Room at {fmt_temp(temp)}.", f"The {said} is off.")
        spike = power is not None and power > 2500
        return CardText(
            f"{name} · Cooling to {fmt_temp(target)}",
            f"Room at {fmt_temp(temp)}, drawing {fmt_power(power)}.",
            f"The {said} is cooling to {target:g} degrees and drawing {spoken_power(power)}.",
            "warn" if spike else "ok",
        )
    if state == "RUNNING":
        left, water = attrs.get("remaining_min"), attrs.get("temp_c")
        at = f" at {fmt_temp(water)}" if water is not None else ""
        return CardText(
            f"{name} · {left} min left",
            f"Running{at}, drawing {fmt_power(power)}.",
            f"The {said} has {left} minutes left.",
            "ok",
        )
    if state == "DONE":
        return CardText(f"{name} · Done", "The cycle has finished.", f"The {said} is done.", "ok")
    if state == "IDLE":
        return CardText(f"{name} · Idle", f"Nothing running. Standby draw {fmt_power(power)}.", f"The {said} is idle.")
    return CardText(f"{name} · {state.title()}", "", f"The {said} is {state.lower()}.")


def problem_text(code: str, hit: dict[str, Any] | None, active_code: str | None, model_id: str) -> CardText:
    if hit is None:
        return CardText(
            f"{code} isn't in the {model_id} manual",
            "Check the code on the display and try again.",
            f"I couldn't find {code} in the {model_id} manual.",
            "warn",
        )
    severity = "error" if active_code == code else "info"
    return CardText(f"{code} · {hit['title']}", hit["summary"], f"{code} means {lower_first(hit['title'])}.", severity)


def todo_text(hit: dict[str, Any], fix_hit: dict[str, Any] | None, phrase: str | None) -> CardText:
    steps = tuple(hit.get("steps") or (fix_hit or {}).get("steps") or ())
    fallback = (fix_hit or {}).get("summary") or hit.get("summary", "")
    speak = f"First, {lower_first(steps[0])}" if steps else (phrase or fallback)
    return CardText("What to do", phrase or fallback, speak, "info", steps)


def energy_text(name: str, attrs: dict[str, Any], hit: dict[str, Any] | None, phrase: str | None) -> CardText:
    power = attrs.get("power_w")
    rated = rated_kw(hit["text"]) if hit else None
    said = spoken_name(name)
    if rated and power:
        pct = round((power / 1000 - rated) / rated * 100)
        fact = (
            f"That's {pct}% above the {rated:g} kW the manual rates it at."
            if pct > 10
            else (f"That's within the {rated:g} kW the manual rates it at.")
        )
        severity = "warn" if pct > 25 else "info"
        speak = (
            f"The {said} is drawing {spoken_power(power)}, {pct} percent above normal."
            if pct > 10
            else (f"The {said} is drawing {spoken_power(power)}, which is normal.")
        )
    else:
        fact, severity = "", "info"
        speak = f"The {said} is drawing {spoken_power(power)}."
    detail = phrase or (hit["summary"] if hit else "")
    return CardText(f"{name} drawing {fmt_power(power)}", f"{fact} {detail}".strip(), speak, severity)


def energy_command(kind: DeviceKind, attrs: dict[str, Any]) -> CommandSpec | None:
    target = attrs.get("target_temp_c")
    if kind == DeviceKind.AC and target is not None and target < AC_COMFORT_TARGET_C:
        return CommandSpec("set_target_temp", {"value": AC_COMFORT_TARGET_C}, f"Set to {AC_COMFORT_TARGET_C:g} °C")
    return None


def confirm_text(
    name: str, kind: DeviceKind, params: dict[str, Any], attrs: dict[str, Any]
) -> tuple[CardText, CommandSpec] | None:
    said = spoken_name(name)
    if kind == DeviceKind.AC and "target_temp_c" in params:
        value = float(params["target_temp_c"])
        text = CardText(
            f"Set the {name} to {value:g} °C?",
            f"The target is {fmt_temp(attrs.get('target_temp_c'))} now.",
            f"Should I set the {said} to {value:g} degrees?",
        )
        return text, CommandSpec("set_target_temp", {"value": value}, f"Set to {value:g} °C")
    if kind == DeviceKind.AC and params.get("power") in ("off", "on"):
        verb = f"power_{params['power']}"
        text = CardText(f"Turn the {name} {params['power']}?", "", f"Should I turn the {said} {params['power']}?")
        return text, CommandSpec(verb, {}, f"Turn {params['power']}")
    if kind == DeviceKind.WASHER and params.get("command") == "restart":
        text = CardText(f"Restart the {name}?", "Only if the filter is clean.", f"Should I restart the {said}?")
        return text, CommandSpec("restart", {}, "Restart")
    return None
