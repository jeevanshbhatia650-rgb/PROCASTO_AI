import asyncio

from app.core.models import CardType
from app.demo.replay import Replay


async def run_demo(ctx, session, outbox, speed=10):
    """Replays the scripted demo while the simulator ticks at the same accelerated pace."""
    stop = asyncio.Event()

    async def ticker():
        while not stop.is_set():
            await ctx.simulator.tick()
            await asyncio.sleep(0.05)

    ticking = asyncio.create_task(ticker())
    await Replay(session, ctx.simulator, outbox, speed=speed).run("main_demo")
    await session.pipeline.orchestrator.drain()
    await asyncio.sleep(0.3)  # let the last speech decision land
    stop.set()
    await ticking


def first(events, kind, after=0, where=lambda e: True):
    return next(i for i, e in enumerate(events) if i >= after and e.kind == kind and where(e))


async def test_demo_script_tells_the_whole_story_in_order(env):
    ctx, session, outbox = env
    await run_demo(ctx, session, outbox)
    events = outbox.timeline()

    i_clause = first(events, "clause")
    i_start = first(events, "task_start", i_clause)
    i_fault = first(events, "device_event", i_start, lambda e: e.detail["attribute"] in ("error_code", "state"))
    i_invalidate = first(events, "invalidate", i_fault)
    i_problem = first(events, "card", i_invalidate, lambda e: e.detail["title"].startswith("E3 ·"))
    i_interrupt = first(events, "interrupt", i_problem)
    i_park = first(events, "park", i_interrupt)
    i_resume = first(events, "resume", i_park)
    assert i_clause < i_start < i_fault < i_invalidate < i_problem < i_interrupt < i_park < i_resume

    auto = [e for e in events if e.kind == "clause" and e.detail["origin"] == "auto"]
    assert [e.detail["error_code"] for e in auto] == ["E3"]


async def test_demo_measures_lead_time_and_resume_reuse(env):
    ctx, session, outbox = env
    await run_demo(ctx, session, outbox)
    metrics = outbox.of("metrics.update")[-1]
    assert metrics.best_lead_time_ms > 0  # retrieval started before the sentence ended
    assert metrics.tasks_reused >= 1  # the manual answer survived the detour
    assert metrics.tasks_refetched >= 1  # the washer's live reading changed while parked
    assert metrics.lead_time_ms is not None  # the spoken "go back to the washer" refetch is timed too


async def test_a_bare_correction_reports_the_device_it_named(env):
    ctx, session, outbox = env
    await run_demo(ctx, session, outbox)
    correction = next(d for d in outbox.of("clauses.update") if d["is_correction"] and d["final"])
    assert correction["clauses"] == []  # "wait I meant the dryer" has no question of its own...
    assert correction["mentions"] == ["dryer-01"]  # ...so the UI shows the question carried over to this device


async def test_demo_ends_back_on_the_washer_with_the_dryer_parked(env):
    ctx, session, outbox = env
    await run_demo(ctx, session, outbox)
    plan = session.engine.active()
    assert {c.device_id for c in plan.clauses} == {"washer-01"}
    assert [p.device_ids for p in session.engine.parked()] == [["dryer-01"]]
    cards = {c.type: c for c in session.composer.cards_for(plan.plan_id)}
    assert cards[CardType.PROBLEM].sources[0].label == "WW90T sample manual §E3 p.41"


async def test_demo_speaks_then_gets_interrupted(env):
    ctx, session, outbox = env
    await run_demo(ctx, session, outbox)
    kinds = [k for k, _ in outbox.messages]
    first_say = kinds.index("speech.say")
    assert "speech.stop" in kinds[first_say:]
    said = [d["text"] for d in outbox.of("speech.say")]
    assert said[0].startswith("The washer stopped with error E3.")
    assert any(text.startswith("Back to the washer.") for text in said)
