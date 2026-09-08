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

Implementation: `apps/api-python/src/jplearn_api/tooling/openapi_diff.py`.
Port đã hoàn tất: so toàn bộ operations, không áp quy tắc subset của giai đoạn
partial port. Hiện runtime/contract có 20 operations; docs UI không thuộc số này.
So cả request/response schemas, parameters, content types và constraints với
mutation tests; zero diff không chứng minh mọi validation/runtime case đều đúng.

Từ repo root:

```bash
cd apps/api-python
PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff
uv run pytest tests/test_openapi_diff.py tests/test_openapi_mutation_suite.py -q
```

Console `jplearn-openapi-diff` giữ nguyên trong bản cài package. Docker image không
chứa YAML contract của repo; khi diff ngoài checkout, truyền `--handwritten` trỏ
file contract đã mount, hoặc `OPENAPI_SPEC_PATH`. HTTP runtime không import diff tool;
normalization dùng chung nằm trong `entrypoints/http/openapi.py`.
