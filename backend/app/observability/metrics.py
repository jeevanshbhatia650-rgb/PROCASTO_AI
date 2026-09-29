"""F20: retrieval lead time = end of speech minus the first retrieval a stable clause started."""

from collections.abc import Callable
from typing import Any

from app.core.models import Metrics

Send = Callable[[str, Any], None]


class MetricsTracker:
    def __init__(self, send: Send) -> None:
        self._send = send
        self._value = Metrics()
        self._first_task_ms: int | None = None
        self._first_card_ms: int | None = None
        self._end_ms: int | None = None

    @property
    def value(self) -> Metrics:
        return self._value

    def begin_utterance(self) -> None:
        self._first_task_ms = self._first_card_ms = self._end_ms = None

    def task_started(self, t_ms: int) -> None:
        if self._first_task_ms is None and self._end_ms is None:
            self._first_task_ms = t_ms

    def card_shown(self, t_ms: int) -> None:
        if self._first_card_ms is None and (self._first_task_ms is not None or self._end_ms is not None):
            self._first_card_ms = t_ms
            if self._end_ms is not None:
                self._publish()

    def end_utterance(self, t_ms: int) -> Metrics:
        self._end_ms = t_ms
        return self._publish()

    def resumed(self, reused: int, refetched: int) -> Metrics:
        self._value = self._value.model_copy(update={"tasks_reused": reused, "tasks_refetched": refetched})
        self._send("metrics.update", self._value)
        return self._value

    def _publish(self) -> Metrics:
        end = self._end_ms
        lead = end - self._first_task_ms if end is not None and self._first_task_ms is not None else None
        first_card = self._first_card_ms - end if end is not None and self._first_card_ms is not None else None
        best = self._value.best_lead_time_ms
        if lead is not None and (best is None or lead > best):
            best = lead
        self._value = self._value.model_copy(
            update={"lead_time_ms": lead, "best_lead_time_ms": best, "first_card_ms": first_card}
        )
        self._send("metrics.update", self._value)
        return self._value
