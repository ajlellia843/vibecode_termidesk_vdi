"""PgVector storage with optional text-search fallback when embeddings are missing."""
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval.storage.base import SearchResult, Storage
from retrieval.storage.models import Chunk, Document


class PgVectorStorage(Storage):
    """Postgres storage: vector search when embeddings exist, else ILIKE text search."""

    def __init__(self, session_factory: type[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        async with self._session_factory() as session:
            try:
                return await self._vector_search(session, query, top_k)
            except Exception as e:
                if isinstance(e, ProgrammingError) and "does not exist" in str(e):
                    return []
                await session.rollback()
                return await self._text_search(session, query, top_k)

    async def _text_search(self, session: AsyncSession, query: str, top_k: int) -> list[SearchResult]:
        """Simple ILIKE search when vector search not available or no embeddings."""
        q = (
            select(Chunk.id, Chunk.text, Document.source)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.text.ilike(f"%{query}%"))
            .limit(top_k * 2)
        )
        result = await session.execute(q)
        rows = result.all()
        out: list[SearchResult] = []
        for i, (chunk_id, text_val, source) in enumerate(rows[:top_k]):
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=1.0 - (i * 0.05),
                )
            )
        if not out and query.strip():
            q_any = (
                select(Chunk.id, Chunk.text, Document.source)
                .join(Document, Chunk.document_id == Document.id)
                .limit(top_k)
            )
            r2 = await session.execute(q_any)
            for i, (chunk_id, text_val, source) in enumerate(r2.all()):
                out.append(
                    SearchResult(
                        chunk_id=str(chunk_id),
                        text=text_val or "",
                        source=source or "",
                        score=0.5 - (i * 0.05),
                    )
                )
        return out

    async def _vector_search(self, session: AsyncSession, query: str, top_k: int) -> list[SearchResult]:
        """Vector similarity search using pgvector (requires query embedding - stub for now)."""
        # For MVP without embedder: use text search from this class
        return await self._text_search(session, query, top_k)
