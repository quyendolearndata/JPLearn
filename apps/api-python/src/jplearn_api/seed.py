"""Seed CLI. Port of apps/api/prisma/seed.ts (ADR-004 moved this off Node).

Idempotent by design and, per FR-CAT-002, **never** overwrites `status` on an
existing catalog item: publish/unpublish are operational decisions owned by
Level QA and Ops. Seed items stay `draft` because they carry no real media —
issue #39 exists precisely because an earlier seed re-published a media-less item.

    jplearn-seed        # uses DATABASE_URL
"""

from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

import asyncpg

from jplearn_api.migrate import resolve_database_url
from jplearn_api.password import hash_password

ADMIN_EMAIL = "admin@jplearn.local"
ADMIN_PASSWORD = "password10"

FLAG_KEYS = (
    "speaking_enabled",
    "l1_subtitles_enabled",
    "grammar_enabled",
    "flashcards_enabled",
)

TOPICS = ("daily_home", "food", "body", "go_somewhere", "nature", "people")

CATALOG_ITEMS = (
    {
        "id": "00000000-0000-4000-8000-0000000000c1",
        "topic_id": "daily_home",
        "ci_level": 0,
        "duration_seconds": 30,
        "title_internal": "seed-ci0-daily-home",
    },
    {
        "id": "00000000-0000-4000-8000-0000000000d1",
        "topic_id": "food",
        "ci_level": 1,
        "duration_seconds": 25,
        "title_internal": "seed-draft-food",
    },
)


async def seed(conn: asyncpg.Connection) -> None:
    await conn.executemany(
        "INSERT INTO feature_flags (key, value) VALUES ($1, false) ON CONFLICT (key) DO NOTHING",
        [(key,) for key in FLAG_KEYS],
    )

    await conn.executemany(
        "INSERT INTO topics (id, label_internal) VALUES ($1, $1) ON CONFLICT (id) DO NOTHING",
        [(topic,) for topic in TOPICS],
    )

    admin_id = await conn.fetchval(
        """
        INSERT INTO users (id, email, password_hash, token_version)
        VALUES ($1, $2, $3, 0)
        ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id
        """,
        str(uuid4()),
        ADMIN_EMAIL,
        hash_password(ADMIN_PASSWORD),
    )

    await conn.executemany(
        'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
        [(admin_id, "admin"), (admin_id, "teacher")],
    )

    for item in CATALOG_ITEMS:
        await conn.execute(
            """
            INSERT INTO catalog_items (
                id, topic_id, ci_level, duration_seconds, media_type, visual_support,
                status, title_internal, created_by
            )
            VALUES ($1, $2, $3, $4, 'video'::"MediaType", 'high'::"VisualSupport",
                    'draft'::"CatalogStatus", $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            item["id"],
            item["topic_id"],
            item["ci_level"],
            item["duration_seconds"],
            item["title_internal"],
            admin_id,
        )


async def seed_url(database_url: str) -> None:
    conn = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await seed(conn)
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    database_url = resolve_database_url(args[0] if args else None)
    if not database_url:
        print("DATABASE_URL is required to seed", file=sys.stderr)
        return 2
    try:
        asyncio.run(seed_url(database_url))
    except Exception as error:
        print(f"seed failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
