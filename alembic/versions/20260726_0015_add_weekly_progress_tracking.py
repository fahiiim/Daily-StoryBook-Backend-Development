"""add weekly progress tracking

Revision ID: 20260726_0015
Revises: 20260726_0014
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0015"
down_revision: str | None = "20260726_0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_goal_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nutrition_plan_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("goal_item_id", sa.UUID(), nullable=False),
        sa.Column("goal_date", sa.Date(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["nutrition_plan_id"], ["nutrition_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "nutrition_plan_id",
            "client_id",
            "goal_item_id",
            "goal_date",
            name="uq_daily_goal_completion_item_date",
        ),
    )
    op.create_index("ix_daily_goal_completions_nutrition_plan_id", "daily_goal_completions", ["nutrition_plan_id"], unique=False)
    op.create_index("ix_daily_goal_completions_client_id", "daily_goal_completions", ["client_id"], unique=False)
    op.create_index("ix_daily_goal_completions_goal_item_id", "daily_goal_completions", ["goal_item_id"], unique=False)
    op.create_index("ix_daily_goal_completions_goal_date", "daily_goal_completions", ["goal_date"], unique=False)

    op.create_table(
        "workout_plan_completion_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nutrition_plan_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("workout_item_id", sa.UUID(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["nutrition_plan_id"], ["nutrition_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workout_plan_completion_events_nutrition_plan_id", "workout_plan_completion_events", ["nutrition_plan_id"], unique=False)
    op.create_index("ix_workout_plan_completion_events_client_id", "workout_plan_completion_events", ["client_id"], unique=False)
    op.create_index("ix_workout_plan_completion_events_workout_item_id", "workout_plan_completion_events", ["workout_item_id"], unique=False)
    op.create_index("ix_workout_plan_completion_events_effective_date", "workout_plan_completion_events", ["effective_date"], unique=False)

    connection = op.get_bind()
    completions = sa.table(
        "workout_plan_completions",
        sa.column("nutrition_plan_id", sa.UUID()),
        sa.column("client_id", sa.UUID()),
        sa.column("workout_item_id", sa.UUID()),
        sa.column("is_completed", sa.Boolean()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
    )
    events = sa.table(
        "workout_plan_completion_events",
        sa.column("id", sa.UUID()),
        sa.column("nutrition_plan_id", sa.UUID()),
        sa.column("client_id", sa.UUID()),
        sa.column("workout_item_id", sa.UUID()),
        sa.column("completed", sa.Boolean()),
        sa.column("effective_date", sa.Date()),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
    )
    rows = connection.execute(
        sa.select(
            completions.c.nutrition_plan_id,
            completions.c.client_id,
            completions.c.workout_item_id,
            completions.c.completed_at,
        ).where(
            completions.c.is_completed.is_(True),
            completions.c.completed_at.is_not(None),
        )
    ).all()
    for nutrition_plan_id, client_id, workout_item_id, completed_at in rows:
        occurred_at = completed_at
        if isinstance(completed_at, str):
            occurred_at = datetime.fromisoformat(completed_at)
        effective_date = occurred_at.date() if isinstance(occurred_at, datetime) else date.today()
        connection.execute(
            sa.insert(events).values(
                id=uuid4(),
                nutrition_plan_id=nutrition_plan_id,
                client_id=client_id,
                workout_item_id=workout_item_id,
                completed=True,
                effective_date=effective_date,
                occurred_at=occurred_at,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_workout_plan_completion_events_effective_date", table_name="workout_plan_completion_events")
    op.drop_index("ix_workout_plan_completion_events_workout_item_id", table_name="workout_plan_completion_events")
    op.drop_index("ix_workout_plan_completion_events_client_id", table_name="workout_plan_completion_events")
    op.drop_index("ix_workout_plan_completion_events_nutrition_plan_id", table_name="workout_plan_completion_events")
    op.drop_table("workout_plan_completion_events")

    op.drop_index("ix_daily_goal_completions_goal_date", table_name="daily_goal_completions")
    op.drop_index("ix_daily_goal_completions_goal_item_id", table_name="daily_goal_completions")
    op.drop_index("ix_daily_goal_completions_client_id", table_name="daily_goal_completions")
    op.drop_index("ix_daily_goal_completions_nutrition_plan_id", table_name="daily_goal_completions")
    op.drop_table("daily_goal_completions")
