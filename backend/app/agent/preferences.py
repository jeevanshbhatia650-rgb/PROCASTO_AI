"""The Preference agent's store: small facts about how this home is used, read by key in well under a millisecond.

Preferences change weekly, not by the second, so a vector search over them would be absurd overhead: this is a plain
key-value store per home (in memory here; Redis is a drop-in when several servers share homes). Values expire after
a month so an old habit fades, and confirmed actions teach it: setting the AC to 24 °C twice makes 24 °C the usual.
"""

import time
from collections.abc import Callable
from typing import Any

from app.core.models import CardCommand

MONTH_S = 30 * 24 * 3600
MAX_KEYS_PER_DEVICE = 20

# What the simulated demo home "remembers", so the demo shows the agent at work. Real homes start empty and learn.
DEMO_PREFERENCES: dict[str, dict[str, Any]] = {
    "washer-01": {"usual_cycle": "Eco 40-60", "usual_temp_c": 30},
    "dryer-01": {"usual_cycle": "Cotton cupboard dry"},
    "ac-01": {"preferred_target_c": 24},
}


class PreferenceStore:
    def __init__(self, seed: dict[str, dict[str, Any]] | None = None, now: Callable[[], float] = time.time) -> None:
        self._now = now
        self._data: dict[str, dict[str, tuple[Any, float]]] = {}
        for device_id, values in (seed or {}).items():
            for key, value in values.items():
                self.set(device_id, key, value)

    def set(self, device_id: str, key: str, value: Any) -> None:
        values = self._data.setdefault(device_id, {})
        values[key] = (value, self._now() + MONTH_S)
        while len(values) > MAX_KEYS_PER_DEVICE:
            values.pop(next(iter(values)))

    def get(self, device_id: str) -> dict[str, Any]:
        now = self._now()
        return {key: value for key, (value, expires) in self._data.get(device_id, {}).items() if expires > now}

    def learn(self, command: CardCommand) -> None:
        """A confirmed action is the strongest signal of a habit."""
        if command.command == "set_target_temp":
            self.set(command.device_id, "preferred_target_c", float(command.args["value"]))


def describe(prefs: dict[str, Any]) -> str:
    """Preferences in words: "usual cycle Eco 40-60, usually 30 °C"."""
    words = {
        "usual_cycle": lambda v: f"usual cycle {v}",
        "usual_temp_c": lambda v: f"usually {v:g} °C" if isinstance(v, int | float) else f"usually {v}",
        "preferred_target_c": lambda v: f"likes {v:g} °C" if isinstance(v, int | float) else f"likes {v}",
    }
    return ", ".join(words.get(k, lambda v, k=k: f"{k.replace('_', ' ')} {v}")(v) for k, v in prefs.items())
