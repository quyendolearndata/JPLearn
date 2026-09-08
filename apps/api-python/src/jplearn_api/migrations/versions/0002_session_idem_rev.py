"""Session idempotency keys and catalog item revision (W3/W4).

Revision ID: 0002_session_idem_rev
Revises: 0001_prisma_baseline
Create Date: 2026-09-06
"""

from __future__ import annotations

from alembic import op

revision = "0002_session_idem_rev"
down_revision = "0001_prisma_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "session_idempotency_keys" (
            "key" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "session_id" TEXT NOT NULL,
            "request_hash" TEXT NOT NULL,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "session_idempotency_keys_pkey" PRIMARY KEY ("user_id", "key"),
            CONSTRAINT "session_idempotency_keys_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE CASCADE,
            CONSTRAINT "session_idempotency_keys_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "learning_sessions"("id") ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
    )

    op.execute(
        """
        ALTER TABLE "catalog_items"
        ADD COLUMN IF NOT EXISTS "revision" INTEGER NOT NULL DEFAULT 1
        """,
    )


def downgrade() -> None:
    op.execute('ALTER TABLE "catalog_items" DROP COLUMN IF EXISTS "revision"')
    op.execute('DROP TABLE IF EXISTS "session_idempotency_keys"')
