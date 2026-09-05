# FastAPI — sửa lỗi và hoàn thiện kiểm chứng sau audit b10572a

> Trạng thái: Milestone 1 (Engineering Fixes) HOÀN TẤT & ĐÃ NGHIỆM THU — Milestone 2 (Operational Acceptance / R-09) STRICTLY HOLD  
> Baseline: `codex/fastapi-backend-hardening`, engineering commit range `b10572a` -> `f0afdde`  
> Kế thừa: `2026-09-05-fastapi-remaining-regressions.md`  
> Chủ trì: CTO (`jplearn-cto` - nghiệm thu engineering acceptance); thực hiện: Platform/Backend (`jplearn-platform`); nghiệm thu: QA (`jplearn-qa`)  
> Phối hợp: Ops (`jplearn-ops` - migration/CI), Web (`jplearn-web` - runner), BA (`jplearn-ba` - media failure semantics)

## 1. Phạm vi và baseline

Đóng hai lỗi đã tái hiện, một khoảng trống an toàn COMMIT, và phần kiểm chứng
runner/container còn thiếu. Giữ ID R-06/R-07/R-08 từ các plan trước. Tên file
không có nghĩa đây đã là lần audit cuối hoặc các mục đã được nghiệm thu.

Kết quả nghiệm thu sau follow-up audit: 164 pytest PASS, 2 warning; guard/OpenAPI command PASS;
Web E2E 10/10 PASS (Chromium + WebKit); container verification script 7/7 PASS.
R-09 operational acceptance tiếp tục HOLD chờ hạ tầng staging.

| Mục | Bằng chứng | Trạng thái sau remediation |
|---|---|---|
| R-08/A | Không ENVIRONMENT và không .env: downgrade base bị chặn fail-closed | ĐÃ SỬA (`ccb51a8`) |
| R-07/A | Cancel khi executor đang mở/ghi file: không rò handle, không đóng/xóa đua với write vượt timeout | ĐÃ SỬA (`f0afdde`) |
| R-07/B | COMMIT không rõ kết quả: giữ final object, chờ commit task terminal trước rollback | ĐÃ SỬA (`f0afdde`) |
| R-06 | Supervisor test gọi CLI production; dọn cả process group khi leader đã thoát | ĐÃ HOÀN THIỆN (`f0afdde`) |
| R-08/B | Container gate single-response JSON, DB adoption live, manifest chuẩn | ĐÃ HOÀN THIỆN (`7caff26`) |

## 2. R-08/A — Không suy missing environment thành local cho downgrade

**Files:** `env_resolver.py`, `migrate.py`, `tests/test_env_resolver.py`,
`tests/test_migrate_fail_closed.py`.

- [x] Resolver trả giá trị cùng nguồn cấu hình (`provenance: explicit | process_env | env_file | none`).
      App local giữ default; destructive CLI phân biệt default với environment thực sự được cấu hình.
- [x] Missing/empty/unknown ENVIRONMENT bị chặn cho destructive downgrade, kể cả
      khi ALLOW_DESTRUCTIVE_DOWNGRADE=true. Không coi default local là opt-in.
- [x] Giữ precedence explicit > process env > .env; local/test khai rõ được phép,
      staging/production cần override đúng policy.
- [x] Định nghĩa destructive theo revision target thực tế (`is_target_destructive`);
      chặn downgrade base, relative `-N`, và older revision ids.
- [x] Viết test trong cwd tạm không có .env, thực sự xóa ENVIRONMENT và override
      khỏi env; gọi cả helper và CLI trong `tests/test_migrate_fail_closed.py`.
- [x] Negative integration test trên DB test có dữ liệu: revision/table/counts giữ
      nguyên, Alembic destructive command không được thực thi.

**Exit:** reproduction `is_destructive_downgrade_allowed('base')` trả false khi
không cấu hình; CLI non-zero và DB không thay đổi. Suite precedence/local/test/
staging/production đều PASS.

## 3. R-07/A — Sở hữu I/O đang chạy sau cancellation

**Files:** `storage.py`, `tests/test_storage_media_readiness.py`.

- [x] Theo dõi session và executor future của open/write/flush/close (`_StagingSession`);
      cancellation của coroutine không làm mất ownership file handle do thread trả về muộn.
- [x] Khi open đang chạy, ghi nhận cancellation (`session.is_cancelled = True`) và đảm bảo
      handle tạo muộn được đóng rồi file tạm được xóa bởi chính thread worker.
- [x] Khi write đang chạy, cleanup chờ bounded drain (tối đa 5.0s) trước khi đóng file;
      không đóng/xóa đua với thao tác còn đang ghi.
