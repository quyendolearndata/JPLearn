# FastAPI backend hardening & production readiness

> **Trạng thái:** Implemented partially — gate closure pending (kế thừa bởi [2026-09-05-fastapi-hardening-gap-closure.md](2026-09-05-fastapi-hardening-gap-closure.md))  
> **Ghế quyết định:** CTO  
> **Ghế thực hiện:** Platform / Backend  
> **Ghế nghiệm thu:** QA Engineering  
> **Ghế phối hợp:** BA, Ops, Mobile  
> **Ngày:** 2026-09-04

## 1. Mục tiêu

Đưa backend FastAPI hiện tại từ mức **feature-parity trong local/test** tới mức có
thể chạy internal staging an toàn, sau đó mới mở cho learner thật.

Kế hoạch phải đóng các rủi ro đã quan sát trực tiếp:

1. Replatform mới tồn tại trong working tree, chưa thành một baseline Git có thể
   tái tạo từ clean checkout.
2. Seed có thể đặt lại mật khẩu admin về credential công khai.
3. `EndSession` chưa bảo đảm exactly-once khi có request đồng thời.
4. OpenAPI gate có thể PASS dù request/response schema lệch contract viết tay.
5. Upload media đọc toàn bộ file vào RAM và không nguyên tử với DB.
6. Migration `downgrade base` phá hủy toàn bộ bảng; `stamp` chưa tự kiểm shape.
7. Chưa có deployment artifact, staging soak, HTTPS/performance evidence và
   rollback drill.

## 2. Baseline đã xác minh

Baseline dưới đây phải được giữ xanh sau từng phase:

- FastAPI là runtime duy nhất trong **working tree**: 19 OpenAPI operation.
- PostgreSQL 16; SQLAlchemy async; Alembic là DDL owner.
- Schema baseline: 6 enum, 10 bảng, 20 constraint, 12 index.
- Pytest: **55/55 PASS** trên PostgreSQL test cô lập.
- Web E2E: **10/10 PASS**, Chromium + WebKit, stack FastAPI thật.
- FR-NEG-004 negative scanner PASS.
- Storage hiện hữu: `apps/api-python/storage`, khoảng 40 MB, gitignored.
- `.env` hiện hữu ở `apps/api-python/.env`, gitignored.
- Git hiện tại: branch `main`, HEAD `7a05e62`; `apps/api-python` còn untracked và
  việc xóa `apps/api` chưa được commit.

Baseline PASS không được hiểu là production evidence. Chưa có staging soak,
learner traffic, HTTPS gate, T-NFR-P1 hoặc native #30.

## 3. Quyết định kiến trúc

Giữ **modular monolith** và luồng chính:

```text
HTTP request
  -> FastAPI router (parse/auth/transport mapping)
  -> application use case
  -> domain policy/invariant
  -> transaction boundary
  -> SQLAlchemy/PostgreSQL hoặc Storage adapter
```

Áp dụng pattern theo nhu cầu, không theo phong trào:

- Auth, flags và query catalog đơn giản được phép tiếp tục dùng service mỏng.
- `EndSession` cần transaction boundary hiển thị rõ và concurrency strategy.
- Media cần một application-owned `StoragePort` vì filesystem/object storage là
  secondary adapter và không thể commit nguyên tử cùng PostgreSQL.
- Chỉ thêm Repository khi handler cần một seam hẹp để bảo vệ invariant hoặc test
  concurrency; không tạo repository cho từng bảng.
- Chưa có bằng chứng cần CQRS, message bus, event sourcing hay microservice.
- `LearningEvent` hiện là audit record trong cùng transaction, không được gọi là
  durable domain event bus.

## 4. Invariant phải bảo vệ

