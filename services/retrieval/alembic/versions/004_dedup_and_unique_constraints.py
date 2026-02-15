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
    # --- Dedup documents: keep min(id) per (source, version), delete rest ---
    op.execute("""
        DELETE FROM retrieval.documents d
        WHERE d.id NOT IN (
            SELECT min(id) FROM retrieval.documents GROUP BY source, version
        )
    """)
    op.create_unique_constraint(
        "uq_documents_source_version",
        "documents",
        ["source", "version"],
        schema="retrieval",
    )

    # --- Dedup chunks: keep min(id) per (document_id, position), delete rest ---
    op.execute("""
        DELETE FROM retrieval.chunks c
        WHERE c.id NOT IN (
            SELECT min(id) FROM retrieval.chunks GROUP BY document_id, position
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
