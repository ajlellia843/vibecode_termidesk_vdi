"""SQLAlchemy models for retrieval schema (documents, chunks with pgvector)."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
    HAS_VECTOR = True
except ImportError:
    HAS_VECTOR = False


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "retrieval"}

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="document")


def _vector_type(dim: int = 384):
    if HAS_VECTOR:
        return Vector(dim)
    return None


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = {"schema": "retrieval"}

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retrieval.documents.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    index_in_doc: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(
        _vector_type(384), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