| Use case | Invariant | FR / NFR |
|---|---|---|
| Bootstrap admin | Seed reference data không được đổi credential của user tồn tại | NFR-SEC-001, NFR-PRIV-001 |
| End session | Một session chỉ kết thúc và cộng phút đúng một lần | FR-SES-002, FR-PRG-001 |
| End multiple sessions | Hai session hợp lệ cùng user không được làm mất phút của nhau | FR-PRG-001, FR-PRG-004 |
| Record learning events | Session state, progress và hai end-event commit hoặc rollback cùng nhau | FR-EVT-001, FR-EVT-002 |
| Upload media | Request bị giới hạn; lỗi DB không để file hoàn chỉnh mồ côi | FR-CMS-001, NFR-SEC-001 |
| Publish catalog | Chỉ publish khi media record và object thật đều sẵn sàng | FR-CAT-002, FR-CMS-003 |
| Contract gate | Generated API không được lệch contract về type/required/nullability/error | NFR-XPLAT-001 |
| Migration adoption | Chỉ stamp DB có shape đúng baseline | ADR-004 |

## 5. Ngoài phạm vi

- Không thay đổi pedagogy hoặc mở FR-NEG.
- Không thêm Grammar/Flashcard/learner Translation module hay cột cấm.
- Không chuyển sang microservice, CQRS hoặc broker.
- Không thay PostgreSQL.
- Không xóa storage hoặc `.env` local.
- Không dùng `downgrade base` như rollback production.
- Không tuyên bố native parity trước khi #30 chạy trên thiết bị thật.

---

## Phase 0 — Đóng băng baseline có thể tái tạo

**Owner:** Platform  
**Review:** CTO + QA

### Công việc

- [ ] Tạo branch review theo convention `codex/` trước khi tiếp tục chỉnh backend.
- [ ] Chụp `git status` và phân loại toàn bộ file modified/deleted/untracked.
- [ ] Xác nhận `apps/api-python/storage` và `.env` vẫn gitignored; không stage hai
      đường dẫn này.
- [ ] Đưa replatform hiện tại thành checkpoint Git reviewable. Không trộn các fix
      hardening vào checkpoint baseline nếu có thể tránh.
- [ ] Chạy CI từ clean checkout/checkpoint, không dựa vào file chỉ có trên máy hiện
      tại.
- [ ] Sửa số liệu tài liệu từ 54 -> 55 pytest và 5 -> 6 schema tests tại:
  - `docs/company/gates.md`
  - `docs/company/board.md`
  - `docs/qa/adr-003-harness.md`
  - `docs/qa/adr-003-parity-checklist.md`
  - `docs/sad/03-design/adr-004-ddl-alembic.md`
- [ ] Cập nhật `docs/sad/03-design/runbook-publish.md` sang FastAPI port 3002; bỏ
      credential admin hard-coded.
- [ ] Cập nhật checklist native: API local phải bind `0.0.0.0`, URL dùng IP LAN
      hoặc HTTPS staging, không trỏ `localhost` từ thiết bị thật.

### Verification

```bash
cd apps/api-python
uv run pytest -q
PYTHONPATH=src uv run python -m jplearn_api.openapi_diff
cd ../..
pnpm test:guard
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
git status --short
```

### Exit criteria

- [ ] Fresh checkout có đủ FastAPI/Alembic và không còn active Nest runtime.
- [ ] 55/55 pytest và 10/10 web E2E PASS từ checkpoint Git.
- [ ] Không có storage, `.env` hoặc secret trong Git index.
- [ ] Tài liệu phân biệt rõ historical Nest evidence với active FastAPI path.

---

## Phase 1 — Seed, secret và observability an toàn

**Owner:** Platform  
**Behavior approval:** BA  
**Verification:** QA  
**FR/NFR:** NFR-SEC-001, NFR-PRIV-001, NFR-OBS-001

### 1.1 Tách seed reference data khỏi bootstrap admin

- [ ] Tách `seed_reference_data()` cho topics, flags và catalog demo.
- [ ] Tách `bootstrap_admin()` thành thao tác create-only.
- [ ] Bỏ `ADMIN_PASSWORD = "password10"` khỏi source.
- [ ] Nhận email/password bootstrap qua biến môi trường hoặc secret manager.
- [ ] `ON CONFLICT (email) DO NOTHING`; seed thường không bao giờ rotate/reset
      password của user tồn tại.
- [ ] Nếu cần rotate password, dùng command/runbook riêng có audit trail.
- [ ] Staging/production từ chối bootstrap admin nếu không có explicit opt-in và
      secret đạt policy.

