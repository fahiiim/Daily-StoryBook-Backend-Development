"""create routine macro logs table

Revision ID: 20260712_0003
Revises: 20260712_0002
Create Date: 2026-07-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260712_0003"
down_revision: str | None = "20260712_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "routine_macro_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("routine_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "macro_type",
            sa.Enum("PROTEIN", "CARBS", "FATS", "FIBER", name="macro_type"),
            nullable=False,
        ),
        sa.Column("food_name", sa.Text(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("amount_unit", sa.String(length=32), nullable=False),
        sa.Column("macro_grams", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["routine_id"], ["routines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routine_macro_logs_routine_id", "routine_macro_logs", ["routine_id"], unique=False)
    op.create_index("ix_routine_macro_logs_user_id", "routine_macro_logs", ["user_id"], unique=False)
    op.create_index("ix_routine_macro_logs_macro_type", "routine_macro_logs", ["macro_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_routine_macro_logs_macro_type", table_name="routine_macro_logs")
    op.drop_index("ix_routine_macro_logs_user_id", table_name="routine_macro_logs")
    op.drop_index("ix_routine_macro_logs_routine_id", table_name="routine_macro_logs")
    op.drop_table("routine_macro_logs")
