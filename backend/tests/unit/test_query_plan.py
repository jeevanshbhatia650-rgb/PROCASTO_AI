import pytest

from app.core.ids import IdCounter
from app.core.models import Clause, Intent, TaskStatus
from app.planning.query_plan import QueryPlanEngine


def clause(intent, device="washer-01", code=None, origin="user", **params):
    key = f"{intent.value}:{device or '?'}:{code or '-'}"
    return Clause(
        clause_id=key,
        device_id=device,
        intent=intent,
        error_code=code,
        params=params,
        stable=True,
        first_seen_ms=0,
        origin=origin,
    )


@pytest.fixture
def revisions():
    return {"washer-01": 1, "dryer-01": 1, "ac-01": 1}


@pytest.fixture
def engine(devices, clock, revisions):
    infos = {d.device_id: d for d in devices}
    return QueryPlanEngine(IdCounter(), clock, infos, revisions.__getitem__, lambda _d: None)


def kinds(tasks):
    return sorted((t.kind, t.device_id) for t in tasks)


def test_status_clause_creates_one_live_task(engine):
    diff = engine.update([clause(Intent.STATUS)], "u1")
    assert kinds(diff.added) == [("live_state", "washer-01")]
    assert engine.active().revision == 1
    assert diff.added[0].plan_revision == 1


def test_error_lookup_shares_the_live_task(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.update([clause(Intent.STATUS), clause(Intent.ERROR_LOOKUP, code="E3")], "u1")
    assert kinds(diff.added) == [("manual", "washer-01")]
    assert diff.added[0].query.startswith("E3")
    assert len(engine.active().tasks) == 2


def test_energy_fans_out_to_three_sources(engine):
    diff = engine.update([clause(Intent.ENERGY, device="ac-01")], "u1")
    assert kinds(diff.added) == [("live_state", "ac-01"), ("manual", "ac-01"), ("session", "ac-01")]


def test_unchanged_clauses_do_not_bump_the_revision(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.update([clause(Intent.STATUS)], "u1")
    assert not diff.changed
    assert engine.active().revision == 1


def test_dropped_clause_cancels_only_its_own_tasks(engine):
    engine.update([clause(Intent.STATUS), clause(Intent.ERROR_LOOKUP, code="E3")], "u1")
    diff = engine.update([clause(Intent.STATUS)], "u1")
    assert kinds(diff.cancelled) == [("manual", "washer-01")]
    assert kinds(engine.active().tasks) == [("live_state", "washer-01")]
    assert engine.active().revision == 2


def test_new_question_retires_the_old_plan(engine):
    first = engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.update([clause(Intent.STATUS, device="dryer-01")], "u2")
    assert diff.retired_plan_id == first.plan_id
    assert kinds(diff.cancelled) == [("live_state", "washer-01")]
    assert kinds(engine.active().tasks) == [("live_state", "dryer-01")]


def test_followup_extends_the_current_plan(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u2", followup=True)
    assert diff.retired_plan_id is None
    assert len(engine.active().clauses) == 2


def test_correction_to_another_device_parks_and_carries_the_intent(engine):
    first = engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.correct([], ["dryer-01"], "u2")
    assert diff.parked_plan_id == first.plan_id
    assert kinds(diff.parked) == [("live_state", "washer-01")]
    assert engine.task(diff.parked[0].task_id).status == TaskStatus.PARKED
    assert [(c.intent, c.device_id) for c in engine.active().clauses] == [(Intent.STATUS, "dryer-01")]
    assert kinds(diff.added) == [("live_state", "dryer-01")]
    assert [p.plan_id for p in engine.parked()] == [first.plan_id]


def test_auto_clauses_are_not_carried_by_a_correction(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    engine.escalate(clause(Intent.ERROR_LOOKUP, code="E3", origin="auto"))
    engine.correct([], ["dryer-01"], "u2")
    assert [c.intent for c in engine.active().clauses] == [Intent.STATUS]


def test_repeated_correction_partials_do_not_park_twice(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    engine.correct([], ["dryer-01"], "u2")
    diff = engine.correct([], ["dryer-01"], "u2")
    assert not diff.changed
    assert len(engine.parked()) == 1


def test_correction_on_the_same_device_replaces_clauses(engine):
    engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1")
    diff = engine.correct([clause(Intent.ERROR_LOOKUP, code="E4")], [], "u2")
    assert diff.parked_plan_id is None
    assert [c.error_code for c in engine.active().clauses] == ["E4"]


def test_parked_stack_keeps_three_plans(engine):
    engine.update([clause(Intent.STATUS, device="washer-01")], "u1")
    for i, device in enumerate(["dryer-01", "ac-01", "washer-01", "dryer-01"], start=2):
        engine.correct([], [device], f"u{i}")
    assert len(engine.parked()) == 3


def test_cancel_all_retires_the_plan(engine):
    first = engine.update([clause(Intent.STATUS)], "u1")
    diff = engine.cancel_all()
    assert diff.retired_plan_id == first.plan_id
    assert engine.active() is None


def test_escalation_is_added_once(engine):
    engine.update([clause(Intent.STATUS)], "u1")
    auto = clause(Intent.ERROR_LOOKUP, code="E3", origin="auto")
    first = engine.escalate(auto)
    second = engine.escalate(auto)
    assert kinds(first.added) == [("manual", "washer-01")]
    assert not second.changed


def test_refetch_replaces_a_task_and_marks_the_old_one_stale(engine):
    diff = engine.update([clause(Intent.STATUS)], "u1")
    old = diff.added[0]
    engine.set_status(old.task_id, TaskStatus.DONE)
    refetch = engine.refetch([old.task_id])
    assert refetch.stale[0].task_id == old.task_id
    assert refetch.stale[0].status == TaskStatus.STALE
    assert refetch.refetched[0].note == f"replaces {old.task_id}"
    assert engine.is_current(refetch.refetched[0].task_id)
    assert not engine.is_current(old.task_id)


def test_revisions_only_go_up(engine):
    seen = [engine.update([clause(Intent.STATUS)], "u1").plan_revision]
    seen.append(engine.update([clause(Intent.STATUS), clause(Intent.ENERGY)], "u1").plan_revision)
    seen.append(engine.correct([], ["dryer-01"], "u2").plan_revision)
    assert seen == sorted(seen) and len(set(seen)) == 3
