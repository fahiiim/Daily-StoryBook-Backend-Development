"""add storybook profile fields

Revision ID: 20260713_0005
Revises: 20260713_0004
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0005"
down_revision: str | None = "20260713_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("wake_up_time", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("bed_time", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("height", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("weight", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("target_weight", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("short_bio", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fitness_motivation", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("fitness_motivation")
        batch_op.drop_column("short_bio")
        batch_op.drop_column("target_weight")
        batch_op.drop_column("weight")
        batch_op.drop_column("height")
        batch_op.drop_column("bed_time")
        batch_op.drop_column("wake_up_time")