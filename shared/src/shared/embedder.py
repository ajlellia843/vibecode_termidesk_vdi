"""Shared embedder: sentence-transformers or mock backend, single contract for ingest and retrieval."""
from __future__ import annotations

import hashlib
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _default_backend() -> str:
    return os.environ.get("EMBEDDER_BACKEND", "sentence_transformers")


def _default_model() -> str:
    return os.environ.get("EMBEDDER_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")


def _default_dim() -> int:
    return int(os.environ.get("EMBED_DIM", "384"))


class Embedder:
    """Embed texts into vectors. Backend: sentence_transformers (default) or mock."""

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
            self._validate_dim()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        except ImportError as e:
            raise RuntimeError(
                "sentence_transformers backend requires: pip install sentence-transformers"
            ) from e

    def _validate_dim(self) -> None:
        """Fail-fast: verify actual model output dim matches configured dim."""
        test_vec = self.embed_texts(["dim validation test"])[0]
        actual = len(test_vec)
        if actual != self._dim:
            raise ValueError(
                f"Embedding dim mismatch: configured dim={self._dim}, "
                f"actual model output dim={actual}. "
                f"Set EMBED_DIM={actual} or use a model with dim={self._dim}."
            )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return list of embedding vectors (each of length embed_dim)."""
        if not texts:
            return []
        if self._backend == "mock":
            # Bag-of-words style: overlapping words => closer vectors so relevant docs score higher
            out = []
            for text in texts:
                words = re.findall(r"\w+", text.lower())
                vec = [0.0] * self._dim
                for w in words:
                    if len(w) >= 2:
                        idx = int(hashlib.sha256(w.encode()).hexdigest(), 16) % self._dim
                        vec[idx] += 1.0
                norm = sum(x * x for x in vec) ** 0.5
                if norm > 0:
                    vec = [x / norm for x in vec]
                out.append(vec)
            return out
        if self._model is None:
            self._load_model()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]
