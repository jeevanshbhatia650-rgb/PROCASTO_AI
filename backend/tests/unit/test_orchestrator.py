import asyncio
import time

from app.core.models import Evidence, RetrievalTask
from app.planning.orchestrator import Orchestrator


class FakeRetriever:
    def __init__(self, delay_ms=0, fail=None):
        self.delay_ms = delay_ms
        self.fail = fail

    async def retrieve(self, task):
        await asyncio.sleep(self.delay_ms / 1000)
        if self.fail:
            raise self.fail
        return make_evidence(task)


class RecordingSink:
    def __init__(self):
        self.events = []

    async def started(self, task):
        self.events.append(("started", task.task_id))

    async def finished(self, task, evidence):
        self.events.append(("finished", task.task_id))

    async def dropped(self, task, evidence):
        self.events.append(("dropped", task.task_id))

    async def failed(self, task, reason):
        self.events.append(("failed", task.task_id, reason))


def make_task(task_id, kind="live_state"):
    return RetrievalTask(
        task_id=task_id, clause_id="c", kind=kind, device_id="washer-01", query="status", plan_revision=1
    )


def make_evidence(task):
    from datetime import UTC, datetime

    return Evidence(
        evidence_id=f"ev-{task.task_id}",
        task_id=task.task_id,
        source_type=task.kind,
        device_id=task.device_id,
        model_id="WW90T",
        authority="simulator",
        observed_at=datetime.now(UTC),
        device_revision=1,
        plan_revision=task.plan_revision,
        payload={},
        citation="live",
    )


def orchestrator(sink, retriever, timeout_ms=3000, current=lambda _t: True):
    return Orchestrator({"live_state": retriever, "manual": retriever}, sink, current, timeout_ms)


async def test_tasks_run_concurrently():
    sink = RecordingSink()
    orch = orchestrator(sink, FakeRetriever(delay_ms=100))
    started = time.perf_counter()
    for i in range(3):
        orch.run(make_task(f"T{i}"))
    await orch.drain()
    elapsed = time.perf_counter() - started
    assert elapsed < 0.25
    assert sorted(e for e in sink.events if e[0] == "finished") == [("finished", f"T{i}") for i in range(3)]


async def test_cancel_stops_a_running_task():
    sink = RecordingSink()
    orch = orchestrator(sink, FakeRetriever(delay_ms=1000))
    orch.run(make_task("T1"))
    await asyncio.sleep(0.01)
    assert orch.cancel("T1") is True
    await orch.drain()
    assert sink.events == [("started", "T1")]
    assert orch.running() == []


async def test_cancel_unknown_task_returns_false():
    orch = orchestrator(RecordingSink(), FakeRetriever())
    assert orch.cancel("nope") is False


async def test_timeout_marks_the_task_failed():
    sink = RecordingSink()
    orch = orchestrator(sink, FakeRetriever(delay_ms=500), timeout_ms=50)
    orch.run(make_task("T1"))
    await orch.drain()
    assert sink.events[-1] == ("failed", "T1", "timeout")


async def test_retriever_errors_are_reported_not_raised():
    sink = RecordingSink()
    orch = orchestrator(sink, FakeRetriever(fail=KeyError("washer-99")))
    orch.run(make_task("T1"))
    await orch.drain()
    assert sink.events[-1] == ("failed", "T1", "KeyError")


async def test_close_cancels_everything():
    sink = RecordingSink()
    orch = orchestrator(sink, FakeRetriever(delay_ms=1000))
    orch.run(make_task("T1"))
    orch.run(make_task("T2"))
    await asyncio.sleep(0.01)
    await orch.close()
    assert orch.running() == []
    assert not any(e[0] == "finished" for e in sink.events)
