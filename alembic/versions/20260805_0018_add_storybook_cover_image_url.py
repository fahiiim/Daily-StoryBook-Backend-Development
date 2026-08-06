"""add storybook cover image url

Revision ID: 20260805_0018
Revises: 20260801_0017
Create Date: 2026-08-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260805_0018"
down_revision = "20260801_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("storybooks", sa.Column("cover_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("storybooks", "cover_image_url")
