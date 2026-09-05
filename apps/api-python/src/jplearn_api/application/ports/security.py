"""Security ports for password hashing and token management (Protocol-based)."""

from __future__ import annotations

from typing import Any, Protocol


class PasswordHasher(Protocol):
    """Port for Argon2 or other password hashing algorithms."""

    async def hash_password(self, password: str) -> str:
        ...

    async def verify_password(self, password_hash: str, candidate: str) -> bool:
        ...


class TokenService(Protocol):
    """Port for signing and decoding JWT access tokens."""

    def sign_access_token(
        self,
        user_id: str,
        email: str,
        token_version: int,
        secret: str,
    ) -> str:
        ...

    def decode_access_token(self, token: str, secret: str) -> dict[str, Any]:
        ...
