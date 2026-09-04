# FastAPI hardening gap closure & production evidence

> **Trạng thái:** Proposed — chưa bắt đầu implementation  
> **Kế thừa:** `2026-09-04-fastapi-backend-hardening.md`  
> **Baseline review:** branch `codex/fastapi-backend-hardening`, HEAD `3180709`  
> **Ghế quyết định:** CTO  
> **Ghế thực hiện:** Platform / Backend  
> **Ghế nghiệm thu:** QA Engineering  
> **Ghế phối hợp bắt buộc:** BA, Ops, Mobile  
> **Ngày:** 2026-09-05

## 1. Mục tiêu

Đóng các khoảng trống còn lại sau plan hardening ngày 2026-09-04 và tạo bằng
chứng đủ để quyết định có cho FastAPI nhận learner traffic hay không.

Plan này không phủ nhận phần implementation đã hoàn thành. Nó sửa trạng thái
overclaim ở `walkthrough.md` và Definition of Done cũ bằng cách tách rõ:

1. code đã tồn tại;
2. test local đã chạy;
3. artifact container có thể vận hành;
4. bằng chứng staging/production;
5. chữ ký của đúng ghế.

Không dùng một command exit `0`, một file walkthrough hoặc checkbox tự đánh dấu
để thay cho bằng chứng ở ranh giới thật.

## 2. Baseline đã đối chiếu

### 2.1 Phần đã có và được giữ lại

- Chuỗi commit `972ce6d` đến `f7e2dee` tồn tại trên branch; `3180709` cập nhật
  checklist/DoD.
- FastAPI/Alembic là backend và DDL owner hiện tại.
- Seed reference data đã tách khỏi bootstrap admin; bootstrap create-only.
- `EndSession` có domain policy, khóa PostgreSQL `FOR UPDATE` trên session và
  progress, explicit commit và rollback khi lỗi.
- Media upload đọc `UploadFile` theo chunk, dùng `.part` rồi promote, có
  compensation khi DB commit lỗi và có reconciliation function.
- Docker image build được, chạy `appuser` UID 10001 và bind `0.0.0.0:3002`.
- Argon2 hash/verify đã offload bằng `asyncio.to_thread`.
- Gate local gần nhất:
  - `pnpm test:guard`: PASS;
  - `uv run pytest -q`: 80 PASS;
  - Web E2E chạy độc lập Chromium + WebKit: 10/10 PASS trong khoảng 2,2 phút;
  - OpenAPI diff: exit 0, nhưng chưa đủ mạnh để nghiệm thu semantic contract.

### 2.2 Điểm nhận xét đính kèm cần hiệu chỉnh

Kết quả Web E2E 8/10 trong một lần audit không được dùng làm bằng chứng backend
regression. Hai E2E runner đã chạy đồng thời, thay API/test database giữa hành
trình 130 giây và tạo các response 401. Khi chạy lại độc lập, cùng command đạt
10/10. Plan vẫn phải cô lập runner để sự cố này không tái diễn.

### 2.3 Khoảng trống đã xác minh

| ID | Khoảng trống | Mức chặn |
|---|---|---|
| G-01 | `jplearn_api.migrate` crash khi import trong Docker do dùng `parents[4]` | Release blocker |
| G-02 | DB rỗng bỏ qua baseline diff và vẫn được stamp | Release blocker |
| G-03 | Baseline JSON không được đóng gói trong image; thiếu baseline chưa fail closed | Release blocker |
| G-04 | OpenAPI diff bỏ sót missing min/max/minLength, nullable, extra field, error body và security alternatives | Contract blocker |
| G-05 | `/ready` bỏ qua `exists(False)` và không kiểm quyền ghi storage | Traffic blocker |
| G-06 | Filesystem traversal check dùng string prefix, chấp nhận sibling-prefix | Security blocker |
| G-07 | Upload chưa có MIME/extension policy đã được BA ký | Contract/security blocker |
| G-08 | `StoragePort.get_path() -> Path` làm application phụ thuộc local filesystem | Architecture debt |
| G-09 | Webhook vẫn nằm trên request path; CORS staging/prod chưa fail closed | Runtime debt |
| G-10 | E2E runner chưa cô lập port/DB/storage/process | Evidence reliability blocker |
| G-11 | Chưa có restore drill, HTTPS, T-NFR-P1, soak, canary và rollback evidence | Production blocker |
| G-12 | #30 native và các chữ ký QA/Ops/BA/Mobile còn mở | Gate blocker |
| G-13 | Plan cũ, gates, traceability và walkthrough mô tả trạng thái mâu thuẫn | Governance blocker |

