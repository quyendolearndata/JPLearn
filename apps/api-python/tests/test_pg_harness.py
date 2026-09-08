from __future__ import annotations

import asyncpg

import pg_harness


def test_can_connect_rejects_a_reachable_server_with_wrong_credentials(monkeypatch):
    async def reject_credentials(*_args, **_kwargs):
        raise asyncpg.InvalidPasswordError("invalid password")

    monkeypatch.setattr(asyncpg, "connect", reject_credentials)

    assert pg_harness._can_connect(
        "postgresql://jplearn_test:wrong@127.0.0.1:5432/jplearn_test"
    ) is False
