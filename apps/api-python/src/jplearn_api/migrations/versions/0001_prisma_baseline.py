"""Baseline schema: exact squash of Prisma migrations 0001..0004 (ADR-004).

Reproduces the schema Prisma owned before DDL moved to Alembic, down to
constraint and index names, so an existing database can be adopted with
`jplearn-migrate stamp` instead of being rebuilt. Verified structurally
identical to docs/qa/adr-004-schema-baseline.json by tests/test_schema_ddl.py.

Hand-written on purpose — see migrations/env.py.
"""

from __future__ import annotations

from alembic import op

revision = "0001_prisma_baseline"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = {
    "Role": ("learner", "teacher", "admin"),
    "DeviceClass": ("web", "phone", "ipad"),
    "MediaType": ("video", "audio"),
    "VisualSupport": ("high", "medium", "low"),
    "CatalogStatus": ("draft", "level_qa", "published", "archived"),
    "EventType": (
        "session_started",
        "session_ended",
        "minutes_comprehensible",
        "level_exposed",
    ),
}

# Reverse dependency order for downgrade.
TABLES = (
    "learning_events",
    "feature_flags",
    "learner_progress",
    "learning_sessions",
    "media_assets",
    "catalog_items",
    "topics",
    "devices",
    "user_roles",
    "users",
)


def upgrade() -> None:
    for name, labels in ENUMS.items():
        values = ", ".join(f"'{label}'" for label in labels)
        op.execute(f'CREATE TYPE "{name}" AS ENUM ({values})')

    op.execute(
        """
        CREATE TABLE "users" (
            "id" TEXT NOT NULL,
            "email" TEXT NOT NULL,
            "password_hash" TEXT NOT NULL,
            "token_version" INTEGER NOT NULL DEFAULT 0,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "users_pkey" PRIMARY KEY ("id")
        )
        """,
    )
    op.execute('CREATE UNIQUE INDEX "users_email_key" ON "users"("email")')

    op.execute(
        """
        CREATE TABLE "user_roles" (
            "user_id" TEXT NOT NULL,
            "role" "Role" NOT NULL,
            CONSTRAINT "user_roles_pkey" PRIMARY KEY ("user_id","role")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE "devices" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "device_class" "DeviceClass" NOT NULL,
            "last_seen_at" TIMESTAMP(3) NOT NULL,
            CONSTRAINT "devices_pkey" PRIMARY KEY ("id")
        )
        """,
    )
    op.execute(
        'CREATE UNIQUE INDEX "devices_user_id_device_class_key" '
        'ON "devices"("user_id", "device_class")',
    )

    op.execute(
        """
        CREATE TABLE "topics" (
            "id" TEXT NOT NULL,
            "label_internal" TEXT NOT NULL,
            CONSTRAINT "topics_pkey" PRIMARY KEY ("id")
        )
        """,
    )

    # FR-CAT-004 / FR-NEG-003: a published clip can never carry an L1 translation.
    op.execute(
        """
        CREATE TABLE "catalog_items" (
            "id" TEXT NOT NULL,
            "topic_id" TEXT NOT NULL,
            "ci_level" INTEGER NOT NULL,
            "duration_seconds" INTEGER NOT NULL,
            "media_type" "MediaType" NOT NULL,
            "visual_support" "VisualSupport" NOT NULL,
            "has_l1_translation" BOOLEAN NOT NULL DEFAULT false,
            "spoken_language" TEXT NOT NULL DEFAULT 'ja',
            "status" "CatalogStatus" NOT NULL DEFAULT 'draft',
            "title_internal" TEXT NOT NULL,
            "created_by" TEXT NOT NULL,
            CONSTRAINT "catalog_items_pkey" PRIMARY KEY ("id")
        )
        """,
    )
    op.execute(
        """
        ALTER TABLE "catalog_items"
        ADD CONSTRAINT "catalog_items_published_without_l1_translation"
        CHECK (("status" <> 'published') OR ("has_l1_translation" = false))
        """,
    )

    op.execute(
        """
        CREATE TABLE "media_assets" (
            "id" TEXT NOT NULL,
            "catalog_item_id" TEXT NOT NULL,
            "storage_key" TEXT NOT NULL,
            "playback_url" TEXT,
            "hls_url" TEXT,
            "mime" TEXT NOT NULL,
            CONSTRAINT "media_assets_pkey" PRIMARY KEY ("id")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE "learning_sessions" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "device_class" "DeviceClass" NOT NULL,
            "started_at" TIMESTAMP(3) NOT NULL,
            "ended_at" TIMESTAMP(3),
            "duration_seconds" INTEGER,
            CONSTRAINT "learning_sessions_pkey" PRIMARY KEY ("id")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE "learner_progress" (
            "user_id" TEXT NOT NULL,
            "minutes_comprehensible" INTEGER NOT NULL DEFAULT 0,
            "current_ci_level" INTEGER NOT NULL DEFAULT 0,
            "updated_at" TIMESTAMP(3) NOT NULL,
            CONSTRAINT "learner_progress_pkey" PRIMARY KEY ("user_id")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE "feature_flags" (
            "key" TEXT NOT NULL,
            "value" BOOLEAN NOT NULL DEFAULT false,
            CONSTRAINT "feature_flags_pkey" PRIMARY KEY ("key")
        )
        """,
    )

    op.execute(
        """
        CREATE TABLE "learning_events" (
            "id" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "session_id" TEXT,
            "type" "EventType" NOT NULL,
            "payload" JSONB NOT NULL,
            "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "learning_events_pkey" PRIMARY KEY ("id")
        )
        """,
    )

    for table, column, target, on_delete in (
        ("user_roles", "user_id", "users", "RESTRICT"),
        ("devices", "user_id", "users", "RESTRICT"),
        ("catalog_items", "topic_id", "topics", "RESTRICT"),
        ("catalog_items", "created_by", "users", "RESTRICT"),
        ("media_assets", "catalog_item_id", "catalog_items", "RESTRICT"),
        ("learning_sessions", "user_id", "users", "RESTRICT"),
        ("learner_progress", "user_id", "users", "RESTRICT"),
        ("learning_events", "user_id", "users", "RESTRICT"),
        ("learning_events", "session_id", "learning_sessions", "SET NULL"),
    ):
        target_column = "key" if target == "feature_flags" else "id"
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{table}_{column}_fkey" '
            f'FOREIGN KEY ("{column}") REFERENCES "{target}"("{target_column}") '
            f"ON DELETE {on_delete} ON UPDATE CASCADE",
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    for name in ENUMS:
        op.execute(f'DROP TYPE IF EXISTS "{name}"')
