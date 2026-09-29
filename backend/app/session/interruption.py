"""F15: barge-in. Stop speaking now, cancel phrasing in flight, let the plan engine park or replace."""

from collections.abc import Callable
from typing import Any

from app.answer.composer import Composer
from app.core.ids import Clock
from app.observability.timeline import Timeline

Send = Callable[[str, Any], None]
MS_PER_WORD = 380  # a typical text-to-speech pace, used to guess when the voice finishes


class SpeechChannel:
    def __init__(self, clock: Clock, send: Send, composer: Composer, timeline: Timeline) -> None:
        self._clock, self._send = clock, send
        self._composer, self._timeline = composer, timeline
        self._speaking_until = 0

    def speak(self, text: str, card_id: str, priority: str = "normal") -> None:
        self._send("speech.say", {"text": text, "card_id": card_id, "priority": priority})
        self._speaking_until = self._clock.ms() + 400 + MS_PER_WORD * len(text.split())

    def finished(self) -> None:
        """The browser reports the voice ended (or was cut)."""
        self._speaking_until = 0

    def is_speaking(self) -> bool:
        return self._clock.ms() < self._speaking_until

    def interrupt(self, reason: str) -> None:
        """Order matters: silence first (same tick), then stop LLM work, then record it."""
        self._send("speech.stop", {})
        was_speaking = self.is_speaking()
        self._speaking_until = 0
        cancelled = self._composer.cancel_llm()
        self._timeline.emit("interrupt", reason=reason, was_speaking=was_speaking, llm_cancelled=cancelled)
