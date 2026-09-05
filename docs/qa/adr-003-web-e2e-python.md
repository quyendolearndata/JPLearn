# ADR-003 Phase 4 — Web E2E trỏ API Python (QA Engineering, 2026-09-04)

Kèm: [ADR-003](../sad/03-design/adr-003-runtime-python.md), [parity checklist](./adr-003-parity-checklist.md) §5.

## Kết luận

**PASS 10/10 trên stack thuần Python** — lần chạy mới nhất, sau khi `apps/api` bị xoá:

| Runtime | Chromium | WebKit | Tổng |
|---|---|---|---|
| FastAPI (`apps/api-python`) | 5/5 | 5/5 | **10/10** |
| Nest (baseline lịch sử) | 5/5 | 5/5 | **10/10** — chạy trước khi xoá, **không tái hiện được trên HEAD** |

Gồm: T-ID-002 + T-PRG-004 (sync.spec UC-L06, phiên thật 2×65s), T-NFR-P2 (hls.spec — **HLS phát thật**, `readyState ≥ 1`), T-CAT-002 + T-FLG-002 (shell.spec), T-NFR-A1 (a11y.spec axe AA + document title).

## Harness

`apps/api-python/differential/web-e2e-python.sh` (idempotent, trap cleanup):

1. `differential/db.py up` → Docker Postgres riêng (Compose project `jplearn-web-e2e`), **Alembic migrate + seed** theo ADR-004 (không đụng DB dev). Bản Node `apps/api/test/docker-db.cjs` đã xoá.
2. FastAPI trên :3002 (uvicorn), `JWT_SECRET=test-secret`, `STORAGE_ROOT` tạm. **Không còn `RUNTIME=nest`** — chỉ còn một backend.
3. Dựng nội dung thật qua API: login `admin@jplearn.local` → upload `media/stock/mp4/level-0-wash-hands.mp4` vào item seed `00000000-0000-4000-8000-0000000000c1` → submit-qa → publish → ffmpeg transcode (codec copy, hls_time 4) → `POST /staff/media/:id/hls`.
4. Web **prod build** (`next build` với `NEXT_PUBLIC_API_URL=http://localhost:3002`, `next start` :3000).
5. `playwright test --project=chromium --project=webkit`.

## Flake WebKit + `next dev` (root cause đã chối)

- Triệu chứng: `page.goto()` bị interrupt bởi navigation khác (vd đi `/progress` bị giật về `/session`), **tái hiện y hệt trên Nest baseline** (đối chứng chạy trước khi retire) → không phải lệch Python.
- Nguyên nhân: on-demand compile của `next dev` trên WebKit — route chưa compile xong, commit chậm, chồng navigation.
- Vá: chạy e2e trên **prod build** (`next build && next start`) trong harness. Cả 4 test trước đây flake đều xanh ổn định sau vá.
- Ghi nhớ §5 checklist: WebKit vẫn **không** thay #30 (Expo/iPad máy thật — mở, manual). Mục 5-native đang bị **CEO override**, không phải đã đạt.

## Tái hiện

```bash
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

Baseline Nest: **không còn cách chạy trên HEAD**. Muốn tái hiện cột lịch sử phải `git checkout 7a05e62` (commit cuối còn `apps/api`) rồi dùng harness Node của commit đó.

Log server: `/tmp/jplearn-web-e2e-py-api.log`, `/tmp/jplearn-web-e2e-py-web.log`, build web `/tmp/jplearn-web-e2e-web-build.log`.
