from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import yaml

METHODS = ("get", "post", "put", "patch", "delete")

# Paths this runtime must implement at the current port slice (Phase 3 auth + flags/catalog).
REQUIRED_OPERATIONS = {
    ("/health", "get"),
    ("/auth/register", "post"),
    ("/auth/login", "post"),
    ("/auth/logout", "post"),
    ("/me", "get"),
    ("/flags", "get"),
    ("/staff/flags", "patch"),
    ("/catalog", "get"),
    ("/staff/catalog", "post"),
    ("/staff/catalog/{id}/submit-qa", "post"),
    ("/staff/catalog/{id}/publish", "post"),
    ("/staff/catalog/{id}/unpublish", "post"),
    ("/sessions", "post"),
    ("/sessions/{id}/end", "post"),
    ("/progress", "get"),
    ("/staff/catalog/{id}/media", "post"),
    ("/media/{id}", "get"),
    ("/media/{id}/hls/{file}", "get"),
    ("/staff/media/{id}/hls", "post"),
}


def _ops(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in METHODS:
            operation = item.get(method)
            if isinstance(operation, dict):
                found[(path, method)] = operation
    return found


def normalize_security_scheme_names(spec: dict[str, Any]) -> dict[str, Any]:
    """FastAPI HTTPBearer defaults to scheme name HTTPBearer; contract uses bearerAuth."""
    components = spec.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    if "HTTPBearer" in schemes:
        schemes.setdefault("bearerAuth", schemes.pop("HTTPBearer"))
    schemes.setdefault(
        "bearerAuth",
        {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    )
    for item in (spec.get("paths") or {}).values():
        if not isinstance(item, dict):
            continue
        for operation in item.values():
            if not isinstance(operation, dict) or "security" not in operation:
                continue
            remapped = []
            for entry in operation["security"]:
                if isinstance(entry, dict) and "HTTPBearer" in entry:
                    remapped.append({"bearerAuth": entry["HTTPBearer"]})
                else:
                    remapped.append(entry)
            operation["security"] = remapped
    return spec


def _bearer(operation: dict[str, Any]) -> bool:
    for entry in operation.get("security") or []:
        if isinstance(entry, dict) and "bearerAuth" in entry:
            return True
    return False


def _statuses(operation: dict[str, Any]) -> set[str]:
    return {str(code) for code in (operation.get("responses") or {})}


def compare_openapi(handwritten: dict[str, Any], generated: dict[str, Any]) -> list[str]:
    """Semantic normalized diff. Returns human-readable problems (empty = pass)."""
    problems: list[str] = []
    generated = normalize_security_scheme_names(copy.deepcopy(generated))
    hand = _ops(handwritten)
    gen = _ops(generated)

    extras = sorted(set(gen) - set(hand))
    for path, method in extras:
        problems.append(f"extra {method.upper()} {path} not in handwritten contract")

    for key in sorted(REQUIRED_OPERATIONS):
        if key not in hand:
            problems.append(f"handwritten missing required {key[1].upper()} {key[0]}")
        if key not in gen:
            problems.append(f"generated missing required {key[1].upper()} {key[0]}")

    for key in sorted(set(hand) & set(gen)):
        path, method = key
        h_op, g_op = hand[key], gen[key]
        if h_op.get("operationId") and h_op.get("operationId") != g_op.get("operationId"):
            problems.append(
                f"{method.upper()} {path} operationId {g_op.get('operationId')!r} "
                f"!= {h_op.get('operationId')!r}",
            )
        if _bearer(h_op) != _bearer(g_op):
            problems.append(f"{method.upper()} {path} security bearerAuth mismatch")
        missing_status = _statuses(h_op) - _statuses(g_op)
        # Generated may omit error statuses we still document; 2xx must exist.
        missing_2xx = {code for code in missing_status if code.startswith("2")}
        if missing_2xx:
            problems.append(f"{method.upper()} {path} missing 2xx {sorted(missing_2xx)}")
        h_fr = h_op.get("x-jplearn-fr") or []
        g_fr = g_op.get("x-jplearn-fr") or []
        if h_fr and list(h_fr) != list(g_fr):
            problems.append(f"{method.upper()} {path} x-jplearn-fr {g_fr} != {h_fr}")
        if (h_op.get("requestBody") or {}).get("required") and not g_op.get("requestBody"):
            problems.append(f"{method.upper()} {path} missing requestBody")

    return problems


def handwritten_spec_path() -> Path:
    return Path(__file__).resolve().parents[4] / "docs" / "sad" / "03-design" / "openapi.yaml"


def load_handwritten_spec(path: Path | None = None) -> dict[str, Any]:
    target = path or handwritten_spec_path()
    with target.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"OpenAPI YAML is not a mapping: {target}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    del argv
    from jplearn_api.main import create_app
    from jplearn_api.settings import Settings

    settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret",
        openapi_ui=False,
    )
    problems = compare_openapi(load_handwritten_spec(), create_app(settings).openapi())
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
