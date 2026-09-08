from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

from jplearn_api.entrypoints.http.schemas import LoginBody


class LoginRateLimiter:
    def __init__(self, attempts: int, window_seconds: int) -> None:
        self._attempts = attempts
        self._window_seconds = window_seconds
        self._timestamps: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        cutoff = current - self._window_seconds

        with self._lock:
            expired_keys = [
                stored_key
                for stored_key, stored_timestamps in self._timestamps.items()
                if stored_key != key
                and (not stored_timestamps or stored_timestamps[-1] <= cutoff)
            ]
            for expired_key in expired_keys:
                del self._timestamps[expired_key]

            timestamps = self._timestamps.get(key)
            if timestamps is not None:
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps:
                    del self._timestamps[key]
                    timestamps = None
            if timestamps is None:
                timestamps = deque()
                self._timestamps[key] = timestamps
            if len(timestamps) >= self._attempts:
                return False
            timestamps.append(current)
            return True

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()


def enforce_login_rate_limit(body: LoginBody, request: Request) -> None:
    client_ip = request.client.host if request.client is not None else "unknown"
    key = f"{client_ip}|{body.email.lower()}"
    limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    if not limiter.check(key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts; try again later",
        )
