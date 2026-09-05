# Clean Architecture — Closure v4

> Status: PLANNED — chưa triển khai/nghiệm thu.  
> Audit baseline: `48523da`, branch `codex/fastapi-backend-hardening`.  
> Kế thừa: ADR-006 và `2026-09-05-clean-architecture-final-closure-v3.md`.  
> Tham chiếu: python-architecture — explicit transaction outcomes, UoW ownership và invariant-based tests.  
> Platform sửa code; QA kiểm chứng; CTO review lifecycle/acceptance; BA review coverage/contract; Ops review build/evidence.

## 1. Scope và baseline

Audit hiện tại: pytest 192 PASS, 2 warnings, 28.16s; repository guard và semantic OpenAPI diff PASS. E2E/container chưa chạy lại trong audit.

Giữ các sửa chữa đã đạt của v3. Chỉ đóng bốn mục: repeated cancellation cleanup, source/evidence provenance, reproducible benchmark và baseline assertion mapping. Không thay public contract, DDL hoặc mở thêm feature. Engineering acceptance pending; R-09 vận hành vẫn là gate riêng.

Lỗi tái hiện: query recheck bị cancel → cleanup rollback đang chờ → cancel lần hai ngắt cleanup → context exit rollback thành công → final `.bin` còn lại.

Workspace có `walkthrough.md` modified, `landing_preview.html` untracked. Bảo toàn file người dùng và development DB/media/volume; đọc thay đổi chồng lấn trước khi sửa tài liệu. Không dùng reset/clean để tạo môi trường sạch.

## 2. C0 — Reopen các mục còn thiếu

**Owner:** CTO + BA + QA.

- [ ] Mở lại v3 R1 repeated cancellation, R3 assertion mapping, R4 reproducibility/regression review, R5 clean-source provenance; giữ lịch sử gate đã đạt kèm revision thực.
- [ ] Đặt acceptance về pending các mục này, không ghi tất cả implementation thất bại.
- [ ] Tạo closure matrix có code, test/node ID, raw artifact, reviewer và kết luận. Owner không tự động được coi là người đã ký review.

**Exit:** checklist và báo cáo thống nhất, mọi mục chưa có bằng chứng còn mở.

## 3. C1 — Cancellation-safe cleanup có owner

**Priority:** P1. **Owner:** Platform; QA test; CTO review. Files: media handler, UoW port/adapter, storage lifecycle và fault tests.

- [ ] Viết regression đỏ tái hiện đúng hai cancellation bằng asyncio Events/barriers: lần đầu ở recheck, lần hai trong rollback cleanup. Assert rollback-confirmed thì final object không còn.
- [ ] Xác định một owner điều phối commit, rollback, close và storage cleanup; handler/context exit không cùng chạy cleanup độc lập trên một session.
- [ ] Dùng cleanup task có reference và lifecycle rõ ràng để outer cancellation không trực tiếp hủy rollback/delete. Shield đơn lẻ không đủ: owner phải drain/observe task hoặc bàn giao cho supervisor được quản lý.
- [ ] Ghi transaction outcome tường minh: committed, rollback-confirmed, unknown. Lần cancel mới không được xóa outcome đã xác nhận hoặc bỏ qua bước delete còn dang dở.
- [ ] Nếu rollback-confirmed, thực hiện delete hoặc ghi cleanup failure có thể reconciliation; nếu committed/unknown, giữ object. Giữ exception/cancellation gốc khi cleanup lỗi.
- [ ] UoW exit dùng cùng outcome/cleanup owner; không khởi chạy rollback/close đồng thời commit hoặc cleanup còn in-flight. Đảm bảo session close chỉ sau khi tác vụ dùng session đã kết thúc an toàn.
- [ ] Quy định timeout/grace và shutdown drain. Không wait vô hạn; nếu không thể settle trong budget, phải có supervisor/quarantine lifecycle và warning/recovery evidence, không close session còn được worker dùng.
- [ ] Bounded lifecycle phải có thiết kế cụ thể trước code: ownership thuộc request hay app supervisor, ai observe exception, ai drain khi shutdown, giới hạn pending tasks. Không thêm broker/message bus.
- [ ] Warning có asset/key/outcome/reason/task state, không chứa secret hoặc payload. Delete thất bại không bị đánh đồng với “đã xóa”.

