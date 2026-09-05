from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any

import yaml

METHODS = ("get", "post", "put", "patch", "delete")

REQUIRED_OPERATIONS = {
    ("/health", "get"),
    ("/ready", "get"),
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

ALLOWED_MIDDLEWARE_HEADERS = {"x-request-id", "traceparent"}


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


def normalize_security(security_list: list[dict[str, list[str]]] | None) -> list[dict[str, list[str]]]:
    if not security_list:
        return []
    normalized = []
    for entry in security_list:
        if isinstance(entry, dict):
            normalized.append({k: sorted(v) for k, v in sorted(entry.items())})
    return sorted(normalized, key=lambda d: str(sorted(d.items())))


def _statuses(operation: dict[str, Any]) -> set[str]:
    return {str(code) for code in (operation.get("responses") or {})}


def lookup_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    parts = ref.strip("#/").split("/")
    curr: Any = spec
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return {}
    return copy.deepcopy(curr) if isinstance(curr, dict) else {}


def resolve_schema(
    spec: dict[str, Any],
    schema: dict[str, Any] | None,
    seen: set[str] | None = None,
    problems: list[str] | None = None,
    ctx: str = "",
) -> dict[str, Any]:
    if not schema or not isinstance(schema, dict):
        return {}
    if seen is None:
        seen = set()

    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in seen:
            return {}
        seen.add(ref)
        resolved = lookup_ref(spec, ref)
        if not resolved:
            if problems is not None:
                problems.append(f"{ctx}: undefined $ref {ref!r}")
            return {}
        return resolve_schema(spec, resolved, seen, problems, ctx)

    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for sub in schema["allOf"]:
            res_sub = resolve_schema(spec, sub, seen, problems, ctx)
            if "properties" in res_sub:
                merged["properties"].update(res_sub["properties"])
            if "required" in res_sub:
                merged["required"].extend(res_sub["required"])
            if "type" in res_sub and res_sub["type"] != "object":
                merged["type"] = res_sub["type"]
        merged["required"] = sorted(set(merged["required"]))
        return merged

    res = copy.deepcopy(schema)

    # Convert OpenAPI 3.1 const to enum
    if "const" in res and "enum" not in res:
        res["enum"] = [res["const"]]

    # OpenAPI 3.1 type union / anyOf normalization:
    t = res.get("type")
    if isinstance(t, list):
        if "null" in t:
            non_null = [item for item in t if item != "null"]
            res["type"] = non_null[0] if len(non_null) == 1 else non_null
            res["nullable"] = True
    if "anyOf" in res:
        any_of = res["anyOf"]
        has_null = any(isinstance(sub, dict) and sub.get("type") == "null" for sub in any_of)
        non_null_subs = [sub for sub in any_of if not (isinstance(sub, dict) and sub.get("type") == "null")]
        if has_null and len(non_null_subs) == 1:
            res_inner = resolve_schema(spec, non_null_subs[0], seen, problems, ctx)
            del res["anyOf"]
            res.update(res_inner)
            res["nullable"] = True

    return res


def compare_schemas(
    h_spec: dict[str, Any],
    g_spec: dict[str, Any],
    h_raw: dict[str, Any] | None,
    g_raw: dict[str, Any] | None,
    ctx: str,
) -> list[str]:
    problems: list[str] = []
    h = resolve_schema(h_spec, h_raw, problems=problems, ctx=f"{ctx}(handwritten)")
    g = resolve_schema(g_spec, g_raw, problems=problems, ctx=f"{ctx}(generated)")

    if not h:
        return problems
    if not g:
        problems.append(f"{ctx}: missing schema in generated spec")
        return problems

    # Missing type in schema
    if "type" not in g and not any(k in g for k in ("anyOf", "oneOf", "allOf", "$ref")):
        problems.append(f"{ctx}: missing 'type' in generated schema")
    if "type" not in h and not any(k in h for k in ("anyOf", "oneOf", "allOf", "$ref")):
        problems.append(f"{ctx}: missing 'type' in handwritten schema")

    h_type = h.get("type")
    g_type = g.get("type")
    if h_type and g_type and h_type != g_type:
        problems.append(f"{ctx}: type mismatch: generated {g_type!r} != handwritten {h_type!r}")

    # Enums check - case-sensitive and type-preserving (distinguish bool from int)
    if "enum" in h:
        if "enum" not in g:
            problems.append(f"{ctx}: missing enum in generated schema")
        else:
            h_enum = set((type(x).__name__, x) for x in h["enum"])
            g_enum = set((type(x).__name__, x) for x in g.get("enum", []))
            if h_enum != g_enum:
                problems.append(
                    f"{ctx}: enum mismatch: generated {sorted(f'{t}:{v}' for t, v in g_enum)} != handwritten {sorted(f'{t}:{v}' for t, v in h_enum)}"
                )
    elif "enum" in g:
        problems.append(f"{ctx}: unexpected enum in generated schema: {g.get('enum')}")

    # Minimum check
    if "minimum" in h:
        g_min = g.get("minimum")
        if g_min is None:
            problems.append(f"{ctx}: missing minimum (expected {h['minimum']})")
        elif g_min != h["minimum"]:
            problems.append(f"{ctx}: minimum mismatch: generated {g_min} != handwritten {h['minimum']}")
    elif "minimum" in g:
        problems.append(f"{ctx}: unexpected minimum in generated schema: {g.get('minimum')}")

    # Maximum check
    if "maximum" in h:
        g_max = g.get("maximum")
        if g_max is None:
            problems.append(f"{ctx}: missing maximum (expected {h['maximum']})")
        elif g_max != h["maximum"]:
            problems.append(f"{ctx}: maximum mismatch: generated {g_max} != handwritten {h['maximum']}")
    elif "maximum" in g:
        problems.append(f"{ctx}: unexpected maximum in generated schema: {g.get('maximum')}")

    # MinLength check: bi-directional exact comparison
    if "minLength" in h:
        g_min_len = g.get("minLength")
        if g_min_len is None:
            problems.append(f"{ctx}: missing minLength (expected {h['minLength']})")
        elif g_min_len != h["minLength"]:
            problems.append(f"{ctx}: minLength mismatch: generated {g_min_len} != handwritten {h['minLength']}")
    elif "minLength" in g:
        problems.append(f"{ctx}: unexpected minLength in generated schema: {g.get('minLength')}")

    # MaxLength check: bi-directional exact comparison
    if "maxLength" in h:
        g_max_len = g.get("maxLength")
        if g_max_len is None:
            problems.append(f"{ctx}: missing maxLength (expected {h['maxLength']})")
        elif g_max_len != h["maxLength"]:
            problems.append(f"{ctx}: maxLength mismatch: generated {g_max_len} != handwritten {h['maxLength']}")
    elif "maxLength" in g:
        problems.append(f"{ctx}: unexpected maxLength in generated schema: {g.get('maxLength')}")

    # Pattern check: cannot be omitted or mismatched
    if "pattern" in h:
        g_pattern = g.get("pattern")
        if not g_pattern:
            problems.append(f"{ctx}: missing pattern (expected {h['pattern']!r})")
        elif g_pattern != h["pattern"]:
            problems.append(f"{ctx}: pattern mismatch: generated {g_pattern!r} != handwritten {h['pattern']!r}")
    elif "pattern" in g:
        problems.append(f"{ctx}: unexpected pattern in generated schema: {g.get('pattern')!r}")

    # Format check (uuid, email, date-time, uri, etc.)
    if "format" in h and h["format"] not in ("binary",):
        g_fmt = g.get("format")
        if g_fmt != h["format"]:
            problems.append(f"{ctx}: format mismatch: generated {g_fmt!r} != handwritten {h['format']!r}")

    # Nullable check
    h_null = bool(h.get("nullable", False))
    g_null = bool(g.get("nullable", False))
    if h_null != g_null:
        problems.append(f"{ctx}: nullable mismatch: generated {g_null} != handwritten {h_null}")

    # AdditionalProperties check
    if "additionalProperties" in h:
        h_add = h["additionalProperties"]
        g_add = g.get("additionalProperties")
        if g_add is not None and g_add != h_add:
            problems.append(f"{ctx}: additionalProperties mismatch: generated {g_add} != handwritten {h_add}")
        elif h_add is False and g_add is not False:
            problems.append(f"{ctx}: additionalProperties mismatch: generated {g_add} != handwritten False")

    # Required fields check
    h_req = set(h.get("required", []))
    g_req = set(g.get("required", []))
    missing_req = h_req - g_req
    if missing_req:
        problems.append(f"{ctx}: missing required fields {sorted(missing_req)}")
    extra_req = g_req - h_req
    if extra_req:
        problems.append(f"{ctx}: extra required fields {sorted(extra_req)}")

    # Properties check
    h_props = h.get("properties", {})
    g_props = g.get("properties", {})
    for prop_name, h_prop in h_props.items():
        if prop_name not in g_props:
            problems.append(f"{ctx}: missing property {prop_name!r}")
            continue
        g_prop = g_props[prop_name]
        problems.extend(
            compare_schemas(h_spec, g_spec, h_prop, g_prop, f"{ctx}.{prop_name}")
        )
    extra_props = sorted(set(g_props) - set(h_props))
    for prop_name in extra_props:
        problems.append(f"{ctx}: extra property {prop_name!r} not in contract")

    # Array items check
    if h_type == "array" and "items" in h:
        if "items" not in g:
            problems.append(f"{ctx}: array missing items schema")
        else:
            problems.extend(
                compare_schemas(h_spec, g_spec, h["items"], g["items"], f"{ctx}[]")
            )

    return problems


def compare_openapi(handwritten: dict[str, Any], generated: dict[str, Any]) -> list[str]:
    """Semantic normalized diff. Returns human-readable problems (empty = pass)."""
    problems: list[str] = []
    generated = normalize_security_scheme_names(copy.deepcopy(generated))
    hand = _ops(handwritten)
    gen = _ops(generated)

    extras = sorted(set(gen) - set(hand))
    for path, method in extras:
        problems.append(f"extra {method.upper()} {path} not in handwritten contract")

    missing = sorted(set(hand) - set(gen))
    for path, method in missing:
        problems.append(f"missing {method.upper()} {path} in generated spec")

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

        # Security structure comparison
        h_sec = normalize_security(h_op.get("security"))
        g_sec = normalize_security(g_op.get("security"))
        if h_sec != g_sec:
            problems.append(f"{method.upper()} {path} security mismatch: generated {g_sec} != handwritten {h_sec}")

        # Responses comparison
        h_statuses = _statuses(h_op)
        g_statuses = _statuses(g_op)
        missing_statuses = sorted(h_statuses - g_statuses)
        if missing_statuses:
            problems.append(f"{method.upper()} {path} missing responses {missing_statuses}")
        extra_statuses = sorted(g_statuses - h_statuses)
        if extra_statuses:
            problems.append(f"{method.upper()} {path} extra responses {extra_statuses} not in contract")

        h_fr = h_op.get("x-jplearn-fr") or []
        g_fr = g_op.get("x-jplearn-fr") or []
        if h_fr and list(h_fr) != list(g_fr):
            problems.append(f"{method.upper()} {path} x-jplearn-fr {g_fr} != {h_fr}")

        # Parameters comparison
        h_params: dict[tuple[str, str], dict[str, Any]] = {}
        for p in h_op.get("parameters") or []:
            if isinstance(p, dict):
                if "$ref" in p:
                    p = lookup_ref(handwritten, p["$ref"])
                h_params[(p.get("name", ""), p.get("in", ""))] = p

        g_params: dict[tuple[str, str], dict[str, Any]] = {}
        for p in g_op.get("parameters") or []:
            if isinstance(p, dict):
                if "$ref" in p:
                    p = lookup_ref(generated, p["$ref"])
                g_params[(p.get("name", ""), p.get("in", ""))] = p

        # Check for extra parameters in generated spec (bi-directional check)
        for (p_name, p_in), g_p in g_params.items():
            if (p_name, p_in) not in h_params:
                if p_in == "header" and p_name.lower() in ALLOWED_MIDDLEWARE_HEADERS:
                    continue
                req_prefix = "required " if g_p.get("required") else ""
                problems.append(
                    f"{method.upper()} {path} extra {req_prefix}{p_in} parameter {p_name!r} not in contract"
                )

        # Check for missing parameters and validate matching parameters
        for (p_name, p_in), h_p in h_params.items():
            if (p_name, p_in) not in g_params:
                if p_in == "header" and p_name.lower() in ALLOWED_MIDDLEWARE_HEADERS:
                    continue
                problems.append(f"{method.upper()} {path} missing parameter {p_name!r} in {p_in}")
                continue
            g_p = g_params[(p_name, p_in)]
            h_req = h_p.get("required", p_in == "path")
            g_req = g_p.get("required", False)
            if h_req != g_req:
                problems.append(f"{method.upper()} {path} parameter {p_name!r} required {g_req} != {h_req}")
            h_schema = resolve_schema(handwritten, h_p.get("schema"), problems=problems, ctx=f"{method.upper()} {path} param({p_name})")
            g_schema = resolve_schema(generated, g_p.get("schema"), problems=problems, ctx=f"{method.upper()} {path} param({p_name})")
            if p_in == "query" and not h_req:
                # Query parameters are absent rather than null in URL query strings
                h_schema.pop("nullable", None)
                g_schema.pop("nullable", None)
            problems.extend(
                compare_schemas(
                    handwritten,
                    generated,
                    h_schema,
                    g_schema,
                    f"{method.upper()} {path} param({p_name})",
                )
            )

        # RequestBody comparison
        h_rb = h_op.get("requestBody")
        g_rb = g_op.get("requestBody")
        if h_rb:
            if not g_rb:
                problems.append(f"{method.upper()} {path} missing requestBody")
            else:
                if h_rb.get("required") and not g_rb.get("required"):
                    problems.append(f"{method.upper()} {path} requestBody required mismatch")
                h_content = h_rb.get("content", {})
                g_content = g_rb.get("content", {})
                for c_type, h_media in h_content.items():
                    if c_type not in g_content:
                        problems.append(f"{method.upper()} {path} missing content-type {c_type!r}")
                        continue
                    g_media = g_content[c_type]
                    problems.extend(
                        compare_schemas(
                            handwritten,
                            generated,
                            h_media.get("schema"),
                            g_media.get("schema"),
                            f"{method.upper()} {path} requestBody[{c_type}]",
                        )
                    )
                for c_type in sorted(set(g_content) - set(h_content)):
                    problems.append(f"{method.upper()} {path} requestBody extra content-type {c_type!r} not in contract")
        elif g_rb:
            problems.append(f"{method.upper()} {path} extra requestBody in generated spec")

        # All declared responses comparison (bi-directional content and schema)
        for status_code in sorted(h_statuses & g_statuses):
            h_resp = h_op.get("responses", {}).get(status_code) or {}
            g_resp = g_op.get("responses", {}).get(status_code) or {}
            h_content = (h_resp or {}).get("content", {})
            g_content = (g_resp or {}).get("content", {})

            # Content types comparison
            missing_ct = sorted(set(h_content) - set(g_content))
            if missing_ct:
                problems.append(f"{method.upper()} {path} response({status_code}) missing content-type {missing_ct}")
            extra_ct = sorted(set(g_content) - set(h_content))
            if extra_ct:
                problems.append(f"{method.upper()} {path} response({status_code}) extra content-type {extra_ct} not in contract")

            for content_type in sorted(set(h_content) & set(g_content)):
                h_schema = h_content[content_type].get("schema")
                g_schema = g_content[content_type].get("schema")
                if h_schema is not None and g_schema is None:
                    problems.append(
                        f"{method.upper()} {path} response({status_code})[{content_type}]: missing schema in generated spec"
                    )
                elif g_schema is not None and h_schema is None:
                    problems.append(
                        f"{method.upper()} {path} response({status_code})[{content_type}]: extra schema in generated spec not in contract"
                    )
                elif h_schema is not None and g_schema is not None:
                    problems.extend(
                        compare_schemas(
                            handwritten,
                            generated,
                            h_schema,
                            g_schema,
                            f"{method.upper()} {path} response({status_code})[{content_type}]",
                        )
                    )

    return problems


def handwritten_spec_path() -> Path:
    env_spec = os.environ.get("OPENAPI_SPEC_PATH")
    if env_spec:
        p = Path(env_spec)
        if p.exists():
            return p
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = curr / "docs" / "sad" / "03-design" / "openapi.yaml"
        if candidate.is_file():
            return candidate
        if curr.parent == curr:
            break
        curr = curr.parent
    raise FileNotFoundError("Could not locate handwritten OpenAPI contract 'docs/sad/03-design/openapi.yaml'")


def load_handwritten_spec(path: Path | None = None) -> dict[str, Any]:
    target = path or handwritten_spec_path()
    with target.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"OpenAPI YAML is not a mapping: {target}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare handwritten and generated OpenAPI specs.")
    parser.add_argument("--handwritten", type=str, default=None, help="Path to handwritten openapi.yaml")
    parser.add_argument("--generated", type=str, default=None, help="Path to generated openapi spec")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    handwritten_path = Path(args.handwritten) if args.handwritten else handwritten_spec_path()
    handwritten = load_handwritten_spec(handwritten_path)

    if args.generated:
        gen_path = Path(args.generated)
        with gen_path.open(encoding="utf-8") as f:
            if gen_path.suffix in (".yaml", ".yml"):
                generated = yaml.safe_load(f)
            else:
                generated = json.load(f)
    else:
        from jplearn_api.main import create_app
        from jplearn_api.settings import Settings

        settings = Settings(
            database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
            jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
            openapi_ui=False,
        )
        generated = create_app(settings).openapi()

    problems = compare_openapi(handwritten, generated)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
