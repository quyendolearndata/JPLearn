# JPLearn

Nền tảng thụ đắc tiếng Nhật (người lớn, input dễ hiểu). Web + Expo (iPhone/iPad/Android) dùng một API.

## Prerequisites

- Node.js 22
- pnpm 9 (`corepack enable`)
- Docker (Postgres) **or** any PostgreSQL 16 at `DATABASE_URL`

## Setup

```bash
docker compose up -d db
cp apps/api/.env.example apps/api/.env
pnpm install
pnpm --filter @jplearn/api exec prisma migrate dev
pnpm db:seed
```

Seed admin: `admin@jplearn.local` / `password10`

## Run

```bash
# API :3001  (JWT_SECRET must be set; .env is loaded by Prisma, export for Nest)
export JWT_SECRET=dev-only-change-me DATABASE_URL=postgresql://jplearn:jplearn@localhost:5432/jplearn API_PUBLIC_URL=http://localhost:3001
pnpm dev:api

pnpm dev:web          # http://localhost:3000
pnpm dev:mobile       # Expo
```

Same account on web and Expo shares catalog and `minutes_comprehensible` (FR-PRG-004).

Web e2e (API + web running): `pnpm --filter @jplearn/web test:e2e`

## Tests

```bash
pnpm test:guard
pnpm --filter @jplearn/api test
pnpm --filter @jplearn/domain test
pnpm --filter @jplearn/mobile test
```

Media Q1 is MP4 on local disk, not HLS. See [docs/sad/03-design/runbook-publish.md](docs/sad/03-design/runbook-publish.md).
