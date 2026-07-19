"""add routine macro meal type

Revision ID: 20260719_0010
Revises: 20260719_0009
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260719_0010"
down_revision: str | None = "20260719_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("routine_macro_logs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "meal_type",
                sa.Enum("BREAKFAST", "LUNCH", "DINNER", "SNACK", name="meal_type"),
                nullable=False,
                server_default=sa.text("'SNACK'"),
            )
        )
        batch_op.create_index("ix_routine_macro_logs_meal_type", ["meal_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("routine_macro_logs") as batch_op:
        batch_op.drop_index("ix_routine_macro_logs_meal_type")
        batch_op.drop_column("meal_type")