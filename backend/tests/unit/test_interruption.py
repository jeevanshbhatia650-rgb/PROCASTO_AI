import asyncio

from app.session.manager import Session


class SlowLLM:
    name = "slow"

    async def phrase(self, intent, facts, manual_text):
        await asyncio.sleep(5)
        return "never arrives"


async def test_barge_in_stops_speech_in_the_same_tick_and_parks_the_plan(env):
    ctx, _, outbox = env
    ctx.llm = SlowLLM()
    session = Session("barge-test", ctx, outbox)
    try:
        await ctx.simulator.trigger("washer_e3")
        await session.on_final("what does E3 mean on the washer", 1)
        await session.pipeline.orchestrator.drain()
        session.speech.speak("The washer stopped with error E3.", "card")
        outbox.messages.clear()

        await session.on_barge_in()
        assert outbox.messages[0] == ("speech.stop", {})  # silence comes first, before anything else
        interrupt = next(e for e in outbox.timeline() if e.kind == "interrupt")
        assert interrupt.detail["llm_cancelled"] == 1  # the half-written phrasing was dropped
        assert not session.speech.is_speaking()

        await session.on_partial("wait I meant the dryer", 1)
        await session.on_final("wait I meant the dryer", 2)
        parked = outbox.of("parked.update")[-1]
        assert [p.device_ids for p in parked] == [["washer-01"]]
        assert {c.device_id for c in session.engine.active().clauses} == {"dryer-01"}
    finally:
        await session.close()


async def test_talking_over_the_voice_counts_as_an_interruption(env):
    ctx, session, outbox = env
    session.speech.speak("The dryer is idle.", "card")
    await session.on_partial("actually", 1)
    kinds = [k for k, _ in outbox.messages]
    assert "speech.stop" in kinds


async def test_a_plan_pushed_out_of_the_parked_stack_takes_its_cards_with_it(env):
    ctx, session, outbox = env
    await session.on_final("how long until the washer finishes", 1)
    await session.pipeline.orchestrator.drain()
    first = session.engine.active().plan_id
    assert session.composer.cards_for(first)
    for correction in ("wait I meant the dryer", "wait I meant the AC", "actually the washer", "no, the dryer"):
        await session.on_final(correction, 1)
        await session.pipeline.orchestrator.drain()
    assert first not in [p.plan_id for p in session.engine.parked()]
    assert session.composer.cards_for(first) == []
    removed = {m["card_id"] for m in outbox.of("card.remove")}
    assert any(card_id.startswith(f"{first}:") for card_id in removed)


async def test_cancel_phrase_clears_the_plan_and_stops_speech(env):
    ctx, session, outbox = env
    await session.on_final("is the dryer done", 1)
    await session.on_final("never mind", 1)
    assert session.engine.active() is None
    assert ("speech.stop", {}) in outbox.messages
