from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import asyncpg
import pytest

from jplearn_api.password import hash_password, verify_password
from jplearn_api.seed import bootstrap_admin, seed, seed_reference_data


@pytest.mark.asyncio
async def test_seed_reference_data_is_idempotent(live_database_url: str):
    conn = await asyncpg.connect(live_database_url)
    try:
        await seed_reference_data(conn)
        await seed_reference_data(conn)

        flags_count = await conn.fetchval("SELECT count(*) FROM feature_flags")
        topics_count = await conn.fetchval("SELECT count(*) FROM topics")
        assert flags_count == 4
        assert topics_count == 6
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_admin_bootstrap_create_only_does_not_reset_password(live_database_url: str):
    conn = await asyncpg.connect(live_database_url)
    test_email = f"admin_{uuid4().hex[:8]}@example.com"
    initial_pw = "initial_password_123"
    updated_pw = "updated_password_456"

    try:
        # 1. First bootstrap creates the admin
        admin_id = await bootstrap_admin(conn, test_email, initial_pw, environment="local")
        assert admin_id is not None

        # Verify initial password works
        pw_hash = await conn.fetchval("SELECT password_hash FROM users WHERE id = $1", admin_id)
        assert verify_password(pw_hash, initial_pw) is True

        # 2. User updates their password
        new_hash = hash_password(updated_pw)
        await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", new_hash, admin_id)

        # 3. Subsequent seed / bootstrap runs with old password
        os.environ["BOOTSTRAP_ADMIN_EMAIL"] = test_email
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = initial_pw
        await seed(conn, environment="local")

        # 4. Invariant: password_hash must NOT be reverted
        current_hash = await conn.fetchval("SELECT password_hash FROM users WHERE id = $1", admin_id)
        assert verify_password(current_hash, updated_pw) is True
        assert verify_password(current_hash, initial_pw) is False
    finally:
        os.environ.pop("BOOTSTRAP_ADMIN_EMAIL", None)
        os.environ.pop("BOOTSTRAP_ADMIN_PASSWORD", None)
        await conn.close()


@pytest.mark.asyncio
async def test_production_bootstrap_fails_without_opt_in(live_database_url: str):
    conn = await asyncpg.connect(live_database_url)
    test_email = f"prod_admin_{uuid4().hex[:8]}@example.com"
    try:
        os.environ.pop("ALLOW_ADMIN_BOOTSTRAP", None)
        with pytest.raises(RuntimeError, match="rejected without explicit ALLOW_ADMIN_BOOTSTRAP=true"):
            await bootstrap_admin(conn, test_email, "SuperSecurePassword123!", environment="production")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_production_bootstrap_fails_with_weak_password(live_database_url: str):
    conn = await asyncpg.connect(live_database_url)
    test_email = f"prod_admin_{uuid4().hex[:8]}@example.com"
    try:
        os.environ["ALLOW_ADMIN_BOOTSTRAP"] = "true"
        with pytest.raises(ValueError, match="does not meet security policy"):
            await bootstrap_admin(conn, test_email, "password10", environment="production")

        with pytest.raises(ValueError, match="does not meet security policy"):
            await bootstrap_admin(conn, test_email, "short", environment="production")
    finally:
        os.environ.pop("ALLOW_ADMIN_BOOTSTRAP", None)
        await conn.close()
