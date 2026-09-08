from fastapi.testclient import TestClient


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


def test_throttle_window_expires(live_client: TestClient) -> None:
    limiter = live_client.app.state.login_rate_limiter
    key = "127.0.0.1|window@jplearn.local"
    for _ in range(10):
        assert limiter.check(key, now=0.0) is True

    assert limiter.check(key, now=59.999) is False
    assert limiter.check(key, now=60.0) is True


def test_throttle_can_be_reset(live_client: TestClient) -> None:
    email = "reset@jplearn.local"
    for _ in range(10):
        _attempt(live_client, email)
    assert _attempt(live_client, email).status_code == 429

    live_client.app.state.login_rate_limiter.reset()

    assert _attempt(live_client, email).status_code in (400, 401)
