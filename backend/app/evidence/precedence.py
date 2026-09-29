"""F13 rules (plan section 2.2). Live state owns the present; manuals must match the model; never the LLM."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.models import DeviceInfo, Evidence

# Lower wins. Live readings beat the conversation, which beats manual defaults.
_RANK = {"smartthings": 0, "simulator": 0, "session": 1, "manual": 2}


@dataclass(frozen=True)
class Fact:
    value: Any
    evidence_id: str
    source_type: str
    observed_at: datetime


@dataclass(frozen=True)
class ResolvedFacts:
    device_id: str | None
    facts: dict[str, Fact]
    manual_hits: list[dict[str, Any]]
    evidence: list[Evidence]

    def value(self, key: str, default: Any = None) -> Any:
        fact = self.facts.get(key)
        return fact.value if fact else default

    def plain(self) -> dict[str, Any]:
        """What the LLM gets: resolved values only, never raw evidence."""
        return {key: fact.value for key, fact in self.facts.items()}


def manual_matches(evidence: Evidence, device: DeviceInfo) -> bool:
    hits = evidence.payload.get("hits", [])
    if evidence.model_id == device.model_id:
        return True
    return bool(hits) and all(h.get("family") == device.family for h in hits)


def _facts_of(evidence: Evidence) -> dict[str, Any]:
    if evidence.source_type == "live_state":
        return evidence.payload.get("attributes", {})
    if evidence.source_type == "manual":
        return evidence.payload.get("facts", {})
    return {}


def resolve(evidence: list[Evidence], device: DeviceInfo | None) -> ResolvedFacts:
    usable = [e for e in evidence if e.source_type != "manual" or device is None or manual_matches(e, device)]
    facts: dict[str, Fact] = {}
    # Weakest first, so stronger (and, within a rank, newer) evidence overwrites.
    for ev in sorted(usable, key=lambda e: (-_RANK[e.authority], e.observed_at)):
        for key, value in _facts_of(ev).items():
            facts[key] = Fact(value, ev.evidence_id, ev.source_type, ev.observed_at)
    hits = [h for e in usable if e.source_type == "manual" for h in e.payload.get("hits", [])]
    return ResolvedFacts(device.device_id if device else None, facts, hits, usable)
