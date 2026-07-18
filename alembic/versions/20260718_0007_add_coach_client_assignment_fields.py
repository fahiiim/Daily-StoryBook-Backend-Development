"""add coach client assignment fields

Revision ID: 20260718_0007
Revises: 20260714_0006
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_0007"
down_revision: str | None = "20260714_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("coach_client") as batch_op:
        batch_op.add_column(sa.Column("personalized_message", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "assign_initial_plan",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("coach_client") as batch_op:
        batch_op.drop_column("assign_initial_plan")
        batch_op.drop_column("personalized_message")