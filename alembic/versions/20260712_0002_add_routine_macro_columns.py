"""add routine macro columns

Revision ID: 20260712_0002
Revises: 7f068ff28b03
Create Date: 2026-07-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260712_0002"
down_revision: str | None = "7f068ff28b03"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("routines") as batch_op:
        batch_op.add_column(sa.Column("meals_kcal", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("goal_kcal", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("goal_protein", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("goal_carbs", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("goal_fats", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("goal_fiber", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("intake_protein", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("intake_carbs", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("intake_fats", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("intake_fiber", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("routines") as batch_op:
        batch_op.drop_column("intake_fiber")
        batch_op.drop_column("intake_fats")
        batch_op.drop_column("intake_carbs")
        batch_op.drop_column("intake_protein")
        batch_op.drop_column("goal_fiber")
        batch_op.drop_column("goal_fats")
        batch_op.drop_column("goal_carbs")
        batch_op.drop_column("goal_protein")
        batch_op.drop_column("goal_kcal")
        batch_op.drop_column("meals_kcal")
