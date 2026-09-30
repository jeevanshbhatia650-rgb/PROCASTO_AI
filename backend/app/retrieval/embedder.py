"""Dense embeddings for manual search (fastembed, BAAI/bge-small-en-v1.5)."""

import logging
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


PASSAGE_BATCH = 4  # ONNX Runtime keeps its peak working memory: batches of 4 hold 215 MB, the default 256 holds 327


class FastEmbedEmbedder:
    name = "BAAI/bge-small-en-v1.5"

    def __init__(self, threads: int | None = None) -> None:
        from fastembed import TextEmbedding  # heavy import, only when dense search is on

        self._model = TextEmbedding(self.name, threads=threads)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.array(list(self._model.passage_embed(texts, batch_size=PASSAGE_BATCH)))

    def embed_query(self, text: str) -> np.ndarray:
        return np.array(next(iter(self._model.query_embed(text))))


def make_embedder(enabled: bool, threads: int = 0) -> Embedder | None:
    """Returns None (BM25-only search) when dense search is off or the model can't load. threads 0 = every core."""
    if not enabled:
        return None
    try:
        return FastEmbedEmbedder(threads or None)
    except Exception:
        log.warning("dense embeddings unavailable, manual search falls back to BM25 only", exc_info=True)
        return None
