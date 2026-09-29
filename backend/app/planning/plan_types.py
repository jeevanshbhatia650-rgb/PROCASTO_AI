"""The plan engine's working state and the diff it returns after every change."""

from dataclasses import dataclass, field
from datetime import datetime

from app.core.models import Clause, Intent, RetrievalTask, TaskStatus

META = (Intent.RESUME, Intent.CANCEL)
OPEN = (TaskStatus.PENDING, TaskStatus.RUNNING)


@dataclass
class PlanDiff:
    plan_id: str | None = None
    plan_revision: int = 0
    added: list[RetrievalTask] = field(default_factory=list)
    cancelled: list[RetrievalTask] = field(default_factory=list)
    parked: list[RetrievalTask] = field(default_factory=list)
    stale: list[RetrievalTask] = field(default_factory=list)
    refetched: list[RetrievalTask] = field(default_factory=list)
    reused: list[RetrievalTask] = field(default_factory=list)
    retired_plan_id: str | None = None
    evicted_plan_ids: list[str] = field(default_factory=list)  # parked plans pushed out of the stack
    parked_plan_id: str | None = None
    resumed_plan_id: str | None = None
    resume_missed: bool = False
    clauses_changed: bool = False

    @property
    def changed(self) -> bool:
        return bool(
            self.added
            or self.cancelled
            or self.parked
            or self.stale
            or self.refetched
            or self.reused
            or self.retired_plan_id
            or self.parked_plan_id
            or self.resumed_plan_id
            or self.clauses_changed
        )


@dataclass
class PlanState:
    plan_id: str
    revision: int
    created_at: datetime
    utterance_id: str | None
    clauses: dict[str, Clause] = field(default_factory=dict)
    clause_utt: dict[str, str | None] = field(default_factory=dict)
    tasks: dict[str, RetrievalTask] = field(default_factory=dict)
    refs: dict[str, set[str]] = field(default_factory=dict)  # task_id -> clause_ids that need it

    def user_devices(self) -> set[str]:
        return {c.device_id for c in self.clauses.values() if c.origin == "user" and c.device_id}
