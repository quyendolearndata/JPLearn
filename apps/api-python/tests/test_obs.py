"""NFR-OBS-001 — health probe, request-id propagation, 5xx alert webhook.

Port of apps/api/test/alert-5xx.e2e-spec.ts (T-NFR-O2) plus the health assertion
(T-NFR-O1). Runs a real HTTP receiver because the alert path posts over the
network via httpx; a monkeypatched client would not prove the payload shape.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from jplearn_api.main import create_app
from jplearn_api.settings import Settings


class _Receiver(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.server.received.append(json.loads(body))  # type: ignore[attr-defined]
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args) -> None:
        pass


@pytest.fixture
def webhook():
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    server.received = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _app(webhook_url: str | None):
    settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        alert_webhook_url=webhook_url,
    )
    app = create_app(settings)

    async def boom() -> None:
        raise RuntimeError("boom")

    async def bad() -> None:
        raise HTTPException(status_code=400, detail="bad_input")

    app.add_api_route("/__test/boom", boom, methods=["GET"], include_in_schema=False)
    app.add_api_route("/__test/bad", bad, methods=["GET"], include_in_schema=False)
    return app


def test_health_is_200_and_echoes_request_id() -> None:
    with TestClient(_app(None)) as client:
        response = client.get("/health", headers={"x-request-id": "req-obs-health"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-request-id"] == "req-obs-health"


def test_request_id_is_generated_when_absent() -> None:
    with TestClient(_app(None)) as client:
        response = client.get("/health")

    assert len(response.headers["x-request-id"]) == 36


def test_no_webhook_configured_means_no_alert(webhook) -> None:
    with TestClient(_app(None), raise_server_exceptions=False) as client:
        assert client.get("/__test/boom").status_code == 500

    assert webhook.received == []


def test_5xx_posts_alert_payload(webhook) -> None:
    url = f"http://127.0.0.1:{webhook.server_address[1]}/hook"
    with TestClient(_app(url), raise_server_exceptions=False) as client:
        response = client.get("/__test/boom", headers={"x-request-id": "req-alert-001"})

    assert response.status_code == 500
    assert len(webhook.received) == 1
    payload = webhook.received[0]
    assert payload["method"] == "GET"
    assert payload["path"] == "/__test/boom"
    assert payload["status"] == 500
    assert payload["requestId"] == "req-alert-001"
    assert "boom" in payload["message"]
    assert payload["timestamp"].startswith("20")
    for fragment in ("500", "/__test/boom", "req-alert-001"):
        assert fragment in payload["text"]


def test_4xx_does_not_alert(webhook) -> None:
    url = f"http://127.0.0.1:{webhook.server_address[1]}/hook"
    with TestClient(_app(url)) as client:
        response = client.get("/__test/bad")

    assert response.status_code == 400
    assert response.json() == {"statusCode": 400, "message": "bad_input", "error": "Bad Request"}
    assert webhook.received == []


def test_sensitive_credentials_redacted_in_5xx_and_webhook(webhook) -> None:
    fake_secret = "super_secret_password_123"
    fake_hash = "$argon2id$v=19$m=65536,t=3,p=4$some_hash_string"
    fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.mock_signature"
    fake_db = "postgresql://user:db_password_456@localhost:5432/jplearn"

    app = _app(f"http://127.0.0.1:{webhook.server_address[1]}/hook")

    async def leak_route() -> None:
        raise RuntimeError(
            f"DB query failed: password='{fake_secret}' hash={fake_hash} token={fake_jwt} uri={fake_db}"
        )

    app.add_api_route("/__test/leak", leak_route, methods=["GET"], include_in_schema=False)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test/leak")

    # Response to client must NEVER contain leaked details (NFR-PRIV-001)
    assert response.status_code == 500
    assert fake_secret not in response.text
    assert fake_hash not in response.text
    assert fake_jwt not in response.text
    assert "db_password_456" not in response.text

    # Webhook payload must have redacted all sensitive data
    assert len(webhook.received) == 1
    alert_payload = webhook.received[0]
    raw_payload_str = json.dumps(alert_payload)
    assert fake_secret not in raw_payload_str
    assert fake_hash not in raw_payload_str
    assert fake_jwt not in raw_payload_str
    assert "db_password_456" not in raw_payload_str
    assert "[REDACTED]" in alert_payload["message"] or "[REDACTED_HASH]" in alert_payload["message"]


def test_settings_validation():
    # 1. Short JWT secret (< 32 bytes) fails
    with pytest.raises(ValueError, match="JWT_SECRET must be at least 32 bytes"):
        Settings(
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="short-key",
        )

    # 2. Relative storage_root fails
    with pytest.raises(ValueError, match="STORAGE_ROOT must be an absolute path"):
        Settings(
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            storage_root="relative/path/storage",
        )

    # 3. Staging/Production without HTTPS fails
    with pytest.raises(ValueError, match="API_PUBLIC_URL must use HTTPS"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="http://insecure.example.com",
            media_signing_secret="b" * 32,
        )

    # 4. Staging/Production missing media_signing_secret fails
    with pytest.raises(ValueError, match="MEDIA_SIGNING_SECRET is required"):
        Settings(
            environment="staging",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret=None,
        )

    # 5. Staging/Production with media_signing_secret identical to jwt_secret fails
    with pytest.raises(ValueError, match="MEDIA_SIGNING_SECRET must be distinct"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="a" * 32,
        )

    # 6. Staging/Production with wildcard CORS fails
    with pytest.raises(ValueError, match="CORS_ORIGINS cannot be empty"):
        Settings(
            environment="staging",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["*"],
        )

    # 6b. Staging/Production inheriting default localhost origins fails
    with pytest.raises(ValueError, match="Explicit HTTPS CORS_ORIGINS required"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
        )

    # 6c. Staging/Production with permissive regex fails
    with pytest.raises(ValueError, match="Broad or unapproved CORS_ORIGIN_REGEX"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["https://app.example.com"],
            cors_origin_regex=".*",
        )

    # 6d. Production with invalid origin URL structure fails
    with pytest.raises(ValueError, match="CORS origin must not include a path"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["https://app.example.com/some/path"],
        )

    # 7. Production with HTTP CORS origin fails
    with pytest.raises(ValueError, match="CORS_ORIGINS entries must use HTTPS in production"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["http://insecure.example.com"],
        )

    # 8. Staging/Production with dev-secret fails
    with pytest.raises(ValueError, match="Insecure JWT_SECRET"):
        Settings(
            environment="staging",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="dev-secret-longer-than-32-bytes-still-insecure",
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["https://staging.example.com"],
        )

    # 9. Production with allow_admin_bootstrap fails
    with pytest.raises(ValueError, match="ALLOW_ADMIN_BOOTSTRAP cannot be enabled in production"):
        Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/db",
            jwt_secret="a" * 32,
            api_public_url="https://api.example.com",
            media_signing_secret="b" * 32,
            cors_origins=["https://production.example.com"],
            allow_admin_bootstrap=True,
        )


def test_slow_webhook_does_not_block_client_response() -> None:
    import time

    class _SlowReceiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            time.sleep(0.4)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), _SlowReceiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/hook"
        app = _app(url)
        with TestClient(app, raise_server_exceptions=False) as client:
            t0 = time.monotonic()
            resp = client.get("/__test/boom")
            elapsed = time.monotonic() - t0
            assert resp.status_code == 500
            # Client request was NOT delayed by the 400ms webhook POST
            assert elapsed < 0.2, f"Client response delayed: {elapsed}s"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_alert_queue_overflow_drops_safely() -> None:
    import asyncio
    from jplearn_api.alert import enqueue_alert

    small_queue: asyncio.Queue = asyncio.Queue(maxsize=2)
    settings = Settings(
        database_url="postgresql://user:pass@localhost:5432/db",
        jwt_secret="a" * 32,
        alert_webhook_url="http://127.0.0.1:9999/hook",
    )
    assert (
        enqueue_alert(
            settings,
            method="GET",
            path="/",
            status=500,
            request_id="1",
            message="m1",
            queue=small_queue,
        )
        is True
    )
    assert (
        enqueue_alert(
            settings,
            method="GET",
            path="/",
            status=500,
            request_id="2",
            message="m2",
            queue=small_queue,
        )
        is True
    )
    # Third item drops safely without blocking or raising
    assert (
        enqueue_alert(
            settings,
            method="GET",
            path="/",
            status=500,
            request_id="3",
            message="m3",
            queue=small_queue,
        )
        is False
    )


def test_production_cors_fail_closed_middleware() -> None:
    """R-02: Production fails closed for unapproved origins, HTTP, lookalikes, null, exp://."""
    from jplearn_api.main import create_app

    settings = Settings(
        environment="production",
        database_url="postgresql://user:pass@localhost:5432/db",
        jwt_secret="a" * 32,
        api_public_url="https://api.jplearn.com",
        media_signing_secret="b" * 32,
        cors_origins=["https://app.jplearn.com", "https://cms.jplearn.com"],
    )
    app = create_app(settings)

    with TestClient(app) as client:
        # Preflight OPTIONS request for approved origin
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://app.jplearn.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://app.jplearn.com"
        assert resp.headers.get("access-control-allow-credentials") == "true"

        # Preflight OPTIONS request for second approved origin
        resp2 = client.options(
            "/health",
            headers={
                "Origin": "https://cms.jplearn.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp2.status_code == 200
        assert resp2.headers.get("access-control-allow-origin") == "https://cms.jplearn.com"

        # Unapproved origins MUST NOT receive permissive CORS headers
        unapproved_origins = [
            "exp://unapproved.example.com",
            "exp://localhost",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://insecure.jplearn.com",
            "https://app.jplearn.com.attacker.com",
            "https://evil-jplearn.com",
            "null",
            "*",
        ]
        for origin in unapproved_origins:
            # Preflight
            preflight = client.options(
                "/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert "access-control-allow-origin" not in preflight.headers, f"Leaked CORS header for {origin}"

            # Actual GET request
            actual = client.get("/health", headers={"Origin": origin})
            assert "access-control-allow-origin" not in actual.headers, f"Leaked CORS header for {origin} in actual GET"


def test_local_test_cors_expo_and_dynamic_ports() -> None:
    """R-02: Local/test environment permits Expo and dynamic local ports."""
    from jplearn_api.main import create_app

    settings = Settings(
        environment="test",
        database_url="postgresql://user:pass@localhost:5432/db",
        jwt_secret="a" * 32,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        # Expo origin allowed in test environment
        resp_expo = client.options(
            "/health",
            headers={
                "Origin": "exp://127.0.0.1:19000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_expo.headers.get("access-control-allow-origin") == "exp://127.0.0.1:19000"

        # Dynamic local dev port allowed in test environment
        resp_dynamic = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:38291",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_dynamic.headers.get("access-control-allow-origin") == "http://localhost:38291"



