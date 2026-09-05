# Bằng chứng issue #17 — UC-L06 đồng bộ thiết bị trên các bề mặt

> Tài liệu lịch sử: lần kiểm chứng này từng dùng embedded PostgreSQL. Workflow
> hiện tại chỉ dùng Docker PostgreSQL qua Compose `db-test`.

- Ghế: **QA Engineering** · Ngày: 2026-08-25 · Issue: [#17](https://github.com/quyendolearndata/JPLearn/issues/17)
- Use case: **UC-L06** (đồng bộ thiết bị) — `docs/sad/02-analysis/use-cases.md` dòng 45–47
- Test ID (theo `docs/sad/03-design/traceability.md`): **T-ID-002** (cùng token schema 3 client, FR-ID-002), **T-PRG-004** (GET /progress, FR-PRG-004); liên quan **NFR-XPLAT-001 / T-NFR-X1** (3 client 1 API)
- Kết luận: **PASS cho phần logic + web UI thật. PARTIAL cho toàn bộ issue** — UI native iPhone/iPad/Android chưa chạy được trong môi trường này (không simulator), xem mục "Chưa chứng minh".

## ĐÃ chứng minh (lệnh + output)

### 1. Logic/API — 1 user, 3 phiên client độc lập (T-ID-002, T-PRG-004) → PASS

Test mới `apps/api/test/sync.e2e-spec.ts` — mô phỏng 3 client web/phone/ipad bằng 3 token độc lập (1 register + 2 login) của cùng tài khoản, DB embedded Postgres thật:

- Cả 3 token: `GET /me` → cùng `user.id`, cùng email (FR-ID-002).
- Cả 3 token: `GET /catalog` → body **deep-equal**, chứa item published, không chứa item draft.
- Client "phone": `POST /sessions {device_class:"phone"}` → kết thúc sau 180s → `minutes_comprehensible = 3`. Client "web" và "ipad" đọc `GET /progress` → cùng `{minutes_comprehensible: 3, current_ci_level: 0}` (FR-PRG-004).
- Chiều ngược: client "ipad" học thêm 60s → web + phone đọc lại thấy `4` (đồng bộ hai chiều, server-side).
- `device_class`: bảng `devices` có đúng 3 dòng `web/phone/ipad` cho user; `learner_progress` đúng **1 dòng** theo `userId` → tiến độ gắn user, **không** gắn thiết bị (schema: `DeviceClass` enum web/phone/ipad, `@@unique([userId, deviceClass])`, `LearnerProgress` khóa chính là `userId`).

```bash
cd apps/api && JWT_SECRET=test-secret NODE_OPTIONS=--experimental-vm-modules npx jest sync.e2e-spec --runInBand
```

```
PASS test/sync.e2e-spec.ts
  UC-L06 sync devices (T-ID-002, T-PRG-004)
    ✓ same identity, same published catalog, same progress across web/phone/ipad (159 ms)
Test Suites: 1 passed, 1 total
```

Toàn bộ API suite (không hồi quy): `npx jest --runInBand` → **9 suites, 23/23 tests passed** (gồm neg/catalog/auth/flags/sessions/media/health/schema.guard/sync).

### 2. Web UI THẬT — 2 browser profile, phiên học thật (UC-L06) → PASS

Test mới `apps/web/e2e/sync.spec.ts` chạy trên stack thật: web `next dev` :3000 + API :3001 + Postgres thật (embedded, đã migrate + seed). Hai browser context riêng biệt = hai "client": **Desktop Chrome** (web) và **iPhone 13 emulation** (đứng ra cho phone web — KHÔNG phải thiết bị iOS thật):

- Client A (desktop) đăng ký qua UI; client B (iPhone emu) **đăng nhập cùng tài khoản** → catalog render giống hệt nhau (so sánh danh sách `li`), progress cùng `0 phút · cấp 0`.
- Client B chạy phiên **thật ~65s** qua UI → "Kết thúc phiên" → cả A và B đều thấy `1 phút · cấp 0`.
- Chiều ngược: client A chạy phiên ~65s → cả hai thấy `2 phút · cấp 0`.

```bash
cd apps/web && npx playwright test        # cần API :3001 + web :3000 đang chạy
```

```
✓ 1 e2e/shell.spec.ts:20:5 › login and progress have no grammar chrome T-FLG-002 T-NEG-002 (1.2s)
✓ 3 e2e/shell.spec.ts:31:5 › catalog shows published seed item, hides draft T-CAT-002 T-FLG-002 (494ms)
✓ 2 e2e/sync.spec.ts:10:5 › UC-L06 cùng user hai client: cùng catalog published, cùng minutes_comprehensible (2.2m)
  3 passed (2.2m)
```

### 3. Guard + mobile unit → PASS

- `npx tsx scripts/assert-no-textbook.ts` (test:guard) → exit 0 (không route/cột textbook).
- `apps/mobile`: `npx jest` → `deviceClass.test.ts` PASS — "NFR-XPLAT-002 ipad vs phone" (ipad khi iOS + cạnh ngắn ≥ 768, ngược lại phone).

### 4. Mobile dùng đúng chung API (đọc code, không chạy app)

- `apps/mobile/src/api.ts`: cùng kiểu `fetch(base + path, Bearer token)` như web (`apps/web/src/lib/api.ts`); base từ `EXPO_PUBLIC_API_URL` / `NEXT_PUBLIC_API_URL` → cùng một API (NFR-XPLAT-001).
- `apps/mobile/app/(tabs)/session.tsx`: `POST /sessions { device_class: deviceClassFrom(...) }` → `phone` hoặc `ipad`; `POST /sessions/:id/end`.
- `apps/mobile/app/(tabs)/catalog.tsx` → `GET /catalog`; `progress.tsx` → `GET /progress`; `login.tsx` → `POST /auth/login` lưu `access_token`.
- Vì tiến độ nằm ở server theo `userId` (mục 1), mobile native đăng nhập cùng tài khoản sẽ đọc cùng giá trị — không có code path nào khác.

## CHƯA chứng minh (cần thiết bị/simulator — không giả vờ)

| Hạng mục | Trạng thái | Lý do |
|---|---|---|
| App iPhone/iPad thật (Expo iOS) | **Chưa** | Môi trường không có Xcode simulator / thiết bị; yêu cầu chạy `pnpm dev:mobile` + Expo Go/simulator |
| App Android thật | **Chưa** | Không có Android SDK/emulator trong phiên |
| Layout iPad ≠ scaled phone (NFR-XPLAT-002, T-NFR-X2 visual) | **Chưa** | Cần render thật trên iPad/simulator; mới chỉ cover ở unit test `deviceClass` (phone vs ipad) |
| iPhone 13 emulation trong Playwright | Đã chạy, nhưng chỉ là **viewport/UA emulation**, không thay thế thiết bị thật | — |

## Sự cố môi trường trong phiên (không phải lỗi logic)

- Đầu phiên: API dev :3001 đang chạy nhưng DB theo `.env` không sống → mọi endpoint DB trả **500** (phát hiện qua `POST /auth/register`). Đây là lý do lần chạy Playwright đầu tiên fail ở bước đăng ký.
- Tôi tự dựng stack e2e riêng (embedded PG :55444 qua `apps/api/test/dev-db.cjs` + API test :3001) nhưng process API test bị SIGKILL giữa chừng và stack dev được một phiên QA song song (issue #14) khôi phục/cấu hình lại trong lúc chạy → token đổi secret → 401 giữa test.
- Lần chạy PASS cuối cùng dùng stack dev ổn định tại thời điểm chạy: web :3000, API :3001 (tsx + `.env`), DB embedded :55444 (`dev-db.cjs`, đã migrate + seed). Tôi đã khởi động lại `dev-db.cjs` sau khi dọn dẹp để stack dev của người dùng không bị gián đoạn (verify: `/health` ok, register 201).

## Files thêm trong issue này (chưa commit)

- `apps/api/test/sync.e2e-spec.ts` — T-ID-002 / T-PRG-004 ở tầng API.
- `apps/web/e2e/sync.spec.ts` — UC-L06 trên web UI thật, 2 browser profile.
- `apps/api/test/dev-db.cjs` — dùng lại file đã có sẵn trong repo (nội dung ghi đè giống hệt bản đã commit, `git status` sạch với file này).

Không commit, không push.
