"""Tests for search with mock storage."""
import pytest

from retrieval.storage.base import SearchResult, Storage


class MockStorage(Storage):
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        return self._results[:top_k]


@pytest.mark.asyncio
async def test_search_returns_results() -> None:
    storage = MockStorage([
        SearchResult(chunk_id="1", text="Termidesk VDI", source="faq.md", score=0.95),
        SearchResult(chunk_id="2", text="Подключение к серверу", source="troubleshooting.md", score=0.8),
    ])
    results = await storage.search("подключение", top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == "1"
    assert results[0].score == 0.95
    assert results[1].source == "troubleshooting.md"


@pytest.mark.asyncio
async def test_search_respects_top_k() -> None:
    storage = MockStorage([
        SearchResult(chunk_id=str(i), text=f"text {i}", source="a.md", score=1.0 - i * 0.1)
        for i in range(5)
    ])
    results = await storage.search("x", top_k=2)
    assert len(results) == 2