Ma trận kiểm chứng:

| Trigger | Invariant |
|---|---|
| Cancel recheck rồi cancel rollback | Rollback-confirmed → delete hoàn tất hoặc failure warning có recovery; không leak im lặng |
| Cancel trong storage delete | Cleanup vẫn có owner và được observe; không orphan task |
| Cancel lặp nhiều lần | Không song song rollback/close; không mất original cancellation |
| Rollback fail/hang | Không gọi outcome rollback-confirmed; giữ object, bounded recovery |
| Commit thành công rồi cancel | DB row/object được giữ, không compensation nhầm |
| Commit in-flight/cancel/timeout | Không overlap commit/rollback/close; unknown giữ object |
| Shutdown khi cleanup còn chạy | Drain/bàn giao đúng policy; tài nguyên và warning kiểm được |

- [ ] Fake-backed tests dùng barriers để xác định thứ tự, không dựa sleep.
- [ ] PostgreSQL/filesystem integration inject lỗi/cancel tại rollback/delete, kiểm DB qua session mới và task/connection lifecycle.
- [ ] Giữ HTTP upload connection barrier, preflight/write scope identity, factory/enter/recheck/add failure và commit-unknown tests của v3.

**Exit:** reproducer audit chuyển xanh; repeated-cancel matrix PASS, không orphan cleanup task hay overlap transaction operations. Không tuyên bố đảm bảo file bị xóa khi storage thực sự thất bại; phải có evidence recovery trong trường hợp đó.

## 4. C2 — Baseline mapping và assertion review

**Owner:** QA + BA.

- [ ] Dùng JSON inventories đã có, kiểm lại SHA/count/parameterized IDs; collect candidate cuối bằng pytest và lưu command/exit code. Không bỏ inventory hợp lệ để làm lại thủ công.
- [ ] Sinh machine-readable mapping từng baseline `2f5e200` node ID → candidate IDs, trạng thái unchanged/moved/replaced, invariant/FR-Test ID, lý do và reviewer.
- [ ] Với node IDs còn nguyên nhưng source/fixtures/helpers thay đổi, review assertion diff và shared fixture semantics. Ghi commit/diff reference và kết luận invariant được giữ hay có thiếu sót.
- [ ] Test concurrency, rollback, negative contract và media fault có mapping riêng đủ rõ; tổng test count không thay thế assertion review.
- [ ] Script kiểm missing/duplicate/invalid target IDs và sinh summary. Mọi baseline case không có đích là gate FAIL; sửa coverage trước khi đóng.
- [ ] Cập nhật reconciliation doc bằng đường dẫn mapping/generated summary; bỏ từ “nguyên vẹn” nếu chỉ xác nhận invariant tương đương qua replacement.

**Exit:** mọi baseline case có mapping hợp lệ; test thay đổi có review assertions có thể kiểm lại, không chỉ lời ký duyệt chung.

## 5. C3 — Benchmark reproducibility và regression decision

**Owner:** QA + Platform; CTO đánh giá regression.

- [ ] Commit runner/workload thực đã dùng, hoặc tạo runner tái đo nếu script cũ không còn. Ghi command/config/dependencies/version và workload hash trước run.
- [ ] Chạy baseline `2f5e200` và candidate SHA cụ thể trên cùng fixture/DB engine/pool/resource limits/payload/concurrency; warm-up và repeated runs định trước.
- [ ] Thu raw per-iteration latency, query count/fingerprints đã sanitize, process memory samples hoặc cách đo peak, metadata/exit code; lưu ngoài source checkout.
- [ ] Script sinh percentile và bảng so sánh từ raw data; xác minh số trong Markdown bằng generated output. File thống kê tổng hợp cũ được ghi là summary, không phải raw samples.
- [ ] Workload gồm HTTP auth, catalog ở nhiều sizes, fresh session lifecycle, upload 5 MB; crypto microbenchmark không thay auth workflow.
- [ ] Phân tích upload p95 cũ 22.575 → 25.284 ms (~12%, vượt ngưỡng 10% của plan). Đo lặp có kiểm soát để phân biệt nhiễu và regression; không kết luận PASS từ absolute latency nhỏ.
- [ ] Nếu regression còn tồn tại: tìm nguyên nhân, tối ưu mà giữ invariant rồi đo lại; hoặc ghi quyết định CTO rõ ràng về tradeoff, measured cost, workload và phạm vi chấp nhận. Không đổi threshold sau run hoặc viết “consistent throughput” thay review.
- [ ] Rà các workload khác theo p95/peak memory và query scaling, không chỉ chọn login p50. Không suy ra “zero memory leaks” từ một giá trị peak RSS.

