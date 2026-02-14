"""Shared embedder: sentence-transformers or mock backend, single contract for ingest and retrieval."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _default_backend() -> str:
    return os.environ.get("EMBEDDER_BACKEND", "mock")


def _default_model() -> str:
    return os.environ.get("EMBEDDER_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")


def _default_dim() -> int:
    return int(os.environ.get("EMBED_DIM", "384"))


class Embedder:
    """Embed texts into 384-dim vectors. Backend: sentence_transformers or mock."""

    def __init__(
        self,
        backend: str | None = None,
        model_name: str | None = None,
        dim: int | None = None,
    ) -> None:
        self._backend = (backend or _default_backend()).lower()
        self._model_name = model_name or _default_model()
        self._dim = dim if dim is not None else _default_dim()
        self._model = None
        if self._backend == "sentence_transformers":
            self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        except ImportError as e:
            raise RuntimeError(
                "sentence_transformers backend requires: pip install sentence-transformers"
            ) from e

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return list of embedding vectors (each of length embed_dim)."""
        if not texts:
            return []
        if self._backend == "mock":
            return [[0.0] * self._dim for _ in texts]
        if self._model is None:
            self._load_model()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]
