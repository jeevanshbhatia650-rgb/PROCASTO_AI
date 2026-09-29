"""Offline stand-ins used by tests."""

import hashlib
import re

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic bag-of-words vectors. No semantics, but stable and offline: good for tests."""

    name = "hash-256"

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim)
        for token in _TOKEN.findall(text.lower()):
            digest = int(hashlib.md5(token.encode(), usedforsecurity=False).hexdigest(), 16)
            vec[digest % self._dim] += 1.0 if digest & 1 else -1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vector(t) for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)
