"""Create retrieval schema, documents, chunks with pgvector.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS retrieval")
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="retrieval",
    )
    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("retrieval.documents.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("index_in_doc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="retrieval",
    )
    op.execute("ALTER TABLE retrieval.chunks ADD COLUMN embedding vector(384)")
    # Create index after loading data (e.g. run after ingest) or use lists=1 for empty table


def downgrade() -> None:
    op.drop_table("chunks", schema="retrieval")
    op.drop_table("documents", schema="retrieval")
    op.execute("DROP SCHEMA IF EXISTS retrieval")
