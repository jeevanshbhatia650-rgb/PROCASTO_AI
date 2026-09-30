"""Device aliases, intent keywords, correction markers and error-code patterns (rules, no LLM)."""

import re
from collections.abc import Iterable

from app.core.models import DeviceInfo, Intent, Span

INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.STATUS: (
        "how long",
        "done",
        "finish",
        "finished",
        "finishes",
        "finishing",
        "status",
        "doing",
        "remaining",
        "time left",
        "left",
        "running",
        "ready",
        "temperature",
        "temp",
    ),
    Intent.ERROR_LOOKUP: (
        "error",
        "code",
        "mean",
        "means",
        "blinking",
        "flashing",
        "wrong",
        "problem",
        "fix",
        "stop",
        "stopped",
    ),
    Intent.ENERGY: (
        r"power(?!\s+(?:off|on)\b)",
        "energy",
        "consuming",
        "consumption",
        "electricity",
        "bill",
        "so much",
        "watts",
        "kilowatts",
        "usage",
    ),
    Intent.ACTION: (
        "set",
        "turn off",
        "turn on",
        "switch off",
        "switch on",
        "change to",
        "change it to",
        "raise",
        "lower",
        "restart",
    ),
    Intent.RESUME: ("go back", "back to", "continue with", "as i was asking", "return to", "where were we"),
    Intent.CANCEL: ("never mind", "nevermind", "forget it", "cancel that", "cancel"),
}
# Keywords that are already regex fragments rather than plain phrases.
_RAW_PATTERNS = {r"power(?!\s+(?:off|on)\b)"}

_CORRECTION = re.compile(
    r"\bactually\b|\bi meant\b|\bi mean\b|\binstead\b|(?:^|[.,!?]\s*)(?:no|wait|sorry)\b|\b(?:no|wait|sorry),"
)
_PRONOUN = re.compile(r"\b(the other one|other one|that one|this one|it|that|this)\b")
_UPPER_CODE = re.compile(r"\b([A-Z]{1,2})\s?(\d{1,2})\b")
_LOWER_CODE = re.compile(r"\b([a-z]{1,2})(\d{1,2})\b")
_SPOKEN_CODE = re.compile(r"\b(?:error|code)\s+(?:code\s+)?([a-z]{1,2})\s(\d{1,2})\b", re.IGNORECASE)
_TEMP = re.compile(r"\b(?:to|at)\s+(\d{2})\b|\b(\d{2})\s*(?:°|degrees)")
_SEGMENT_BREAK = re.compile(r"\s+(?:and|also|then|plus|but)\s+|[,;.?!]")
_NOT_CODES = {"AC", "TV", "AM", "PM", "OK"}
# Codes the manuals know take other shapes too (4C, 9C1, UE, tE1). Those are only trusted when a manual lists them.
_WORD = re.compile(r"\b[A-Za-z0-9]{2,4}\b")
_CUED = re.compile(r"\b(?:error|code)\s+(?:code\s+)?([a-z0-9]{1,3}(?:\s[a-z0-9]{1,3}){0,2})\b", re.IGNORECASE)
_PIECE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOP_ALONE = {"stop", "stop it", "stop talking", "ok stop", "please stop"}
_FOLLOWUP_PREFIXES = ("and ", "also ", "plus ", "what about ", "how about ")

Match = tuple[int, int, str]


def _phrase_regex(phrases: Iterable[str]) -> re.Pattern[str]:
    parts = [p if p in _RAW_PATTERNS else re.escape(p) for p in sorted(phrases, key=len, reverse=True)]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b")


