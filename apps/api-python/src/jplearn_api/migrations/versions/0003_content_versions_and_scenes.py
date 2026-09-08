"""Content versions and scenes (ADR-007 PR1).

Revision ID: 0003_content_versions_and_scenes
Revises: 0002_session_idem_rev
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0003_content_versions_and_scenes"
down_revision = "0002_session_idem_rev"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "content_versions" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "version_number" INTEGER NOT NULL DEFAULT 1,
            "revision" INTEGER NOT NULL DEFAULT 1,
            "is_frozen" BOOLEAN NOT NULL DEFAULT FALSE,
            "is_published" BOOLEAN NOT NULL DEFAULT FALSE,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "published_at" TIMESTAMP(3) NULL,
            CONSTRAINT "content_versions_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "content_versions_catalog_item_id_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES "catalog_items"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "content_versions_item_version_key" UNIQUE ("catalog_item_id", "version_number")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "scenes" (
            "id" TEXT NOT NULL,
            "content_version_id" TEXT NOT NULL,
            "scene_index" INTEGER NOT NULL,
            "start_time_seconds" INTEGER NOT NULL,
            "end_time_seconds" INTEGER NOT NULL,
            "title_jp" TEXT NOT NULL,
            "transcript_jp" TEXT NOT NULL,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "scenes_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "scenes_content_version_id_fkey" FOREIGN KEY ("content_version_id") REFERENCES "content_versions"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "scenes_version_index_key" UNIQUE ("content_version_id", "scene_index"),
            CONSTRAINT "scenes_timing_check" CHECK ("start_time_seconds" >= 0 AND "end_time_seconds" > "start_time_seconds")
        )
        """,
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "scenes"')
    op.execute('DROP TABLE IF EXISTS "content_versions"')
