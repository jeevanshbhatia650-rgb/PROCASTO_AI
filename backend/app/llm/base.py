"""F18: the LLM only phrases. Facts and structure come from templates; the model writes 1-2 sentences."""

from typing import Any, Protocol

from app.core.models import Intent

SYSTEM_PROMPT = (
    "You are the voice of a smart-home assistant. Write one or two short sentences (under 40 words) "
    "telling the person what to do next. Use only the live facts and manual text you are given. "
    "Live readings override manual defaults. No lists, no markdown, no greetings."
)


class AnswerModel(Protocol):
    name: str

    async def phrase(self, intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str: ...


def user_prompt(intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str:
    live = ", ".join(f"{k}={v}" for k, v in facts.items()) or "none"
    return f"Question type: {intent.value}\nLive facts: {live}\nManual: {manual_text or 'none'}"


def make_llm(provider: str, gemini_api_key: str = "", gemini_model: str = "") -> AnswerModel:
    if provider == "gemini":
        if not gemini_api_key:
            raise ValueError("LLM_PROVIDER=gemini needs GEMINI_API_KEY")
        from app.llm.gemini import GeminiAnswerModel

        return GeminiAnswerModel(gemini_api_key, gemini_model)
    from app.llm.fake import FakeAnswerModel

    return FakeAnswerModel()
