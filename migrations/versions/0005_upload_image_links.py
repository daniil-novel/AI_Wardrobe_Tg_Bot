"""Repair direct Mini App upload image links.

Revision ID: 0005_upload_image_links
Revises: 0004_commercial_integrity
Create Date: 2026-07-29
"""

from alembic import op

revision = "0005_upload_image_links"
down_revision = "0004_commercial_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older direct-upload code read ImageAsset.id before the first flush. Both rows
    # received the same transaction timestamp, so only exact, one-to-one orphan
    # pairs are safe to reconnect automatically.
    op.execute(
        """
        WITH candidate_pairs AS (
            SELECT
                upload.id AS upload_id,
                image.id AS image_id
            FROM uploads AS upload
            JOIN image_assets AS image
              ON image.user_id = upload.user_id
             AND image.source_type = 'upload'
             AND image.created_at = upload.created_at
            WHERE upload.source = 'miniapp'
              AND upload.original_image_id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM uploads AS linked_upload
                  WHERE linked_upload.original_image_id = image.id
              )
        ),
        unambiguous_uploads AS (
            SELECT upload_id
            FROM candidate_pairs
            GROUP BY upload_id
            HAVING COUNT(*) = 1
        ),
        unambiguous_images AS (
            SELECT image_id
            FROM candidate_pairs
            GROUP BY image_id
            HAVING COUNT(*) = 1
        )
        UPDATE uploads AS upload
        SET original_image_id = candidate.image_id
        FROM candidate_pairs AS candidate
        JOIN unambiguous_uploads USING (upload_id)
        JOIN unambiguous_images USING (image_id)
        WHERE upload.id = candidate.upload_id
        """
    )


def downgrade() -> None:
    # The repaired references are valid domain links and must not be removed.
    pass
