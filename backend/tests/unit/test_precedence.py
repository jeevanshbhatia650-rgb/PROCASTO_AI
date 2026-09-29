from datetime import timedelta

from app.core.models import Evidence
from app.evidence.precedence import manual_matches, resolve
from app.evidence.store import EvidenceStore


def ev(clock, eid, source_type, payload, authority=None, model_id="WW90T", offset_s=0, device="washer-01"):
    return Evidence(
        evidence_id=eid,
        task_id=f"T-{eid}",
        source_type=source_type,
        device_id=device,
        model_id=model_id,
        authority=authority or {"live_state": "simulator", "manual": "manual", "session": "session"}[source_type],
        observed_at=clock.now() + timedelta(seconds=offset_s),
        device_revision=3 if source_type == "live_state" else None,
        plan_revision=1,
        payload=payload,
        citation="c",
    )


def washer(devices):
    return next(d for d in devices if d.device_id == "washer-01")


def test_live_reading_beats_the_manual_default(devices, clock):
    manual = ev(clock, "m", "manual", {"facts": {"remaining_min": 60}, "hits": [{"family": "washer"}]}, offset_s=5)
    live = ev(clock, "l", "live_state", {"attributes": {"remaining_min": 14}})
    facts = resolve([manual, live], washer(devices))
    assert facts.value("remaining_min") == 14
    assert facts.facts["remaining_min"].source_type == "live_state"


def test_newer_live_reading_wins(devices, clock):
    old = ev(clock, "a", "live_state", {"attributes": {"state": "RUNNING"}})
    new = ev(clock, "b", "live_state", {"attributes": {"state": "ERROR"}}, offset_s=2)
    assert resolve([new, old], washer(devices)).value("state") == "ERROR"


def test_manual_for_another_model_is_ignored(devices, clock):
    dryer_manual = ev(
        clock, "d", "manual", {"hits": [{"family": "dryer", "title": "Airflow blocked"}]}, model_id="DV90T"
    )
    facts = resolve([dryer_manual], washer(devices))
    assert facts.manual_hits == []
    assert facts.evidence == []


def test_family_fallback_manual_is_accepted(devices, clock):
    sibling = ev(clock, "s", "manual", {"hits": [{"family": "washer"}]}, model_id="WW80T")
    assert manual_matches(sibling, washer(devices))


def test_plain_facts_are_what_the_llm_sees(devices, clock):
    live = ev(clock, "l", "live_state", {"attributes": {"state": "ERROR", "error_code": "E3"}})
    assert resolve([live], washer(devices)).plain() == {"state": "ERROR", "error_code": "E3"}


def test_evidence_store_indexes_by_task_and_device(clock):
    store = EvidenceStore()
    item = ev(clock, "x", "live_state", {"attributes": {}})
    store.put(item)
    store.put(item)  # idempotent
    assert store.get("x") is item
    assert store.for_task("T-x") is item
    assert store.for_device("washer-01") == [item]
    assert store.for_task("nope") is None
