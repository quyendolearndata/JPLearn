"""Security capability ports (Pure Python, protocol-based)."""

from __future__ import annotations

from typing import Any, Protocol


class PasswordHasher(Protocol):
    """Port for Argon2 or other password hashing algorithms."""

    async def hash_password(self, password: str) -> str: ...

    async def verify_password(self, password_hash: str, candidate: str) -> bool: ...


class TokenService(Protocol):
    """Port for signing and decoding JWT access tokens."""

    def sign_access_token(
        self,
        user_id: str,
        email: str,
        token_version: int,
        secret: str,
    ) -> str: ...

    def decode_access_token(self, token: str, secret: str) -> dict[str, Any]: ...


class MediaUrlSigner(Protocol):
    """Port for signing and verifying media access URLs."""

    def sign_playback_url(self, asset_id: str) -> str:
        """Generate time-limited signed URL for MP4 playback."""
        ...

    def sign_hls_url(self, asset_id: str) -> str:
        """Generate time-limited signed URL for HLS manifest."""
        ...

    def playback_url(self, asset_id: str) -> str:
        """Generate canonical public URL for MP4 playback."""
        ...

    def manifest_url(self, asset_id: str) -> str:
        """Generate canonical public URL for HLS master manifest."""
        ...

    def verify_media_sig(self, asset_id: str, exp: int, sig: str) -> bool:
        """Verify URL signature for asset access."""
        ...