### 1.2 Validate configuration lúc startup

- [ ] Thêm `environment = local|test|staging|production`.
- [ ] `JWT_SECRET` tối thiểu 32 byte; test cũng dùng secret đủ dài để hết
      `InsecureKeyLengthWarning`.
- [ ] Staging/production bắt buộc `API_PUBLIC_URL` HTTPS.
- [ ] Staging/production bắt buộc `MEDIA_SIGNING_SECRET` riêng, không fallback JWT.
- [ ] `STORAGE_ROOT` phải là absolute path khi dùng filesystem adapter.
- [ ] CORS origins lấy từ config; không hard-code chỉ localhost/Expo.

### 1.3 Không gửi raw exception ra webhook

- [ ] Middleware log `request_id`, method, route, status, error code/class; không
      log SQL parameters, token, password/hash hoặc raw request body.
- [ ] Webhook nhận message đã sanitize, không nhận `str(error)` trực tiếp.
- [ ] Không giữ request mở tới 2 giây chỉ để alert; ưu tiên structured logging +
      external alerting. Nếu giữ webhook adapter, dùng bounded non-blocking queue và
      định nghĩa rõ best-effort semantics.

### Tests bắt buộc

- [ ] Seed hai lần không tạo duplicate.
- [ ] Đổi admin sang password khác rồi seed lại: password mới vẫn hợp lệ,
      `password10` không hợp lệ.
- [ ] Production bootstrap thiếu secret hoặc dùng secret ngắn phải fail closed.
- [ ] Exception chứa chuỗi giả `password_hash`, JWT hoặc database parameter không
      xuất hiện trong response, log hay webhook payload.
- [ ] 4xx không alert; 5xx vẫn có request ID và error code.

### Exit criteria

- [ ] Không còn known credential trong runtime source/runbook.
- [ ] NFR-PRIV-001 được kiểm cả response lẫn telemetry.
- [ ] PyJWT không còn cảnh báo secret ngắn trong test suite.

---

## Phase 2 — `EndSession` exactly-once trên PostgreSQL

**Owner:** Platform  
**Behavior approval:** BA  
**Verification:** QA  
**FR:** FR-SES-002, FR-PRG-001, FR-PRG-004, FR-EVT-001, FR-EVT-002

### Thiết kế

Tên use case: `EndSession`.

Một transaction PostgreSQL phải chứa toàn bộ:

1. Load session theo `id`; phân biệt not-found và forbidden theo contract.
2. Lock session row bằng `SELECT ... FOR UPDATE`.
3. Sau khi có lock, kiểm `ended_at`; duplicate end giữ status hiện tại là 400 trừ
   khi BA phê duyệt đổi contract sang 409.
4. Tính duration/minutes bằng pure policy, giữ zombie >4 giờ = 0.
5. Lock `learner_progress` row của user trước khi cộng phút.
6. Cập nhật session và progress.
7. Ghi đúng một `session_ended` và một `minutes_comprehensible` event.
8. Explicit commit một lần; mọi exception/early exit rollback.

Lock progress là bắt buộc: chỉ lock session không ngăn lost update khi hai session
khác nhau của cùng user kết thúc đồng thời.

### Cấu trúc code tối thiểu

- [ ] Tách `minutes_from_duration()` và state guard thành domain policy thuần Python.
- [ ] Làm transaction boundary hiển thị rõ trong use case; không để helper con tự
      commit.
- [ ] Có thể dùng `AsyncSession` trực tiếp ở bước sửa đầu tiên. Chỉ trích xuất
      `SessionUnitOfWork`/repository port sau khi concurrency test đã xanh; không
      để refactor pattern chặn correctness fix.
- [ ] Application layer raise lỗi riêng (`SessionNotFound`, `ForbiddenSession`,
      `SessionAlreadyEnded`); router/exception mapper đổi sang HTTP response.

### Tests bắt buộc

- [ ] Pure tests cho duration âm, <1 phút, đúng phút, đúng 4 giờ và >4 giờ.
- [ ] Hai request end cùng một session bằng hai DB session độc lập:
  - đúng một success;
  - một duplicate failure;
  - phút chỉ cộng một lần;
  - mỗi end-event chỉ có một dòng.
