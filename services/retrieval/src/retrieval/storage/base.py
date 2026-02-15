"""Storage abstraction for retrieval - can be swapped for different backends."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    source: str
    score: float
    distance: float | None = None
    confidence: float = 0.0
    version: str | None = None
    document_title: str | None = None
    section_title: str | None = None
    position: int = 0


class Storage(ABC):
    """Abstract storage for document chunks and vector/text search."""

    @abstractmethod
    async def search(
        self, query: str, top_k: int = 5, version: str | None = None
    ) -> list[SearchResult]:
        """Search for relevant chunks. Returns list ordered by relevance (score)."""
        ...
