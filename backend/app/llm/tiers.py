"""Model tiers: try each model in order; one that is rate-limited, overloaded or gone cools down and the next answers.

Hedged: a tier that hasn't answered within `hedge_s` gets the next tier racing alongside it, and the first good
answer wins, so one slow model costs seconds, not its whole timeout. Every free model has its own quota, so a chain
rarely runs dry; when it does, callers fall back to the templates, which never fail.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.models import Intent
from app.llm.base import SYSTEM_PROMPT, ChatModel, Message, user_prompt
from app.llm.gemini import GeminiChat
from app.llm.openai_compat import BASE_URLS, OpenAICompatChat

log = logging.getLogger(__name__)
BUSY_S = 30.0  # overloaded (5xx) or too slow: try again soon
RATE_LIMITED_S = 60.0  # 429 without a Retry-After
GONE_S = 3600.0  # 400/401/403/404: retired model or bad key, stop asking for an hour


class AllTiersBusy(RuntimeError):
    pass


def cooldown_s(exc: BaseException) -> float:
    if not isinstance(exc, httpx.HTTPStatusError):
        return BUSY_S
    status = exc.response.status_code
    if status == 429:
        try:
            return float(exc.response.headers.get("retry-after", RATE_LIMITED_S))
        except ValueError:
            return RATE_LIMITED_S
    return GONE_S if status in (400, 401, 403, 404) else BUSY_S


@dataclass
class Tier:
    model: ChatModel
    resting_until: float = 0.0
    failures: int = 0


class TieredModel:
    def __init__(
        self,
        models: list[ChatModel],
        per_try_s: float = 8.0,
        hedge_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not models:
            raise ValueError("TieredModel needs at least one model")
        self._tiers = [Tier(m) for m in models]
        self._per_try_s, self._hedge_s, self._clock = per_try_s, hedge_s, clock
        self.last_used: str | None = None

    @property
    def name(self) -> str:
        more = len(self._tiers) - 1
        return self._tiers[0].model.name + (f" +{more} fallback{'s' if more > 1 else ''}" if more else "")

    def status(self) -> list[dict[str, Any]]:
        now = self._clock()
        return [{"model": t.model.name, "ready": t.resting_until <= now, "failures": t.failures} for t in self._tiers]

    async def chat(self, system: str, messages: list[Message], max_tokens: int = 300) -> tuple[str, str]:
        queue = [t for t in self._tiers if t.resting_until <= self._clock()]
        resting = len(self._tiers) - len(queue)
        running: dict[asyncio.Task[str], Tier] = {}

        def start_next() -> None:
            if queue:
                tier = queue.pop(0)
                running[asyncio.create_task(self._attempt(tier, system, messages, max_tokens))] = tier

        start_next()
        try:
            while running:
                wait_s = self._hedge_s if queue else None
                done, _ = await asyncio.wait(running, timeout=wait_s, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    start_next()  # still thinking: race the next tier alongside
                for task in done:
                    tier = running.pop(task)
                    text = task.result()
                    if text:
                        self.last_used = tier.model.name
                        return text, tier.model.name
                    start_next()  # it failed or said nothing: the next tier takes its place
        finally:
            for task in running:  # the answer is in: the slower tiers lose the race
                task.cancel()
        raise AllTiersBusy(f"no model answered ({len(self._tiers) - resting} tried, {resting} resting)")

    async def _attempt(self, tier: Tier, system: str, messages: list[Message], max_tokens: int) -> str:
        """The tier's reply, or "" after marking it to rest. Losing a race (cancelled) is not a failure."""
        try:
            text = await asyncio.wait_for(tier.model.complete(system, messages, max_tokens), self._per_try_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            tier.failures += 1
            tier.resting_until = self._clock() + cooldown_s(exc)
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            log.warning("LLM tier %s failed (%s); trying the next one", tier.model.name, status)
            return ""
        return " ".join(text.split())

    async def phrase(self, intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str:
        text, _ = await self.chat(
            SYSTEM_PROMPT, [{"role": "user", "text": user_prompt(intent, facts, manual_text)}], 200
        )
        return text


def build_tiers(spec: str, keys: dict[str, str], client: httpx.AsyncClient | None = None) -> list[ChatModel]:
    """ "gemini:gemma-4-26b-a4b-it,groq:llama-3.3-70b-versatile" -> models, skipping providers without a key."""
    models: list[ChatModel] = []
    for item in (s.strip() for s in spec.split(",")):
        provider, _, model = item.partition(":")
        key = keys.get(provider, "")
        if not item or not model or not key:
            continue
        if provider == "gemini":
            models.append(GeminiChat(key, model, client))
        elif provider in BASE_URLS:
            models.append(OpenAICompatChat(BASE_URLS[provider], key, model, client))
        else:
            log.warning("unknown LLM provider %r in LLM_TIERS, skipped", provider)
    return models