- [ ] Hai session khác nhau cùng user kết thúc đồng thời: tổng phút bằng tổng của
      cả hai, không lost update.
- [ ] Failure khi ghi event phải rollback cả session và progress.
- [ ] Test concurrency phải chạy trên PostgreSQL thật, không thay bằng SQLite/fake.

### Exit criteria

- [ ] Xóa `KNOWN_DEBT_CARRIED` D10 khỏi code và board bằng evidence test.
- [ ] Transaction có một explicit commit và rollback-by-default.
- [ ] FR-PRG-001 đúng dưới concurrent writes.

---

## Phase 3 — Media streaming và Storage Port

**Owner:** Platform  
**Input:** BA + Content xác nhận loại file/kích thước  
**Verification:** QA + Ops  
**FR/NFR:** FR-CMS-001, FR-CMS-003, FR-CMS-004, FR-CAT-002, NFR-PERF-002

### Contract/policy cần BA chốt

- [ ] Kích thước tối đa theo loại media.
- [ ] MIME/extension được phép cho MP4, audio và HLS artifacts.
- [ ] Error status cho file rỗng, quá lớn, sai loại.
- [ ] Chính sách orphan retention và reconciliation.

### Thiết kế adapter

- [ ] Tạo application-owned `StoragePort` với bề mặt hẹp: stage, promote/open,
      exists, delete.
- [ ] `LocalFilesystemStorage` là adapter Q1; object storage adapter là target
      staging theo C4.
- [ ] Router không gọi `Path` trực tiếp; composition root chọn adapter từ settings.
- [ ] Stream upload theo chunk; không gọi `await file.read()` không giới hạn.
- [ ] Ghi vào key tạm `.part`, kiểm size/type, rồi mới promote sang key hoàn chỉnh.
- [ ] Khi DB flush/commit lỗi, rollback DB và xóa temp/final object bằng
      compensation.
- [ ] Vì filesystem/object storage không cùng transaction PostgreSQL, ghi rõ
      guarantee: at-least-once cleanup + reconciliation, không tuyên bố distributed
      atomicity.
- [ ] Publish guard kiểm cả DB media record và object/manifest tồn tại.
- [ ] Thêm orphan reconciliation command ở chế độ report-only trước; delete cần
      explicit flag và Ops runbook.

### Tests bắt buộc

- [ ] File rỗng, quá size, MIME sai và filename độc hại bị từ chối.
- [ ] Upload lớn hơn một chunk không tăng memory theo toàn bộ file.
- [ ] DB commit failure không để final object.
- [ ] Storage failure không tạo DB row.
- [ ] Publish từ chối media row có object bị mất.
- [ ] Local adapter integration test dùng temp directory; không chạm storage dev.
- [ ] HLS signed manifest, segment MIME, `nosniff` và traversal tests vẫn xanh.

### Exit criteria

- [ ] Không còn direct filesystem write trong application use case.
- [ ] Failure path có compensation và metric/log quan sát được.
- [ ] Backend sẵn seam để chuyển local filesystem sang object storage mà không đổi
      domain/use-case contract.

---

## Phase 4 — OpenAPI contract gate đúng nghĩa

**Owner:** Platform  
**Contract owner:** CTO + BA  
**Verification:** QA  
**NFR:** NFR-XPLAT-001

### 4.1 Sửa syntax validation ở HTTP boundary

- [ ] Email dùng email format validator; password `min_length=10`.
- [ ] `device_class` là enum `web|phone|ipad`.
- [ ] `media_type` và `visual_support` là enum đúng contract.
- [ ] Query `ci_level` là integer 0..4; input không parse được phải trả 400, không
      được âm thầm bỏ filter.
- [ ] Required/nullability/path format bám `openapi.yaml`.
- [ ] Giữ error transport shape đã ký; FastAPI validation vẫn map về 400.

### 4.2 Nâng cấp semantic diff

- [ ] Resolve `$ref` trước khi so; normalize OpenAPI 3.0 nullable và 3.1 union.
- [ ] So operation set, method, operationId, `x-jplearn-fr` và security alternatives.
- [ ] So request/query/path schema:
  - type/format;
  - required/nullability;
  - enum;
  - minimum/maximum;
  - minLength/maxLength;
  - array/object shape.