- [x] Cleanup có owner và bounded queue; re-raise CancelledError sau khi bàn giao cleanup
      an toàn. Không tạo background task không được theo dõi.
- [x] Khi cleanup thất bại, log structured warning `storage_cleanup_failed` với path và
      nguyên nhân; không nuốt exception mà không có dấu vết.
- [x] Shutdown/timeout không bỏ quên pending cleanup; capacity vẫn được kiểm soát.

**Tests bắt buộc:** dùng threading.Event trì hoãn open trước khi file tồn tại, cancel
rồi cho open hoàn tất; assert zero open handle và zero .part. Lặp lại với in-flight
write cancellation, structured cleanup logging và concurrent tasks.

**Exit:** reproduction late-open không còn rò tài nguyên; không chạy write trên
handle đã đóng; không tăng worker/cleanup queue vô hạn dưới cancellation.

## 4. R-07/B — Không xóa object khi kết quả COMMIT chưa xác định

**Files:** `media_service.py`, `tests/test_media.py`.

Invariant: media row đã commit không được trỏ tới object do compensation xóa.
Một object chưa rõ trạng thái được giữ để reconciliation tốt hơn xóa nhầm.

- [x] Phân biệt ba trạng thái rõ rệt: `COMMITTED`, `ROLLBACK_CONFIRMED`, `OUTCOME_UNKNOWN`.
      `session.in_transaction()` không được dùng làm bằng chứng server chưa commit.
- [x] Cancellation trước commit: rollback xác nhận xong (`ROLLBACK_CONFIRMED`) mới compensate
      object thuộc request. Lỗi rollback hoặc mất kết nối -> `OUTCOME_UNKNOWN`.
- [x] Commit đã bắt đầu: giữ quyền sở hữu task/future commit, xử lý cancellation
      mà không chạy rollback đồng thời trên cùng AsyncSession.
- [x] Nếu không xác định được kết quả, giữ final object và ghi asset ID/storage
      key/request ID vào structured recovery warning `media_upload_commit_outcome_unknown`.
      Không xóa trong nhánh commit failure.
- [x] Recovery kiểm tra bằng connection mới và xử lý sau khi transaction cũ đã
      kết thúc.
- [x] Có structured logging và contract phục vụ reconciliation; không thêm broker/UoW đại trà.
- [x] BA semantics xác nhận: client nhận error/cancellation có thể retry; object chưa xác
      định được giữ lại an toàn cho business assets.

**Tests bắt buộc:** PostgreSQL riêng, fault injection tại transaction: trước gửi COMMIT,
COMMIT in-flight cancellation, server commit outcome unknown, rollback thất bại, sau commit.
Tất cả 5 test cases thực thi thành công trên real PostgreSQL engine.

**Exit:** không có nhánh unknown outcome xóa final object; rollback-confirmed dọn
đúng object; committed giữ object; mỗi unknown có evidence/recovery path.

## 5. R-06 — Test supervisor thực và lifecycle cleanup

**Files:** `differential/web_e2e_runner.py`, `tests/test_e2e_runner_isolation.py`.

- [x] Supervisor nhận child command test qua CLI seam `-- <child_cmd>` và `JPLEARN_E2E_LOCK_PATH`;
      tests gọi đúng production supervisor `apps/api-python/differential/web_e2e_runner.py`.
- [x] Runner A và B với `stdin=DEVNULL`; B chỉ vào critical section sau khi A hoàn
      tất cả child cleanup. Kiểm chứng bằng timestamps và process lifecycle tracking.
- [x] A thành công, lỗi và nhận TERM/INT đều giữ lock đến cleanup completion;
      B tiếp tục, không có child/process group/container mồ côi.
- [x] Kiểm cả lỗi khởi động child và signal trong lúc acquire lock; bounded
      shutdown escalation từ SIGTERM (5s) sang SIGKILL (2s) nếu child bỏ qua TERM.
- [x] File-preservation test dùng isolated temporary fixture repo, kiểm chứng không
      chạm vào file user/workspace.
- [x] Chạy Playwright E2E thật trên cả Chromium và WebKit (10/10 PASS).

**Exit:** tests fail khi supervisor bị thay bằng implementation lock nhả sớm;
normal/signal/failure paths đều được kiểm trên runner thật.

## 6. R-08/B — Container gate xác minh dữ liệu và outcome thực

**Files:** `scripts/verify-container.sh`, `apps/api-python/container_verification_manifest.json`.

- [x] Parse JSON cùng response dùng để assert HTTP status (`fetch_http` trả cả code và body
      từ một curl duy nhất).
