"""Seed CLI. Port of apps/api/prisma/seed.ts (ADR-004 moved this off Node).

Idempotent by design and, per FR-CAT-002, **never** overwrites `status` on an
existing catalog item: publish/unpublish are operational decisions owned by
Level QA and Ops. Seed items stay `draft` because they carry no real media.

Decoupled reference data (topics, flags, initial catalog items) from admin bootstrap.
Bootstrap is create-only and never resets an existing user's credentials.

    jplearn-seed        # uses DATABASE_URL
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import asyncpg

from jplearn_api.migrate import resolve_database_url
from jplearn_api.password import hash_password

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


async def seed_reference_data(conn: asyncpg.Connection, *, admin_id: str | None = None) -> None:
    """Seed feature flags, topics, and initial draft catalog items."""
    await conn.executemany(
        "INSERT INTO feature_flags (key, value) VALUES ($1, false) ON CONFLICT (key) DO NOTHING",
        [(key,) for key in FLAG_KEYS],
    )

    await conn.executemany(
        "INSERT INTO topics (id, label_internal) VALUES ($1, $1) ON CONFLICT (id) DO NOTHING",
        [(topic,) for topic in TOPICS],
    )

    creator_id = admin_id
    if not creator_id:
        creator_id = await conn.fetchval(
            """
            SELECT u.id FROM users u
            JOIN user_roles r ON u.id = r.user_id
            WHERE r.role = 'admin'
            ORDER BY u.created_at ASC
            LIMIT 1
            """
        )

    if creator_id:
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
                str(creator_id),
            )


async def bootstrap_admin(
    conn: asyncpg.Connection,
    email: str,
    password: str,
    *,
    environment: str = "local",
) -> str | None:
    """Create-only admin bootstrap. NEVER updates password of an existing user."""
    if environment in ("staging", "production"):
        opt_in = os.environ.get("ALLOW_ADMIN_BOOTSTRAP", "").strip().lower()
        if opt_in not in ("true", "1", "yes"):
            raise RuntimeError(
                f"Admin bootstrap in {environment} is rejected without explicit ALLOW_ADMIN_BOOTSTRAP=true"
            )
        if len(password) < 12 or password.lower() in ("password10", "admin", "password", "1234567890"):
            raise ValueError(
                f"Bootstrap password in {environment} does not meet security policy (min 12 chars, non-default)"
            )
    elif len(password) < 10:
        raise ValueError("Admin password must be at least 10 characters")

    existing_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    if existing_id is not None:
        # Idempotent: user already exists. Do NOT touch password_hash!
        return str(existing_id)

    new_id = str(uuid4())
    inserted_id = await conn.fetchval(
        """
        INSERT INTO users (id, email, password_hash, token_version)
        VALUES ($1, $2, $3, 0)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        new_id,
        email,
        hash_password(password),
    )
    admin_id = str(inserted_id) if inserted_id else str(
        await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    )

    await conn.executemany(
        'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
        [(admin_id, "admin"), (admin_id, "teacher")],
    )
    return admin_id


async def seed(conn: asyncpg.Connection, *, environment: str = "local") -> None:
    admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "admin@jplearn.local"
    admin_password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")

    admin_id: str | None = None
    if admin_password:
        admin_id = await bootstrap_admin(
            conn,
            admin_email,
            admin_password,
            environment=environment,
        )
    else:
        existing_admin = await conn.fetchval("SELECT id FROM users WHERE email = $1", admin_email)
        if existing_admin:
            admin_id = str(existing_admin)

    await seed_reference_data(conn, admin_id=admin_id)


async def seed_url(database_url: str, *, environment: str = "local") -> None:
    conn = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await seed(conn, environment=environment)
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    database_url = resolve_database_url(args[0] if args else None)
    if not database_url:
        print("DATABASE_URL is required to seed", file=sys.stderr)
        return 2
    environment = os.environ.get("ENVIRONMENT", "local")
    try:
        asyncio.run(seed_url(database_url, environment=environment))
    except Exception as error:
        print(f"seed failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

