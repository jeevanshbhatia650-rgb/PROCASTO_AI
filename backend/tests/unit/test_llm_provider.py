import json

import httpx
import pytest

from app.core.models import Intent
from app.llm.base import make_llm, user_prompt
from app.llm.fake import FakeAnswerModel
from app.llm.gemini import GeminiAnswerModel

MANUAL = "The washer cannot pump the water out. It stops.\n1. Switch the washer off.\n2. Drain it."


async def test_fake_is_deterministic_and_grounded():
    text = await FakeAnswerModel().phrase(Intent.ERROR_LOOKUP, {}, MANUAL)
    assert text == "The washer cannot pump the water out. Start with this: Switch the washer off."
    assert await FakeAnswerModel().phrase(Intent.STATUS, {}, None) == ""


def test_prompt_contains_resolved_facts_only():
    prompt = user_prompt(Intent.ERROR_LOOKUP, {"state": "ERROR", "error_code": "E3"}, "manual text")
    assert "state=ERROR" in prompt and "error_code=E3" in prompt and "manual text" in prompt


async def test_gemini_request_shape_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": " Clean the filter. "}]}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    model = GeminiAnswerModel("test-key", "gemini-test", client)
    assert await model.phrase(Intent.ERROR_LOOKUP, {"error_code": "E3"}, MANUAL) == "Clean the filter."
    assert seen["url"].endswith("/models/gemini-test:generateContent")
    assert "key=" not in seen["url"]  # the key travels in a header, never the URL
    assert seen["key"] == "test-key"
    assert "systemInstruction" in seen["body"]


async def test_gemini_http_errors_raise_so_the_composer_can_fall_back():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        await GeminiAnswerModel("k", "m", client).phrase(Intent.ENERGY, {}, None)


def test_factory_picks_the_provider():
    assert make_llm("fake").name == "templates"
    assert make_llm("gemini", "k", "m").name == "gemini"
    with pytest.raises(ValueError):
        make_llm("gemini", "", "m")
