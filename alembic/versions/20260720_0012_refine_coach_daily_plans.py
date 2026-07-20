"""refine coach daily plans

Revision ID: 20260720_0012
Revises: 20260720_0011
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0012"
down_revision: str | None = "20260720_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_EMPTY_JSON_ARRAY = sa.text("'[]'")
_EMPTY_JSON_OBJECT = sa.text("'{}'")


def upgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.add_column(sa.Column("fiber", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "workout_plan",
                sa.JSON(),
                nullable=False,
                server_default=_EMPTY_JSON_ARRAY,
            )
        )
        batch_op.add_column(
            sa.Column(
                "daily_goals",
                sa.JSON(),
                nullable=False,
                server_default=_EMPTY_JSON_ARRAY,
            )
        )
        batch_op.add_column(
            sa.Column(
                "legacy_meals",
                sa.JSON(),
                nullable=False,
                server_default=_EMPTY_JSON_OBJECT,
            )
        )

    nutrition_plans = sa.table(
        "nutrition_plans",
        sa.column("id"),
        sa.column("breakfast", sa.Text()),
        sa.column("lunch", sa.Text()),
        sa.column("dinner", sa.Text()),
        sa.column("snacks", sa.Text()),
        sa.column("legacy_meals", sa.JSON()),
    )
    rows = connection.execute(
        sa.select(
            nutrition_plans.c.id,
            nutrition_plans.c.breakfast,
            nutrition_plans.c.lunch,
            nutrition_plans.c.dinner,
            nutrition_plans.c.snacks,
        )
    ).all()
    for plan_id, breakfast, lunch, dinner, snacks in rows:
        legacy_meals = {
            meal_name: meal_value
            for meal_name, meal_value in (
                ("breakfast", breakfast),
                ("lunch", lunch),
                ("dinner", dinner),
                ("snacks", snacks),
            )
            if meal_value is not None
        }
        connection.execute(
            sa.update(nutrition_plans)
            .where(nutrition_plans.c.id == plan_id)
            .values(legacy_meals=legacy_meals)
        )

    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.drop_column("snacks")
        batch_op.drop_column("dinner")
        batch_op.drop_column("lunch")
        batch_op.drop_column("breakfast")

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


def downgrade() -> None:
    with op.batch_alter_table("workout_plans") as batch_op:
        batch_op.add_column(sa.Column("exercises_text", sa.Text(), nullable=True))

    workout_plans = sa.table(
        "workout_plans",
        sa.column("id"),
        sa.column("exercises", sa.JSON()),
        sa.column("exercises_text", sa.Text()),
    )
    connection = op.get_bind()
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

    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.add_column(sa.Column("breakfast", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("lunch", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("dinner", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("snacks", sa.Text(), nullable=True))

    nutrition_plans = sa.table(
        "nutrition_plans",
        sa.column("id"),
        sa.column("breakfast", sa.Text()),
        sa.column("lunch", sa.Text()),
        sa.column("dinner", sa.Text()),
        sa.column("snacks", sa.Text()),
        sa.column("legacy_meals", sa.JSON()),
    )
    rows = connection.execute(
        sa.select(nutrition_plans.c.id, nutrition_plans.c.legacy_meals)
    ).all()
    for plan_id, legacy_meals in rows:
        archived = legacy_meals if isinstance(legacy_meals, dict) else {}
        connection.execute(
            sa.update(nutrition_plans)
            .where(nutrition_plans.c.id == plan_id)
            .values(
                breakfast=archived.get("breakfast"),
                lunch=archived.get("lunch"),
                dinner=archived.get("dinner"),
                snacks=archived.get("snacks"),
            )
        )

    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.drop_column("legacy_meals")
        batch_op.drop_column("daily_goals")
        batch_op.drop_column("workout_plan")
        batch_op.drop_column("fiber")
