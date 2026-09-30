"""Any OpenAI-compatible chat endpoint: Groq, OpenRouter's free models, Hugging Face's router."""

import httpx

from app.llm.base import Message

BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "hf": "https://router.huggingface.co/v1",
}


class OpenAICompatChat:
    def __init__(self, base_url: str, api_key: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self.name = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    async def complete(self, system: str, messages: list[Message], max_tokens: int) -> str:
        body = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m["role"], "content": m["text"]} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        response = await self._client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._api_key}"})
        response.raise_for_status()
        return (response.json()["choices"][0]["message"].get("content") or "").strip()
