"""F6: partial transcript -> clauses, with the stability rule (seen in N consecutive partials)."""

from dataclasses import dataclass, field
from typing import Any

from app.core.models import Clause, Intent, Span
from app.nlu.lexicon import Lexicon


@dataclass(frozen=True)
class Extraction:
    clauses: list[Clause]  # clauses in the text after the last correction marker
    is_correction: bool
    stable_mentions: list[str]  # devices named after the correction marker, stable
    spans: list[Span]
    is_followup: bool


@dataclass(frozen=True)
class _Raw:
    device_id: str | None
    intent: Intent
    error_code: str | None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.intent.value}:{self.device_id or '?'}:{self.error_code or '-'}"


def _unique(items: list[Any]) -> list[Any]:
    return list(dict.fromkeys(items))


class ClauseExtractor:
    def __init__(self, lexicon: Lexicon, stability_n: int = 2) -> None:
        self._lex = lexicon
        self._n = stability_n
        self.reset()

    def reset(self) -> None:
        """Call at the start of every utterance."""
        self._streak: dict[str, int] = {}
        self._first_seen: dict[str, int] = {}

    def update(self, text: str, t_ms: int, final: bool = False) -> Extraction:
        lower = text.lower()
        marker_end = self._lex.last_correction_end(lower)
        active = text[marker_end or 0 :]
        raws = self._parse(active)
        mentions = _unique([d for _, _, d in self._lex.devices_in(active.lower())])

        keys = [r.key for r in raws] + [f"mention:{d}" for d in mentions]
        self._streak = {k: self._streak.get(k, 0) + 1 for k in keys}
        for k in keys:
            self._first_seen.setdefault(k, t_ms)

        clauses = [self._clause(r, final) for r in raws]
        stable_mentions = [d for d in mentions if final or self._streak[f"mention:{d}"] >= self._n]
        return Extraction(
            clauses=clauses,
            is_correction=marker_end is not None,
            stable_mentions=stable_mentions if marker_end is not None else [],
            spans=self._lex.spans(text),
            is_followup=self._lex.is_followup(lower),
        )

    def _clause(self, raw: _Raw, final: bool) -> Clause:
        seen_enough = self._streak[raw.key] >= self._n
        # A device-less clause without a pronoun is a guess until the sentence ends. That includes "go back to...":
        # resuming before the device is named would bring back the wrong parked plan.
        if raw.device_id is None and "ref" not in raw.params and raw.intent != Intent.CANCEL:
            seen_enough = False
        return Clause(
            clause_id=raw.key,
            device_id=raw.device_id,
            intent=raw.intent,
            error_code=raw.error_code,
            params=raw.params,
            stable=final or seen_enough,
            first_seen_ms=self._first_seen[raw.key],
        )

    def _parse(self, text: str) -> list[_Raw]:
        lower = text.lower()
        if self._lex.is_standalone_stop(lower):
            return [_Raw(None, Intent.CANCEL, None)]
        out: list[_Raw] = []
        pending: list[str] = []  # devices named in intent-less segments ("the washer and ...")
        last_device: str | None = None
        for start, end in self._lex.segments(lower):
            seg_lower, seg_text = lower[start:end], text[start:end]
            intents = _unique([i for _, _, i in self._lex.intents_in(seg_lower)])
            codes = [c for _, _, c in self._lex.codes_in(seg_text)]
            devices = _unique(pending + [d for _, _, d in self._lex.devices_in(seg_lower)])
            if codes and Intent.ERROR_LOOKUP not in intents:
                intents.append(Intent.ERROR_LOOKUP)
            if not intents:
                pending = devices
                continue
            pending = []
            ref = self._lex.pronoun_in(seg_lower)
            extra: dict[str, Any] = {}
            if not devices and last_device and ref != "other":
                devices = [last_device]
            elif not devices:
                devices = [None]
                extra = {"ref": ref} if ref else {}
            for device in devices:
                for intent in intents:
                    params = dict(extra)
                    if intent == Intent.ACTION:
                        params.update(self._lex.action_params(seg_lower))
                    code = codes[0] if intent == Intent.ERROR_LOOKUP and codes else None
                    out.append(_Raw(device, intent, code, params))
            last_device = next((d for d in reversed(devices) if d), last_device)
        return self._dedupe(out)

    @staticmethod
    def _dedupe(raws: list[_Raw]) -> list[_Raw]:
        coded = {r.device_id for r in raws if r.intent == Intent.ERROR_LOOKUP and r.error_code}
        seen: dict[str, _Raw] = {}
        for r in raws:
            if r.intent == Intent.ERROR_LOOKUP and not r.error_code and r.device_id in coded:
                continue  # "what does E3 mean ... how do I fix it" is one lookup, not two
            seen.setdefault(r.key, r)
        return list(seen.values())
