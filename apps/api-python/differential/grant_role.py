"""Grant a role to an E2E user inside the isolated Compose database only.

.venv/bin/python differential/grant_role.py <database_url> <email> <role>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from pg_harness import assert_test_database_url  # noqa: E402


async def main(url: str, email: str, role: str) -> int:
    assert_test_database_url(url)  # refuses anything that is not a test database
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
        if user_id is None:
            print(f"no user {email}", file=sys.stderr)
            return 1
        await conn.execute(
            'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
            user_id,
            role,
        )
    finally:
        await conn.close()
    print(f"granted {role} to {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(*sys.argv[1:4])))
