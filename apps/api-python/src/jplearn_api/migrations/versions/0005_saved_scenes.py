"""Saved scenes (ADR-007 PR3).

Revision ID: 0005_saved_scenes
Revises: 0004_series
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0005_saved_scenes"
down_revision = "0004_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "saved_scenes" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "scene_id" TEXT NOT NULL,
            "saved_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "saved_scenes_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "saved_scenes_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON
            DELETE CASCADE,
            CONSTRAINT "saved_scenes_scene_id_fkey" FOREIGN KEY ("scene_id") REFERENCES "scenes"("id") ON UPDATE CASCADE
            ON DELETE RESTRICT,
            CONSTRAINT "saved_scenes_user_scene_unique" UNIQUE ("user_id", "scene_id")
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "saved_scenes_user_saved_at_idx" ON '
        '"saved_scenes"("user_id", "saved_at" DESC, "id" DESC)'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "saved_scenes"')
