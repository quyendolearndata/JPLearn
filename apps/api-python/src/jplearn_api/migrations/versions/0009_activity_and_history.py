"""Activity, preferences, and history deletions worker (ADR-007 PR5).

Revision ID: 0009_activity_and_history
Revises: 0008_playback_tracking
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0009_activity_and_history"
down_revision = "0008_playback_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add preferred_topic_ids to learning_preferences
    op.execute(
        """
        ALTER TABLE "learning_preferences"
        ADD COLUMN IF NOT EXISTS "preferred_topic_ids" JSONB NOT NULL DEFAULT '[]'::jsonb;
        """
    )

    # 2. history_deletions: durable deletion job queue & audit
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "history_deletions" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'queued',
            "cutoff_time" TIMESTAMP(3) NOT NULL,
            "records_deleted" INTEGER NOT NULL DEFAULT 0,
            "attempts" INTEGER NOT NULL DEFAULT 0,
            "error_message" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "completed_at" TIMESTAMP(3),
            CONSTRAINT "history_deletions_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "history_deletions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE
            CASCADE ON DELETE CASCADE
        );
        """
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "history_deletions_user_created_idx" ON '
        '"history_deletions"("user_id", "created_at" DESC);'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "history_deletions_status_idx" ON "history_deletions"("status", "created_at");'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "history_deletions" CASCADE;')
    op.execute('ALTER TABLE "learning_preferences" DROP COLUMN IF EXISTS "preferred_topic_ids";')