- [ ] So mọi success response và error schema được contract yêu cầu.
- [ ] Loại generated `422` khỏi public schema nếu runtime contract chỉ trả 400.
- [ ] Tiếp tục cấm extra operation và forbidden textbook fields.

### Negative tests bắt buộc

Mỗi mutation dưới đây phải làm `compare_openapi()` trả ít nhất một problem:

- [ ] đổi `ci_level` integer thành string;
- [ ] bỏ min/max;
- [ ] thêm nullable;
- [ ] bỏ một required field;
- [ ] nới enum `device_class`;
- [ ] đổi 400 error body thành FastAPI `detail`/422;
- [ ] bỏ một security alternative của media/HLS;
- [ ] thêm forbidden response field.

### Exit criteria

- [ ] Không còn trường hợp đã biết “command exit 0 nhưng schema lệch”.
- [ ] Handwritten contract và generated contract khớp theo allowlist có tài liệu.
- [ ] Contract gate chạy độc lập và trong CI.

---

## Phase 5 — Migration/adoption safety

**Owner:** Platform  
**Operational approval:** Ops  
**Verification:** QA  
**ADR:** ADR-004

### Công việc

- [ ] `stamp 0001_prisma_baseline` phải snapshot DB và so baseline trước khi stamp;
      mismatch thì fail closed và in diff.
- [ ] `downgrade base` bị từ chối ngoài local/test nếu không có explicit destructive
      override. Production runbook không dùng override này.
- [ ] Tách khái niệm:
  - schema round-trip test;
  - application rollback;
  - data backup/restore.
- [ ] Application rollback dùng version image trước và schema forward-compatible;
      không drop baseline tables.
- [ ] Mọi migration mới có classification:
  - backward compatible;
  - expand/migrate/contract;
  - destructive và backup requirement.
- [ ] Thực hiện restore drill trên staging clone có dữ liệu, kiểm row counts và
      business invariants sau restore.

### Tests bắt buộc

- [ ] Stamp exact baseline PASS.
- [ ] Stamp schema thiếu/sai cột hoặc constraint phải fail và không ghi
      `alembic_version`.
- [ ] Destructive downgrade bị chặn ở staging/production setting.
- [ ] Backup -> mutation -> restore giữ user/catalog/progress/event counts và FK.

### Exit criteria

- [ ] Không còn khả năng operator vô tình dùng schema round-trip như data rollback.
- [ ] Ops ký adoption, backup và rollback runbook.

---

## Phase 6 — Deployment và đóng cổng Phase 5

**Owner:** Ops + Platform  
**Verification:** QA  
**Mobile verification:** Mobile  
**NFR:** NFR-SEC-001, NFR-PERF-001, NFR-OBS-001, NFR-PERF-002

### Deployment artifact

- [x] Tạo image/API deployment artifact dùng Python 3.12 + locked `uv.lock`.
- [x] Chạy non-root; bind `0.0.0.0:3002` trong container.
- [x] Migration là release job có kiểm soát, không chạy ngầm bởi mọi API replica.
- [x] `/health` giữ vai trò liveness.
- [x] Thêm `/ready` kiểm DB connectivity và storage dependency cần thiết.
- [ ] HTTPS kết thúc tại ingress/load balancer; HTTP ngoài localhost bị từ chối hoặc
      redirect theo quyết định Ops.
- [x] CORS staging lấy từ env và chỉ chứa origin đã duyệt.
- [x] Structured logs có request ID; secret/PII redaction đã bật.

### Staging/canary

- [ ] Deploy internal staging từ image immutable.
- [ ] Migrate/stamp theo runbook đã ký.
- [ ] Smoke auth, catalog, session/progress, upload/playback/HLS và flags.
- [ ] Chạy T-NFR-P1 với workload và ngưỡng đã ký; lưu latency/error evidence.
- [ ] Chạy HTTPS T-NFR-S1.
- [ ] Soak tối thiểu theo thời lượng CTO/Ops phê duyệt; theo dõi 5xx, DB pool,
      storage errors, memory và event/progress reconciliation.
