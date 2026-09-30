"""The vector database: real Samsung fault codes (ApplianceDB, ODbL) in ChromaDB, embedded with bge-small.

Built outside the app from data/real/samsung_appliance_codes.csv with BAAI/bge-small-en-v1.5, the same model the
manual search uses, so questions and stored codes share one vector space. Two ways in:
exact (metadata filter on appliance type + code) for the pipeline, semantic (nearest neighbours) for conversation.
"""

import logging
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from app.retrieval.manual_ingest import Section

log = logging.getLogger(__name__)
COLLECTION = "samsung_appliance_codes"
SOURCE = "ApplianceDB Samsung codes (ODbL)"
_MEANING = re.compile(r"indicates:\s*(.+?)(?:\s+System diagnostics state|$)", re.DOTALL)
_STEPS = re.compile(r"Troubleshooting and repair steps:\s*(.+)$", re.DOTALL)
_STEP_SPLIT = re.compile(r"(?:^|\s)\d+\.\s+")


def to_section(document: str, meta: dict[str, Any]) -> Section:
    """One stored code as a manual section, so the composer, cache and citations treat it like any manual."""
    kind, code = str(meta["appliance_type"]), str(meta["code"]).upper()
    found = _MEANING.search(document)
    meaning = (found.group(1) if found else document).strip()
    steps_found = _STEPS.search(document)
    steps = [s.strip() for s in _STEP_SPLIT.split(steps_found.group(1)) if s.strip()] if steps_found else []
    facts = [f"Part: {meta['component']}." if meta.get("component") else ""]
    facts.append(f"Severity: {str(meta['severity']).replace('_', ' ')}." if meta.get("severity") else "")
    text = "\n".join([meaning, " ".join(f for f in facts if f), *(f"{i}. {s}" for i, s in enumerate(steps, 1))])
    return Section(
        model_id=f"Samsung {kind}",
        family=kind,
        section_id=code,
        title=meaning.rstrip("."),
        text=text,
        page=None,
        codes=(code,),
        source=SOURCE,
        family_wide=True,
    )


class VectorCodes:
    def __init__(self, path: Path, embed_query: Callable[[str], np.ndarray] | None) -> None:
        import chromadb  # heavy import, only when the vector database is used

        # ponytail: opened from a temp copy, because Chroma writes to its folder on open (dirty git, read-only images).
        work = Path(tempfile.mkdtemp(prefix="procasto-chroma-")) / "db"
        shutil.copytree(path, work)
        client = chromadb.PersistentClient(path=str(work), settings=chromadb.Settings(anonymized_telemetry=False))
        self._collection = client.get_collection(COLLECTION)
        self._embed = embed_query
        metas = self._collection.get(include=["metadatas"])["metadatas"] or []
        self._codes = {(str(m["appliance_type"]), str(m["code"]).upper()) for m in metas}

    @property
    def size(self) -> int:
        """Stored rows; a code can have one per market."""
        return self._collection.count()

    def types(self) -> set[str]:
        return {kind for kind, _ in self._codes}

    def codes(self) -> set[str]:
        return {code for _, code in self._codes}

    def lookup(self, appliance_type: str, code: str) -> list[Section]:
        """Exact: this appliance type's rows for this code (one per market). Case-insensitive on the code."""
        code = code.upper()
        if (appliance_type, code) not in self._codes:
            return []
        found = self._collection.get(
            where={"$and": [{"appliance_type": appliance_type}, {"code": code}]}, include=["documents", "metadatas"]
        )
        return [to_section(d, m) for d, m in zip(found["documents"] or [], found["metadatas"] or [], strict=True)]

    def search(self, query: str, appliance_types: list[str] | None = None, k: int = 3) -> list[tuple[Section, float]]:
        """Semantic: the stored codes nearest the question, with cosine similarity. Needs the dense model."""
        if self._embed is None:
            return []
        wanted = [t for t in appliance_types or [] if t in self.types()]
        where: Any = {"appliance_type": {"$in": wanted}} if wanted else None
        found = self._collection.query(
            query_embeddings=[self._embed(query).tolist()],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        docs, metas, dists = found["documents"] or [[]], found["metadatas"] or [[]], found["distances"] or [[]]
        return [
            (to_section(d, m), round(1.0 - float(dist), 4))  # the collection uses cosine distance
            for d, m, dist in zip(docs[0], metas[0], dists[0], strict=True)
        ]


def open_vector_codes(path: Path, embed_query: Callable[[str], np.ndarray] | None) -> VectorCodes | None:
    """None (manuals only) when the database is missing or ChromaDB can't open it."""
    if not (path / "chroma.sqlite3").exists():
        return None
    try:
        return VectorCodes(path, embed_query)
    except Exception:
        log.warning("vector database unavailable, fault-code lookups use the manuals only", exc_info=True)
        return None
