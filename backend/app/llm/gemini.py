"""Gemini and Gemma (open weights) through Google's generateContent REST API; one free quota per model."""

import httpx

from app.llm.base import Message

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def thinking(model: str) -> dict[str, object]:
    """Voice can't wait for long reasoning: 2.x models take a zero budget, newer ones the minimal level."""
    return {"thinkingBudget": 0} if model.startswith("gemini-2") else {"thinkingLevel": "minimal"}


class GeminiChat:
    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self.name = model
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    async def complete(self, system: str, messages: list[Message], max_tokens: int) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["text"]}]}
                for m in messages
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens,
                "thinkingConfig": thinking(self.name),
            },
        }
        response = await self._client.post(
            URL.format(model=self.name), json=body, headers={"x-goog-api-key": self._api_key}
        )
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"].get("parts", [])
        return " ".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
