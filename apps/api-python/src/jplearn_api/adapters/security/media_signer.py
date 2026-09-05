"""HMAC media URL signing adapter."""

from __future__ import annotations

from collections.abc import Callable
from time import time

from jplearn_api.application.ports.security import MediaUrlSigner
from jplearn_api.signed_url import sign_hls_url, sign_media_url, verify_media_sig


class HmacMediaUrlSigner(MediaUrlSigner):
    """HMAC-SHA256 URL signer holding signing credentials."""

    def __init__(
        self,
        base_url: str,
        secret: str,
        clock: Callable[[], int] = lambda: int(time()),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._clock = clock

    def sign_playback_url(self, asset_id: str) -> str:
        return sign_media_url(
            asset_id=asset_id,
            base_url=self._base_url,
            secret=self._secret,
            now_sec=self._clock(),
        )

    def sign_hls_url(self, asset_id: str) -> str:
        return sign_hls_url(
            asset_id=asset_id,
            base_url=self._base_url,
            secret=self._secret,
            now_sec=self._clock(),
        )

    def manifest_url(self, asset_id: str) -> str:
        return f"{self._base_url}/media/{asset_id}/hls/index.m3u8"

    def verify_media_sig(self, asset_id: str, exp: int, sig: str) -> bool:
        return verify_media_sig(
            asset_id=asset_id,
            exp=exp,
            sig=sig,
            secret=self._secret,
            now_sec=self._clock(),
        )
