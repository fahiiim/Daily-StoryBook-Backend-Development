"""add story page title

Revision ID: 20260801_0017
Revises: 20260726_0016
Create Date: 2026-08-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260801_0017"
down_revision = "20260726_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("story_pages", sa.Column("title", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("story_pages", "title")
