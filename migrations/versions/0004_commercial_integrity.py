"""Add commercial quota and data-integrity constraints.

Revision ID: 0004_commercial_integrity
Revises: 0003_avatar_billing
Create Date: 2026-07-28
"""

from alembic import op

revision = "0004_commercial_integrity"
down_revision = "0003_avatar_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration currently builds from live metadata. IF NOT EXISTS keeps
    # this migration safe both for fresh databases and for databases created by an
    # older metadata snapshot.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_user_role
        ON roles (user_id, role)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_active_user
        ON subscriptions (user_id)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_promo_redemptions_user_expiry
        ON promo_redemptions (user_id, expires_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_usage_limits_user_period_reset
        ON usage_limits (user_id, period, resets_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_provider_event
        ON payments (provider, provider_payment_id)
        WHERE provider_payment_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_try_on_items_job_order
        ON try_on_items (try_on_job_id, sort_order)
        """
    )
    op.execute(
        """
        WITH ranked_analysis_requests AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY task_id, request_type
                    ORDER BY created_at ASC, id ASC
                ) AS duplicate_rank
            FROM ai_requests
            WHERE task_id IS NOT NULL
              AND request_type = 'analyze_image'
        )
        UPDATE ai_requests
        SET task_id = NULL
        WHERE id IN (
            SELECT id
            FROM ranked_analysis_requests
            WHERE duplicate_rank > 1
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_requests_analysis_task
        ON ai_requests (task_id, request_type)
        WHERE task_id IS NOT NULL AND request_type = 'analyze_image'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_try_on_jobs_user_created
        ON try_on_jobs (user_id, created_at)
        """
    )
    constraints = (
        (
            "promo_codes",
            "ck_promo_codes_duration_positive",
            "duration_hours > 0",
        ),
        (
            "promo_codes",
            "ck_promo_codes_limit_positive",
            "max_redemptions > 0",
        ),
        (
            "promo_codes",
            "ck_promo_codes_redemption_count",
            "redemption_count >= 0 AND redemption_count <= max_redemptions",
        ),
        (
            "promo_redemptions",
            "ck_promo_redemptions_expiry",
            "expires_at > redeemed_at",
        ),
        (
            "usage_limits",
            "ck_usage_limits_item_count",
            "item_count >= 0",
        ),
        (
            "usage_limits",
            "ck_usage_limits_ai_count",
            "ai_analysis_count >= 0",
        ),
        (
            "avatar_measurements",
            "ck_avatar_measurements_value_positive",
            "value > 0",
        ),
    )
    for table, name, expression in constraints:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = '{name}'
                ) THEN
                    ALTER TABLE {table}
                    ADD CONSTRAINT {name} CHECK ({expression});
                END IF;
            END
            $$;
            """  # noqa: S608 - all fragments come from the fixed tuple above
        )


def downgrade() -> None:
    for table, name in (
        ("avatar_measurements", "ck_avatar_measurements_value_positive"),
        ("usage_limits", "ck_usage_limits_ai_count"),
        ("usage_limits", "ck_usage_limits_item_count"),
        ("promo_redemptions", "ck_promo_redemptions_expiry"),
        ("promo_codes", "ck_promo_codes_redemption_count"),
        ("promo_codes", "ck_promo_codes_limit_positive"),
        ("promo_codes", "ck_promo_codes_duration_positive"),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    for name in (
        "ix_try_on_jobs_user_created",
        "uq_ai_requests_analysis_task",
        "uq_try_on_items_job_order",
        "uq_payments_provider_event",
        "uq_usage_limits_user_period_reset",
        "ix_promo_redemptions_user_expiry",
        "uq_subscriptions_active_user",
        "uq_roles_user_role",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")
