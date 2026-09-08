"""Series and series items (ADR-007 PR2).

Revision ID: 0004_series
Revises: 0003_content_versions_and_scenes
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0004_series"
down_revision = "0003_content_versions_and_scenes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "series" (
            "id" TEXT NOT NULL,
            "title" TEXT NOT NULL,
            "description" TEXT NOT NULL,
            "ci_level" TEXT NOT NULL,
            "topic_id" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'draft',
            "revision" INTEGER NOT NULL DEFAULT 1,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "series_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "series_topic_id_fkey" FOREIGN KEY ("topic_id") REFERENCES "topics"("id") ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "series_items" (
            "series_id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "position" INTEGER NOT NULL,
            CONSTRAINT "series_items_pkey" PRIMARY KEY ("series_id", "position"),
            CONSTRAINT "series_items_series_id_fkey" FOREIGN KEY ("series_id") REFERENCES "series"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "series_items_catalog_item_id_fkey" FOREIGN KEY ("catalog_item_id") REFERENCES "catalog_items"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
            CONSTRAINT "series_items_unique_item_key" UNIQUE ("series_id", "catalog_item_id")
        )
        """,
    )

    op.execute('CREATE INDEX IF NOT EXISTS "series_topic_id_idx" ON "series"("topic_id")')
    op.execute('CREATE INDEX IF NOT EXISTS "series_status_idx" ON "series"("status")')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "series_items"')
    op.execute('DROP TABLE IF EXISTS "series"')
