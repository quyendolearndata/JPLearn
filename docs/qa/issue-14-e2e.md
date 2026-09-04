# Bằng chứng issue #14 — Playwright e2e với API + web sống

> Tài liệu lịch sử: lần chạy này từng dùng embedded PostgreSQL. Workflow hiện tại
> đã chuyển sang `apps/api/test/docker-db.cjs` và Docker Compose `db-test`.

- Ghế: **QA Engineering** · Ngày: 2026-08-25 · Issue: [#14](https://github.com/quyendolearndata/JPLearn/issues/14)
- Kết luận: **PASS** — 3/3 Playwright spec xanh trên API :3001 + web :3000 thật, DB embedded Postgres thật.

## Môi trường

| Thành phần | Chi tiết |
|---|---|
| OS / Node | macOS arm64 (darwin 25.5.0) · Node v25.8.1 |
| Package manager | pnpm 9.15.0 (qua `npx pnpm@9.15.0`, pnpm chưa cài global) |
| DB test | embedded-postgres 18.4.0-beta.17, port **55444**, db `jplearn_web_e2e` — khởi động bằng `apps/api/test/dev-db.cjs` (đã migrate deploy + seed) |
| API | `pnpm dev:api` → tsx + `apps/api/.env` (DATABASE_URL trỏ 55444, JWT_SECRET=test-secret, API_PUBLIC_URL=http://localhost:3001), listen :3001 |
| Web | `pnpm dev:web` → next dev :3000, `NEXT_PUBLIC_API_URL` mặc định http://localhost:3001 |
| Browser | Chromium Headless Shell 131.0.6778.33 (playwright build v1148) |

## Lệnh tái hiện

```bash
npx pnpm@9.15.0 install                       # một lần
node apps/api/test/dev-db.cjs &               # giữ sống; chờ "E2E_DB_READY <url>"
# apps/api/.env: DATABASE_URL=<url từ dev-db>, JWT_SECRET=test-secret, API_PUBLIC_URL=http://localhost:3001
npx pnpm@9.15.0 dev:api &                     # :3001
npx pnpm@9.15.0 dev:web &                     # :3000
npx pnpm@9.15.0 --filter @jplearn/web test:e2e
```

## Kết quả chạy

### 1. Playwright e2e — `pnpm --filter @jplearn/web test:e2e` → **3 passed (2.2m)**

```
✓ 1 e2e/shell.spec.ts:20:5 › login and progress have no grammar chrome T-FLG-002 T-NEG-002 (1.5s)
✓ 3 e2e/shell.spec.ts:31:5 › catalog shows published seed item, hides draft T-CAT-002 T-FLG-002 (532ms)
✓ 2 e2e/sync.spec.ts:10:5 › UC-L06 cùng user hai client: cùng catalog published, cùng minutes_comprehensible (2.2m)
  3 passed (2.2m)
```

| Spec | Test ID bao phủ | Xác nhận |
|---|---|---|
| shell.spec.ts test 1 | T-FLG-002, T-NEG-002 | Đăng ký qua UI → `/`, `/session`, `/progress` không có text "Ngữ pháp" / "Flashcard" / "Bản dịch"; `/progress` hiển thị "phút" |
| shell.spec.ts test 2 | T-CAT-002, T-FLG-002, FR-CAT-001 | Trang chủ catalog hiển thị item published từ seed (`daily_home · video · 30s`); item draft (`food`) **không** xuất hiện |
| sync.spec.ts | T-ID-002, T-PRG-004 (UC-L06) | Cùng user trên 2 browser context (Desktop Chrome + iPhone 13 emulation): cùng catalog published, cùng `minutes_comprehensible` sau 2 phiên thật ~65s |

### 2. Domain guard — `pnpm test:guard` → **PASS** (không `vocabulary_score` / `grammar_lesson_id` / `textbook_percent` / `translation_vi` trong apps/packages)

### 3. API jest (phục vụ regression sau khi sửa DI) — `pnpm --filter @jplearn/api test` → **10 suites, 28 tests passed**

Gồm `neg.e2e-spec.ts` (T-NEG-001/002/003: không route flashcard/grammar, không translation trên public item), `catalog.e2e-spec.ts` (T-CAT-*), `auth`, `flags`, `sessions`, `media`, `hls`, `sync`, `health`, `schema.guard`.

### 4. Web typecheck — `pnpm --filter @jplearn/web test` (tsc --noEmit) → **PASS**

### 5. Smoke API trực tiếp (curl)

- `POST /auth/register` → access_token (296 ký tự) + user roles `["learner"]`
- `GET /catalog` → đúng 1 item published; payload public chỉ gồm `id, ci_level, duration_seconds, media_type, topic_id, visual_support` — **không field dịch** (FR-CAT-004 / T-NEG-003)
- `GET /flags` → cả 4 flag `false` (T-FLG-001)

## Sửa đổi kèm theo (cần thiết để chạy thật)

1. **Root cause lớn nhất**: script `start` của API chạy qua **tsx (esbuild) — esbuild không emit `design:paramtypes`**, nên NestJS inject `undefined` vào mọi constructor → mọi route trả 500 (`TypeError: Cannot read properties of undefined (reading 'register')`). Jest không bị vì ts-jest dùng TypeScript compiler thật. Fix: thêm `@Inject(Token)` tường minh tại **17 điểm inject** trong 15 file `apps/api/src/**` (auth, catalog, flags, sessions, progress, events, media) — cách khuyến nghị của NestJS cho runner không có `emitDecoratorMetadata`. Không đổi hành vi; jest suite 28/28 vẫn xanh sau sửa.
2. **`apps/api/prisma/seed.ts`**: thêm 1 catalog item **published** (`daily_home`, ci_level 0, video 30s, visual high) và 1 item **draft** (`food`) — upsert idempotent, phục vụ đúng yêu cầu issue "seed có ít nhất một catalog item published hiển thị được" và cho phép assert draft bị ẩn.
3. **`apps/web/e2e/shell.spec.ts`**: tách helper `register`/`expectNoBannedChrome`, thêm test catalog (published hiển thị + draft ẩn), mở rộng chrome cấm sang `/session`. Email test unique theo run → deterministic, không flaky.
4. **`apps/api/.env`** (đã gitignore): trỏ embedded Postgres test.

## Ghi chú

- Screenshot: không đính kèm — việc chụp qua script ad-hoc ngoài spec bị chặn theo policy phiên; assertion trong spec đã kiểm chứng trực tiếp DOM render.
- NFR-A11Y-001 (T-NFR-A1): phần "pause/play bằng bàn phím" thuộc player Phase 5 (đang hold); phần chrome AA (contrast) chưa có đo lường tự động trong scope issue này.
- Quan sát phụ (chuyển ghế Platform/CTO, **không** sửa trong issue này): `media.service.ts`/`catalog.service.ts` tham chiếu `hlsUrl` nhưng `MediaAsset` trong `schema.prisma` chưa có cột `hls_url` — gọi `POST /staff/media/:id/hls` sẽ lỗi Prisma validation lúc runtime.
- Không commit, không push. Các tiến trình nền lúc chạy xong: embedded Postgres :55444, API :3001, web :3000.
