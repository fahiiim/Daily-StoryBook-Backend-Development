"""add coach client request status

Revision ID: 20260718_0008
Revises: 20260718_0007
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_0008"
down_revision: str | None = "20260718_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("coach_client") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("PENDING", "ACCEPTED", "DECLINED", name="coach_client_status"),
                nullable=False,
                server_default=sa.text("'ACCEPTED'"),
            )
        )
        batch_op.create_index("ix_coach_client_status", ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("coach_client") as batch_op:
        batch_op.drop_index("ix_coach_client_status")
        batch_op.drop_column("status")