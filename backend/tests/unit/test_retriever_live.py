import pytest

from app.core.models import RetrievalTask
from app.devices.normalizer import normalize
from app.retrieval.live_state import LiveStateRetriever
from app.state.live_store import LiveStore


def task(device="washer-01"):
    return RetrievalTask(
        task_id="T1", clause_id="c", kind="live_state", device_id=device, query="status", plan_revision=2
    )


async def test_live_evidence_carries_attributes_and_revision(devices, bus, clock):
    store = LiveStore(devices, bus, clock)
    await store.apply(normalize("washer-01", "state", "RUNNING", "simulator", clock.now()))
    await store.apply(normalize("washer-01", "remaining_min", 14, "simulator", clock.now()))
    ev = await LiveStateRetriever(store, "simulator").retrieve(task())
    assert ev.payload["attributes"] == {"state": "RUNNING", "remaining_min": 14}
    assert (ev.device_revision, ev.plan_revision, ev.authority, ev.model_id) == (2, 2, "simulator", "WW90T")
    assert ev.evidence_id == "ev-T1"


async def test_task_without_device_is_an_error(devices, bus, clock):
    retriever = LiveStateRetriever(LiveStore(devices, bus, clock), "simulator")
    with pytest.raises(ValueError):
        await retriever.retrieve(task(device=None))
