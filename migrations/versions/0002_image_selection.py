"""Persist user-confirmed garment recognition regions.

Revision ID: 0002_image_selection
Revises: 0001_initial_schema
Create Date: 2026-07-28
"""

from aiwardrobe_core.models import ImageSelection
from alembic import op

revision = "0002_image_selection"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ImageSelection.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ImageSelection.__table__.drop(bind=op.get_bind(), checkfirst=True)