## 3. Nguyên tắc kiến trúc

Giữ modular monolith và dependency direction:

```text
HTTP/CLI
  -> transport validation
  -> application use case
  -> domain policy/invariant
  -> application-owned port
  -> PostgreSQL/filesystem/webhook adapter
```

- Không refactor toàn bộ backend sang Repository/UoW chỉ để đồng nhất hình thức.
  `EndSession` được phép tiếp tục dùng request-scoped `AsyncSession` nếu một use
  case vẫn có đúng một transaction boundary, một explicit commit và rollback
  trên mọi failure path.
- Port phải mô tả capability của application, không trả kiểu hạ tầng như `Path`
  nếu consumer cần hỗ trợ cả filesystem và object storage.
- Syntax validation ở FastAPI/Pydantic; semantic precondition trong service;
  invariant trạng thái trong domain policy.
- Alert webhook là side effect best-effort. Structured log là nguồn quan sát
  chính; không giữ HTTP request chờ webhook và không tạo task vô hạn.
- Migration/adoption và readiness phải fail closed.
- Không thêm CQRS, message bus, broker hoặc microservice trong plan này.

## Phase 0 — Reset trạng thái và bằng chứng

**Owner:** CTO + QA  
**Implement:** Platform  
**Phối hợp:** BA + Ops

### Công việc

- [ ] Chụp clean-checkout baseline từ commit review; không đưa `.env`, storage dev,
      `landing_preview.html` hoặc thay đổi ngoài scope vào PR.
- [ ] Phân loại `walkthrough.md`: chỉ commit sau khi nội dung được tạo từ evidence
      cuối; trước đó ghi rõ `DRAFT / NOT ACCEPTED`.
- [ ] Đổi trạng thái plan 2026-09-04 từ self-declared complete thành
      `Implemented partially — gate closure pending`; không xóa lịch sử checkbox.
- [ ] Tạo thư mục evidence theo run, ví dụ
      `docs/qa/fastapi-hardening/<UTC timestamp>/`, chứa manifest có commit SHA,
      command, exit code, duration, OS/image digest và link log đã redact.
- [ ] Reconcile D10 trong `traceability.md`, `adr-003-contract-delta.md`, board và
      parity checklist: phân biệt historical replatform debt với runtime fix hiện
      tại; không để `KNOWN_DEBT_CARRIED` còn mô tả code đã được sửa.
- [ ] BA xác nhận hoặc mở decision record cho:
  - duplicate `EndSession` giữ status 400 hay đổi 409;
  - MIME/extension/size theo loại media;
  - orphan retention và quyền delete;
  - public error body và các status bắt buộc trong OpenAPI.
- [ ] Không thêm chữ ký giả. Mỗi chữ ký ghi tên ghế, người, ngày, evidence run và
      phạm vi ký/exception.

### Exit criteria

- [ ] Một người checkout commit review ở thư mục sạch chạy được baseline mà không
      dùng file untracked.
- [ ] Tài liệu không còn đồng thời ghi `Proposed`, `[ ]` toàn phase và “ALL
      COMPLETED”.
- [ ] BA decision không để trống trước khi Phase 2–3 thay đổi contract.

## Phase 1 — Migration và release artifact fail closed

**Owner:** Platform  
**Review:** CTO + Ops  
**Verification:** QA

### 1.1 Đóng gói migration resources

- [ ] Chuyển schema baseline thành package resource được version cùng migration,
      hoặc cấu hình một đường dẫn tuyệt đối bắt buộc; không suy ra repo root bằng
      số lượng `Path.parents`.
- [ ] Khai báo package data trong `pyproject.toml` và kiểm tra wheel/image thật có
      baseline JSON.
- [ ] `openapi_diff` cũng không phụ thuộc repo depth khi chạy trong artifact; nếu
      contract không nằm trong production image, tạo riêng CI artifact/checker có
      input explicit.
- [ ] Pin base image và `uv` image bằng digest hoặc version đã duyệt; lưu digest
      trong evidence.

