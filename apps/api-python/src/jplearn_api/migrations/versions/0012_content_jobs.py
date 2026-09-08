"""Durable content jobs queue for AI workflows (ADR-007 PR8).

Revision ID: 0012_content_jobs
Revises: 0011_ai_quota_and_usage_ledger
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0012_content_jobs"
down_revision = "0011_ai_quota_and_usage_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. content_jobs: durable background job queue with leases and attempt tracking
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "content_jobs" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "task" TEXT NOT NULL,
            "language" TEXT NOT NULL DEFAULT 'ja',
            "status" TEXT NOT NULL DEFAULT 'queued',
            "progress" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            "provenance" JSONB NOT NULL DEFAULT '{}',
            "source_hash" TEXT NOT NULL,
            "config_hash" TEXT NOT NULL,
            "idempotency_key" TEXT NOT NULL,
            "created_by" TEXT NOT NULL,
            "attempt" INTEGER NOT NULL DEFAULT 0,
            "max_attempts" INTEGER NOT NULL DEFAULT 3,
            "attempt_token" TEXT,
            "lease_expires_at" TIMESTAMP(3),
            "result_draft" JSONB,
            "error_message" TEXT,
            "applied_at" TIMESTAMP(3),
            "applied_by" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "content_jobs_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "content_jobs_catalog_item_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_jobs_content_version_fkey" FOREIGN KEY ("content_version_id") REFERENCES "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_jobs_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_jobs_applied_by_fkey" FOREIGN KEY ("applied_by") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE SET NULL,
            CONSTRAINT "content_jobs_user_idem_uniq" UNIQUE ("created_by", "idempotency_key"),
            CONSTRAINT "content_jobs_status_check" CHECK (
                "status" IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
            ),
            CONSTRAINT "content_jobs_task_check" CHECK (
                "task" IN ('transcript', 'segmentation')
            )
        );
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_jobs_status_lease_idx" ON "content_jobs"("status", "lease_expires_at");'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_jobs_item_version_idx" ON "content_jobs"("catalog_item_id", "content_version_id");'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "content_jobs" CASCADE;')
