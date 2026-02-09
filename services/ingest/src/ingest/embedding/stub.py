"""Stub embedder - returns zero vector for MVP."""
from ingest.embedding.base import BaseEmbedder


class StubEmbedder(BaseEmbedder):
    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        return [0.0] * self._dim
