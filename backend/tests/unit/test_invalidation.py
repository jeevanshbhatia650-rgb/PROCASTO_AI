from app.core.models import CardType, DeviceEvent, DeviceInfo, DeviceSnapshot, Intent
from app.planning.invalidation import is_material
from app.state.live_store import DeviceChange

INFO = DeviceInfo(device_id="ac-01", kind="ac", model_id="AR12", family="ac", display_name="AC")


def change(attribute, old, new):
    event = DeviceEvent(
        event_id="e",
        device_id="ac-01",
        attribute=attribute,
        value=new,
        observed_at="2026-01-01T00:00:00Z",
        source="simulator",
    )
    snap = DeviceSnapshot(info=INFO, attributes={attribute: new}, revision=2, updated_at="2026-01-01T00:00:00Z")
    return DeviceChange(snap, event, old)


def test_telemetry_noise_is_not_material():
    assert not is_material(change("power_w", 1800, 1830))
    assert not is_material(change("temp_c", 25.9, 25.8))
    assert not is_material(change("state", "COOLING", "COOLING"))


def test_real_changes_are_material():
    assert is_material(change("power_w", 1800, 3200))
    assert is_material(change("temp_c", 26.0, 24.0))
    assert is_material(change("state", "RUNNING", "ERROR"))
    assert is_material(change("remaining_min", 14, 13))
    assert is_material(change("power_w", None, 450))


async def test_device_event_replaces_stale_live_evidence(env):
    ctx, session, outbox = env
    await session.on_final("how long until the washer finishes", 1)
    await session.pipeline.orchestrator.drain()
    first = next(t for t in session.engine.active().tasks if t.kind == "live_state")
    await ctx.simulator.trigger("washer_e3")
    await session.pipeline.orchestrator.drain()
    invalidations = [e for e in outbox.timeline() if e.kind == "invalidate"]
    assert invalidations and invalidations[0].detail["stale"] == [first.task_id]
    assert not session.engine.is_current(first.task_id)


async def test_fault_during_a_status_question_escalates_once(env):
    ctx, session, outbox = env
    await session.on_final("how long until the washer finishes", 1)
    await session.pipeline.orchestrator.drain()
    await ctx.simulator.trigger("washer_e3")
    await session.pipeline.orchestrator.drain()
    await ctx.simulator.trigger("washer_e3")  # a repeated fault is not a new question
    await session.pipeline.orchestrator.drain()
    plan = session.engine.active()
    auto = [c for c in plan.clauses if c.origin == "auto"]
    assert [(c.intent, c.error_code) for c in auto] == [(Intent.ERROR_LOOKUP, "E3")]
    types = {c.type for c in session.composer.cards_for(plan.plan_id)}
    assert {CardType.STATUS, CardType.PROBLEM, CardType.ACTION} <= types


async def test_changes_to_other_devices_leave_the_plan_alone(env):
    ctx, session, outbox = env
    await session.on_final("how long until the washer finishes", 1)
    await session.pipeline.orchestrator.drain()
    revision = session.engine.active().revision
    await ctx.simulator.trigger("ac_spike")
    await session.pipeline.orchestrator.drain()
    assert session.engine.active().revision == revision
    assert any(e.kind == "device_event" and e.detail["device_id"] == "ac-01" for e in outbox.timeline())
