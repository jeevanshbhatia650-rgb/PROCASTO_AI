"""F7 + F16: stable clauses in, retrieval tasks out. Revisioned, parkable and resumable."""

from collections.abc import Callable

from app.core.ids import Clock, IdCounter
from app.core.models import (
    Clause,
    DeviceInfo,
    Evidence,
    Intent,
    ParkedPlan,
    QueryPlan,
    RetrievalTask,
    TaskKind,
    TaskStatus,
)
from app.planning.plan_types import META, OPEN, PlanDiff, PlanState


class QueryPlanEngine:
    def __init__(
        self,
        ids: IdCounter,
        clock: Clock,
        infos: dict[str, DeviceInfo],
        device_revision: Callable[[str], int],
        current_error: Callable[[str], str | None],
        max_parked: int = 3,
    ) -> None:
        self._ids, self._clock, self._infos = ids, clock, infos
        self._device_revision, self._current_error = device_revision, current_error
        self._max_parked = max_parked
        self._active: PlanState | None = None
        self._parked: list[PlanState] = []
        self._revision = 0
        self._pending_rev = 1

    # ---------- queries ----------

    def active(self) -> QueryPlan | None:
        return self._snapshot(self._active) if self._active else None

    def parked(self) -> list[ParkedPlan]:
        return [
            ParkedPlan(
                plan_id=p.plan_id, label=self._label(p), device_ids=sorted(p.user_devices()), task_count=len(p.tasks)
            )
            for p in reversed(self._parked)
        ]

    def task(self, task_id: str) -> RetrievalTask | None:
        plan = self._owner(task_id)
        return plan.tasks[task_id] if plan else None

    def is_current(self, task_id: str) -> bool:
        return self._active is not None and task_id in self._active.tasks

    def set_status(self, task_id: str, status: TaskStatus, **fields: object) -> RetrievalTask | None:
        plan = self._owner(task_id)
        if plan is None:
            return None
        plan.tasks[task_id] = plan.tasks[task_id].model_copy(update={"status": status, **fields})
        return plan.tasks[task_id]

    # ---------- changes ----------

    def update(self, clauses: list[Clause], utterance_id: str, followup: bool = False) -> PlanDiff:
        diff = self._begin()
        wanted = {c.clause_id: c for c in clauses if c.intent not in META and c.device_id}
        plan = self._active
        if wanted and (plan is None or (plan.utterance_id != utterance_id and not followup)):
            if plan:
                self._retire(plan, diff)
            plan = self._new_plan(utterance_id, diff)
        if plan is None:
            return self._finish(diff)
        if wanted:
            plan.utterance_id = utterance_id
        current = {
            cid for cid, u in plan.clause_utt.items() if u == utterance_id and plan.clauses[cid].origin == "user"
        }
        for cid, c in wanted.items():
            if cid not in plan.clauses:
                self._add_clause(plan, c, utterance_id, diff)
            elif plan.clauses[cid].params != c.params:
                plan.clauses[cid] = c
                diff.clauses_changed = True
        for cid in current - wanted.keys():
            self._remove_clause(plan, cid, diff)
        return self._finish(diff)

    def correct(self, clauses: list[Clause], mentions: list[str], utterance_id: str) -> PlanDiff:
        content = [c for c in clauses if c.intent not in META and c.device_id]
        targets = {c.device_id for c in content if c.device_id} or set(mentions)
        plan = self._active
        if plan is None or not targets:
            return self.update(content, utterance_id) if content else self._finish(self._begin())
        diff = self._begin()
        if targets <= plan.user_devices():  # same device: the new clauses replace the old ones
            for c in content:
                if c.clause_id not in plan.clauses:
                    self._add_clause(plan, c, utterance_id, diff)
            keep = {c.clause_id for c in content}
            for cid in [cid for cid, c in plan.clauses.items() if c.origin == "user" and content and cid not in keep]:
                self._remove_clause(plan, cid, diff)
            return self._finish(diff)
        carried = content or [
            self._carry(c, d) for c in plan.clauses.values() if c.origin == "user" for d in sorted(targets)
        ]
        self._park(plan, diff)
        new_plan = self._new_plan(utterance_id, diff)
        for c in carried:
            self._add_clause(new_plan, c, utterance_id, diff)
        return self._finish(diff)

    def resume(
        self, device_id: str | None, evidence_for: Callable[[str], Evidence | None], plan_id: str | None = None
    ) -> PlanDiff:
        """Brings back the newest parked plan about device_id (or plan_id, or simply the newest one)."""
        diff = self._begin()

        def matches(plan: PlanState) -> bool:
            if plan_id is not None:
                return plan.plan_id == plan_id
            return device_id is None or device_id in plan.user_devices()

        idx = next((i for i in range(len(self._parked) - 1, -1, -1) if matches(self._parked[i])), None)
        if idx is None:
            diff.resume_missed = True
            return self._finish(diff)
        plan = self._parked.pop(idx)
        if self._active:
            self._park(self._active, diff)
        self._active = plan
        diff.resumed_plan_id = plan.plan_id
        for task in list(plan.tasks.values()):
            ev = evidence_for(task.task_id)
            if task.status == TaskStatus.DONE and ev is not None and self._fresh(ev):
                diff.reused.append(task)
            else:
                self._replace_task(plan, task, diff)
        return self._finish(diff)

    def cancel_all(self) -> PlanDiff:
        diff = self._begin()
        if self._active:
            self._retire(self._active, diff)
        return self._finish(diff)

    def escalate(self, clause: Clause) -> PlanDiff:
        """Adds an engine-originated clause (e.g. error lookup after a device fault) to the active plan."""
        diff = self._begin()
        plan = self._active
        if plan and clause.clause_id not in plan.clauses:
            self._add_clause(plan, clause, plan.utterance_id, diff)
        return self._finish(diff)

    def refetch(self, task_ids: list[str]) -> PlanDiff:
        """Replaces tasks whose evidence went stale with fresh copies."""
        diff = self._begin()
        plan = self._active
        for task_id in task_ids:
            if plan and task_id in plan.tasks:
                self._replace_task(plan, plan.tasks[task_id], diff)
        return self._finish(diff)

    # ---------- internals ----------

    def _begin(self) -> PlanDiff:
        self._pending_rev = self._revision + 1
        return PlanDiff()

    def _finish(self, diff: PlanDiff) -> PlanDiff:
        if diff.changed:
            self._revision = self._pending_rev
            if self._active:
                self._active.revision = self._revision
        diff.plan_id = self._active.plan_id if self._active else None
        diff.plan_revision = self._revision
        return diff

    def _new_plan(self, utterance_id: str | None, diff: PlanDiff) -> PlanState:
        self._active = PlanState(self._ids.next("P"), self._pending_rev, self._clock.now(), utterance_id)
        diff.clauses_changed = True
        return self._active

    def _specs(self, clause: Clause) -> list[tuple[TaskKind, str | None, str]]:
        device = clause.device_id
        live: tuple[TaskKind, str | None, str] = ("live_state", device, "status")
        if clause.intent in (Intent.STATUS, Intent.ACTION):
            return [live]
        if clause.intent == Intent.ERROR_LOOKUP:
            code = clause.error_code or (self._current_error(device) if device else None) or ""
            return [live, ("manual", device, f"{code} error meaning fix".strip())]
        if clause.intent == Intent.ENERGY:
            return [
                live,
                ("manual", device, "power consumption energy use"),
                ("session", device, "recent conversation"),
            ]
        return []

    def _add_clause(self, plan: PlanState, clause: Clause, utterance_id: str | None, diff: PlanDiff) -> None:
        plan.clauses[clause.clause_id] = clause
        plan.clause_utt[clause.clause_id] = utterance_id
        diff.clauses_changed = True
        for kind, device, query in self._specs(clause):
            existing = next(
                (t for t in plan.tasks.values() if (t.kind, t.device_id, t.query) == (kind, device, query)), None
            )
            if existing:
                plan.refs[existing.task_id].add(clause.clause_id)
                continue
            task = RetrievalTask(
                task_id=self._ids.next("T"),
                clause_id=clause.clause_id,
                kind=kind,
                device_id=device,
                query=query,
                plan_revision=self._pending_rev,
                depends_on_device_rev=self._device_revision(device) if kind == "live_state" and device else None,
            )
            plan.tasks[task.task_id] = task
            plan.refs[task.task_id] = {clause.clause_id}
            diff.added.append(task)

    def _remove_clause(self, plan: PlanState, clause_id: str, diff: PlanDiff) -> None:
        plan.clauses.pop(clause_id, None)
        plan.clause_utt.pop(clause_id, None)
        diff.clauses_changed = True
        for task_id, refs in list(plan.refs.items()):
            refs.discard(clause_id)
            if refs:
                continue
            task = plan.tasks.pop(task_id)
            plan.refs.pop(task_id)
            if task.status in OPEN:
                diff.cancelled.append(task.model_copy(update={"status": TaskStatus.CANCELLED}))

    def _replace_task(self, plan: PlanState, old: RetrievalTask, diff: PlanDiff) -> None:
        new = old.model_copy(
            update={
                "task_id": self._ids.next("T"),
                "plan_revision": self._pending_rev,
                "status": TaskStatus.PENDING,
                "started_ms": None,
                "finished_ms": None,
                "note": f"replaces {old.task_id}",
                "depends_on_device_rev": self._device_revision(old.device_id)
                if old.kind == "live_state" and old.device_id
                else None,
            }
        )
        plan.tasks.pop(old.task_id)
        plan.tasks[new.task_id] = new
        plan.refs[new.task_id] = plan.refs.pop(old.task_id)
        old_status = TaskStatus.STALE if old.status in (TaskStatus.DONE, TaskStatus.RUNNING) else TaskStatus.CANCELLED
        diff.stale.append(old.model_copy(update={"status": old_status}))
        diff.refetched.append(new)

    def _park(self, plan: PlanState, diff: PlanDiff) -> None:
        for task_id, task in plan.tasks.items():
            if task.status in OPEN:
                plan.tasks[task_id] = task.model_copy(update={"status": TaskStatus.PARKED})
                diff.parked.append(plan.tasks[task_id])
        self._parked.append(plan)
        if len(self._parked) > self._max_parked:
            diff.evicted_plan_ids.append(self._parked.pop(0).plan_id)
        diff.parked_plan_id = plan.plan_id
        self._active = None

    def _retire(self, plan: PlanState, diff: PlanDiff) -> None:
        diff.cancelled.extend(
            t.model_copy(update={"status": TaskStatus.CANCELLED}) for t in plan.tasks.values() if t.status in OPEN
        )
        diff.retired_plan_id = plan.plan_id
        self._active = None

    def _fresh(self, ev: Evidence) -> bool:
        if ev.device_revision is None or ev.device_id is None:
            return True  # manual and session evidence don't age with the device
        return ev.device_revision >= self._device_revision(ev.device_id)

    @staticmethod
    def _carry(clause: Clause, device_id: str) -> Clause:
        key = f"{clause.intent.value}:{device_id}:{clause.error_code or '-'}"
        return clause.model_copy(update={"clause_id": key, "device_id": device_id, "stable": True})

    def _owner(self, task_id: str) -> PlanState | None:
        return next((p for p in [self._active, *self._parked] if p and task_id in p.tasks), None)

    def _label(self, plan: PlanState) -> str:
        names = [self._infos[d].display_name for d in sorted(plan.user_devices()) if d in self._infos]
        asks = [c.error_code or c.intent.value.replace("_", " ") for c in plan.clauses.values() if c.origin == "user"]
        return f"{' + '.join(names) or 'Question'}: {', '.join(dict.fromkeys(asks))}"

    def _snapshot(self, plan: PlanState) -> QueryPlan:
        return QueryPlan(
            plan_id=plan.plan_id,
            revision=plan.revision,
            clauses=list(plan.clauses.values()),
            tasks=list(plan.tasks.values()),
            created_at=plan.created_at,
            label=self._label(plan),
        )
