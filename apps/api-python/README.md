# `jplearn-api` — FastAPI (ADR-003, ADR-004)

Backend **duy nhất** của JPLearn. Sở hữu luôn DDL qua Alembic từ ADR-004 — NestJS
(`apps/api`) đã retire, commit cuối còn nó là `7a05e62`.

SQLAlchemy trong `models.py` vẫn **mapping-only**: cấm `create_all`, cấm
autogenerate. Revision viết tay, khóa bởi baseline chống drift.

## Run

```bash
cd apps/api-python
uv sync
cp .env.example .env      # hoặc export thủ công
export JWT_SECRET=dev-only-change-me
export DATABASE_URL=postgresql://jplearn:jplearn@localhost:5432/jplearn
export API_PUBLIC_URL=http://localhost:3002
PYTHONPATH=src uv run uvicorn jplearn_api.main:app --reload --port 3002
```

Docs UI tắt trừ khi `OPENAPI_UI=1`.

## Migrations (ADR-004)

```bash
PYTHONPATH=src uv run python -m jplearn_api.migrate upgrade
PYTHONPATH=src uv run python -m jplearn_api.migrate current
PYTHONPATH=src uv run python -m jplearn_api.seed
```

DB đã có schema từ Prisma (trước ADR-004) thì **adopt**, đừng dựng lại — nếu
`upgrade` thẳng sẽ vỡ vì `CREATE TYPE` trên type đã tồn tại:

```bash
PYTHONPATH=src uv run python -m jplearn_api.migrate stamp 0001_prisma_baseline
```

Đổi schema thì regenerate baseline **trong cùng commit**, không nới lỏng test:

```bash
PYTHONPATH=src uv run python -m jplearn_api.schema_snapshot "$DATABASE_URL" \
  ../../docs/qa/adr-004-schema-baseline.json
```

### Vì sao mọi lệnh đều có `PYTHONPATH=src`

`uv` gắn cờ `UF_HIDDEN` của macOS lên cả cây `.venv`, và `site.addpackage` của
CPython **cố tình bỏ qua file `.pth` hidden** — nên editable install im lặng không
nằm trên `sys.path` và console script (`jplearn-migrate`, …) chết với
`ModuleNotFoundError`. `chflags nohidden` chỉ sống tới lần `uv sync` kế tiếp.
`PYTHONPATH=src` hành xử như nhau trên mọi OS; pytest đã dùng đúng cách này qua
`pythonpath = ["src"]`. `[project.scripts]` vẫn giữ cho bản cài non-editable.

## Test

```bash
# Không cần Postgres:
uv run pytest tests/test_health.py tests/test_errors.py tests/test_openapi_diff.py tests/test_vectors.py

# Toàn bộ (Alembic migrate `jplearn_test`, Docker test profile nếu chưa có URL):
JWT_SECRET=test-secret uv run pytest
```

`JPLEARN_TEST_DATABASE_URL` (pathname phải là `/jplearn_test`) được migrate rồi
dùng; không có thì pytest tự start `db-test` trong `docker-compose.yml`.

Web E2E và harness DB dùng-một-lần: `differential/web-e2e-python.sh`,
`differential/db.py up|url|down`.
