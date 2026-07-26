"""replace standalone workout plans with assigned progress

Revision ID: 20260726_0014
Revises: 20260720_0013
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0014"
down_revision: str | None = "20260720_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("workout_plans", "legacy_workout_plans")
    op.rename_table("workout_plan_assignments", "legacy_workout_plan_assignments")

    op.create_table(
        "workout_plan_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nutrition_plan_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("workout_item_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["nutrition_plan_id"],
            ["nutrition_plans.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "nutrition_plan_id",
            "client_id",
            "workout_item_id",
            name="uq_workout_plan_completion_item",
        ),
    )
    op.create_index(
        "ix_workout_plan_completions_nutrition_plan_id",
        "workout_plan_completions",
        ["nutrition_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_workout_plan_completions_client_id",
        "workout_plan_completions",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        "ix_workout_plan_completions_workout_item_id",
        "workout_plan_completions",
        ["workout_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_plan_completions_workout_item_id",
        table_name="workout_plan_completions",
    )
    op.drop_index(
        "ix_workout_plan_completions_client_id",
        table_name="workout_plan_completions",
    )
    op.drop_index(
        "ix_workout_plan_completions_nutrition_plan_id",
        table_name="workout_plan_completions",
    )
    op.drop_table("workout_plan_completions")

    op.rename_table("legacy_workout_plans", "workout_plans")
    op.rename_table("legacy_workout_plan_assignments", "workout_plan_assignments")
