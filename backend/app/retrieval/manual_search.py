"""F11: hybrid manual search. Filter by model (fallback family), BM25 + dense, fused with RRF (k=60).

A code the manuals don't cover falls through to the vector database (ChromaDB, real Samsung codes)."""

import asyncio
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.ids import Clock
from app.core.models import DeviceInfo, Evidence, RetrievalTask
from app.retrieval.base import evidence_id
from app.retrieval.embedder import Embedder
from app.retrieval.manual_ingest import Section
from app.retrieval.semantic_cache import SemanticCache
from app.retrieval.vector_db import VectorCodes

RRF_K = 60
EXACT_CODE_BOOST = 1.0  # an exact error-code heading always outranks fuzzy matches
MENTIONED_CODE_BOOST = 0.01
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "to", "is", "and", "or", "it", "on", "in", "for", "what", "does", "my"}
_LEADING_CODE = re.compile(r"^([A-Z0-9]{2,4}) error\b")  # the planner asks "<code> error meaning fix"


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
            "heading_codes": list(s.heading_codes),
            "citation": s.citation,
            "summary": s.summary(),
            "steps": s.steps(),
            "score": round(self.score, 4),
        }


class ManualIndex:
    def __init__(
        self, sections: list[Section], embedder: Embedder | None = None, vectors: VectorCodes | None = None
    ) -> None:
        self._embedder = embedder
        self.vectors = vectors
        self.reload(sections)

    def reload(self, sections: list[Section]) -> None:
        """Rebuilds every index, then swaps them in together so searches never see a half-built state."""
        groups: dict[str, list[int]] = defaultdict(list)
        for i, s in enumerate(sections):
            groups[f"model:{s.model_id}"].append(i)
            groups[f"family:{s.family}"].append(i)
        models = {s.model_id: s.family for s in sections if not s.family_wide}
        for i, s in enumerate(sections):  # a family-wide table answers for every model of that family
            if s.family_wide:
                for model_id, family in models.items():
                    if family == s.family:
                        groups[f"model:{model_id}"].append(i)
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

    def query_embedder(self) -> "Callable[[str], np.ndarray] | None":
        """The dense model's query embedding, for the semantic cache; None when dense search is off."""
        return self._embedder.embed_query if self._embedder else None

    @property
    def dense_model(self) -> str | None:
        return self._embedder.name if self._embedder else None

    def model_ids(self) -> list[str]:
        return sorted({s.model_id for s in self._sections})

    def error_codes(self) -> list[str]:
        """Every code a manual has a section for, so speech and typing can recognise it."""
        vector = self.vectors.codes() if self.vectors else set()
        return sorted({code for s in self._sections for code in s.heading_codes} | vector)

    def search(
        self, query: str, model_id: str, family: str | None = None, error_code: str | None = None, k: int = 2
    ) -> list[Hit]:
        hits = self._search_manuals(query, model_id, family, error_code, k)
        if error_code and family and self.vectors and not any(error_code in h.section.heading_codes for h in hits):
            found = self.vectors.lookup(family, error_code)
            hits = [Hit(s, EXACT_CODE_BOOST) for s in found[:1]] + hits  # one row: markets repeat the same code
        return hits[:k]

    def _search_manuals(
        self, query: str, model_id: str, family: str | None, error_code: str | None, k: int
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
            if error_code and error_code in section.heading_codes:
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
    """The Manual agent: hybrid search over the manuals, behind a semantic cache shared by the whole home."""

    def __init__(
        self, index: ManualIndex, infos: dict[str, DeviceInfo], clock: Clock, cache: SemanticCache | None = None
    ) -> None:
        self._index, self._infos, self._clock, self._cache = index, infos, clock, cache

    async def retrieve(self, task: RetrievalTask) -> Evidence:
        info = self._infos[task.device_id or ""]
        match = _LEADING_CODE.match(task.query)
        code = match.group(1) if match else None
        hits, cache = await search_cached(self._index, self._cache, task.query, info, code)
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
            payload={"hits": [h.as_payload() for h in hits], "error_code": code, "cache": cache},
            citation=top.citation if top else f"{info.model_id} manual · no match",
        )


async def search_cached(
    index: ManualIndex, cache: SemanticCache | None, query: str, info: DeviceInfo, code: str | None
) -> tuple[list[Hit], str]:
    """Hits for a question, and whether the semantic cache answered ("hit"), or the index did ("miss", "off")."""
    if cache is not None:
        found = await asyncio.to_thread(cache.get, info.model_id, code, query)
        if found is not None:
            return found[0], "hit"
    hits = await asyncio.to_thread(index.search, query, info.model_id, info.family, code, 2)
    if cache is not None:
        cache.put(info.model_id, code, query, hits)
    return hits, "miss" if cache is not None else "off"
