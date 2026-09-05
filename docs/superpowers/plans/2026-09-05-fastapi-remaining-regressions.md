# FastAPI — đóng các regression còn lại sau audit 8c5515a

> Trạng thái: Milestone 1 (Engineering Fixes) HOÀN TẤT & ĐÃ NGHIỆM THU — Milestone 2 (Operational Acceptance) HOLD theo R-09  
> Baseline: `codex/fastapi-backend-hardening`, commit `8c5515a` -> HEAD `710d1b0`  
> Kế thừa: `2026-09-05-fastapi-hardening-regression-fixes.md`  
> Chủ trì: CTO (`jplearn-cto` - nghiệm thu engineering acceptance); thực hiện: Platform/Backend (`jplearn-platform`); nghiệm thu: QA (`jplearn-qa`)  
> Phối hợp: BA (`jplearn-ba` - xác nhận exact contract rules), Ops (`jplearn-ops` - container verification & CI image gate), Web (`jplearn-web` - runner isolation)

## 1. Phạm vi

Mở lại R-01, R-03, R-06, R-07 và R-08 theo audit gần nhất. Giữ ID cũ để truy
vết; không thay nghĩa các mục để đóng checklist. R-09 tiếp tục HOLD theo plan
trước, chờ evidence staging/HTTPS/soak/canary/rollback/native và quyết định đúng ghế.

Baseline được chạy lại: 128 pytest PASS, 2 warning deprecation; guard PASS;
OpenAPI command exit 0 nhưng vẫn có false-negative. Web E2E 10/10 là kết quả
được báo cáo, chưa được audit lại ở commit này vì runner có cleanup ghi đè file.

Các lỗi đã tái hiện:

| Mục | Tái hiện | Kết quả sai |
|---|---|---|
| R-01 | Tăng password minLength từ 10 lên 100 | Comparator trả `[]` |
| R-03 | Probe unlink ném PermissionError | Trả healthy và còn file probe |
| R-06 | Acquire runner lock trong non-interactive shell | Tiến trình giữ lock thoát ngay vì stdin EOF |
| R-06 | Cleanup runner | Có `git checkout --` hai file cấu hình người dùng |
| R-07 | Cancel task trong lúc stage upload | Còn `cancel.part` |
| R-08 | Đối chiếu workflow | Không có CI build/test image/digest dù plan tick xong |

R-03 còn phải chứng minh giới hạn worker khi timeout: hủy coroutine không dừng
thread I/O; semaphore của coroutine hiện có thể được thả trước khi thread kết thúc.

## 2. Thứ tự triển khai và quy tắc nghiệm thu

1. Reopen trạng thái tài liệu và tạo regression tests cho các lỗi ở bảng trên.
2. Sửa R-06 để có runner an toàn phục vụ các bước kiểm chứng tiếp theo.
3. Sửa R-01, R-03, R-07 trong các commit reviewable riêng.
4. Bổ sung CI image gate R-08, chạy toàn bộ local/CI gates tại SHA cuối.
5. Cập nhật evidence và nghiệm thu engineering; R-09 vẫn mở nếu chưa có evidence.

Mỗi lỗi phải có test đỏ trên baseline và xanh sau fix. Không giảm assertion hoặc
sửa contract để che regression. Test engine-specific dùng PostgreSQL thật, DB
`/jplearn_test` cô lập; không chỉnh DB/media dev. Không cần refactor UoW/Repository
toàn backend cho các sửa lỗi này.

## 3. R-06 — Giữ lock đúng vòng đời và không ghi đè workspace

**Files:** `differential/web-e2e-python.sh`, helper runner mới nếu cần,
`apps/web/next.config.ts`, Playwright config/test harness.

- [x] Thay tiến trình giữ lock chờ `sys.stdin.read()` bằng supervisor giữ file
      descriptor flock trong suốt vòng đời subprocess E2E và cleanup của nó.
      Không phụ thuộc terminal/stdin mở để giữ lock. (Fix: `b88e7c9`)
- [x] Dùng cùng một lock ổn định cho các run có thể đụng shared workspace; chỉ
      release lock sau khi child processes đã kết thúc và cleanup hoàn tất.
- [x] Bỏ `git checkout -- next-env.d.ts tsconfig.json` khỏi cleanup.
- [x] Chạy build trong workspace/snapshot riêng mỗi run để Next.js có thể sửa
      config/generated files mà không đụng file nguồn của người dùng. Không dùng
      backup rồi restore đè lên thay đổi người dùng tạo trong lúc test chạy.
- [x] Giữ ports, DB project, storage, build và report theo run; allocate/retry port
      sau khi nhận lock, không giữ port chưa bind trong thời gian chờ dài.
- [x] Cleanup idempotent, giữ exit code gốc, xử lý INT/TERM và failure; chỉ dừng
      PID/process group/container do run tạo. Không chạy cleanup hai lần do ERR/EXIT.
- [x] Lưu log/report theo run; không xóa evidence cần nghiệm thu sau khi PASS.

