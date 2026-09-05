"""HTTP contract normalization shared by runtime and contract tooling."""

from typing import Any


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
    schemes.setdefault(
        "signedQuery",
        {
            "type": "apiKey",
            "in": "query",
            "name": "sig",
            "description": "HMAC-SHA256 signature for media streaming (with exp timestamp)",
        },
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
