"""JWT token service adapter."""

from __future__ import annotations

from typing import Any

from jplearn_api.application.ports.security import TokenService
from jplearn_api.tokens import decode_access_token, sign_access_token


class JwtTokenService(TokenService):
    """JWT implementation of TokenService."""

    def sign_access_token(
        self,
        user_id: str,
        email: str,
        token_version: int,
        secret: str,
    ) -> str:
        return sign_access_token(
            user_id=user_id,
            email=email,
            ver=token_version,
            secret=secret,
        )

    def decode_access_token(self, token: str, secret: str) -> dict[str, Any]:
        return decode_access_token(token=token, secret=secret)
