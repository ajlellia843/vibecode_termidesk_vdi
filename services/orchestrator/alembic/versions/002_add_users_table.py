"""Add orchestrator.users table.

Revision ID: 002
Revises: 001
Create Date: 2025-02-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.String(255), nullable=False),
        sa.Column("termidesk_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="orchestrator",
    )
    op.create_index(
        "ix_orchestrator_users_telegram_id",
        "users",
        ["telegram_id"],
        unique=True,
        schema="orchestrator",
    )


def downgrade() -> None:
    op.drop_index("ix_orchestrator_users_telegram_id", table_name="users", schema="orchestrator")
    op.drop_table("users", schema="orchestrator")