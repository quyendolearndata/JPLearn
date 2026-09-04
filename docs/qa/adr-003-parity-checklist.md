# ADR-003 — Ma trận parity NestJS → FastAPI (QA sở hữu)

- Ghế: **QA Engineering** · Ngày: 2026-08-31 · Kèm: [ADR-003](../sad/03-design/adr-003-runtime-python.md)
- ADR-003 **Accepted** 2026-08-31. Checklist là điều kiện retire Nest — **QA chưa ký** file này. QA **không** thay BA trên cổng SAD-3.
- Nguồn test ID: [`traceability.md`](../sad/03-design/traceability.md) — 39 ID + `T-P5-hold`.
- Đánh giá tĩnh: **không** kế thừa PASS cũ khi harness Docker còn thay đổi chưa merge.

## 0. Nguyên tắc

1. Parity = test chạy được trên **hai runtime, hai DB clone** (seed giống; không ghi kép một DB). So: HTTP status, JSON **key-set**, nullability, error body, headers, MIME, side effect DB, file trên `STORAGE_ROOT`.
2. Contract: semantic normalized diff vs `openapi.yaml` 3.0.3 (xem ADR-003 D4). Không so YAML literal với FastAPI 3.1.0.
3. Postman / so tay **không đủ**.
4. Ô đổi trạng thái phải dán log. `PASS-Nest*` = từng xanh trong issue, **phải chạy lại** sau harness ổn định.

## 1. Critical = 100% (cấm ngưỡng 90%)

Không retire Nest, không cutover write sang Python, nếu **một** ID dưới đây chưa `PASS cả hai`:

| Vùng | Test ID |
|---|---|
| Auth | T-ID-001, T-ID-002, T-ID-003 |
| Authorization | T-ID-004, T-NFR-S2 |
| Session / progress | T-SES-001…003, T-PRG-001…004, T-EVT-001…003 |
| HLS / media signed | T-CMS-003, T-CMS-004, T-NFR-P2 |
| FR-NEG | T-NEG-001…004 |

Abort/cutover: xem §8. Vùng còn lại (catalog CRUD, flags, obs, a11y web) không được «90% critical».

## 2. Ma trận (suite Jest đã retire → pytest)

Trạng thái: `Chưa` / `PASS-Nest` / `PASS-Py` / `PASS cả hai`.

**Đọc cột 3 cho đúng**: `apps/api` đã bị **xoá** 2026-09-04. Suite Jest liệt kê dưới đây **không còn tồn tại trong repo** — tên để lại làm dấu vết lịch sử, muốn chạy phải `git checkout 7a05e62`. Mọi `PASS cả hai` từ nay là **bằng chứng lịch sử đã đóng băng** (log + differential JSON), không tái hiện được trên HEAD. Số hiện tại: pytest **55/55 PASS**, web e2e **10/10**.

