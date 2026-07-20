"""add complete meal macros

Revision ID: 20260720_0011
Revises: 20260719_0010
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_0011"
down_revision: str | None = "20260719_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("routine_macro_logs") as batch_op:
        batch_op.add_column(sa.Column("protein", sa.Float(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("carbs", sa.Float(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("fat", sa.Float(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("fiber", sa.Float(), nullable=False, server_default=sa.text("0")))

    op.execute(
        """
        UPDATE routine_macro_logs
        SET protein = CASE WHEN macro_type = 'PROTEIN' THEN macro_grams ELSE 0 END,
            carbs = CASE WHEN macro_type = 'CARBS' THEN macro_grams ELSE 0 END,
            fat = CASE WHEN macro_type = 'FATS' THEN macro_grams ELSE 0 END,
            fiber = CASE WHEN macro_type = 'FIBER' THEN macro_grams ELSE 0 END
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("routine_macro_logs") as batch_op:
        batch_op.drop_column("fiber")
        batch_op.drop_column("fat")
        batch_op.drop_column("carbs")
        batch_op.drop_column("protein")