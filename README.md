# JPLearn

Nền tảng thụ đắc tiếng Nhật (người lớn, input dễ hiểu). Web + Expo (iPhone/iPad/Android) dùng một API.

Backend là **FastAPI/Python** (`apps/api-python`) và sở hữu cả DDL qua Alembic —
xem [ADR-003](docs/sad/03-design/adr-003-runtime-python.md) và
[ADR-004](docs/sad/03-design/adr-004-ddl-alembic.md). NestJS đã retire.

## Prerequisites

- Python 3.12 + [`uv`](https://docs.astral.sh/uv/)
- Node.js 22 + pnpm 9 (`corepack enable`) — cho web, mobile, guard FR-NEG
- Docker Desktop/Engine với Docker Compose

## Setup

```bash
docker compose up -d db
cp apps/api-python/.env.example apps/api-python/.env
pnpm install
uv --directory apps/api-python sync
pnpm db:migrate
pnpm db:seed
```

Seed admin: `admin@jplearn.local` / `password10`

DB đã có schema từ Prisma (trước ADR-004) thì nhận nó thay vì dựng lại:

```bash
cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.migrate stamp 0001_prisma_baseline
```

## Run

```bash
# API :3002
export JWT_SECRET=dev-only-change-me DATABASE_URL=postgresql://jplearn:jplearn@localhost:5432/jplearn API_PUBLIC_URL=http://localhost:3002
pnpm dev:api

pnpm dev:web          # http://localhost:3000
pnpm dev:mobile       # Expo
```

Web và Expo cần `NEXT_PUBLIC_API_URL` / `EXPO_PUBLIC_API_URL` trỏ `:3002`.
Cùng một tài khoản trên web và Expo chia sẻ catalog và `minutes_comprehensible` (FR-PRG-004).

## Tests

Pytest tự dựng PostgreSQL 16 cô lập bằng service Docker `db-test`, chạy Alembic
migration và xóa Compose project test khi xong. DB dev `jplearn` không bị reset.

```bash
pnpm test:guard
pnpm test:api                     # = uv --directory apps/api-python run pytest
pnpm --filter @jplearn/domain test
pnpm --filter @jplearn/mobile test
```

Web E2E chạy trên DB test riêng, API + web thật, có cả nội dung HLS thật:

```bash
apps/api-python/differential/web-e2e-python.sh                     # chromium + webkit
apps/api-python/differential/web-e2e-python.sh --project=chromium
```

Muốn dựng tay thì `differential/db.py up|url|down` thay cho harness Node cũ.

Evidence parity Nest↔FastAPI (40/40) đóng băng ở
[`docs/qa/differential/2026-09-04T071945Z-parity.json`](docs/qa/differential/2026-09-04T071945Z-parity.json);
chạy lại `differential/run_parity.py` cần checkout commit còn `apps/api`.

Media Q1 is MP4 on local disk, not HLS. See [docs/sad/03-design/runbook-publish.md](docs/sad/03-design/runbook-publish.md).