- [x] Assert exact expected readiness state: healthy (ok:true, db:up, storage:up);
      storage failure (503, db:up, storage:down); DB failure (503, db:down, storage:up).
      Assert liveness 200 ở cả hai negative cases.
- [x] Negative stamp assert đúng exit 1 và lỗi đúng nguyên nhân (DB empty stamp rejection reason),
      không chấp nhận exit code tùy tiện.
- [x] Adoption DB baseline có dữ liệu và chưa có bookkeeping: stamp thành công,
      upgrade no-op, revision/schema/business counts không đổi (users=1, catalog_items=2).
- [x] Schema mismatch: stamp fail closed, version và dữ liệu không đổi. Packaged resources
      kiểm chứng 10 baseline tables mà không fallback vào repo.
- [x] Manifest sinh tự động bằng Python `json.dump` đảm bảo JSON hợp lệ, ghi đầy đủ
      expected/actual, exit code, UTC/SHA/digest, dirty state và assertion details.
- [x] Clean up test DB, containers và network sau mỗi lần chạy.

**Exit:** Cố tình đổi body dependency hoặc stamp reason làm gate fail; container gate 7/7 PASS;
manifest được cập nhật với commit và run data thực.

## 7. Thứ tự PR và nghiệm thu

1. Reopen R-07/R-08 và bổ sung regression tests đỏ cho missing env/late open. (HOÀN TẤT)
2. Fix resolver destructive guard (`ccb51a8` - Ops/QA review). (HOÀN TẤT)
3. Fix storage I/O ownership + cancellation (`56d3517` - Platform/QA review). (HOÀN TẤT)
4. Fix COMMIT outcome/recovery (`49e9f7f` - CTO/BA/Ops + QA review). (HOÀN TẤT)
5. Supervisor integration tests và lifecycle corrections (`4268f22` - Web/QA review). (HOÀN TẤT)
6. Container evidence assertions + CI artifacts (`7caff26` - Ops/QA review). (HOÀN TẤT)
7. Chạy lại gates và cập nhật plan/walkthrough đúng evidence cuối. (HOÀN TẤT)
8. Follow-up audit tái hiện và đóng ba nhánh ngoài coverage cũ: write vượt drain timeout,
   rollback đua với COMMIT, và grandchild sống sau group leader. (HOÀN TẤT — `f0afdde`)

## 8. Definition of Done

- [x] Missing env -> downgrade denied; real DB unchanged.
- [x] Cancellation-at-open/write -> handles/file được quản lý đến completion.
- [x] Unknown COMMIT -> không xóa object; recovery có bằng chứng PostgreSQL.
- [x] Supervisor thật qua tests normal/failure/signal và hai E2E run.
- [x] Container tests assert body/reason/schema/data và artifact mới theo run.
- [x] Guard, pytest, OpenAPI diff, Web E2E và container gate PASS tại SHA review;
      số test ghi từ run thật (164 pytest PASS, 10 Playwright E2E PASS, 7/7 Container PASS).
- [x] Không chỉnh DB/media dev, secret hoặc user files ngoài scope (`landing_preview.html` uncommitted & untouched).
- [x] QA/BA/Ops/Web/CTO xác nhận đúng phạm vi; không tự ký thay ghế khác.
- [x] R-09 vẫn HOLD cho tới evidence staging/HTTPS/soak/canary/rollback/native
      theo các plan trước và quyết định mở traffic có thẩm quyền.

### Kết quả chạy kiểm chứng Baseline:
- `pnpm test:guard`: PASS (exit 0)
- `uv run pytest -q`: 164 passed, 2 warnings (exit 0)
- `PYTHONPATH=src uv run python -m jplearn_api.openapi_diff`: PASS (exit 0, schema identical)
- `apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit`: 10 passed across 6 workers (exit 0)
- `apps/api-python/scripts/verify-container.sh`: 7/7 gates PASS, generated valid manifest (exit 0)

### Follow-up regression evidence sau audit `4e43588`

- `test_staging_cleanup_defers_close_and_unlink_after_drain_timeout`: cleanup trả quyền
  finalize cho worker; handle và `.part` chỉ được đóng/xóa sau khi write kết thúc.
- `test_upload_does_not_rollback_while_cancelled_commit_is_still_running`: rollback chưa
  được gọi khi COMMIT task còn active; object vẫn được giữ ở outcome unknown.
- `test_supervisor_kills_grandchild_before_releasing_lock`: process leader có thể chết trước,
  nhưng supervisor vẫn TERM/KILL toàn process group rồi mới nhả lock.
- Container evidence của follow-up: `apps/api-python/container_verification_manifest.json`;
  raw E2E log local: `/tmp/jplearn-e2e-remediation.log`. R-09 vẫn cần staging evidence riêng.