| Test ID | FR/NFR | Suite Nest (retired `7a05e62`) | pytest / web hiện tại | Ghi chú |
|---|---|---|---|---|
| T-ID-001 | FR-ID-001 | `auth.e2e-spec.ts` | `apps/api-python/tests/test_auth.py` | **PASS cả hai** — differential 40/40 (`docs/qa/differential/2026-09-04T071945Z-parity.json`) |
| T-ID-002 | FR-ID-002 | `sync.e2e-spec.ts`, `e2e/sync.spec.ts` | `apps/api-python/tests/test_sync.py`, `apps/web/e2e/sync.spec.ts` | **PASS cả hai** — port `test_sync.py`: 3 token web/phone/ipad cùng identity → cùng catalog published + cùng progress; `devices` đúng 1 dòng/`device_class`. Ô này **trước đây chỉ có bên Nest** — lỗ hổng đã vá **trước** khi xoá |
| T-ID-003 | FR-ID-003 | `auth.e2e-spec.ts` | `apps/api-python/tests/test_auth.py` | **PASS cả hai** — logout → `/me` 401 trong differential |
| T-ID-004 | FR-ID-004 | catalog/flags 403 | `test_flags.py` / `test_catalog.py` | **PASS cả hai** — 403 learner/teacher `Forbidden resource` khớp byte |
| T-CAT-001…005 | FR-CAT-* | `catalog.e2e-spec.ts` | `apps/api-python/tests/test_catalog.py` | **PASS cả hai** — create/submit-qa/publish/400-no-media/list shape trong differential |
| T-SES-001…003 | FR-SES-* | `sessions.e2e-spec.ts` | `apps/api-python/tests/test_sessions.py` | **PASS cả hai** — start null, end 2 phút, double-end 400 |
| T-PRG-001…004 | FR-PRG-* | sessions + neg + sync | `apps/api-python/tests/test_sessions.py`, `test_sync.py` | **PASS cả hai** — minutes_comprehensible khớp; T-PRG-004 nay có bản pytest (`test_sync.py`: đúng 1 dòng `learner_progress` / user); zombie 0 còn pytest-only |
| T-CMS-001…002 | FR-CMS-001/002 | media + catalog | `apps/api-python/tests/test_media.py`, `test_catalog.py` | **PASS cả hai** — upload 201 + admin-only publish |
| T-CMS-003…004 | FR-CMS-003/004 | `signed-url.spec.ts`, media, hls | `apps/api-python/tests/test_media.py`, `test_hls.py`, `test_vectors.py` | **PASS cả hai** — dual-mode Bearer/signed, expired sig 401 |
| T-FLG-001 | FR-FLG-001 | `flags.e2e-spec.ts` | `apps/api-python/tests/test_flags.py` | **PASS cả hai** — defaults false + patch admin |
| T-FLG-002 | FR-FLG-002 | `e2e/shell.spec.ts` | `apps/web/e2e/shell.spec.ts` | **PASS cả hai** — shell.spec xanh Chromium+WebKit; HEAD chỉ còn nhánh Python |
| T-EVT-001…003 | FR-EVT-* | `sessions.e2e-spec.ts` | `apps/api-python/tests/test_sessions.py` | **PASS cả hai** — so trực tiếp `learning_events` trên 2 DB clone |
| T-NEG-001…003 | FR-NEG-001…003 | `neg.e2e-spec.ts` | `apps/api-python/tests/test_neg.py` | **PASS cả hai** — 404 `Cannot GET /…` khớp byte |
| T-NEG-004 | FR-NEG-004 | `schema.guard.spec.ts` | `apps/api-python/tests/test_schema_ddl.py` | **PASS cả hai** — Nest 3/3 (2026-09-04, trước khi xoá) rồi **port sang pytest**: assert `information_schema` không có cột textbook, và scanner `scripts/assert-no-textbook.ts` phải **đỏ** khi có cột cấm trong file `.py`. 5 test PASS (kèm baseline drift ADR-004) |
| T-NFR-X1 | NFR-XPLAT-001 | sync | `apps/api-python/tests/test_sync.py`, `apps/web/e2e/sync.spec.ts` | **PASS cả hai** — cùng catalog + cùng progress cho web/phone/ipad token; native theo #30 **vẫn mở** |
| T-NFR-X2 | NFR-XPLAT-002 | `deviceClass.test.ts` + #30 | `apps/mobile` unit + #30 | WebKit **không** thay iPad native; #30 đang mở |
| T-NFR-P1 | NFR-PERF-001 | runbook thủ công | **Chưa** — không có test | Vẫn thủ công. Cần **exception ký ở cổng nền tảng** — 2026-09-04 **chưa ai ký** |
| T-NFR-P2 | NFR-PERF-002 | `hls.e2e-spec.ts`, `e2e/hls.spec.ts` | `apps/api-python/tests/test_hls.py`, `apps/web/e2e/hls.spec.ts` | **PASS cả hai** — differential (rewrite, MIME, nosniff, traversal) + hls.spec HLS thật xanh Chromium/WebKit |
| T-NFR-S1 | NFR-SEC-001 | hash ≠ plaintext; HTTPS deploy | `test_vectors.py`, `test_auth.py` (phần hash) | **PASS một phần** — hash ≠ plaintext có test; **HTTPS là mức deploy, chưa có test** → cần exception, **chưa ký** |
| T-NFR-S2 | NFR-SEC-002 | flags/catalog 403 | `test_flags.py` / `test_catalog.py` | **PASS cả hai** |
| T-NFR-PR1 | NFR-PRIV-001 | `/me` không `passwordHash` | `apps/api-python/tests/test_auth.py::test_no_auth_payload_leaks_credentials` | **PASS-Py** — có test thật, hết «cần BA»: quét **raw text** response, cấm `argon2` / `password_hash` / `token_version`; `/me` key-set đúng `{id,email,roles}` |
| T-NFR-A1 | NFR-A11Y-001 | `e2e/a11y.spec.ts` | `apps/web/e2e/a11y.spec.ts` | **PASS cả hai** — a11y.spec axe AA + document title |
| T-NFR-O1/O2 | NFR-OBS-001 | health + `alert-5xx.e2e-spec.ts` | `apps/api-python/tests/test_obs.py` | **PASS-Py** — có test thật: health 200 + echo `x-request-id`, tự sinh request-id khi client không gửi, 5xx → POST webhook đúng payload, **4xx KHÔNG alert**, không cấu hình webhook thì không gọi |
| T-P5-hold | FR-LRN-002…004 | — | — | ngoài phạm vi |

