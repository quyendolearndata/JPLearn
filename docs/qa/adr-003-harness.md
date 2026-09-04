# ADR-003 — Harness + contract baseline (2026-09-04)

Ghế: Platform / QA · Harness Docker `db-test` **ổn định trên máy founder**.

Harness Node đã **xoá** cùng `apps/api` (`test/docker-postgres.cjs`, `test/docker-db.cjs`, `test/global-setup.cjs`). Muốn đọc bản cũ: `git checkout 7a05e62`. Dưới đây là hiện trạng, không phải kế hoạch.

## Pytest API

`uv run pytest` trong `apps/api-python`:

- **54/54 PASS** (lần chạy 2026-09-04), gồm contract + vectors + schema DDL.
- Harness: `apps/api-python/tests/pg_harness.py` — `docker compose --profile test up db-test` trong project riêng, chờ `pg_isready`, đọc port động, rồi migrate.
- **DDL do Alembic sở hữu** (ADR-004): `jplearn-migrate upgrade|stamp`. Dữ liệu mẫu: `jplearn-seed`. **Không** `create_all`, **không** `prisma migrate` — Prisma không còn dính vào đường test.
- Guard DB: `assert_test_database_url` chỉ cho pathname `/jplearn_test`. Chạy trúng DB khác → raise, không «cẩn thận nhé».
- Tái dùng DB có sẵn nếu `JPLEARN_TEST_DATABASE_URL` / `DATABASE_URL` trỏ `/jplearn_test` và connect được; nếu không thì tự dựng Docker theo PID.

CI: job `api-python` dùng `JPLEARN_TEST_DATABASE_URL` (Postgres service `jplearn_test`). Không còn job Jest.

Web E2E: `apps/api-python/differential/db.py up|down|url` — Compose project `jplearn-web-e2e`, Alembic + seed, in `E2E_DB_READY <url>`; `down` chỉ hạ project đó nên DB dev `jplearn` không bị đụng.

## Chống drift schema

`docs/qa/adr-004-schema-baseline.json` + `apps/api-python/tests/test_schema_ddl.py` — **5 test PASS**. Phủ cả T-NEG-004: `information_schema` không được có cột textbook, và scanner `scripts/assert-no-textbook.ts` phải **đỏ** khi cột cấm xuất hiện trong file `.py`.

## Contract

`contract.e2e-spec.ts` đã chết cùng `apps/api`. Nay tách hai file:

- `apps/api-python/tests/test_contract.py` — bề mặt runtime: **mọi** operation trong `docs/sad/03-design/openapi.yaml` phải được route (không 404); body rỗng → **400 shape Nest** (`{statusCode,message}`), **không** 422 `{detail}` (ADR-003 D6).
- `apps/api-python/tests/test_openapi_diff.py` — semantic normalized diff spec tay ↔ spec FastAPI sinh ra (`compare_openapi` phải trả `[]`), cộng `/docs` `/redoc` `/openapi.json` đều 404.

Baseline Nest từng xanh **trước** khi xoá (mục 2 §7 checklist = ĐẠT). Từ nay không so được hai runtime nữa: `differential/run_parity.py` còn trong repo nhưng **fail sớm**, thông báo trỏ về `7a05e62`.
