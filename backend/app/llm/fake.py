"""Deterministic stand-in for an LLM: the manual's first sentence plus its first step."""

import re
from typing import Any

from app.core.models import Intent

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_STEP = re.compile(r"^\s*1\.\s+(.*)$", re.MULTILINE)


class FakeAnswerModel:
    name = "templates"

    async def phrase(self, intent: Intent, facts: dict[str, Any], manual_text: str | None) -> str:
        if not manual_text:
            return ""
        prose = " ".join(line for line in manual_text.splitlines() if line.strip() and not line.lstrip()[:1].isdigit())
        first = _SENTENCE_END.split(prose.strip())[0]
        step = _STEP.search(manual_text)
        return f"{first} Start with this: {step.group(1)}" if step else first