Chưa có test ID (BA bổ sung, không bịa): seed #39 không đè status; error body shape; race `end()` D10 (freeze hành vi hiện tại).

## 3. Byte-level gates (Phase 1 tạo vector — không trích «file checklist đã có»)

### 3.1 HMAC

`HMAC-SHA256(secret, "${assetId}:${exp}")` hex, TTL 3600s, `timingSafeEqual`, fallback `MEDIA_SIGNING_SECRET` → `JWT_SECRET`. Tạo file JSON vector **trong Phase 1** (Node spec + pytest cùng file). Phủ: non-ASCII secret, exp quá khứ, sig sai độ dài, hex hoa, fallback secret.

### 3.2 Argon2

`argon2.hash(plain)` default **node-argon2**. Hash Node verify được argon2-cffi và ngược lại. Seed `admin@jplearn.local` / `password10`. Ghi type/memory/time/parallelism vào test, không «default».

### 3.3 JWT

Claims `sub`, `email`, `ver` (= `tokenVersion`), `jti`; `exp` 8h. Logout: token cũ 401 trên `/me` **và** nhánh Bearer media. Token Nest ↔ Python cùng `JWT_SECRET`.

### 3.4 HLS / ORB / storage

`X-Content-Type-Options: nosniff`; MIME `.m3u8` / `.ts` / `.m4s` / `.vtt`; rewrite `exp`+`sig` trên URI relative; regex `^[A-Za-z0-9._-]+$` + chặn `..`; dual-mode auth. **Risk spike Phase 1** trên shared `STORAGE_ROOT` (thay `process.cwd()/storage`) + streaming — không đợi Phase 3 media xong mới phát hiện ORB.

Playwright: thêm project **WebKit** cạnh Desktop Chrome (`playwright.config.ts` hiện chỉ Chrome). WebKit **không** thay #30 Expo/iPad native.

### 3.5 Error + key-set

Handler FastAPI: validation → **400** shape Nest, không 422 `{detail}`. Từng response model: test key-set và chỗ `null` vs omit (`LearningSession.ended_at`). **Cấm** `response_model_exclude_none` global.

## 4. Guard FR-NEG — tiền điều kiện

- Mở `assert-no-textbook.ts` sang `.py` / `.pyi`.
- T-NEG-004 assert `information_schema.columns` sau migrate, không chỉ đọc text Prisma.
- Negative test: cột cấm trên model Python → guard **đỏ**.

## 5. Cross-surface