### 1.2 Stamp safety

- [ ] `stamp 0001_prisma_baseline` từ chối khi baseline resource thiếu hoặc parse
      lỗi.
- [ ] DB rỗng phải bị từ chối; DB dành cho tạo mới phải dùng `upgrade`, không
      `stamp`.
- [ ] DB có bất kỳ mismatch table/enum/constraint/index nào phải bị từ chối.
- [ ] Khi stamp thất bại, `alembic_version` không được tạo hoặc thay đổi.
- [ ] Chỉ exact baseline mới được stamp; sau stamp, `upgrade head` là no-op và
      không đổi business data.

### 1.3 Downgrade và rollback

- [ ] Dùng một typed environment resolver cho app và migration CLI; không để
      `Settings` dùng `local` nhưng migration tự dùng `development`.
- [ ] Destructive downgrade mặc định bị chặn. Chỉ cho phép khi environment được
      khai rõ `local|test`, hoặc có explicit override theo runbook Ops.
- [ ] Missing/unknown environment không được suy thành local trong destructive
      path.
- [ ] Ghi migration classification: additive, compatible, destructive; chỉ
      additive/compatible được đi cùng application rollback thông thường.
- [ ] Viết runbook backup/restore; không gọi schema downgrade là data rollback.

### Tests bắt buộc

- [ ] Unit: baseline missing/malformed và environment missing/unknown fail closed.
- [ ] PostgreSQL integration: exact baseline PASS; empty DB, missing column,
      changed constraint, extra index đều FAIL.
- [ ] PostgreSQL integration: stamp failure giữ nguyên `alembic_version`.
- [ ] Container test: build image rồi chạy `python -m jplearn_api.migrate current`,
      `upgrade` và adoption `stamp` trên DB test cô lập.
- [ ] Restore drill trên staging clone giữ row counts và FK cho
      users/catalog/progress/events.

### Exit criteria

- [ ] Release migration chạy được từ chính immutable image/artifact sẽ deploy.
- [ ] Không có nhánh code nào stamp được DB rỗng hoặc bỏ verify vì thiếu file.
- [ ] Ops ký migration, adoption, backup và rollback runbook.

## Phase 2 — Semantic OpenAPI gate đầy đủ

**Owner:** Platform / Backend  
**Contract owner:** BA  
**Verification:** QA

### Comparator

- [ ] Tập operation cần so được suy từ handwritten contract hoặc allowlist có lý
      do; `/ready` là operation bắt buộc.
- [ ] So hai chiều operation, parameter, property và required set; extra generated
      response property phải fail nếu contract không cho phép.
- [ ] Resolve `$ref`, `allOf`, array items và normalize OpenAPI 3.0 nullable với
      OpenAPI 3.1 `anyOf/type union` trước khi so.
- [ ] So cả sự tồn tại và giá trị của min/max/minLength/maxLength/pattern/format,
      enum và nullable.
- [ ] So mọi success response và mọi error response được contract khai báo, bao
      gồm content type và schema body.
- [ ] So nguyên cấu trúc security alternatives; bearer và signed query là hai
      lựa chọn khác nhau, không rút gọn thành boolean.
- [ ] Loại generated 422 khỏi public generated schema tại custom OpenAPI boundary
      nếu runtime contract chỉ trả 400; comparator không được che drift bằng cách
      xóa 422 chỉ trong bản sao nội bộ.
- [ ] CLI trả non-zero và in diff có operation/context rõ cho mọi mismatch.

### Mutation suite bắt buộc

- [ ] `ci_level`: integer -> string.
- [ ] Bỏ minimum hoặc maximum.
- [ ] Thêm nullable.
- [ ] Bỏ required field.
- [ ] Nới enum `device_class`.
- [ ] Đổi 400 error body thành `{detail}` hoặc 422.
- [ ] Bỏ signed-query hoặc bearer alternative của media/HLS.
- [ ] Thêm forbidden response field.
- [ ] Xóa `/ready` khỏi generated operations.
- [ ] Mỗi mutation chứng minh CLI/gate đỏ, không chỉ gọi helper riêng.

### Exit criteria

