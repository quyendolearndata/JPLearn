"""Content reports and moderation audit (ADR-007 PR3b).

Revision ID: 0007_content_reports
Revises: 0006_personal_collections
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0007_content_reports"
down_revision = "0006_personal_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "content_reports" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "scene_id" TEXT,
            "position_ms" INTEGER,
            "category" TEXT NOT NULL,
            "description" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'open',
            "revision" INTEGER NOT NULL DEFAULT 1,
            "assignee_id" TEXT,
            "public_reply" TEXT,
            "internal_note" TEXT,
            "resolution_version_id" TEXT,
            "idempotency_key" TEXT,
            "request_hash" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "content_reports_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "content_reports_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE
            ON DELETE CASCADE,
            CONSTRAINT "content_reports_catalog_item_id_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES
            "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_reports_content_version_id_fkey" FOREIGN KEY ("content_version_id") REFERENCES
            "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_reports_scene_id_fkey" FOREIGN KEY ("scene_id") REFERENCES "scenes"("id") ON UPDATE
            CASCADE ON DELETE SET NULL,
            CONSTRAINT "content_reports_assignee_id_fkey" FOREIGN KEY ("assignee_id") REFERENCES "users"("id") ON UPDATE
            CASCADE ON DELETE SET NULL,
            CONSTRAINT "content_reports_resolution_version_id_fkey" FOREIGN KEY ("resolution_version_id") REFERENCES
            "content_versions"("id") ON UPDATE CASCADE ON DELETE SET NULL,
            CONSTRAINT "content_reports_user_idempotency_unique" UNIQUE ("user_id", "idempotency_key")
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_reports_status_updated_idx" ON '
        '"content_reports"("status", "updated_at" DESC, "id" DESC)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_reports_user_created_idx" ON '
        '"content_reports"("user_id", "created_at" DESC, "id" DESC)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_reports_catalog_item_idx" ON '
        '"content_reports"("catalog_item_id", "created_at" DESC)'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "content_report_audit" (
            "id" TEXT NOT NULL,
            "report_id" TEXT NOT NULL,
            "actor_id" TEXT NOT NULL,
            "from_status" TEXT,
            "to_status" TEXT NOT NULL,
            "revision" INTEGER NOT NULL,
            "reason" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "content_report_audit_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "content_report_audit_report_id_fkey" FOREIGN KEY ("report_id") REFERENCES
            "content_reports"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_report_audit_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON UPDATE
            CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "content_report_audit_report_idx" ON '
        '"content_report_audit"("report_id", "created_at" ASC)'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "content_report_audit"')
    op.execute('DROP TABLE IF EXISTS "content_reports"')
