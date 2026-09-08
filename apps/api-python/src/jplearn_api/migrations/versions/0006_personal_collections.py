"""Personal collections (ADR-007 PR3a).

Revision ID: 0006_personal_collections
Revises: 0005_saved_scenes
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0006_personal_collections"
down_revision = "0005_saved_scenes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "learner_library_state" (
            "user_id" TEXT NOT NULL,
            "collection_count" INTEGER NOT NULL DEFAULT 0,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "learner_library_state_pkey" PRIMARY KEY ("user_id"),
            CONSTRAINT "learner_library_state_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "personal_collections" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "name" TEXT NOT NULL,
            "revision" INTEGER NOT NULL DEFAULT 1,
            "idempotency_key" TEXT,
            "request_hash" TEXT,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "personal_collections_pkey" PRIMARY KEY ("id"),
            CONSTRAINT "personal_collections_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "personal_collections_id_user_unique" UNIQUE ("id", "user_id"),
            CONSTRAINT "personal_collections_user_idempotency_unique" UNIQUE ("user_id", "idempotency_key")
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "personal_collections_user_created_idx" ON "personal_collections"("user_id", "created_at" DESC, "id" DESC)'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "collection_scenes" (
            "collection_id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "scene_id" TEXT NOT NULL,
            "position" INTEGER NOT NULL,
            "added_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "collection_scenes_pkey" PRIMARY KEY ("collection_id", "position"),
            CONSTRAINT "collection_scenes_unique_scene" UNIQUE ("collection_id", "scene_id"),
            CONSTRAINT "collection_scenes_collection_user_fkey" FOREIGN KEY ("collection_id", "user_id") REFERENCES "personal_collections"("id", "user_id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "collection_scenes_saved_scene_fkey" FOREIGN KEY ("user_id", "scene_id") REFERENCES "saved_scenes"("user_id", "scene_id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "collection_scenes_user_scene_idx" ON "collection_scenes"("user_id", "scene_id")'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "collection_scenes"')
    op.execute('DROP TABLE IF EXISTS "personal_collections"')
    op.execute('DROP TABLE IF EXISTS "learner_library_state"')
