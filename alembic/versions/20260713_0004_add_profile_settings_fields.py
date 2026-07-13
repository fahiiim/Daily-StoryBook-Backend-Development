"""add profile settings fields

Revision ID: 20260713_0004
Revises: 20260712_0003
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0004"
down_revision: str | None = "20260712_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("max_client_capacity", sa.Integer(), nullable=False, server_default=sa.text("20"))
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("max_client_capacity")
        batch_op.drop_column("phone_number")