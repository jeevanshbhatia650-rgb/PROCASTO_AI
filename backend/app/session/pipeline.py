"""Applies plan diffs: runs, cancels and parks tasks, streams their status, and recomposes cards."""

from collections.abc import Callable, Mapping
from typing import Any

from app.answer.composer import Composer
from app.core.models import AnswerCard, Evidence, RetrievalTask, TaskStatus, TimelineKind
from app.evidence.store import EvidenceStore
from app.observability.metrics import MetricsTracker
from app.observability.timeline import Timeline
from app.planning.orchestrator import Orchestrator
from app.planning.plan_types import PlanDiff
from app.planning.query_plan import QueryPlanEngine
from app.retrieval.base import Retriever

Send = Callable[[str, Any], None]


class Pipeline:
    def __init__(
        self,
        engine: QueryPlanEngine,
        composer: Composer,
        evidence: EvidenceStore,
        timeline: Timeline,
        metrics: MetricsTracker,
        send: Send,
        retrievers: Mapping[str, Retriever],
        timeout_ms: int,
        on_cards: Callable[[list[AnswerCard]], None],
    ) -> None:
        self._engine, self._composer, self._evidence = engine, composer, evidence
        self._timeline, self._metrics, self._send = timeline, metrics, send
        self._on_cards = on_cards
        self.orchestrator = Orchestrator(retrievers, self, engine.is_current, timeout_ms)

    def apply(self, diff: PlanDiff, from_speech: bool = False) -> None:
        if not diff.changed:
            return
        reason = "new question" if diff.retired_plan_id else "clause dropped"
        for task in diff.cancelled:
            self.orchestrator.cancel(task.task_id)
            self._task(task, "task_cancel", reason=reason)
        for task in diff.parked:
            self.orchestrator.cancel(task.task_id)
            self._task(task, "task_park", plan_id=diff.parked_plan_id)
        if diff.parked_plan_id:
            parked = next((p for p in self._engine.parked() if p.plan_id == diff.parked_plan_id), None)
            self._timeline.emit(
                "park",
                plan_id=diff.parked_plan_id,
                label=parked.label if parked else "",
                in_flight=[t.task_id for t in diff.parked],
            )
        for task in diff.stale:
            self.orchestrator.cancel(task.task_id)
            self._task(task, None)
        for task in diff.reused:
            self._task(self._engine.set_status(task.task_id, task.status, note="reused") or task, None)
        if diff.retired_plan_id:
            self._composer.retire(diff.retired_plan_id)
        now = self._timeline.now_ms()
        for task in [*diff.added, *diff.refetched]:
            self._task(task, None)
            self.orchestrator.run(task)
            if from_speech:
                self._metrics.task_started(now)
        self.publish_plan()
        self.compose()

    def publish_plan(self) -> None:
        self._send("plan.update", self._engine.active())
        self._send("parked.update", self._engine.parked())

    def compose(self) -> None:
        plan = self._engine.active()
        if plan is None:
            return
        changed = self._composer.compose(plan)
        if changed:
            self._on_cards(changed)

    def _task(self, task: RetrievalTask, kind: TimelineKind | None, **detail: Any) -> None:
        self._send("task.update", task)
        if kind:
            self._timeline.emit(kind, task_id=task.task_id, source=task.kind, device_id=task.device_id, **detail)

    # ---------- TaskSink: called by the orchestrator ----------

    async def started(self, task: RetrievalTask) -> None:
        now = self._timeline.now_ms()
        updated = self._engine.set_status(task.task_id, TaskStatus.RUNNING, started_ms=now)
        if updated:
            self._task(updated, "task_start", query=task.query, plan_revision=task.plan_revision, note=task.note)

    async def finished(self, task: RetrievalTask, evidence: Evidence) -> None:
        self._evidence.put(evidence)
        now = self._timeline.now_ms()
        current = self._engine.task(task.task_id)
        started = current.started_ms if current and current.started_ms is not None else now
        updated = self._engine.set_status(task.task_id, TaskStatus.DONE, finished_ms=now)
        if updated:
            self._task(updated, "task_done", duration_ms=now - started, citation=evidence.citation)
        self.compose()

    async def dropped(self, task: RetrievalTask, evidence: Evidence) -> None:
        plan = self._engine.active()
        stale = task.model_copy(
            update={
                "status": TaskStatus.STALE,
                "finished_ms": self._timeline.now_ms(),
                "note": "arrived after the plan moved on",
            }
        )
        self._task(
            stale, "stale_drop", plan_revision=task.plan_revision, current_revision=plan.revision if plan else None
        )

    async def failed(self, task: RetrievalTask, reason: str) -> None:
        updated = self._engine.set_status(
            task.task_id, TaskStatus.CANCELLED, finished_ms=self._timeline.now_ms(), note=reason
        )
        if updated:
            self._task(updated, "task_cancel", reason=reason)
        self.compose()