- [ ] Handwritten và generated contract khớp theo rule đã được BA ký.
- [ ] Mutation suite chạy trong CI và không còn false-negative đã biết.
- [ ] OpenAPI checker chạy được từ clean checkout với input path explicit.

## Phase 3 — Storage, media và readiness đúng ports/adapters

**Owner:** Platform / Backend  
**Contract owner:** BA  
**Verification:** QA + Security review

### 3.1 Thu hẹp StoragePort

- [ ] Thay `get_path() -> Path` bằng capability application-owned, ví dụ
      `open_read()/stream_read()` cùng metadata cần thiết; local adapter và object
      storage adapter không làm router biết concrete storage.
- [ ] Composition root là nơi duy nhất chọn `LocalFilesystemStorage` hay adapter
      khác; router/service chỉ nhận port.
- [ ] File I/O blocking được offload hoặc dùng async adapter; test tải lớn xác nhận
      event loop không bị nghẽn đáng kể theo ngưỡng đã ký.
- [ ] Dùng `Path.relative_to()`/`is_relative_to()` hoặc kiểm parent canonical thay
      string prefix.

### 3.2 Upload policy và consistency

- [ ] Áp matrix BA đã ký cho MIME, extension, kích thước tối đa và status code.
- [ ] Không tin duy nhất `UploadFile.content_type`; xác định mức kiểm content
      signature cần thiết cho MP4/audio/HLS artifact.
- [ ] File rỗng, quá size, MIME/extension sai, filename độc hại và traversal đều
      bị từ chối trước khi tạo DB row.
- [ ] Giữ `.part -> promote`; mọi failure path xóa temp/final object tương ứng.
- [ ] Reconciliation có CLI report-only, structured metric/log và runbook. Delete
      chỉ chạy khi có explicit flag, retention window và Ops approval.
- [ ] Publish tiếp tục kiểm cả DB record và object/manifest thật.

### 3.3 Readiness capability

- [ ] Thêm `check_ready()` hoặc `probe_writable()` vào port thay vì introspect
      thuộc tính adapter.
- [ ] Local probe thực hiện bounded create/write/fsync-or-close/read/delete trong
      namespace riêng; object storage probe dùng capability tương đương.
- [ ] Probe trả 503 khi storage thiếu, read-only, quota/permission lỗi hoặc cleanup
      probe thất bại; không để lại orphan.
- [ ] `/health` không kiểm dependency; `/ready` kiểm DB và storage, có timeout và
      không chứa secret/path nhạy cảm trong response.

### Tests bắt buộc

- [ ] Traversal: `../outside`, absolute path, symlink escape và sibling-prefix.
- [ ] Upload nhiều chunk không buffer toàn file; MIME/size matrix đầy đủ.
- [ ] Storage failure không tạo DB row; DB failure không để final object.
- [ ] Readiness: `exists=False`, permission denied, read-only và write/delete lỗi
      đều 503; healthy adapter trả 200.
- [ ] Contract test chạy cùng một media use case qua local adapter và fake
      object-storage adapter mà không đổi router/service.

### Exit criteria

- [ ] Application layer không import hoặc trả `Path` cho media delivery.
- [ ] Readiness chứng minh dependency có thể phục vụ workload cần thiết, không chỉ
      chứng minh thư mục tồn tại.
- [ ] BA và QA ký media boundary; Ops ký reconciliation policy.

## Phase 4 — Runtime configuration, observability và deterministic test harness

**Owner:** Platform  
**Review:** Ops + QA

### Configuration/security

- [ ] Staging/production yêu cầu explicit non-empty CORS allowlist; không kế thừa
      localhost hoặc `exp://.*` regex mặc định.
- [ ] Local/test defaults được tách khỏi staging/production settings.
- [ ] Known password chỉ tồn tại trong isolated test fixture. README/runbook không
      hướng dẫn credential cố định và không có runtime default password.
- [ ] Secret validation được chạy trong API, migration/release job và seed CLI với
      cùng environment semantics.

### Observability

- [ ] Request path chỉ ghi structured/redacted log và enqueue alert best-effort.
- [ ] Dùng bounded queue có lifecycle trong composition root; không tạo unbounded
      background task cho từng lỗi.
- [ ] Định nghĩa timeout, retry/drop policy và metrics: queued, sent, failed,
      dropped; shutdown có bounded drain.
