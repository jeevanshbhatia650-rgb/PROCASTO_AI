"""F12: session context. Last turns plus recently referenced devices, to resolve "it" and "the other one"."""

from collections import deque
from dataclasses import dataclass

from app.core.ids import Clock
from app.core.models import Clause, Evidence, RetrievalTask
from app.retrieval.base import evidence_id


@dataclass(frozen=True)
class Turn:
    text: str
    device_ids: tuple[str, ...]


class SessionContext:
    def __init__(self, max_turns: int = 5) -> None:
        self._turns: deque[Turn] = deque(maxlen=max_turns)
        self._recent: list[str] = []  # most recently referenced last

    def note_devices(self, device_ids: list[str]) -> None:
        for device_id in device_ids:
            if device_id in self._recent:
                self._recent.remove(device_id)
            self._recent.append(device_id)

    def add_turn(self, text: str, device_ids: list[str]) -> None:
        self._turns.append(Turn(text, tuple(device_ids)))
        self.note_devices(device_ids)

    def turns(self) -> list[Turn]:
        return list(self._turns)

    def last_device(self) -> str | None:
        return self._recent[-1] if self._recent else None

    def other_device(self) -> str | None:
        return self._recent[-2] if len(self._recent) > 1 else None

    def resolve(self, clause: Clause) -> Clause:
        """Fills a missing device from context; returns the clause unchanged if nothing fits."""
        if clause.device_id:
            return clause
        target = self.other_device() if clause.params.get("ref") == "other" else self.last_device()
        if target is None:
            return clause
        key = f"{clause.intent.value}:{target}:{clause.error_code or '-'}"
        params = {**clause.params, "resolved_from": clause.params.get("ref", "context")}
        return clause.model_copy(update={"device_id": target, "clause_id": key, "params": params})


class SessionRetriever:
    def __init__(self, context: SessionContext, clock: Clock) -> None:
        self._context = context
        self._clock = clock

    async def retrieve(self, task: RetrievalTask) -> Evidence:
        turns = self._context.turns()
        return Evidence(
            evidence_id=evidence_id(task),
            task_id=task.task_id,
            source_type="session",
            device_id=task.device_id,
            model_id=None,
            authority="session",
            observed_at=self._clock.now(),
            device_revision=None,
            plan_revision=task.plan_revision,
            payload={
                "turns": [{"text": t.text, "devices": list(t.device_ids)} for t in turns],
                "last_device": self._context.last_device(),
            },
            citation=f"session · last {len(turns)} turns",
        )
