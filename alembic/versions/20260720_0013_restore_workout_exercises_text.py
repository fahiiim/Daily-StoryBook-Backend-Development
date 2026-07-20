"""restore standalone workout exercises text

Revision ID: 20260720_0013
Revises: 20260720_0012
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0013"
down_revision: str | None = "20260720_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_EMPTY_JSON_ARRAY = sa.text("'[]'")


def upgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("workout_plans") as batch_op:
        batch_op.add_column(sa.Column("exercises_text", sa.Text(), nullable=True))

    workout_plans = sa.table(
        "workout_plans",
        sa.column("id"),
        sa.column("exercises", sa.JSON()),
        sa.column("exercises_text", sa.Text()),
    )
    rows = connection.execute(
        sa.select(workout_plans.c.id, workout_plans.c.exercises)
    ).all()
    for plan_id, exercises in rows:
        if isinstance(exercises, list):
            exercises_text = "\n".join(str(item) for item in exercises)
        elif exercises is None:
            exercises_text = None
        else:
            exercises_text = str(exercises)
        connection.execute(
            sa.update(workout_plans)
            .where(workout_plans.c.id == plan_id)
            .values(exercises_text=exercises_text)
        )

    with op.batch_alter_table("workout_plans") as batch_op:
        batch_op.drop_column("exercises")
        batch_op.alter_column(
            "exercises_text",
            new_column_name="exercises",
            existing_type=sa.Text(),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("workout_plans") as batch_op:
        batch_op.add_column(sa.Column("exercises_json", sa.JSON(), nullable=True))

    workout_plans = sa.table(
        "workout_plans",
        sa.column("id"),
        sa.column("exercises", sa.Text()),
        sa.column("exercises_json", sa.JSON()),
    )
    rows = connection.execute(
        sa.select(workout_plans.c.id, workout_plans.c.exercises)
    ).all()
    for plan_id, exercises in rows:
        exercise_items = [exercises] if exercises is not None and exercises.strip() else []
        connection.execute(
            sa.update(workout_plans)
            .where(workout_plans.c.id == plan_id)
            .values(exercises_json=exercise_items)
        )

    with op.batch_alter_table("workout_plans") as batch_op:
        batch_op.drop_column("exercises")
        batch_op.alter_column(
            "exercises_json",
            new_column_name="exercises",
            existing_type=sa.JSON(),
            nullable=False,
            server_default=_EMPTY_JSON_ARRAY,
        )
