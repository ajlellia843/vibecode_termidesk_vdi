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


def _query_word_overlap(query: str, text: str) -> int:
    """Number of query words (len>=2) that appear in text. For tie-break when distances are equal."""
    q_words = {w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2}
    if not q_words:
        return 0
    text_words = {w for w in re.findall(r"\w+", (text or "").lower()) if len(w) >= 2}
    return len(q_words & text_words)


def _keyword_score(query: str, text: str) -> float:
    """BM25-like simplified: fraction of query words found in text, in [0, 1]."""
    q_words = [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2]
    if not q_words:
        return 0.0
    text_lower = (text or "").lower()
    hits = sum(1 for w in q_words if w in text_lower)
    return min(1.0, hits / len(q_words))


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
        min_score: float = 0.35,
        kb_latest_version: str = "6.1 (latest)",
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._retrieval_mode = (retrieval_mode or "vector").lower()
        self._min_score = min_score
        self._kb_latest_version = kb_latest_version

    async def search(
        self, query: str, top_k: int = 5, version: str | None = None
    ) -> list[SearchResult]:
        effective_version = version if version is not None else self._kb_latest_version
        # #region agent log
        _dlog("search entry", {"query": query[:50], "top_k": top_k, "version": effective_version}, "H1")
        # #endregion
        async with self._session_factory() as session:
            if self._retrieval_mode == "text":
                return await self._text_search(session, query, top_k, effective_version)
            if self._retrieval_mode in ("vector", "hybrid"):
                try:
                    out = await self._vector_search(
                        session, query, top_k, effective_version
                    )
                    top_score = max((r.score for r in out), default=0.0)
                    try:
                        import structlog
                        structlog.get_logger().info(
                            "retrieval_search",
                            query=query[:100],
                            top_score=round(top_score, 4),
                            retrieved_count=len(out),
                        )
                    except Exception:
                        _dlog("search result", {"top_score": top_score, "retrieved_count": len(out)}, "H1")
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
            return []

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
            select(
                Chunk.id,
                Chunk.text,
                Document.source,
                Document.version,
                Chunk.section_title,
                Chunk.document_title,
                Chunk.position,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.version == version)
        )
        q = base.where(Chunk.text.ilike(f"%{query}%")).limit(top_k * 2)
        result = await session.execute(q)
        rows = result.all()
        out: list[SearchResult] = []
        for i, row in enumerate(rows[:top_k]):
            chunk_id, text_val, source, doc_version = row[0], row[1], row[2], row[3]
            section_title = row[4] if len(row) > 4 else None
            document_title = row[5] if len(row) > 5 else None
            position = int(row[6]) if len(row) > 6 else 0
            doc_title = (document_title or source or "").strip() or None
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=1.0 - (i * 0.05),
                    confidence=1.0 - (i * 0.05),
                    version=doc_version,
                    document_title=doc_title,
                    section_title=(section_title or "").strip() if section_title else None,
                    position=position,
                )
            )
        if not out and query.strip():
            words = [w for w in re.split(r"\W+", query) if len(w) >= 2][:6]
            if words:
                q_words = base.where(
                    or_(*[Chunk.text.ilike(f"%{w}%") for w in words])
                ).limit(top_k * 2)
                r_words = await session.execute(q_words)
                seen = set()
                for row in r_words.all():
                    chunk_id, text_val, source, doc_version = row[0], row[1], row[2], row[3]
                    section_title = row[4] if len(row) > 4 else None
                    document_title = row[5] if len(row) > 5 else None
                    position = int(row[6]) if len(row) > 6 else 0
                    doc_title = (document_title or source or "").strip() or None
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
                                document_title=doc_title,
                                section_title=(section_title or "").strip() if section_title else None,
                                position=position,
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

        # Use l2_distance() so return_type=Float is set
        dist_col = Chunk.embedding.l2_distance(bindparam("q_emb", type_=Vector(384)))
        distance_col = dist_col.label("distance")
        stmt = (
            select(
                Chunk.id,
                Chunk.text,
                Document.source,
                Document.version,
                Chunk.section_title,
                Chunk.document_title,
                Chunk.position,
                distance_col,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.embedding.isnot(None))
            .order_by(dist_col)
            .limit(top_k * 2)
        )
        stmt = stmt.where(Document.version == version)
        # #region agent log
        _dlog("_vector_search executing", {"version_filter": True}, "H1")
        # #endregion
        result = await session.execute(stmt, {"q_emb": query_embedding})
        rows = result.all()
        # #region agent log
        _dlog("_vector_search rows", {"count": len(rows)}, "H2")
        # #endregion
        out: list[SearchResult] = []
        for row in rows:
            chunk_id = row[0]
            text_val = row[1]
            source = row[2]
            doc_version = row[3]
            section_title = row[4] if len(row) > 4 else None
            document_title = row[5] if len(row) > 5 else None
            position = int(row[6]) if len(row) > 6 else 0
            distance = row[-1]
            dist_float = float(distance) if distance is not None else 0.0
            vector_confidence = 1.0 / (1.0 + dist_float)
            kw_score = _keyword_score(query, text_val or "")
            final_score = 0.8 * vector_confidence + 0.2 * kw_score
            if final_score < self._min_score:
                continue
            doc_title = (document_title or source or "").strip() or None
            out.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    text=text_val or "",
                    source=source or "",
                    score=final_score,
                    distance=dist_float,
                    confidence=vector_confidence,
                    version=doc_version,
                    document_title=doc_title,
                    section_title=(section_title or "").strip() if section_title else None,
                    position=position,
                )
            )
        out.sort(
            key=lambda sr: (
                -sr.score,
                sr.distance or 0.0,
                -_query_word_overlap(query, sr.text),
            )
        )
        return out[:top_k]
