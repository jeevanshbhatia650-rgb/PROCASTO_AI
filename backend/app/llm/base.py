"""F18: the LLM phrases and talks. Facts and structure come from templates and retrieval, never from the model."""

from typing import TYPE_CHECKING, Any, Protocol

from app.core.models import Intent

if TYPE_CHECKING:
    from app.config import Settings

SYSTEM_PROMPT = (
    "You are the voice of a smart-home assistant. Write one or two short sentences (under 40 words) "
    "telling the person what to do next. Use only the live facts and manual text you are given. "
    "Live readings override manual defaults. If the code asked about is not the one on the display, say what "
    "to do if it appears, not that all is fine. No lists, no markdown, no greetings."
)

Message = dict[str, str]  # {"role": "user" | "assistant", "text": ...}


class ChatModel(Protocol):
    """One hosted model. Raises on any failure (HTTP error, timeout) so the tiers can move on."""

    name: str

    async def complete(self, system: str, messages: list[Message], max_tokens: int) -> str: ...


class AnswerModel(Protocol):
    name: str

    async def phrase(self, intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str: ...

    async def chat(self, system: str, messages: list[Message], max_tokens: int = 300) -> tuple[str, str]:
        """(reply, the model that wrote it). An empty reply means no model is available right now."""
        ...

    def status(self) -> list[dict[str, Any]]:
        """Each model tier: its name, whether it's ready or resting, and how often it failed."""
        ...


def user_prompt(intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str:
    live = ", ".join(f"{k}={v}" for k, v in facts.items()) or "none"
    return f"Question type: {intent.value}\nLive facts: {live}\nManual: {manual_text or 'none'}"


def llm_keys(settings: "Settings") -> dict[str, str]:
    return {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "openrouter": settings.openrouter_api_key,
        "hf": settings.hf_token,
    }


def make_llm(settings: "Settings") -> AnswerModel:
    """LLM_PROVIDER=fake: templates only. Otherwise every tier in LLM_TIERS whose provider has a key, in order."""
    if settings.llm_provider == "fake":
        from app.llm.fake import FakeAnswerModel

        return FakeAnswerModel()
    from app.llm.tiers import TieredModel, build_tiers

    models = build_tiers(settings.llm_tiers, llm_keys(settings))
    if not models:
        raise ValueError(f"LLM_PROVIDER={settings.llm_provider} needs a key for at least one tier in LLM_TIERS")
    return TieredModel(models, settings.llm_tier_timeout_ms / 1000, settings.llm_hedge_ms / 1000)
