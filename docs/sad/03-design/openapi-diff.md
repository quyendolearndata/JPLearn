# OpenAPI semantic diff (ADR-003 D9)

File [openapi.yaml](openapi.yaml) (3.0.3) is the contract. FastAPI may emit 3.1.0.

## Must match

- HTTP status per operation
- `required` and nullability
- `security` (including Bearer **or** `exp`+`sig` on media/HLS)
- `operationId`
- `x-jplearn-fr`
- Error schema `HttpError` (Nest 400 `{statusCode,message,error}` — not FastAPI 422 `{detail}`)

## Allowlist (ignore)

- `openapi` 3.0.3 vs 3.1.0 (`nullable: true` vs type union)
- Generated component names
- `servers`, `info` (except forbidden-field regressions)

Contract tests **read this YAML in git**. Do not use a public `/openapi.json` on staging/prod (D8).

Implementation: `apps/api-python/src/jplearn_api/openapi_diff.py` (pytest + `uv run jplearn-openapi-diff`). During partial port, FastAPI paths must be a **subset** of this file; required ops (health + auth in Phase 3) must match.
