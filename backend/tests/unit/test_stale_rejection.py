from app.core.ids import IdCounter
from app.core.models import Clause, Intent
from app.planning.orchestrator import Orchestrator
from app.planning.query_plan import QueryPlanEngine
from tests.unit.test_orchestrator import FakeRetriever, RecordingSink, make_task


def clause(device):
    return Clause(clause_id=f"status:{device}:-", device_id=device, intent=Intent.STATUS, stable=True, first_seen_ms=0)


async def test_late_result_for_a_task_no_longer_in_the_plan_is_dropped():
    current = {"T1"}
    sink = RecordingSink()
    orch = Orchestrator({"live_state": FakeRetriever(delay_ms=50)}, sink, current.__contains__, 3000)
    orch.run(make_task("T1"))
    current.clear()  # the plan moved on while T1 was in flight
    await orch.drain()
    assert sink.events == [("started", "T1"), ("dropped", "T1")]


async def test_result_for_a_current_task_is_kept():
    sink = RecordingSink()
    orch = Orchestrator({"live_state": FakeRetriever(delay_ms=10)}, sink, lambda _t: True, 3000)
    orch.run(make_task("T1"))
    await orch.drain()
    assert sink.events[-1] == ("finished", "T1")


async def test_new_question_makes_in_flight_results_stale(devices, clock):
    engine = QueryPlanEngine(IdCounter(), clock, {d.device_id: d for d in devices}, lambda _d: 1, lambda _d: None)
    sink = RecordingSink()
    orch = Orchestrator({"live_state": FakeRetriever(delay_ms=50)}, sink, engine.is_current, 3000)
    first = engine.update([clause("washer-01")], "u1")
    orch.run(first.added[0])
    engine.update([clause("dryer-01")], "u2")  # new plan revision; washer task not in it
    await orch.drain()
    assert ("dropped", first.added[0].task_id) in sink.events
