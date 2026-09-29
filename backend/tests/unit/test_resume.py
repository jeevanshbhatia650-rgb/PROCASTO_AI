from app.core.ids import IdCounter
from app.core.models import Clause, Evidence, Intent, TaskStatus
from app.planning.query_plan import QueryPlanEngine


def clause(intent, device="washer-01", code=None):
    return Clause(
        clause_id=f"{intent.value}:{device}:{code or '-'}",
        device_id=device,
        intent=intent,
        error_code=code,
        stable=True,
        first_seen_ms=0,
    )


def evidence_for(task, device_revision, clock):
    return Evidence(
        evidence_id=f"ev-{task.task_id}",
        task_id=task.task_id,
        source_type=task.kind,
        device_id=task.device_id,
        model_id="WW90T",
        authority="manual" if task.kind == "manual" else "simulator",
        observed_at=clock.now(),
        device_revision=device_revision if task.kind == "live_state" else None,
        plan_revision=task.plan_revision,
        payload={},
        citation="x",
    )


def setup(devices, clock):
    revisions = {"washer-01": 5, "dryer-01": 1, "ac-01": 1}
    infos = {d.device_id: d for d in devices}
    engine = QueryPlanEngine(IdCounter(), clock, infos, revisions.__getitem__, lambda _d: "E3")
    first = engine.update([clause(Intent.STATUS), clause(Intent.ERROR_LOOKUP, code="E3")], "u1")
    store = {}
    for task in first.added:
        engine.set_status(task.task_id, TaskStatus.DONE)
        store[task.task_id] = evidence_for(task, 5, clock)
    engine.correct([], ["dryer-01"], "u2")
    return engine, revisions, store


def test_resume_reuses_fresh_and_refetches_stale(devices, clock):
    engine, revisions, store = setup(devices, clock)
    revisions["washer-01"] = 7  # the washer changed while we talked about the dryer
    diff = engine.resume("washer-01", store.get)
    assert [t.kind for t in diff.reused] == ["manual"]
    assert [t.kind for t in diff.refetched] == ["live_state"]
    assert diff.stale[0].status == TaskStatus.STALE
    assert [c.device_id for c in engine.active().clauses] == ["washer-01", "washer-01"]


def test_resume_reuses_everything_when_nothing_changed(devices, clock):
    engine, _, store = setup(devices, clock)
    diff = engine.resume("washer-01", store.get)
    assert len(diff.reused) == 2
    assert diff.refetched == []


def test_resume_parks_the_current_plan(devices, clock):
    engine, _, store = setup(devices, clock)
    dryer_plan = engine.active().plan_id
    diff = engine.resume("washer-01", store.get)
    assert diff.parked_plan_id == dryer_plan
    assert [p.plan_id for p in engine.parked()] == [dryer_plan]


def test_resume_without_a_matching_plan_is_a_miss(devices, clock):
    engine, _, store = setup(devices, clock)
    diff = engine.resume("ac-01", store.get)
    assert diff.resume_missed
    assert not diff.changed


def test_resume_bumps_the_revision(devices, clock):
    engine, _, store = setup(devices, clock)
    before = engine.active().revision
    engine.resume("washer-01", store.get)
    assert engine.active().revision > before
