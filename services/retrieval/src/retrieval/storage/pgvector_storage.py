"""PgVector storage: vector search (pgvector), optional text/hybrid fallback."""
import json
import os
import re
import time
from typing import Any

from sqlalchemy import bindparam, or_, select
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


def _get_embedder():  # lazy import to avoid loading sentence_transformers at import time
    from shared.embedder import Embedder
    return Embedder


class PgVectorStorage(Storage):
    """Postgres storage: vector and/or text search by RETRIEVAL_MODE."""

    def __init__(
        self,
        session_factory: type[AsyncSession],
        embedder: Any | None = None,
        retrieval_mode: str = "vector",
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._retrieval_mode = (retrieval_mode or "vector").lower()

    async def search(
        self, query: str, top_k: int = 5, version: str | None = None
    ) -> list[SearchResult]:
        # #region agent log
        _dlog("search entry", {"query": query[:50], "top_k": top_k, "version": version}, "H1")
        # #endregion
        async with self._session_factory() as session:
            if self._retrieval_mode == "text":
                return await self._text_search(session, query, top_k, version)
            if self._retrieval_mode == "vector":
                try:
                    out = await self._vector_search(session, query, top_k, version)
                    return out
                except ProgrammingError as e:
                    # #region agent log
                    _dlog("vector_search ProgrammingError", {"exc_msg": str(e)[:250]}, "H1")
                    # #endregion
                    if "does not exist" in str(e):
                        return []
                    raise
                except Exception as e:
                    # #region agent log
                    _dlog("vector_search exception", {"exc_type": type(e).__name__, "exc_msg": str(e)[:250]}, "H3")
                    # #endregion
                    await session.rollback()
                    return []
            # hybrid: vector first, then text if empty
            try:
                out = await self._vector_search(session, query, top_k, version)
                if out:
                    return out
            except (ProgrammingError, Exception):
                await session.rollback()
            return await self._text_search(session, query, top_k, version)

    async def _text_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int,
        version: str | None = None,
    ) -> list[SearchResult]:
        """ILIKE + word-based fallback; no q_any. Returns [] when nothing matches."""
        # #region agent log
        _dlog("_text_search execute", {"query": query[:30]}, "H3")
        # #endregion
        base = (
            select(Chunk.id, Chunk.text, Document.source, Document.version)
            .join(Document, Chunk.document_id == Document.id)
        )
        if version is not None:
            base = base.where(Document.version == version)
        q = base.where(Chunk.text.ilike(f"%{query}%")).limit(top_k * 2)
        result = await session.execute(q)
        rows = result.all()
        out: list[SearchResult] = []
        for i, (chunk_id, text_val, source, doc_version) in enumerate(rows[:top_k]):
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=1.0 - (i * 0.05),
                    confidence=1.0 - (i * 0.05),
                    version=doc_version,
                )
            )
        if not out and query.strip():
            words = [w for w in re.split(r"\W+", query) if len(w) >= 2][:6]
            if words:
                q_words = (
                    base.where(or_(*[Chunk.text.ilike(f"%{w}%") for w in words]))
                    .limit(top_k * 2)
                )
                r_words = await session.execute(q_words)
                seen = set()
                for (chunk_id, text_val, source, doc_version) in r_words.all():
                    if chunk_id not in seen and len(out) < top_k:
                        seen.add(chunk_id)
                        out.append(
                            SearchResult(
                                chunk_id=str(chunk_id),
                                text=text_val or "",
                                source=source or "",
                                score=0.7,
                                confidence=0.7,
                                version=doc_version,
                            )
                        )
        return out

    async def _vector_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int,
        version: str | None = None,
    ) -> list[SearchResult]:
        """Vector similarity search (L2). Requires embedder and chunks.embedding."""
        # #region agent log
        _dlog("_vector_search start", {"retrieval_mode": self._retrieval_mode, "version": version}, "H4")
        # #endregion
        embedder = self._embedder
        if embedder is None:
            embedder = _get_embedder()()
        query_embedding = embedder.embed_texts([query])[0]

        try:
            from pgvector.sqlalchemy import Vector
        except ImportError:
            # #region agent log
            _dlog("_vector_search no pgvector", {"message": "ImportError"}, "H3")
            # #endregion
            return []

        dist_col = Chunk.embedding.op("<->")(bindparam("q_emb", type_=Vector(384)))
        stmt = (
            select(Chunk.id, Chunk.text, Document.source, Document.version, dist_col)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.embedding.isnot(None))
            .order_by(dist_col)
            .limit(top_k)
        )
        if version is not None:
            stmt = stmt.where(Document.version == version)

        # #region agent log
        _dlog("_vector_search executing", {"version_filter": version is not None}, "H1")
        # #endregion
        result = await session.execute(stmt, {"q_emb": query_embedding})
        rows = result.all()
        # #region agent log
        _dlog("_vector_search rows", {"count": len(rows)}, "H2")
        # #endregion
        out: list[SearchResult] = []
        for chunk_id, text_val, source, doc_version, distance in rows:
            confidence = 1.0 / (1.0 + float(distance))
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=confidence,
                    distance=float(distance),
                    confidence=confidence,
                    version=doc_version,
                )
            )
        return out
