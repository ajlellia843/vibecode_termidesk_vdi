"""Search service - delegates to Storage."""
from retrieval.storage.base import SearchResult, Storage


class SearchService:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def search(
        self, query: str, top_k: int = 5, version: str | None = None
    ) -> list[SearchResult]:
        return await self._storage.search(query, top_k=top_k, version=version)
