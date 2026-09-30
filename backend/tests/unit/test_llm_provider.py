import asyncio
import json

import httpx
import pytest

from app.core.models import Intent
from app.llm.base import make_llm, user_prompt
from app.llm.fake import FakeAnswerModel
from app.llm.gemini import GeminiChat, thinking
from app.llm.openai_compat import OpenAICompatChat
from app.llm.tiers import GONE_S, AllTiersBusy, TieredModel, build_tiers, cooldown_s
from tests.conftest import make_settings

MANUAL = "The washer cannot pump the water out. It stops.\n1. Switch the washer off.\n2. Drain it."
ASK = [{"role": "user", "text": "hi"}]


class Scripted:
    """A model that replays outcomes: a string answers, an exception fails."""

    def __init__(self, name: str, *outcomes: object) -> None:
        self.name, self._outcomes, self.calls = name, list(outcomes), 0

    async def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int) -> str:
        self.calls += 1
        outcome = self._outcomes.pop(0) if self._outcomes else "ok"
        if isinstance(outcome, BaseException):
            raise outcome
        return str(outcome)


def status_error(code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test")
    return httpx.HTTPStatusError("x", request=request, response=httpx.Response(code, headers=headers, request=request))


async def test_fake_is_deterministic_and_grounded():
    text = await FakeAnswerModel().phrase(Intent.ERROR_LOOKUP, {}, MANUAL)
    assert text == "The washer cannot pump the water out. Start with this: Switch the washer off."
    assert await FakeAnswerModel().phrase(Intent.STATUS, {}, None) == ""
    assert await FakeAnswerModel().chat("s", ASK) == ("", "templates")  # no conversation without a model


def test_prompt_contains_resolved_facts_only():
    prompt = user_prompt(Intent.ERROR_LOOKUP, {"state": "ERROR", "error_code": "E3"}, "manual text")
    assert "state=ERROR" in prompt and "error_code=E3" in prompt and "manual text" in prompt


async def test_gemini_request_shape_skips_thoughts_and_keeps_the_key_out_of_the_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"], seen["body"] = (
            str(request.url),
            request.headers["x-goog-api-key"],
            json.loads(request.content),
        )
        parts = [{"text": "thinking...", "thought": True}, {"text": " Clean the filter. "}]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}}]})

    model = GeminiChat("test-key", "gemma-4-26b-a4b-it", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    history = [
        {"role": "user", "text": "E3?"},
        {"role": "assistant", "text": "Drain issue."},
        {"role": "user", "text": "and now?"},
    ]
    assert await model.complete("be brief", history, 120) == "Clean the filter."
    assert seen["url"].endswith("/models/gemma-4-26b-a4b-it:generateContent") and "key=" not in seen["url"]
    assert seen["key"] == "test-key"
    assert [c["role"] for c in seen["body"]["contents"]] == ["user", "model", "user"]
    assert seen["body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert thinking("gemini-2.5-flash") == {"thinkingBudget": 0}


async def test_openai_compatible_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = (
            str(request.url),
            request.headers["authorization"],
            json.loads(request.content),
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": "Sure."}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    model = OpenAICompatChat("https://api.groq.com/openai/v1/", "gk", "llama-3.3-70b-versatile", client)
    assert await model.complete("sys", ASK, 50) == "Sure."
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions" and seen["auth"] == "Bearer gk"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}


async def test_a_failing_tier_rests_and_the_next_one_answers():
    now = [0.0]
    first = Scripted("first", status_error(429, {"retry-after": "20"}), "back")
    second = Scripted("second", "hello there")
    tiers = TieredModel([first, second], clock=lambda: now[0])
    assert await tiers.chat("s", ASK) == ("hello there", "second")
    assert await tiers.chat("s", ASK) == ("ok", "second")  # the first is resting, not asked again
    assert first.calls == 1 and tiers.status()[0] == {"model": "first", "ready": False, "failures": 1}
    now[0] = 21.0  # its Retry-After has passed
    assert await tiers.chat("s", ASK) == ("back", "first")
    assert tiers.last_used == "first" and tiers.name == "first +1 fallback"


class Slow:
    def __init__(self, name: str, delay: float, reply: str) -> None:
        self.name, self.delay, self.reply, self.cancelled = name, delay, reply, False

    async def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int) -> str:
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return self.reply


async def test_a_slow_tier_gets_the_next_one_racing_alongside_and_the_first_answer_wins():
    slow, quick = Slow("slow", 5.0, "late"), Slow("quick", 0.01, "on time")
    tiers = TieredModel([slow, quick], hedge_s=0.05)
    assert await tiers.chat("s", ASK) == ("on time", "quick")
    await asyncio.sleep(0)  # let the cancellation land
    assert slow.cancelled and tiers.status()[0] == {"model": "slow", "ready": True, "failures": 0}  # lost, not failed


async def test_the_first_tier_still_wins_when_it_answers_before_the_hedge():
    tiers = TieredModel([Slow("a", 0.01, "first"), Slow("b", 0.01, "second")], hedge_s=1.0)
    assert await tiers.chat("s", ASK) == ("first", "a")


async def test_all_tiers_busy_raises_so_callers_fall_back_to_templates():
    tiers = TieredModel([Scripted("a", status_error(503)), Scripted("b", TimeoutError())])
    with pytest.raises(AllTiersBusy):
        await tiers.chat("s", ASK)
    with pytest.raises(AllTiersBusy):  # both are resting now: nothing is even tried
        await tiers.phrase(Intent.ENERGY, {}, None)


async def test_an_empty_reply_moves_on_without_resting():
    empty, good = Scripted("empty", "  "), Scripted("good", "Hi!")
    tiers = TieredModel([empty, good])
    assert await tiers.chat("s", ASK) == ("Hi!", "good")
    assert tiers.status()[0]["ready"] is True


def test_cooldowns():
    assert cooldown_s(status_error(429, {"retry-after": "7"})) == 7
    assert cooldown_s(status_error(429, {"retry-after": "soon"})) == 60
    assert cooldown_s(status_error(404)) == GONE_S  # a retired model is not asked again for an hour
    assert cooldown_s(status_error(503)) == 30 and cooldown_s(TimeoutError()) == 30


def test_tiers_skip_providers_without_a_key():
    spec = "gemini:gemma-4-26b-a4b-it, groq:llama-3.3-70b-versatile ,openrouter:meta-llama/x:free,nope:m,gemini:"
    models = build_tiers(spec, {"gemini": "g", "openrouter": "o", "nope": "n"})
    assert [m.name for m in models] == ["gemma-4-26b-a4b-it", "meta-llama/x:free"]  # a model id may contain ":"


def test_factory_picks_the_provider():
    assert make_llm(make_settings()).name == "templates"
    tiered = make_llm(make_settings(llm_provider="gemini", gemini_api_key="k"))
    assert tiered.name.startswith("gemini-3.1-flash-lite +")
    with pytest.raises(ValueError):
        make_llm(make_settings(llm_provider="gemini"))
    with pytest.raises(ValueError):
        TieredModel([])
