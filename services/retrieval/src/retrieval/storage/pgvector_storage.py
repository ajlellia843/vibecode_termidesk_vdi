"""PgVector storage: vector search (pgvector), optional text/hybrid fallback."""
import json
import os
import re
import time
from typing import Any

from sqlalchemy import bindparam, func, or_, select
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
        # Diagnostic: total chunks vs chunks with embedding (same DB?)
        try:
            r_tot = await session.execute(select(func.count()).select_from(Chunk))
            r_emb = await session.execute(select(func.count()).select_from(Chunk).where(Chunk.embedding.isnot(None)))
            _dlog("_vector_search DB diagnostic", {"total_chunks": r_tot.scalar() or 0, "chunks_with_embedding": r_emb.scalar() or 0}, "H2")
        except Exception as e:
            _dlog("_vector_search DB diagnostic failed", {"exc_type": type(e).__name__, "exc_msg": str(e)[:200]}, "H2")
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

        # Use l2_distance() so return_type=Float is set; op("<->") without it can yield 0 with asyncpg
        dist_col = Chunk.embedding.l2_distance(bindparam("q_emb", type_=Vector(384)))
        distance_col = dist_col.label("distance")
        stmt = (
            select(Chunk.id, Chunk.text, Document.source, Document.version, distance_col)
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
        for i, row in enumerate(rows):
            chunk_id = row[0]
            text_val = row[1]
            source = row[2]
            doc_version = row[3]
            distance = row[4]
            dist_float = float(distance) if distance is not None else 0.0
            # #region agent log
            if i == 0:
                _dlog("_vector_search first row distance", {"raw_distance": str(distance), "raw_type": type(distance).__name__, "dist_float": dist_float, "score": 1.0 / (1.0 + dist_float)}, "H4")
            # #endregion
            confidence = 1.0 / (1.0 + dist_float)
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=confidence,
                    distance=dist_float,
                    confidence=confidence,
                    version=doc_version,
                )
            )
        return out
