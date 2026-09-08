"""Argon2 password hasher adapter."""

from __future__ import annotations

import asyncio

from jplearn_api.application.ports.security import PasswordHasher
from jplearn_api.adapters.security.password import hash_password, verify_password


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id implementation of PasswordHasher."""

    async def hash_password(self, password: str) -> str:
        return await asyncio.to_thread(hash_password, password)

    async def verify_password(self, password_hash: str, candidate: str) -> bool:
        return await asyncio.to_thread(verify_password, password_hash, candidate)
