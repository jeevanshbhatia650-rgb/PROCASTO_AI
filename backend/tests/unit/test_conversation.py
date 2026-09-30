"""The one-to-one conversation: grounded replies, memory of earlier turns, and the cards as the fallback."""

import asyncio

import httpx
import numpy as np

from app.answer.conversation import Conversation, grounding
from app.config import DATA_DIR
from app.llm.tiers import TieredModel
from app.retrieval.vector_db import VectorCodes
from app.session.manager import Session


class Chatty:
    name = "chatty"

    def __init__(self, reply: str = "E3 means the washer can't drain. Check the filter.", delay: float = 0.0) -> None:
        self.reply, self.delay, self.seen = reply, delay, []

    async def phrase(self, intent, facts, manual_text):
        return ""

    async def chat(self, system, messages, max_tokens=300):
        self.seen.append(messages)
        await asyncio.sleep(self.delay)
        return self.reply, self.name

    def status(self):
        return [{"model": self.name, "ready": True, "failures": 0}]


class Down:
    name = "down"

    async def complete(self, system, messages, max_tokens):
        raise httpx.ConnectError("offline")


async def settle(session: Session) -> None:
    await session.pipeline.orchestrator.drain()
    await session._speech_task


async def test_a_model_reply_is_shown_spoken_and_remembered(env):
    ctx, _, outbox = env
    ctx.llm = model = Chatty()
    session = Session("chat", ctx, outbox)
    try:
        await ctx.simulator.trigger("washer_e3")
        await session.on_final("what does E3 mean on the washer", 1)
        await settle(session)
        [reply] = outbox.of("chat.reply")
        assert reply["text"] == model.reply and reply["model"] == "chatty"
        assert outbox.of("speech.say")[-1]["text"] == model.reply
        stats = outbox.of("agents.stats")[-1]
        assert stats["models"] == [{"model": "chatty", "ready": True, "failures": 0}] and stats["vector_db"] == 84
        facts = model.seen[0][-1]["text"]
        assert "what does E3 mean on the washer" in facts and "Home right now:" in facts
        assert "error_code=E3" in facts and "Answer cards on screen" in facts  # live readings and the cards
        assert "Washer E3: Water not draining" in facts and "WW90T sample manual §E3" in facts  # its own manual

        await session.on_final("ok and how long will that take", 2)
        await settle(session)
        history = model.seen[1]
        assert [m["role"] for m in history] == ["user", "assistant", "user"]
        assert history[0]["text"] == "what does E3 mean on the washer" and history[1]["text"] == model.reply
    finally:
        await session.close()


async def test_small_talk_gets_a_reply_without_any_device(env):
    ctx, _, outbox = env
    ctx.llm = Chatty("Hi! Ask me about your washer, dryer or AC.")
    session = Session("hello", ctx, outbox)
    try:
        await session.on_final("hello there", 1)
        await settle(session)
        assert outbox.of("chat.reply")[-1]["text"].startswith("Hi!")
        assert outbox.of("speech.say")[-1]["card_id"] == ""
    finally:
        await session.close()


async def test_without_a_model_small_talk_stays_quiet(env):
    ctx, session, outbox = env
    await session.on_final("hello there", 1)
    await settle(session)
    assert outbox.of("chat.reply") == [] and outbox.of("speech.say") == []


async def test_a_reply_that_lands_after_they_start_talking_again_is_dropped(env):
    ctx, _, outbox = env
    ctx.llm = Chatty(delay=0.3)
    session = Session("stale", ctx, outbox)
    try:
        await session.on_final("hello there", 1)
        task = session._speech_task
        await asyncio.sleep(0.2)
        await session.on_partial("actually", 1)  # talking again while the model thinks
        await task
        assert outbox.of("chat.reply") == [] and outbox.of("speech.say") == []
    finally:
        await session.close()


async def test_when_every_model_is_down_the_cards_answer(env):
    ctx, _, outbox = env
    ctx.llm = TieredModel([Down()])
    session = Session("down", ctx, outbox)
    try:
        await ctx.simulator.trigger("washer_e3")
        await session.on_final("what does E3 mean on the washer", 1)
        await settle(session)
        reply = outbox.of("chat.reply")[-1]
        assert reply["model"] == "templates" and "E3" in reply["text"]
        assert outbox.of("speech.say")[-1]["text"] == reply["text"]
    finally:
        await session.close()


async def test_grounding_brings_in_related_codes_from_the_vector_database(env):
    ctx, _, _ = env
    probe = VectorCodes(DATA_DIR / "vector_db", None)
    where = {"$and": [{"appliance_type": "dishwasher"}, {"code": "5C"}]}
    target = np.array(probe._collection.get(where=where, include=["embeddings"])["embeddings"][0])
    ctx.manuals.vectors = VectorCodes(DATA_DIR / "vector_db", lambda _: target)
    ctx.preferences.set("ac-01", "preferred_target_c", 24)
    facts = grounding(ctx, [], "my dishwasher won't drain")
    assert "fault-code database (ChromaDB)" in facts and "Samsung dishwasher 5C" in facts
    assert "ApplianceDB Samsung codes (ODbL) §5C" in facts and "likes 24 °C" in facts


async def test_history_is_bounded_and_keeps_plain_questions():
    model = Chatty("fine")
    chat = Conversation(model)
    for i in range(10):
        await chat.reply(f"question {i}", "facts")
    last = model.seen[-1]
    assert len(last) == 13 and last[0]["text"] == "question 3"  # six earlier turns, then the new question
    assert all("facts" not in m["text"] for m in last[:-1])
    assert await Conversation(Chatty("")).reply("hi", "facts") is None


async def test_a_reply_claiming_it_changed_a_device_is_never_spoken():
    for false_claim in ["I have updated the AC to 24 degrees.", "I've set it to 24.", "Okay, I'll turn it off now."]:
        assert await Conversation(Chatty(false_claim)).reply("set the AC to 24", "facts") is None
    honest = "Press the button on the card to set the AC to 24 degrees, I've got the details ready."
    assert await Conversation(Chatty(honest)).reply("set the AC to 24", "facts") == (honest, "chatty")


async def test_cards_with_a_button_say_nothing_has_changed_yet(env):
    ctx, session, _ = env
    await session.on_final("set the AC to 24 degrees", 1)
    await settle(session)
    facts = grounding(ctx, session.composer.cards_for(session.engine.active().plan_id), "set the AC to 24 degrees")
    assert "nothing changes until they press it" in facts
