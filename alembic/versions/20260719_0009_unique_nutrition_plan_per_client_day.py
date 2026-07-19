"""unique nutrition plan per client day

Revision ID: 20260719_0009
Revises: 20260718_0008
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260719_0009"
down_revision: str | None = "20260718_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.create_unique_constraint(
            "uq_nutrition_plans_coach_client_date",
            ["coach_id", "client_id", "date"],
        )


def downgrade() -> None:
    with op.batch_alter_table("nutrition_plans") as batch_op:
        batch_op.drop_constraint("uq_nutrition_plans_coach_client_date", type_="unique")