- [ ] 4xx không alert; 5xx có request ID/error class nhưng không có JWT, password,
      DB parameter hoặc PII.

### E2E isolation

- [ ] Mỗi run có unique Compose project, database/schema, storage temp dir và
      deterministic free ports hoặc process lock.
- [ ] Cleanup chỉ dừng PID/container do chính run tạo; không kill service của run
      khác.
- [ ] Test identity chứa run ID + browser/project; không dựa riêng vào
      `Date.now()`.
- [ ] Log và Playwright artifact mang cùng run ID; cleanup chạy cả khi test fail.
- [ ] CI không cho hai job dùng chung DB/ports/storage.

### Exit criteria

- [ ] Hai E2E run song song đều 10/10 hoặc bị serialize rõ ràng, không gây 401 do
      thay runtime của nhau.
- [ ] Webhook outage không kéo dài request latency ngoài ngưỡng đã ký.
- [ ] Production config thiếu CORS/environment/secret bắt buộc phải fail startup.

## Phase 5 — CI artifact gate và staging evidence

**Owner:** Ops + Platform  
**Verification:** QA  
**Phối hợp:** BA + Mobile

### CI/image gate

- [ ] CI build Docker image từ clean checkout và lưu immutable digest.
- [ ] Chạy image bằng non-root user; verify `/health`, `/ready`, shutdown và storage
      permissions.
- [ ] Chạy migration release job từ cùng image/digest trước API smoke.
- [ ] Chạy guard, 80+ pytest, complete OpenAPI mutation suite và 10/10 Web E2E.
- [ ] Không publish/deploy image nếu bất kỳ gate nào fail hoặc evidence thiếu.

### Staging

- [ ] Deploy internal staging từ immutable digest.
- [ ] HTTPS termination/redirect theo quyết định Ops; T-NFR-S1 ghi evidence từ
      external client, không chỉ gọi localhost.
- [ ] CORS chỉ cho origin staging đã ký.
- [ ] Smoke auth, catalog, session/progress, flags, media upload/playback/HLS,
      readiness và reconciliation report.
- [ ] BA + QA định nghĩa workload T-NFR-P1 trước khi chạy. Bằng chứng phải kiểm
      NFR-PERF-001: publish đến khi web/phone/iPad nhìn thấy item <= 5 phút, hoặc
      <= 15 phút chỉ khi pilot exception được ghi trong runbook.
- [ ] CTO + Ops ký thời lượng soak và ngưỡng 5xx, latency, DB pool, memory, storage
      error, alert loss và progress/event reconciliation trước khi bắt đầu soak.
- [ ] Chạy canary nội bộ; chưa mở learner traffic.
- [ ] Thực hiện application rollback bằng image trước và restore drill theo Phase
      1; lưu timestamps, row counts và người thực hiện.
- [ ] Chạy #30 trên thiết bị thật hoặc ghi exception đúng ghế; WebKit không thay
      native evidence.

### Exit criteria

- [ ] QA ký functional, contract, T-NFR-P1 và HTTPS evidence, hoặc ghi rõ exception
      cho từng mục.
- [ ] Ops ký deploy/migration/backup/restore/soak/canary/rollback.
- [ ] Mobile ký #30 hoặc exception vẫn mở và không tuyên bố native parity.
- [ ] CTO chỉ mở learner traffic sau khi toàn bộ release blocker được đóng.

## Phase 6 — Đóng tài liệu và walkthrough

**Owner:** CTO  
**Verification:** QA + Ops + BA + Mobile theo phạm vi

### Công việc

- [ ] Cập nhật plan 2026-09-04 bằng liên kết sang plan closure này; không viết lại
      lịch sử như thể mọi việc đã hoàn tất ngày 2026-09-04.
- [ ] Cập nhật `gates.md`, `board.md`, parity checklist, traceability, deployment và
      runbook bằng cùng evidence run ID.
- [ ] Tạo lại `walkthrough.md` từ kết quả cuối, ghi riêng `implemented`, `local
      verified`, `staging verified`, `exception/open`.
- [ ] Mỗi claim có commit SHA/image digest/command/evidence link; không dùng “100%”
      nếu comparator hoặc scope có allowlist.
- [ ] Ghi rõ Nest rollback chỉ còn qua Git history, không phải operational rollback.
- [ ] Review toàn bộ checkbox: chỉ đánh `[x]` khi evidence và chữ ký tương ứng đã
      tồn tại trong Git.

