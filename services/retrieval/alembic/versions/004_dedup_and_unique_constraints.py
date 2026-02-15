"""Dedup existing rows and add UNIQUE constraints for idempotent ingest.

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 00:00:03

"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Dedup documents: keep one row per (source, version), delete rest (PostgreSQL has no min(uuid)) ---
    op.execute("""
        DELETE FROM retrieval.documents d
        WHERE d.id NOT IN (
            SELECT id FROM (
                SELECT DISTINCT ON (source, version) id
                FROM retrieval.documents
                ORDER BY source, version, id
            ) keep
        )
    """)
    op.create_unique_constraint(
        "uq_documents_source_version",
        "documents",
        ["source", "version"],
        schema="retrieval",
    )

    # --- Dedup chunks: keep one row per (document_id, position), delete rest ---
    op.execute("""
        DELETE FROM retrieval.chunks c
        WHERE c.id NOT IN (
            SELECT id FROM (
                SELECT DISTINCT ON (document_id, position) id
                FROM retrieval.chunks
                ORDER BY document_id, position, id
            ) keep
        )
    """)
    op.create_unique_constraint(
        "uq_chunks_document_position",
        "chunks",
        ["document_id", "position"],
        schema="retrieval",
    )


def downgrade() -> None:
    op.drop_constraint("uq_chunks_document_position", "chunks", schema="retrieval")
    op.drop_constraint("uq_documents_source_version", "documents", schema="retrieval")
