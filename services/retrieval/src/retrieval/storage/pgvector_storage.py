"""PgVector storage with optional text-search fallback when embeddings are missing."""
import json
import os
import time

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval.storage.base import SearchResult, Storage
from retrieval.storage.models import Chunk, Document

# #region agent log
def _dlog(msg: str, data: dict, hypothesis_id: str) -> None:
    p = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"hypothesisId": hypothesis_id, "location": "pgvector_storage.py", "message": msg, "data": data, "timestamp": int(time.time() * 1000)}, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion


class PgVectorStorage(Storage):
    """Postgres storage: vector search when embeddings exist, else ILIKE text search."""

    def __init__(self, session_factory: type[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        # #region agent log
        _dlog("search entry", {"query": query[:50], "top_k": top_k}, "H1")
        # #endregion
        async with self._session_factory() as session:
            try:
                # #region agent log
                _dlog("before vector_search", {}, "H1")
                # #endregion
                out = await self._vector_search(session, query, top_k)
                # #region agent log
                _dlog("vector_search ok", {"len": len(out)}, "H1")
                # #endregion
                return out
            except Exception as e:
                # #region agent log
                _dlog("search except", {"exc_type": type(e).__name__, "exc_msg": str(e)[:200]}, "H1")
                # #endregion
                if isinstance(e, ProgrammingError) and "does not exist" in str(e):
                    # #region agent log
                    _dlog("missing table, return empty", {}, "H1")
                    # #endregion
                    return []
                await session.rollback()
                # #region agent log
                _dlog("after rollback, retry _text_search", {}, "H1")
                # #endregion
                out2 = await self._text_search(session, query, top_k)
                # #region agent log
                _dlog("retry _text_search ok", {"len": len(out2)}, "H1")
                # #endregion
                return out2

    async def _text_search(self, session: AsyncSession, query: str, top_k: int) -> list[SearchResult]:
        """Simple ILIKE search when vector search not available or no embeddings."""
        # #region agent log
        _dlog("_text_search execute", {"query": query[:30]}, "H3")
        # #endregion
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
