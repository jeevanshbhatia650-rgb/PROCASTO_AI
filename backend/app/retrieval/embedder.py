"""Dense embeddings for manual search (fastembed, BAAI/bge-small-en-v1.5)."""

import logging
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    name = "BAAI/bge-small-en-v1.5"

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # heavy import, only when dense search is on

        self._model = TextEmbedding(self.name)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.array(list(self._model.passage_embed(texts)))

    def embed_query(self, text: str) -> np.ndarray:
        return np.array(next(iter(self._model.query_embed(text))))


def make_embedder(enabled: bool) -> Embedder | None:
    """Returns None (BM25-only search) when dense search is off or the model can't load."""
    if not enabled:
        return None
    try:
        return FastEmbedEmbedder()
    except Exception:
        log.warning("dense embeddings unavailable, manual search falls back to BM25 only", exc_info=True)
        return None
