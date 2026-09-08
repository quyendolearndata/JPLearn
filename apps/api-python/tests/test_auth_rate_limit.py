from fastapi.testclient import TestClient

from jplearn_api.entrypoints.http.rate_limit import LoginRateLimiter


def _attempt(client: TestClient, email: str):
    return client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-wrong"},
    )


def test_login_is_throttled_after_limit(live_client: TestClient) -> None:
    email = "throttle-me@jplearn.local"
    codes = [_attempt(live_client, email).status_code for _ in range(10)]
    assert set(codes) <= {400, 401}, codes

    throttled = _attempt(live_client, email)

    assert throttled.status_code == 429
    assert throttled.json() == {
        "statusCode": 429,
        "message": "Too many login attempts; try again later",
        "error": "Too Many Requests",
    }


def test_throttle_is_scoped_per_normalized_email(live_client: TestClient) -> None:
    email = "a@jplearn.local"
    for _ in range(10):
        _attempt(live_client, email.upper())

    assert _attempt(live_client, email).status_code == 429
    assert _attempt(live_client, "b@jplearn.local").status_code in (400, 401)


def test_throttle_is_scoped_per_stripped_email(live_client: TestClient) -> None:
    email = "throttle@jplearn.local"
    for _ in range(10):
        _attempt(live_client, email)

    assert _attempt(live_client, f" {email} ").status_code == 429


def test_throttle_window_expires(live_client: TestClient) -> None:
    limiter = live_client.app.state.login_rate_limiter
    key = "127.0.0.1|window@jplearn.local"
    for _ in range(10):
        assert limiter.check(key, now=0.0) is True

    assert limiter.check(key, now=59.999) is False
    assert limiter.check(key, now=60.0) is True


def test_check_drops_all_expired_keys() -> None:
    limiter = LoginRateLimiter(attempts=10, window_seconds=60)
    expired_keys = {
        "1.1.1.1|a@x.test",
        "1.1.1.1|b@x.test",
    }
    for key in expired_keys:
        assert limiter.check(key, now=0.0) is True

    assert limiter.check("1.1.1.1|c@x.test", now=60.0) is True

    assert expired_keys.isdisjoint(limiter._timestamps)


def test_check_caps_active_keys_without_evicting_updated_key() -> None:
    limiter = LoginRateLimiter(attempts=10, window_seconds=60, max_keys=2)
    assert limiter.check("1.1.1.1|a@x.test", now=0.0) is True
    assert limiter.check("1.1.1.1|b@x.test", now=0.0) is True

    updated_key = "1.1.1.1|c@x.test"
    assert limiter.check(updated_key, now=1.0) is True

    assert len(limiter._timestamps) == 2
    assert updated_key in limiter._timestamps


def test_throttle_can_be_reset(live_client: TestClient) -> None:
    email = "reset@jplearn.local"
    for _ in range(10):
        _attempt(live_client, email)
    assert _attempt(live_client, email).status_code == 429

    live_client.app.state.login_rate_limiter.reset()

    assert _attempt(live_client, email).status_code in (400, 401)
