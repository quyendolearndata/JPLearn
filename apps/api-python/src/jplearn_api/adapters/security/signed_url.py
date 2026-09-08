from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlparse, urlunparse

DEFAULT_TTL_SEC = 60 * 60


def signing_secret(explicit: str | None, media_signing_secret: str | None, jwt_secret: str) -> str:
    secret = explicit or media_signing_secret or jwt_secret
    if not secret:
        raise RuntimeError("MEDIA_SIGNING_SECRET or JWT_SECRET must be set")
    return secret


def hmac_hex(secret: str, asset_id: str, exp: int) -> str:
    return hmac.new(secret.encode("utf-8"), f"{asset_id}:{exp}".encode("utf-8"), hashlib.sha256).hexdigest()


def sign_media_url(
    *,
    asset_id: str,
    base_url: str,
    secret: str,
    now_sec: int,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> str:
    exp = now_sec + ttl_sec
    sig = hmac_hex(secret, asset_id, exp)
    base = base_url.rstrip("/")
    return f"{base}/media/{asset_id}?exp={exp}&sig={sig}"


def sign_hls_url(
    *,
    asset_id: str,
    base_url: str,
    secret: str,
    now_sec: int,
    file: str = "index.m3u8",
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> str:
    unsigned = sign_media_url(
        asset_id=asset_id,
        base_url=base_url,
        secret=secret,
        now_sec=now_sec,
        ttl_sec=ttl_sec,
    )
    parsed = urlparse(unsigned)
    return urlunparse(parsed._replace(path=f"/media/{asset_id}/hls/{file}"))


def verify_media_sig(
    *,
    asset_id: str,
    exp: int,
    sig: str,
    secret: str,
    now_sec: int,
) -> bool:
    if not isinstance(exp, int) and not (isinstance(exp, float) and exp.is_integer()):
        return False
    exp_int = int(exp)
    if len(sig) != 64:
        return False
    if exp_int < now_sec:
        return False
    expected = hmac_hex(secret, asset_id, exp_int)
    try:
        return hmac.compare_digest(bytes.fromhex(expected), bytes.fromhex(sig))
    except ValueError:
        return False
