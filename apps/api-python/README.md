# `jplearn-api` — FastAPI (ADR-003, ADR-004)

Backend **duy nhất** của JPLearn. Sở hữu luôn DDL qua Alembic từ ADR-004 — NestJS
(`apps/api`) đã retire, commit cuối còn nó là `7a05e62`.

SQLAlchemy trong `src/jplearn_api/adapters/persistence/models.py` vẫn **mapping-only**: cấm `create_all`, cấm
autogenerate. Revision viết tay, khóa bởi baseline chống drift (ADR-006 Clean Architecture).

## Tài liệu theo công việc

- [Mục lục backend](../../docs/backend/README.md)
- [Setup, cấu trúc và quy trình phát triển](../../docs/backend/development.md)
- [Gọi API và workflow learner](../../docs/backend/api-usage.md)
- [Vận hành và cấu hình](../../docs/ops/runbook-backend.md)
- [Upload/QA/publish/HLS](../../docs/sad/03-design/runbook-publish.md)
- [Backup/restore](../../docs/ops/runbook-backup-restore.md)

## Package layout

```text
src/jplearn_api/
├── domain/                 # Business rules, entities, domain errors
├── application/            # Use-case handlers, commands, queries, ports
├── adapters/
│   ├── persistence/        # ORM, repositories, UoW, connection, schema snapshot
│   ├── security/           # Argon2, JWT, HMAC signing implementations
│   ├── storage/            # Local filesystem implementation
│   └── observability/      # Alerts and log sanitization
├── entrypoints/
│   ├── http/               # ASGI app, routers, schemas, dependencies, middleware
│   └── cli/                # Migrate, seed, reconciliation
├── config/                 # Environment provenance and resolution
├── tooling/                # OpenAPI contract comparison
├── migrations/             # Packaged Alembic revisions
├── resources/              # Packaged schema baseline
├── bootstrap.py            # Dependency composition
└── settings.py             # Validated runtime settings
```

Root module paths such as `jplearn_api.main`, `jplearn_api.migrate`,
`jplearn_api.seed`, `jplearn_api.openapi_diff`, `jplearn_api.storage` and
`jplearn_api.alert` have been removed. Use the canonical paths in this README;
there are no `sys.modules` compatibility aliases. Console command names
`jplearn-migrate`, `jplearn-seed`, `jplearn-openapi-diff` remain unchanged.
Reinstall/sync the package after updating to refresh their entrypoint metadata.
Historical QA evidence and completed plans retain the paths used at their tested
revisions; they are not current launch instructions.

This is a package-layout refactor, not a change to HTTP routes, database schema,
transaction semantics, or the outstanding operational acceptance requirements.

## Run

```bash
cd apps/api-python
uv sync
test -e .env || cp .env.example .env      # không ghi đè cấu hình sẵn có
export ENVIRONMENT=local
export JWT_SECRET=dev-only-change-me-at-least-32-bytes
export DATABASE_URL=postgresql://jplearn:jplearn@localhost:5432/jplearn
export API_PUBLIC_URL=http://localhost:3002
PYTHONPATH=src uv run uvicorn jplearn_api.entrypoints.http.app:app --reload --port 3002
```

Docs UI tắt trừ khi `OPENAPI_UI=1`.

## Migrations (ADR-004)

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate upgrade
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate current
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.seed
```

DB đã có schema từ Prisma (trước ADR-004) thì **adopt**, đừng dựng lại — nếu
`upgrade` thẳng sẽ vỡ vì `CREATE TYPE` trên type đã tồn tại:

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate stamp 0001_prisma_baseline
```

Snapshot read-only để kiểm tra schema (ghi ra artifact mới, không đè baseline Prisma):

```bash
PYTHONPATH=src uv run python -m jplearn_api.adapters.persistence.schema_snapshot "$DATABASE_URL" \
  /tmp/jplearn-current-schema.json
```

Baseline Prisma và packaged copy phục vụ adoption `0001`; không regenerate chỉ
để schema drift hết đỏ. Migration mới cần revision viết tay, FR/UC review và test
head-schema/adoption phù hợp. Xem [development](../../docs/backend/development.md).

Seed không có password admin mặc định; credentials bootstrap phải export cho
process CLI, không chỉ đặt trong `.env`. Không dùng seed để reset user có sẵn.

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
uv run pytest
```

`JPLEARN_TEST_DATABASE_URL` (pathname phải là `/jplearn_test`) được migrate rồi
dùng; không có thì pytest tự start `db-test` trong `docker-compose.yml`.

Web E2E và harness DB dùng-một-lần: `differential/web-e2e-python.sh`,
`differential/db.py up|url|down`.