Playwright web trỏ API Python. Expo `EXPO_PUBLIC_API_URL` trên iPhone **và** iPad máy thật (#30). Tuyên bố UC-L06 parity **chỉ khi #30 đóng** với baseline Nest rồi lặp trên Python.

## 6. Hạ tầng

Harness Node đã xoá cùng `apps/api` (`docker-postgres.cjs`, `docker-db.cjs`, `global-setup.cjs` — xem `7a05e62`). Hiện tại:

- Pytest: `apps/api-python/tests/pg_harness.py` — Docker Postgres riêng, DDL bằng **Alembic** (ADR-004), không còn `prisma migrate`.
- Differential / web e2e: `apps/api-python/differential/db.py up|down|url`.
- DDL: `jplearn-migrate upgrade|stamp`, dữ liệu mẫu `jplearn-seed`. Chống drift: `docs/qa/adr-004-schema-baseline.json` + `apps/api-python/tests/test_schema_ddl.py` (5 test PASS).
- Guard vẫn giữ (`assert_test_database_url`) — chỉ cho pathname `/jplearn_test`.
- CI: job `api-python` (uv, pytest, contract diff, vectors, T-NEG). Không còn job Jest.

Flake hạ tầng ≥3 lần / 2 tuần → dừng, sửa harness. Chi tiết: [`adr-003-harness.md`](./adr-003-harness.md).

## 7. Definition of Done (retire Nest) — quyết toán 2026-09-04

`apps/api` **đã bị xoá**. Commit cuối còn Nest: **`7a05e62`**. CEO chọn «đóng nốt mục 6 trước khi xoá, chỉ override #30 và staging soak». Trạng thái thật từng mục:

1. Critical §1 = 100% `PASS cả hai` + log — **ĐẠT**. Differential 40/40, evidence `docs/qa/differential/2026-09-04T071945Z-parity.json`.
2. Contract semantic diff trong allowlist; baseline Nest xanh trước — **ĐẠT**. `contract.e2e-spec.ts` đã xoá, thay bằng `apps/api-python/tests/test_contract.py`: mọi operation trong `openapi.yaml` đều được route; body rỗng → **400 shape Nest**, không 422 `{detail}`.
3. Mọi gate §3 có test CI — **ĐẠT**. Vectors argon2 / JWT / HMAC + pytest trong job `api-python`.
4. §4 đóng, kể cả negative guard — **ĐẠT**. Port sang `apps/api-python/tests/test_schema_ddl.py`.
5. §5: web E2E Python xanh — **ĐẠT** 10/10 (chromium + webkit). Native theo #30 — **CHƯA ĐẠT**, #30 **vẫn mở**. → **CEO override 2026-09-04**.
6. T-NFR-P1 / T-NFR-PR1 / T-NFR-S1 HTTPS — **ĐẠT MỘT PHẦN**. Đã trả nợ bằng test thật: T-NFR-O1/O2 (`tests/test_obs.py`) và T-NFR-PR1 (`tests/test_auth.py::test_no_auth_payload_leaks_credentials`). **Còn nợ**: T-NFR-P1 (NFR-PERF-001, runbook thủ công) và T-NFR-S1 phần HTTPS (mức deploy) — cần **exception ký ở cổng nền tảng**, hiện **CHƯA KÝ**.
7. Stabilization trên internal staging; runbook Platform+Ops duyệt; rollback drill — **CHƯA ĐẠT**. Phase 5 chưa bắt đầu; Python **chưa nhận request thật nào**; prod env riêng chưa kiểm chứng. → **CEO override 2026-09-04**.

### Ghi nhận của QA

**QA KHÔNG ký mục 7, và không ký phần native của mục 5.** Việc xoá `apps/api` là **quyết định vượt cổng** của CEO ngày 2026-09-04, không phải kết quả của một cổng sạch. Cổng còn nợ, đúng ba khoản:

- mục 5 — #30 (iPad/iPhone native, NFR-XPLAT-002) còn mở;
- mục 6 — exception T-NFR-P1 + T-NFR-S1 HTTPS chưa có chữ ký;
- mục 7 — chưa soak staging, chưa duyệt runbook, chưa chạy rollback drill.

Hệ quả kỹ thuật phải nói thẳng: **rollback về Nest không còn là thao tác vận hành**, chỉ còn là `git checkout 7a05e62`. `differential/run_parity.py` vẫn nằm trong repo nhưng **fail sớm** với thông báo trỏ về `7a05e62` — không còn runtime thứ hai để so. Từ đây mọi «parity» là bằng chứng lịch sử, không phải kiểm chứng lại được.

Quyền phủ quyết ở mục này đã bị override, không phải đã được thoả mãn. Ai đọc file sau này đừng đọc ngược.

## 8. Abort

- Critical chưa 100% sau thời hạn đã ghi trên runbook (không dùng 90% cho critical).
- Một gate HMAC / argon2 / ORB / FR-NEG không đóng được.
- Guard `.py` không vá trước khi viết model Python.

Khi abort: **dừng deployment** Python, tag/archive nhánh, giữ log/vector/diff. **Không** lấy việc xoá `apps/api-python` làm bước abort.

Feature freeze API: bug vá Nest trước, Python theo. Ngoại lệ: lỗ bảo mật.
