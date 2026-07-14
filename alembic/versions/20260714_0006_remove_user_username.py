"""remove user username

Revision ID: 20260714_0006
Revises: 20260713_0005
Create Date: 2026-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260714_0006"
down_revision: str | None = "20260713_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_username")
        batch_op.drop_column("username")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=50), nullable=True))
        batch_op.create_index("ix_users_username", ["username"], unique=True)
