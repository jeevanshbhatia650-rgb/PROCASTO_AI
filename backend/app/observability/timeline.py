"""F20: every step the engine takes, stamped relative to the session start, streamed to the UI."""

from collections.abc import Callable
from typing import Any

from app.core.ids import Clock
from app.core.models import TimelineEvent, TimelineKind

Send = Callable[[str, Any], None]


class Timeline:
    def __init__(self, clock: Clock, send: Send) -> None:
        self._clock = clock
        self._t0 = clock.ms()
        self._send = send

    def now_ms(self) -> int:
        return self._clock.ms() - self._t0

    def emit(self, kind: TimelineKind, **detail: Any) -> TimelineEvent:
        event = TimelineEvent(t_ms=self.now_ms(), kind=kind, detail=detail)
        self._send("timeline.event", event)
        return event