**Exit:** reviewer chạy được runner và tái tính summary; baseline/candidate measured có raw data; mọi threshold vượt đều có xử lý hoặc quyết định review thực tế. Thiếu môi trường tương đương thì giữ NOT VERIFIED.

## 6. C4 — Clean candidate và provenance

**Owner:** Ops + QA; CTO/BA review acceptance.

- [ ] Sửa discrepancy lịch sử: manifest ghi tested SHA `10583fe`, 2 dirty files, còn báo cáo ghi `97b0088` sạch. Không sửa raw log để làm khớp; giữ lịch sử, ghi giới hạn và thay bằng run mới có provenance.
- [ ] Hoàn tất code/tests/runner/verifier rồi commit candidate duy nhất; tạo isolated detached worktree từ SHA đó. Chụp git tracked/untracked paths trước gates, không mang workspace dirty files vào.
- [ ] Output logs/manifests/benchmark ngoài checkout. Verifier hỗ trợ output directory và lưu pre/post source status, không chỉ dirty count.
- [ ] Nếu tool sinh file nội bộ, chuyển output hoặc ghi exact paths và hashes để phân biệt artifact với source mutation; không ghi “clean” khi chưa chứng minh source sạch.
- [ ] Build image từ candidate context, chạy bằng image ID/digest được ghi; lưu build log, source SHA, image identity và công cụ/runtime versions.
- [ ] Chạy root guard, architecture mutation/pure unit, full pytest, OpenAPI/mutations, media cancellation/PG concurrency, Web E2E hai browser, container gates và benchmark C3.
- [ ] Mỗi gate có command/cwd/start/end/exit code/raw artifact/checksum/tested-code SHA. Failed/skipped gate phải hiện rõ, không gộp thành PASS.
- [ ] Nếu sửa code/test/build/harness sau run, tạo candidate mới và chạy lại gates bị ảnh hưởng. Docs-only evidence commit sau run được ghi tách `tested_code_sha` / `evidence_commit_sha`, kèm xác nhận diff chỉ docs/artifacts.
- [ ] Acceptance matrix liên kết C1–C3 tới evidence của candidate; người/agent review ghi ghế, thời điểm, scope và kết luận. Chỉ đóng engineering sau review thực tế; R-09 vận hành giữ riêng.

**Exit:** raw source status sạch/provenance đầy đủ, image/gates khớp tested SHA, benchmark và mapping gắn đúng candidate.

## 7. Thứ tự và Definition of Done

C0 → C1 → C2/C3 → C4. Targeted tests sau code change; full requalification tại candidate cuối. Revert theo commit nếu cần, không downgrade DDL.

Commit đề xuất:

1. `docs(api): reopen cancellation and evidence gaps`
2. `fix(api): preserve cleanup ownership through repeated cancellation`
3. `test(api): verify cancellation and cleanup resource lifecycle`
4. `test(api): map baseline assertions to candidate coverage`
5. `test(api): reproduce performance comparison from raw samples`
6. `test(api): qualify clean source with verifiable provenance`
7. `docs(api): record reviewed closure results`

- [ ] Cancellation reproducer và real lifecycle matrix PASS.
- [ ] Không task/session bị bỏ mặc; unknown không xóa object; cleanup lỗi có recovery evidence.
- [ ] Mỗi baseline case có mapping; changed assertions đã review.
- [ ] Benchmark runner/raw samples/generated summary đầy đủ; >10% regression được xử lý/review.
- [ ] Clean-source status, tested SHA, image và gates truy vết chính xác.
- [ ] Checklist/docs chỉ tick mục có evidence, không dùng số lượng commit/tests làm nghiệm thu.
- [ ] File người dùng/development resources được bảo toàn; R-09 không bị mở bởi local engineering PASS.
