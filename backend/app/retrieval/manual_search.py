"""F11: hybrid manual search. Filter by model (fallback family), BM25 + dense, fused with RRF (k=60)."""

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.ids import Clock
from app.core.models import DeviceInfo, Evidence, RetrievalTask
from app.retrieval.base import evidence_id
from app.retrieval.embedder import Embedder
from app.retrieval.manual_ingest import Section

RRF_K = 60
EXACT_CODE_BOOST = 1.0  # an exact error-code heading always outranks fuzzy matches
MENTIONED_CODE_BOOST = 0.01
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "to", "is", "and", "or", "it", "on", "in", "for", "what", "does", "my"}
_LEADING_CODE = re.compile(r"^([A-Z]{1,2}\d{1,2})\b")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


def rrf(*rankings: list[int]) -> dict[int, float]:
    """Reciprocal rank fusion over lists of document indices, best first."""
    scores: defaultdict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] += 1.0 / (RRF_K + rank)
    return dict(scores)


@dataclass(frozen=True)
class Hit:
    section: Section
    score: float

    def as_payload(self) -> dict[str, object]:
        s = self.section
        return {
            "model_id": s.model_id,
            "family": s.family,
            "section_id": s.section_id,
            "title": s.title,
            "text": s.text,
            "page": s.page,
            "codes": list(s.codes),
            "citation": s.citation,
            "summary": s.summary(),
            "steps": s.steps(),
            "score": round(self.score, 4),
        }


class ManualIndex:
    def __init__(self, sections: list[Section], embedder: Embedder | None = None) -> None:
        self._embedder = embedder
        self.reload(sections)

    def reload(self, sections: list[Section]) -> None:
        """Rebuilds every index, then swaps them in together so searches never see a half-built state."""
        groups: dict[str, list[int]] = defaultdict(list)
        for i, s in enumerate(sections):
            groups[f"model:{s.model_id}"].append(i)
            groups[f"family:{s.family}"].append(i)
        bm25 = {key: BM25Okapi([tokenize(self._doc(sections[i])) for i in idx]) for key, idx in groups.items()}
        # Dense side embeds what a section is about (heading + opening sentences); BM25 covers the full text.
        vectors = (
            self._embedder.embed_passages([f"{s.title}. {s.title}. {s.summary()}" for s in sections])
            if self._embedder
            else None
        )
        self._sections, self._groups, self._bm25, self._vectors = sections, groups, bm25, vectors

    @property
    def sections(self) -> list[Section]:
        return list(self._sections)

    @property
    def dense_model(self) -> str | None:
        return self._embedder.name if self._embedder else None

    def model_ids(self) -> list[str]:
        return sorted({s.model_id for s in self._sections})

    def search(
        self, query: str, model_id: str, family: str | None = None, error_code: str | None = None, k: int = 2
    ) -> list[Hit]:
        key = f"model:{model_id}" if f"model:{model_id}" in self._groups else f"family:{family}"
        idx = self._groups.get(key, [])
        if not idx:
            return []
        bm25 = self._bm25[key].get_scores(tokenize(query))
        rankings = [[idx[i] for i in np.argsort(-bm25, kind="stable")]]
        if self._embedder is not None and self._vectors is not None:
            sims = self._vectors[idx] @ self._embedder.embed_query(query)
            rankings.append([idx[i] for i in np.argsort(-sims, kind="stable")])
        scores = rrf(*rankings)
        for i in idx:
            section = self._sections[i]
            if error_code and section.heading_code == error_code:
                scores[i] += EXACT_CODE_BOOST
            elif error_code and error_code in section.codes:
                scores[i] += MENTIONED_CODE_BOOST
        keyword = dict(zip(idx, bm25, strict=True))
        best = sorted(idx, key=lambda i: (scores[i], keyword[i]), reverse=True)[:k]  # ties go to the keyword match
        return [Hit(self._sections[i], scores[i]) for i in best]

    @staticmethod
    def _doc(section: Section) -> str:
        return f"{section.section_id} {section.title}\n{section.text}"


class ManualRetriever:
    def __init__(self, index: ManualIndex, infos: dict[str, DeviceInfo], clock: Clock) -> None:
        self._index, self._infos, self._clock = index, infos, clock

    async def retrieve(self, task: RetrievalTask) -> Evidence:
        info = self._infos[task.device_id or ""]
        match = _LEADING_CODE.match(task.query)
        code = match.group(1) if match else None
        hits = await asyncio.to_thread(self._index.search, task.query, info.model_id, info.family, code, 2)
        top = hits[0].section if hits else None
        return Evidence(
            evidence_id=evidence_id(task),
            task_id=task.task_id,
            source_type="manual",
            device_id=task.device_id,
            model_id=top.model_id if top else info.model_id,
            authority="manual",
            observed_at=self._clock.now(),
            device_revision=None,
            plan_revision=task.plan_revision,
            payload={"hits": [h.as_payload() for h in hits], "error_code": code},
            citation=top.citation if top else f"{info.model_id} manual · no match",
        )
