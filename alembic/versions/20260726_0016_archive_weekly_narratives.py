"""archive obsolete weekly narrative summaries

Revision ID: 20260726_0016
Revises: 20260726_0015
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_0016"
down_revision: str | None = "20260726_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("weekly_summaries", "legacy_weekly_summaries")


def downgrade() -> None:
    op.rename_table("legacy_weekly_summaries", "weekly_summaries")
