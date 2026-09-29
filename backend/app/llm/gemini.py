"""Gemini via its REST API. Only used when LLM_PROVIDER=gemini and GEMINI_API_KEY is set."""

from typing import Any

import httpx

from app.core.models import Intent
from app.llm.base import SYSTEM_PROMPT, user_prompt

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiAnswerModel:
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))

    async def phrase(self, intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(intent, facts, manual_text)}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200},
        }
        response = await self._client.post(
            URL.format(model=self._model), json=body, headers={"x-goog-api-key": self._api_key}
        )
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        return " ".join(p.get("text", "") for p in parts).strip()