### Exit criteria

- [ ] Không còn mâu thuẫn giữa plan, walkthrough, gates, board và QA checklist.
- [ ] Một reviewer mới có thể tái tạo local gates và lần theo staging evidence mà
      không cần kiến thức ngoài repo.
- [ ] Walkthrough được commit cùng evidence hoặc sau evidence; file untracked không
      được dùng làm artifact nghiệm thu.

## 4. Thứ tự PR/commit khuyến nghị

1. `docs(api): reset hardening status and decision ownership`
2. `fix(api): make migration artifact and stamp fail closed`
3. `test(api): close semantic OpenAPI mutation gaps`
4. `fix(api): harden storage boundary and readiness probe`
5. `fix(api): fail closed runtime config and decouple alerts`
6. `test(api): isolate differential web e2e runs`
7. `ci(api): verify immutable image and migration job`
8. `ops(api): capture staging soak and rollback evidence`
9. `docs(api): close hardening gates with signed evidence`

Mỗi PR phải nhỏ, reviewable và giữ gate trước đó xanh. Không squash mất evidence
boundary nếu điều đó làm khó audit migration/contract/security fix.

## 5. Gate bắt buộc trên PR

```bash
pnpm test:guard
cd apps/api-python
uv run pytest -q
PYTHONPATH=src uv run python -m jplearn_api.openapi_diff
```

PR chạm contract/media/runtime phải chạy thêm:

```bash
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

Sau khi Phase 1 và Phase 5 bổ sung script lặp lại được, CI phải có thêm:

```text
build immutable image
run migration CLI from that image against isolated PostgreSQL
run image as UID 10001
probe /health and /ready including negative storage cases
run OpenAPI mutation gate
```

Command output phải được lưu với commit SHA/run ID; không chạm development DB,
named volume hoặc storage dev.

## 6. Definition of Done

- [ ] Trạng thái tài liệu phản ánh đúng implemented/local/staging/production.
- [ ] Migration CLI chạy trong immutable image; missing baseline, empty DB và schema
      drift đều fail closed.
- [ ] Destructive downgrade không chạy khi environment thiếu hoặc không hợp lệ.
- [ ] OpenAPI gate bắt toàn bộ mutation matrix và kiểm success/error/security.
- [ ] Storage traversal, MIME/size, compensation và reconciliation được test theo
      policy BA đã ký.
- [ ] StoragePort không làm application phụ thuộc local `Path`.
- [ ] `/ready` kiểm DB và storage write capability, có negative integration tests.
- [ ] Alert webhook không nằm trên critical request path; queue bounded và có
      metrics.
- [ ] E2E độc lập đạt 10/10 và không thể phá nhau khi chạy đồng thời.
- [ ] CI kiểm image, migration và readiness từ clean checkout.
- [ ] Có HTTPS, T-NFR-P1, staging soak, canary, application rollback và data restore
      evidence.
- [ ] #30 native đã PASS hoặc exception được ký đúng ghế.
- [ ] QA, Ops, BA, Mobile và CTO ký đúng phạm vi; không có self-declared sign-off.

## 7. Điều kiện dừng

Dừng release và không mở learner traffic nếu có một trong các điều kiện:

- migration command trong image không chạy hoặc có thể stamp DB rỗng;
- OpenAPI gate còn PASS với mutation bắt buộc;
- readiness có thể trả 200 khi storage không ghi được;
- traversal/MIME/upload compensation chưa có negative evidence;
- production config có thể fallback local CORS/environment/secret;
- E2E/evidence runner dùng chung DB, port hoặc storage không kiểm soát;
- staging chưa có HTTPS, performance, soak, rollback và restore evidence;
- chữ ký/exception bắt buộc chưa tồn tại trong Git.

## 8. Khối ký nghiệm thu

Chỉ điền sau khi evidence tương ứng đã commit.

- BA — media/error semantics: _chưa ký_
- QA — functional/contract/performance/HTTPS: _chưa ký_
- Ops — image/migration/backup/restore/soak/rollback: _chưa ký_
- Mobile — #30 hoặc exception: _chưa ký_
- CTO — quyết định mở learner traffic: _chưa ký_