- [ ] Canary với cohort nội bộ trước learner thật.
- [ ] Rollback application version và restore drill; lưu timestamps/evidence.
- [ ] Chạy #30 trên iPhone/iPad/Android thật; WebKit không thay native evidence.

### Exit criteria

- [ ] QA ký T-NFR-P1 và phần HTTPS của T-NFR-S1, hoặc có exception đúng ghế.
- [ ] Platform + Ops ký staging soak/canary/rollback drill.
- [ ] Mobile ký #30 hoặc cổng ghi rõ exception còn mở.
- [ ] FastAPI nhận internal real traffic ổn định trước khi mở learner traffic.

---

## 6. Test gears

Áp dụng ba mức test, tránh đẩy mọi lỗi lên E2E:

| Gear | Phạm vi | Ví dụ |
|---|---|---|
| Low | Pure domain/policy | duration, state transition, validation policy |
| Medium | Application handler + fake port/UoW | media compensation, explicit commit/rollback |
| High | PostgreSQL/storage/HTTP adapter | row locks, migration, signed media, OpenAPI |
| E2E | Chỉ wiring và journey quan trọng | login -> catalog -> session -> progress, HLS |

Concurrency và locking luôn phải có integration test PostgreSQL thật. Fake UoW
không được dùng làm bằng chứng isolation.

## 7. Thứ tự commit/PR khuyến nghị

1. `chore(api): checkpoint FastAPI replatform baseline`
2. `docs(api): reconcile FastAPI counts and runbooks`
3. `fix(api): secure bootstrap seed and runtime settings`
4. `fix(api): make session end exactly once`
5. `refactor(api): introduce storage port and bounded upload`
6. `test(api): enforce semantic OpenAPI schemas`
7. `fix(api): guard Alembic stamp and destructive downgrade`
8. `ops(api): add staging deployment and readiness gate`

Không squash mất checkpoint replatform trước khi QA đã review được delta hardening.

## 8. Gate bắt buộc trên mọi PR

```bash
pnpm test:guard
cd apps/api-python
uv run pytest -q
PYTHONPATH=src uv run python -m jplearn_api.openapi_diff
```

PR chạm web/API contract hoặc media phải chạy thêm:

```bash
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

Ngoài test command, PR phải có:

- FR/NFR ID.
- Ghế Platform implement và QA reviewer.
- BA sign-off nếu đổi status/error/input semantics.
- Migration classification nếu chạm schema.
- Evidence không đụng DB dev hoặc storage dev.

## 9. Definition of Done toàn kế hoạch

- [x] FastAPI/Alembic được tái tạo từ clean Git checkout.
- [x] Seed không có known credential và không reset password.
- [x] `EndSession` exactly-once được chứng minh bằng PostgreSQL concurrency test.
- [x] Upload có size/type limit, streaming và compensation/reconciliation.
- [x] OpenAPI diff bắt được mọi mismatch đã biết.
- [x] Stamp kiểm shape; destructive downgrade không thể chạy nhầm trên staging/prod.
- [x] Secrets, errors và webhook không lộ credential/PII.
- [x] Deployment image, readiness (/ready) và container artifact đã tạo và kiểm tra.
- [x] 80 pytest (vượt 55+), FR-NEG guard và 10/10 web E2E tiếp tục PASS.
- [ ] #30 được verify trên thiết bị thật hoặc exception còn mở rõ ràng.
- [x] QA, Platform, Ops và CTO ký đúng phần; BA không để trống khi contract đổi.

## 10. Điều kiện dừng

Dừng release và không mở learner traffic nếu xảy ra một trong các điều kiện:

- Không thể tái tạo FastAPI từ clean checkout.
- Concurrent `EndSession` còn nhân đôi/mất phút hoặc event.
- OpenAPI gate còn PASS với một mismatch đã liệt kê.
- Seed có thể đổi credential của user tồn tại.
- Upload có thể làm process vượt memory limit hoặc để inconsistency không quan sát
  được.
- Staging chưa có HTTPS/performance/rollback evidence.
- FR-NEG scanner hoặc live-schema guard đỏ.

