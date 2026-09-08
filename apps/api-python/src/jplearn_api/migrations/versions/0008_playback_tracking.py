"""Playback tracking, heartbeat accounting, and resume (ADR-007 PR4).

Revision ID: 0008_playback_tracking
Revises: 0007_content_reports
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0008_playback_tracking"
down_revision = "0007_content_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. learner_playback_state: single active lease per learner
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "learner_playback_state" (
            "user_id" TEXT NOT NULL,
            "active_playback_id" TEXT,
            "current_epoch" INTEGER NOT NULL DEFAULT 1,
            "lease_expires_at" TIMESTAMP(3) NOT NULL,
            "device_class" TEXT NOT NULL,
            "client_instance_id" TEXT NOT NULL,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "learner_playback_state_pkey" PRIMARY KEY ("user_id"),
            CONSTRAINT "learner_playback_state_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    # 2. playbacks: immutable tracking session records
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "playbacks" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "epoch" INTEGER NOT NULL DEFAULT 1,
            "device_class" TEXT NOT NULL,
            "client_instance_id" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'active',
            "last_seq" INTEGER NOT NULL DEFAULT 0,
            "total_active_ms" INTEGER NOT NULL DEFAULT 0,
            "last_position_ms" INTEGER NOT NULL DEFAULT 0,
            "last_server_time" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "last_client_cumulative_ms" INTEGER NOT NULL DEFAULT 0,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "closed_at" TIMESTAMP(3),
            CONSTRAINT "playbacks_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "playbacks_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "playbacks_catalog_item_id_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "playbacks_content_version_id_fkey" FOREIGN KEY ("content_version_id") REFERENCES "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "playbacks_user_created_idx" ON "playbacks"("user_id", "created_at" DESC, "id" DESC)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "playbacks_catalog_item_idx" ON "playbacks"("catalog_item_id", "created_at" DESC)'
    )

    # 3. playback_receipts: idempotent ACK storage per checkpoint seq
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "playback_receipts" (
            "playback_id" TEXT NOT NULL,
            "seq" INTEGER NOT NULL,
            "request_hash" TEXT NOT NULL,
            "accepted_delta_ms" INTEGER NOT NULL DEFAULT 0,
            "cumulative_active_ms" INTEGER NOT NULL DEFAULT 0,
            "response_payload" JSONB NOT NULL,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "playback_receipts_pkey" PRIMARY KEY ("playback_id", "seq"),
            CONSTRAINT "playback_receipts_playback_id_fkey" FOREIGN KEY ("playback_id") REFERENCES "playbacks"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    # 4. playback_checkpoints: cross-device resume points
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "playback_checkpoints" (
            "user_id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "position_ms" INTEGER NOT NULL DEFAULT 0,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "playback_checkpoints_pkey" PRIMARY KEY ("user_id", "catalog_item_id"),
            CONSTRAINT "playback_checkpoints_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "playback_checkpoints_catalog_item_id_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "playback_checkpoints_content_version_id_fkey" FOREIGN KEY ("content_version_id") REFERENCES "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "playback_checkpoints_user_updated_idx" ON "playback_checkpoints"("user_id", "updated_at" DESC)'
    )

    # 5. learning_preferences: timezone and daily goal policy
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "learning_preferences" (
            "user_id" TEXT NOT NULL,
            "daily_goal_minutes" INTEGER NOT NULL DEFAULT 15,
            "timezone" TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            "revision" INTEGER NOT NULL DEFAULT 1,
            "effective_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "learning_preferences_pkey" PRIMARY KEY ("user_id"),
            CONSTRAINT "learning_preferences_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    # 6. learner_daily_activity: aggregated active watch time per calendar day in user timezone
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "learner_daily_activity" (
            "user_id" TEXT NOT NULL,
            "date" TEXT NOT NULL,
            "timezone" TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            "active_ms" INTEGER NOT NULL DEFAULT 0,
            "goal_minutes" INTEGER NOT NULL DEFAULT 15,
            "goal_met" BOOLEAN NOT NULL DEFAULT FALSE,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "learner_daily_activity_pkey" PRIMARY KEY ("user_id", "date"),
            CONSTRAINT "learner_daily_activity_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "learner_daily_activity_user_date_idx" ON "learner_daily_activity"("user_id", "date" DESC)'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "learner_daily_activity"')
    op.execute('DROP TABLE IF EXISTS "learning_preferences"')
    op.execute('DROP TABLE IF EXISTS "playback_checkpoints"')
    op.execute('DROP TABLE IF EXISTS "playback_receipts"')
    op.execute('DROP TABLE IF EXISTS "playbacks"')
    op.execute('DROP TABLE IF EXISTS "learner_playback_state"')
