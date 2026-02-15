"""HTTP client for retrieval service."""
from dataclasses import dataclass

import httpx


@dataclass
class RetrievalResultItem:
    chunk_id: str
    text: str
    source: str
    score: float
    document_title: str | None = None
    section_title: str | None = None
    position: int = 0


class RetrievalClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(
        self, query: str, top_k: int = 5, version: str | None = None
    ) -> list[RetrievalResultItem]:
        url = f"{self._base_url}/search"
        payload: dict = {"query": query, "top_k": top_k}
        if version is not None:
            payload["version"] = version
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        return [
            RetrievalResultItem(
                chunk_id=r["chunk_id"],
                text=r["text"],
                source=r["source"],
                score=float(r.get("score", 0)),
                document_title=r.get("document_title"),
                section_title=r.get("section_title"),
                position=int(r.get("position", 0)),
            )
            for r in results
        ]
