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
        jwt_secret="test-secret",
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
    assert payload["message"] == "boom"
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