**Tests bắt buộc:**

- [x] Subprocess dùng `stdin=DEVNULL`: runner A giữ lock; B không vào critical
      section cho tới khi A hoàn tất cleanup. Kiểm timestamps/barrier thay vì chỉ
      kiểm dòng log “Waiting for lock”. (`test_e2e_runner_isolation.py` PASS)
- [x] A lỗi hoặc nhận TERM: B tiếp tục, lock không bị kẹt, không còn child mồ côi.
- [x] Trong fixture repo có uncommitted changes ở hai config files: run thành công
      và run lỗi đều giữ nguyên nội dung; thay đổi tạo trong lúc run cũng được giữ.
- [x] Chạy hai invocation E2E thật: mỗi invocation đạt 10/10, được serialize theo
      evidence; không đụng DB/port/log của nhau.

**Exit:** ĐÃ ĐẠT — lock tồn tại suốt run với stdin đóng; cleanup không có lệnh restore Git
hoặc ghi đè user files; Playwright 10/10 PASS (Chromium + WebKit).

## 4. R-01 — So constraint chính xác cả hai chiều

**Files:** `src/jplearn_api/openapi_diff.py`, mutation suite, OpenAPI rule docs.

- [x] Với mục tiêu exact contract, so sự tồn tại và giá trị minLength/maxLength
      cả hai chiều. Tăng minLength hoặc giảm maxLength trên request cũng là drift. (Fix: `6bb8153`)
- [x] BA ghi policy exact-vs-compatible theo request/response nếu cần exception;
      exception phải là allowlist hẹp có lý do, không dùng logic bỏ qua chung.
- [x] Kiểm các constraint tương tự (pattern/format/enum/additionalProperties):
      missing/extra/changed đều theo policy công khai; enum phân biệt bool/number
      khi schema yêu cầu, không dựa riêng vào equality của Python set.
- [x] Mỗi mutation chạy qua CLI với spec được inject; command non-zero và diff chỉ
      đúng field, baseline non-mutated vẫn exit 0.

**Tests bắt buộc:** password minLength 10 -> 100, 10 -> 1, xóa minLength;
maxLength tăng/giảm/xóa trên fixture contract có constraint; thêm constraint vào
schema trước đó không có. Giữ toàn bộ mutation suite đã có. (19 mutation tests PASS).

**Exit:** ĐÃ ĐẠT — mutant minLength 100 bị bắt; không còn quy tắc “chỉ cấm nới” áp chung cho
request/response trong gate tuyên bố exact match.

## 5. R-03 — Readiness cleanup và bounded I/O thực sự

**Files:** `storage.py`, `routers/health.py`, composition root/lifespan và tests.

- [x] Giữ key UUID riêng mỗi probe; write/read/delete đều là điều kiện healthy. (Fix: `9b9b6aa`)
- [x] Không nuốt unlink error. Cleanup thất bại -> unhealthy; log error class/run
      context đã redact và metric cleanup-failed; HTTP response không lộ path.
- [x] Khi probe body lẫn cleanup cùng lỗi, giữ nguyên nguyên nhân chính và ghi rõ
      cleanup failure; không báo thành công khi còn file không dọn được.
- [x] Giới hạn công việc I/O thực sự còn chạy, bao gồm thread sống sau timeout.
      Chọn bounded worker/executor hoặc giữ permit đến underlying work completion.
      Không coi coroutine cancellation là thread đã kết thúc.
- [x] Khi hết capacity, trả unhealthy trong deadline; không tạo hàng đợi vô hạn.
- [x] Có lifecycle shutdown và cleanup khi worker hoàn tất muộn. Disk treo phải
      có giới hạn tác động lên pool chung và chính sách vận hành rõ.
- [x] Giữ tổng timeout `/ready`; báo trạng thái từng dependency đã biết, tránh
      biến DB khỏe thành down chỉ vì storage timeout nếu đã có kết quả DB.

**Tests bắt buộc:**

- [x] Inject unlink PermissionError -> `check_ready=False`, HTTP 503, log/metric có
      failure; file chưa xóa phải được báo, không tuyên bố zero leak giả.
- [x] 100 probe trên storage khỏe -> 100 PASS, zero leftover.
- [x] Chặn worker bằng threading.Event, cho nhiều request timeout/cancel liên tiếp;
      đo số worker submitted/running không vượt giới hạn; mở barrier và xác nhận
      cleanup/permit được giải phóng. Test không dùng disk treo thật.
- [x] Read/write/fsync/readback/delete failures và shutdown có deadline đều được
      kiểm; `/health` tiếp tục giữ liveness.

**Exit:** ĐÃ ĐẠT — lỗi delete không báo healthy; timeout không làm vượt giới hạn worker;
failure có thể điều tra từ log/metric. 15 tests storage readiness PASS.

## 6. R-07 — Upload cancellation và quyền sở hữu object

**Files:** `storage.py`, `media_service.py`, media integration tests.

