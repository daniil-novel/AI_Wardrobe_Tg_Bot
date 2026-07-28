"""Add consent-safe avatar, virtual try-on, and promo entitlement tables.

Revision ID: 0003_avatar_billing
Revises: 0002_image_selection
Create Date: 2026-07-28
"""

from aiwardrobe_core.models import (
    AvatarMeasurement,
    AvatarProfile,
    PromoCode,
    PromoRedemption,
    TryOnItem,
    TryOnJob,
)
from alembic import op

revision = "0003_avatar_billing"
down_revision = "0002_image_selection"
branch_labels = None
depends_on = None

TABLES = (
    PromoCode.__table__,
    PromoRedemption.__table__,
    AvatarProfile.__table__,
    AvatarMeasurement.__table__,
    TryOnJob.__table__,
    TryOnItem.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
