"""Ingest pipeline: load files -> normalize -> chunk -> embed -> write to DB."""
import re
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ingest.chunking import ParagraphChunker
from ingest.db.models import Chunk, Document
from ingest.loaders import PDFLoader, TextLoader
from shared.embedder import Embedder

MIN_CHUNK_LENGTH = 150


def normalize_content(content: str) -> str:
    """Normalize newlines, collapse repeated spaces; preserve structure for markdown."""
    if not content:
        return ""
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_section_title(chunk_text: str) -> str | None:
    """Extract last markdown header (## or #) from chunk as section title."""
    match = list(re.finditer(r"^#+\s*(.+)$", chunk_text, re.MULTILINE))
    if not match:
        return None
    return match[-1].group(1).strip()


def merge_short_chunks(chunks: list[str]) -> list[str]:
    """Merge chunks shorter than MIN_CHUNK_LENGTH with previous or next."""
    if not chunks:
        return []
    result: list[str] = []
    for c in chunks:
        if not c.strip():
            continue
        if result and len(result[-1]) < MIN_CHUNK_LENGTH:
            result[-1] = result[-1] + "\n\n" + c.strip()
        elif len(c.strip()) < MIN_CHUNK_LENGTH and result:
            result[-1] = result[-1] + "\n\n" + c.strip()
        else:
            result.append(c.strip())
    return result


def collect_files(knowledge_path: str) -> list[Path]:
    path = Path(knowledge_path)
    if not path.exists():
        return []
    exts = {".md", ".txt", ".pdf"}
    files = []
    for f in path.rglob("*"):
        if f.is_file() and f.suffix.lower() in exts:
            files.append(f)
    return files


def load_content(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return PDFLoader().load(path)
    return TextLoader().load(path)


async def run_ingest(
    database_url: str,
    knowledge_path: str,
    chunk_size: int = 900,
    chunk_overlap: int = 180,
    kb_default_version: str = "6.1 (latest)",
    embedder: Embedder | None = None,
    embedder_backend: str = "sentence_transformers",
    embedder_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    embedding_dim: int = 384,
) -> int:
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    chunker = ParagraphChunker(chunk_size=chunk_size, overlap=chunk_overlap)
    if embedder is None:
        embedder = Embedder(
            backend=embedder_backend,
            model_name=embedder_model_name,
            dim=embedding_dim,
        )

    try:
        import structlog
        log = structlog.get_logger()
        log.info(
            "embedder_config",
            backend=embedder._backend,
            model=embedder._model_name,
            dim=embedder._dim,
        )
        if embedder._backend == "mock":
            log.warning(
                "embedder_mock_mode",
                msg="Mock embedder active: embeddings are not semantic. "
                "Set INGEST_EMBEDDER_BACKEND=sentence_transformers for production.",
            )
    except Exception:
        print(
            f"[ingest] Embedder: backend={embedder._backend}, model={embedder._model_name}, dim={embedder._dim}",
            file=sys.stderr,
        )

    files = collect_files(knowledge_path)
    total_chunks = 0
    used_mock_embedder = getattr(embedder, "_backend", None) == "mock"

    async with session_factory() as session:
        for path in files:
            try:
                content = load_content(path)
            except Exception:
                continue
            if not content.strip():
                continue
            content = normalize_content(content)
            if not content:
                continue
            source = path.name
            doc_path = str(path)
            doc = Document(
                id=uuid4(),
                source=source,
                path=doc_path,
                meta={"ingest_path": doc_path},
                version=kb_default_version,
            )
            session.add(doc)
            await session.flush()

            chunks_text = chunker.chunk(content)
            chunks_text = merge_short_chunks(chunks_text)
            embeddings = embedder.embed_texts(chunks_text) if chunks_text else []
            chunk_embeddings: list[tuple[uuid4, list[float] | None]] = []
            for i, chunk_text in enumerate(chunks_text):
                emb = embeddings[i] if i < len(embeddings) else None
                section_title = extract_section_title(chunk_text)
                document_title = source
                position = i
                token_count = max(0, len(chunk_text) // 4)
                chunk = Chunk(
                    id=uuid4(),
                    document_id=doc.id,
                    text=chunk_text,
                    index_in_doc=i,
                    section_title=section_title,
                    document_title=document_title,
                    position=position,
                    token_count=token_count,
                    embedding=None,
                )
                session.add(chunk)
                chunk_embeddings.append((chunk.id, emb))
                total_chunks += 1
            await session.flush()
            num_emb = 0
            for cid, emb in chunk_embeddings:
                if emb is not None:
                    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                    result = await session.execute(
                        text(
                            "UPDATE retrieval.chunks SET embedding = CAST(:emb AS vector) WHERE id = CAST(:id AS uuid)"
                        ),
                        {"emb": emb_str, "id": str(cid)},
                    )
                    num_emb += result.rowcount
            if num_emb > 0:
                print(f"[ingest] Updated {num_emb} chunk embeddings via SQL", file=sys.stderr)
            await session.commit()
    await engine.dispose()

    if used_mock_embedder:
        try:
            import structlog
            structlog.get_logger().warning(
                "ingest_embedder_mock",
                message="EMBEDDER_BACKEND=mock: embeddings are not semantic; retrieval quality will be limited.",
            )
        except Exception:
            print(
                "[ingest] WARNING: EMBEDDER_BACKEND=mock — embeddings are not semantic; retrieval quality will be limited.",
                file=sys.stderr,
            )
    return total_chunks