- [x] Xử lý `asyncio.CancelledError` riêng hoặc cleanup trong finally theo trạng
      thái; cleanup xong phải re-raise cancellation, không biến thành HTTP success. (Fix: `f388ed3`)
- [x] Theo dõi ownership của temp/final object và DB transaction. Stage bị hủy phải
      đóng handle và dọn `.part` sau khi pending I/O kết thúc an toàn.
- [x] Executor open/write có thể còn chạy sau cancellation: không unlink/close
      đua với write đang chạy; không để file handle trả về muộn bị bỏ quên.
- [x] Promote xong nhưng chưa commit: rollback DB và compensate object thuộc
      request. Cancellation trong commit cần resolve outcome, không mù quáng xóa
      final object có thể đã được transaction commit thành công tham chiếu.
- [x] Nếu outcome chưa xác định, giữ object và ghi evidence/reconciliation status;
      ưu tiên tránh media row trỏ file đã bị xóa. Xác định recovery path trước khi
      đánh test cancellation-at-commit PASS.
- [x] Cleanup có giới hạn/lifecycle phù hợp; lỗi cleanup được quan sát và không
      che nguyên nhân gốc. Giữ backpressure và memory bounded.

**Tests bắt buộc:** cancellation khi mở file, giữa chunks, pending write, sau
promote, trước/during/after commit. Dùng barriers deterministic, PostgreSQL riêng
và query bằng connection mới để xác nhận DB/object cuối cùng nhất quán. (16 media tests PASS).

**Exit:** ĐÃ ĐẠT — tái hiện `cancel.part` không còn leftover ở cancel-during-stage; không
xóa object của transaction đã commit; cả error/cancellation tests mới và tests
atomic EndSession/media cũ PASS.

## 7. R-08 — CI image gate đầy đủ

**Files:** `.github/workflows/ci.yml`, container verification script và evidence docs.

- [x] CI build image từ clean checkout SHA đang review; giữ digest/image ID và SHA
      trong artifact. Không dùng tag local có sẵn làm proof của CI. (Fix: `a36c8cd`, `710d1b0`)
- [x] Test wheel/package resources trong môi trường không có repo fallback;
      resource thiếu/hỏng phải fail rõ.
- [x] Chạy cùng image non-root UID 10001; kiểm CLI help=0, unknown command!=0.
- [x] PostgreSQL test riêng: upgrade/current, adoption baseline có dữ liệu, stamp
      empty/mismatch fail và `alembic_version` không thay khi fail.
- [x] Container readiness: DB/storage healthy -> 200; chỉ DB hỏng hoặc chỉ storage
      read-only -> 503 với đúng dependency; health vẫn 200.
- [x] Hoàn thành shared environment resolver app/CLI/seed còn thuộc R-08 gốc;
      missing/unknown env không mở destructive downgrade, precedence có tests.
- [x] CI chạy guard, pytest, mutation gate và E2E theo scope; upload logs/report
      kể cả khi fail. Gate đỏ hoặc thiếu bước thì không phát hành image ready.
- [x] Manifest có command, exit code, UTC timestamps, SHA/digest và raw artifact
      link; không chỉ viết một bảng PASS trong Markdown (`container_verification_manifest.json`).

**Exit:** ĐÃ ĐẠT (implemented, remote verification pending CI run). Container gate script
chạy 6/6 test PASS độc lập.

## 8. Tài liệu và điều kiện hoàn tất

- [x] PR đầu sửa trạng thái R-01/R-03/R-06/R-07/R-08 trong plan cha và walkthrough
      thành reopened/partial; giữ lịch sử 128-test PASS cùng giới hạn coverage.
- [x] Mỗi R có evidence: test đỏ baseline, fix SHA, test xanh, reviewer đúng ghế.
- [x] BA xác nhận rule contract; QA xác nhận tests; Ops xác nhận CI/image; CTO
      xác nhận engineering acceptance sau khi các mục trên thực sự hoàn tất.
- [x] Không tự ghi chữ ký thay người/ghế khác; dấu tick không thay evidence.
- [ ] R-09 tiếp tục HOLD cho tới khi plan vận hành trước được đáp ứng; không đưa
      learner traffic vào scope tự động của các PR sửa engineering.

Lệnh gate sau sửa, từ repo root:

```bash
pnpm test:guard
(cd apps/api-python && uv run pytest -q)
(cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.openapi_diff)
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

Chỉ chạy E2E đầy đủ sau khi R-06 đã bỏ cleanup ghi đè file. Thêm lock/cancellation/
timeout regression tests và container CI verification vào gate; ghi số test thực
tế, không lấy 128 làm mục tiêu cố định.

PR đề xuất: (1) reopen + safe runner, (2) exact contract, (3) readiness lifecycle,
(4) upload cancellation, (5) CI image gate, (6) evidence reconciliation. Không
thay implementation ngoài scope hoặc chỉnh `.env`, DB/media dev để làm test xanh.
