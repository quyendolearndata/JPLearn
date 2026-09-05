"""Contract surface — port of the Nest-only parts of apps/api/test/contract.e2e-spec.ts.

The semantic schema comparison lives in test_openapi_diff.py. What is left here
is the runtime surface: every documented operation must actually be routed, and
validation failures must keep the Nest error shape rather than FastAPI's 422
`{detail}` (ADR-003 D6).
"""

from __future__ import annotations

from jplearn_api.openapi_diff import load_handwritten_spec

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
SAMPLES = {
    "{id}": "00000000-0000-4000-8000-0000000000aa",
    "{file}": "index.m3u8",
}


def _documented_operations() -> list[tuple[str, str]]:
    spec = load_handwritten_spec()
    operations = [
        (method, path)
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    ]
    assert len(operations) >= 10, f"too few OpenAPI operations parsed: {len(operations)}"
    return operations


def _sample(path: str) -> str:
    for template, value in SAMPLES.items():
        path = path.replace(template, value)
    return path


def test_every_documented_operation_is_routed(live_client):
    missing = []
    for method, path in _documented_operations():
        request_kwargs = {"json": {}} if method in ("post", "put", "patch") else {}
        response = live_client.request(method.upper(), _sample(path), **request_kwargs)
        if response.status_code == 404:
            missing.append(f"{method.upper()} {path}")

    assert not missing, "documented operations not routed: " + ", ".join(missing)


def test_empty_body_is_400_in_nest_shape(live_client):
    response = live_client.post("/auth/register", json={})

    assert response.status_code == 400
    body = response.json()
    assert body["statusCode"] == 400
    assert isinstance(body["message"], (str, list))
    assert "detail" not in body
