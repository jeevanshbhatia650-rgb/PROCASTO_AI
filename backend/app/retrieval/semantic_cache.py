"""The Manual agent's semantic cache: a close enough question about the same model and code reuses the last answer.

A related pivot ("washer finish time" -> "how long left on the washer") sits around 0.65-0.85 cosine similarity;
unrelated questions sit around 0.1-0.4, so 0.60 is the line. The error code is part of the key, never part of the
similarity: "E3 meaning" and "E4 meaning" read alike but must never share an answer. Live device state is never
cached (it is pushed and always fresh); only manual lookups, which change when the manual does.

An exact repeat is a dict lookup with no embedding at all; only a near miss pays for one vector.
"""

import hashlib
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

REUSE_AT = 0.60
MAX_ENTRIES = 256
_WORD = re.compile(r"[a-z0-9]+")
_BOW_DIMS = 512


def bag_of_words(text: str) -> np.ndarray:
    """A cheap stand-in vector when the dense model is off: hashed word counts, unit length."""
    vector = np.zeros(_BOW_DIMS, dtype=np.float32)
    for word in _WORD.findall(text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % _BOW_DIMS] += 1.0
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


@dataclass
class _Entry:
    query: str
    vector: np.ndarray | None
    hits: list
    prefetched: bool


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    prefetched: int = 0
    prefetch_hits: int = 0

    def as_payload(self) -> dict[str, object]:
        asked = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / asked, 2) if asked else None,
            "prefetched": self.prefetched,
            "prefetch_hits": self.prefetch_hits,
        }


class SemanticCache:
    def __init__(self, embed: Callable[[str], np.ndarray] | None = None, threshold: float = REUSE_AT) -> None:
        raw = embed or bag_of_words
        self._embed = lambda text: _unit(raw(text))  # cosine becomes a dot product
        self._threshold = threshold
        self._entries: OrderedDict[tuple[str, str, str], _Entry] = OrderedDict()
        self.stats = CacheStats()

    def get(self, model_id: str, code: str | None, query: str) -> tuple[list, float] | None:
        """Cached hits and the similarity that matched them, or None. Counts a hit or a miss."""
        exact = self._entries.get((model_id, code or "", query))
        found: tuple[_Entry, float] | None = (exact, 1.0) if exact else None
        if found is None:
            vector = self._embed(query)
            best = max(
                (
                    (entry, float(np.dot(self._vector(entry), vector)))
                    for (m, c, _), entry in self._entries.items()
                    if (m, c) == (model_id, code or "")
                ),
                key=lambda pair: pair[1],
                default=None,
            )
            found = best if best and best[1] >= self._threshold else None
        if found is None:
            self.stats.misses += 1
            return None
        entry, similarity = found
        self.stats.hits += 1
        if entry.prefetched:
            self.stats.prefetch_hits += 1
            entry.prefetched = False  # count a prefetch as useful once
        self._entries.move_to_end((model_id, code or "", entry.query))
        return entry.hits, similarity

    def put(self, model_id: str, code: str | None, query: str, hits: list, prefetched: bool = False) -> None:
        key = (model_id, code or "", query)
        if prefetched and key in self._entries:
            return  # already warm
        self._entries[key] = _Entry(query, None, hits, prefetched)
        self._entries.move_to_end(key)
        if prefetched:
            self.stats.prefetched += 1
        while len(self._entries) > MAX_ENTRIES:
            self._entries.popitem(last=False)

    def has(self, model_id: str, code: str | None, query: str) -> bool:
        return (model_id, code or "", query) in self._entries

    def clear(self) -> None:
        self._entries.clear()

    def _vector(self, entry: _Entry) -> np.ndarray:
        if entry.vector is None:  # embedded lazily: exact repeats never need it
            entry.vector = self._embed(entry.query)
        return entry.vector
