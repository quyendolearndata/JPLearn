"""Transcript revisions, approved scene texts, and language analysis jobs (ADR-007 PR8a).

Revision ID: 0010_transcripts_analysis
Revises: 0009_activity_and_history
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0010_transcripts_analysis"
down_revision = "0009_activity_and_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. transcript_revisions: staff draft, QA review and provenance
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "transcript_revisions" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "revision" INTEGER NOT NULL DEFAULT 1,
            "status" TEXT NOT NULL DEFAULT 'draft',
            "segments" JSONB NOT NULL DEFAULT '[]'::jsonb,
            "provenance" TEXT NOT NULL DEFAULT 'manual_teacher',
            "created_by" TEXT NOT NULL,
            "approved_by" TEXT,
            "return_reason" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "transcript_revisions_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "transcript_revisions_item_version_rev_key" UNIQUE ("catalog_item_id", "content_version_id",
            "revision"),
            CONSTRAINT "transcript_revisions_catalog_item_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES
            "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "transcript_revisions_content_version_fkey" FOREIGN KEY ("content_version_id") REFERENCES
            "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "transcript_revisions_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON
            UPDATE CASCADE ON DELETE RESTRICT,
            CONSTRAINT "transcript_revisions_approved_by_fkey" FOREIGN KEY ("approved_by") REFERENCES "users"("id") ON
            UPDATE CASCADE ON DELETE SET NULL
        );
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "transcript_revisions_item_status_idx" ON '
        '"transcript_revisions"("catalog_item_id", "status");'
    )

    # 2. approved_scene_texts: search projection & approved Japanese snippets
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "approved_scene_texts" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "scene_id" TEXT NOT NULL,
            "transcript_revision_id" TEXT NOT NULL,
            "text_ja" TEXT NOT NULL,
            "scene_index" INTEGER NOT NULL,
            "start_time_seconds" INTEGER NOT NULL,
            "end_time_seconds" INTEGER NOT NULL,
            "is_active" BOOLEAN NOT NULL DEFAULT true,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "approved_scene_texts_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "approved_scene_texts_version_scene_rev_key" UNIQUE ("content_version_id", "scene_id",
            "transcript_revision_id"),
            CONSTRAINT "approved_scene_texts_catalog_item_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES
            "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "approved_scene_texts_content_version_fkey" FOREIGN KEY ("content_version_id") REFERENCES
            "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "approved_scene_texts_scene_fkey" FOREIGN KEY ("scene_id") REFERENCES "scenes"("id") ON UPDATE
            CASCADE ON DELETE CASCADE,
            CONSTRAINT "approved_scene_texts_transcript_rev_fkey" FOREIGN KEY ("transcript_revision_id") REFERENCES
            "transcript_revisions"("id") ON UPDATE CASCADE ON DELETE CASCADE
        );
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "approved_scene_texts_active_item_idx" ON '
        '"approved_scene_texts"("is_active", "catalog_item_id");'
    )
    op.execute('CREATE INDEX IF NOT EXISTS "approved_scene_texts_scene_idx" ON "approved_scene_texts"("scene_id");')

    # 3. language_analysis_jobs: durable tokenization and reading analysis
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "language_analysis_jobs" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "transcript_revision_id" TEXT NOT NULL,
            "idempotency_key" TEXT,
            "status" TEXT NOT NULL DEFAULT 'queued',
            "results" JSONB,
            "error_message" TEXT,
            "created_by" TEXT NOT NULL,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "completed_at" TIMESTAMP(3),
            CONSTRAINT "language_analysis_jobs_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "language_analysis_jobs_catalog_item_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES
            "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "language_analysis_jobs_transcript_rev_fkey" FOREIGN KEY ("transcript_revision_id") REFERENCES
            "transcript_revisions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "language_analysis_jobs_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON
            UPDATE CASCADE ON DELETE RESTRICT
        );
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "language_analysis_jobs_item_rev_idx" ON '
        '"language_analysis_jobs"("catalog_item_id", "transcript_revision_id");'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "language_analysis_jobs_idempotency_idx" ON '
        '"language_analysis_jobs"("idempotency_key") WHERE "idempotency_key" IS '
        "NOT NULL;"
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "language_analysis_jobs" CASCADE;')
    op.execute('DROP TABLE IF EXISTS "approved_scene_texts" CASCADE;')
    op.execute('DROP TABLE IF EXISTS "transcript_revisions" CASCADE;')