class Lexicon:
    def __init__(
        self, devices: list[DeviceInfo], model_ids: Iterable[str] = (), known_codes: Iterable[str] = ()
    ) -> None:
        self._known_codes = {c.upper() for c in known_codes}
        self._alias_to_device: dict[str, str] = {}
        for device in devices:
            for alias in [*device.aliases, device.display_name]:
                self._alias_to_device[alias.lower()] = device.device_id
        self._device_re = _phrase_regex(self._alias_to_device)
        self._intent_res = {intent: _phrase_regex(words) for intent, words in INTENT_KEYWORDS.items()}
        self._model_ids = {m.upper() for m in model_ids}

    def devices_in(self, lower: str) -> list[Match]:
        return [(m.start(), m.end(), self._alias_to_device[m.group(0)]) for m in self._device_re.finditer(lower)]

    def intents_in(self, lower: str) -> list[tuple[int, int, Intent]]:
        found = [(m.start(), m.end(), intent) for intent, rx in self._intent_res.items() for m in rx.finditer(lower)]
        return sorted(found)

    def codes_in(self, text: str) -> list[Match]:
        found: dict[int, Match] = {}
        for rx in (_UPPER_CODE, _LOWER_CODE, _SPOKEN_CODE):
            for m in rx.finditer(text):
                code = f"{m.group(1).upper()}{m.group(2)}"
                if m.group(1).upper() in _NOT_CODES or code in self._model_ids:
                    continue
                found.setdefault(m.start(), (m.start(), m.end(), code))
        for m in _WORD.finditer(text):  # a known code written out: "4C", "9c1", "UE" (letters alone only in capitals)
            word, code = m.group(0), m.group(0).upper()
            if code in self._known_codes and code not in _NOT_CODES and (word.isupper() or not word.isalpha()):
                found[m.start()] = (m.start(), m.end(), code)
        for m in _CUED.finditer(text):  # after "error"/"code" a known code may be spoken apart: "error u e", "code 4 c"
            pieces = list(_PIECE.finditer(m.group(1)))
            for n in range(len(pieces), 0, -1):
                code = "".join(p.group(0) for p in pieces[:n]).upper()
                if code in self._known_codes:
                    start = m.start(1)
                    found[start] = (start, start + pieces[n - 1].end(), code)
                    break
        return sorted(found.values())

    def pronoun_in(self, lower: str) -> str | None:
        refs = [m.group(1) for m in _PRONOUN.finditer(lower)]
        if not refs:
            return None
        return "other" if any("other" in r for r in refs) else "it"

    def last_correction_end(self, lower: str) -> int | None:
        ends = [m.end() for m in _CORRECTION.finditer(lower)]
        return ends[-1] if ends else None

    def action_params(self, lower: str) -> dict[str, object]:
        if re.search(r"\b(?:turn|switch) off\b", lower):
            return {"power": "off"}
        if re.search(r"\b(?:turn|switch) on\b", lower):
            return {"power": "on"}
        if re.search(r"\brestart\b", lower):
            return {"command": "restart"}
        m = _TEMP.search(lower)
        return {"target_temp_c": int(m.group(1) or m.group(2))} if m else {}

    def segments(self, lower: str) -> list[tuple[int, int]]:
        bounds, start = [], 0
        for m in _SEGMENT_BREAK.finditer(lower):
            bounds.append((start, m.start()))
            start = m.end()
        bounds.append((start, len(lower)))
        return [(s, e) for s, e in bounds if lower[s:e].strip()]

    @staticmethod
    def is_standalone_stop(lower: str) -> bool:
        return lower.strip(" .!?") in _STOP_ALONE

    @staticmethod
    def is_followup(lower: str) -> bool:
        return lower.lstrip().startswith(_FOLLOWUP_PREFIXES)

    def spans(self, text: str) -> list[Span]:
        lower = text.lower()
        candidates = [
            *((s, e, "device") for s, e, _ in self.devices_in(lower)),
            *((s, e, "intent") for s, e, _ in self.intents_in(lower)),
            *((s, e, "code") for s, e, _ in self.codes_in(text)),
            *((m.start(), m.end(), "correction") for m in _CORRECTION.finditer(lower)),
            *((m.start(), m.end(), "pronoun") for m in _PRONOUN.finditer(lower)),
        ]
        spans: list[Span] = []
        for start, end, role in sorted(candidates, key=lambda c: (c[0], -(c[1] - c[0]))):
            start = start + len(text[start:end]) - len(text[start:end].lstrip(" .,!?"))
            if spans and start < spans[-1].end:
                continue  # overlaps an earlier, longer match
            spans.append(Span(start=start, end=end, role=role))
        return spans
