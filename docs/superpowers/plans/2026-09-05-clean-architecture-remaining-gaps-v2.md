# Clean Architecture — Remaining Gaps v2

> Status: PLANNED — chưa triển khai.  
> Baseline: `b565b7b`, branch `codex/fastapi-backend-hardening`.  
> Bổ sung: `2026-09-05-clean-architecture-audit-gap-closure.md`, ADR-006.  
> Kiến trúc: python-architecture — UoW sở hữu transaction/repositories, dependency inversion, explicit DI, test bằng state/invariant.  
> Owner: Platform implementation; CTO architecture review; BA contract/coverage; QA verification; Ops container evidence.

## 1. Phạm vi và kết quả đã xác nhận

Giữ các sửa chữa đã đạt: compensation khi media repository add lỗi, xóa root ORM alias/media service, reconciliation application handler và public contract hiện tại.

Audit baseline: guard PASS; pytest 179 passed, 2 warnings, 34.14s; semantic OpenAPI diff PASS. Web E2E/container chưa được chạy lại trong audit. Manifest đang có SHA `59fe698` và `git_dirty_files=2`; không đủ chứng minh clean checkout. HEAD có thêm thay đổi test harness `b565b7b`.

Các block dưới đây đóng G1, G3, G4, G5, G6 còn thiếu. Không viết lại backend lần nữa, không thay DDL/OpenAPI/FR-NFR. R-09 tiếp tục là gate vận hành riêng.

Workspace đang có `walkthrough.md` modified và `landing_preview.html` untracked. Giữ nguyên thay đổi của người dùng; đọc và đối chiếu trước khi chỉnh tài liệu chồng lấn. Không dùng reset/clean để tạo checkout sạch.

## 2. V0 — Reopen đúng checklist

**Owner:** CTO + BA + QA.

- [ ] Đổi engineering status sang “verification pending” trong tài liệu nghiệm thu liên quan; giữ nguyên lịch sử gate đã chạy cùng SHA/phạm vi.
- [ ] Mở lại đúng các checkbox G1 transaction ownership/short scope, G3 signing fallback, G4 transitive/alias guard, G5 per-test mapping, G6 performance/clean evidence.
- [ ] Với các checkbox khác, lập bảng `requirement → code → test → raw evidence`. Mục chỉ có lời khẳng định vẫn để pending; không suy ra PASS từ tổng số test.
- [ ] Ghi owner và review artifact cho mỗi V0–V6. Phân công ghế không đồng nghĩa ghế đã ký nghiệm thu.

**Exit:** checklist phản ánh đúng audit, không xóa kết quả đã đạt và không tự tuyên bố tất cả các mục ngoài audit đều hoàn tất.

## 3. V1 — UoW ownership và upload không giữ transaction dài

**Owner:** Platform; review CTO; verification QA. **Ưu tiên đầu tiên.**

Files: `application/ports/unit_of_work.py`, `adapters/persistence/unit_of_work.py`, `bootstrap.py`, `application/handlers/media.py`, `routers/media.py`, dependency/security wiring và các write handlers liên quan.

- [ ] UoW factory tạo session và repositories cùng scope; handler lấy repositories từ UoW. Loại bỏ API production nhận cặp UoW/repository độc lập có thể thuộc hai session khác nhau.
- [ ] Read queries có query scope riêng. Chuyển các write use cases còn dùng cặp session/repository độc lập sang cùng contract; không để hai mô hình UoW tồn tại vô thời hạn.
- [ ] Upload chạy theo ba scope: preflight query mở/đóng ngắn → stage/promote không giữ DB transaction → metadata write trong UoW mới. Kiểm auth dependency cũng đóng read transaction trước khi stream upload.
- [ ] Revalidate catalog reference tại write boundary; nếu catalog biến mất giữa preflight và write, FK/adapter error dẫn tới rollback và compensation đúng contract.
- [ ] UoW context có explicit commit, rollback-by-default và close khi sở hữu session. Media commit coordinator phải settle hoặc kết thúc an toàn commit task trước rollback/close; không thêm `async with` đơn thuần gây race.
- [ ] Thể hiện outcome trong application-owned type/state; cleanup chỉ xóa object sau rollback xác nhận. Unknown giữ object và warning. Không biến post-commit response error thành rollback-confirmed.
- [ ] Quy định task cancellation lặp lại và cleanup timeout: task còn hoạt động phải có owner; không rollback/close session đang COMMIT, không chờ vô hạn không có recovery policy. Adapter xử lý cancellation phải có test thực tế.

**Tests bắt buộc:**

- [ ] UoW tạo mới mỗi invocation, repositories dùng chính session đó; managed scope close trên success/error/cancel/early exit.
- [ ] Tạm dừng byte stream bằng barrier: connection của auth/preflight đã trả pool, không còn transaction request đó trong `pg_stat_activity`; không dùng sleep để suy đoán.
- [ ] Catalog bị xóa giữa preflight/write: không có metadata mồ côi, final object được dọn sau rollback xác nhận.
- [ ] Giữ add/flush/pre-commit failure tests; thêm rollback failure, repeated cancellation, commit success/response cancelled, commit unknown và cleanup warning tests.
- [ ] Commit/rollback/close instrumentation chứng minh không overlap; dữ liệu kiểm lại bằng PostgreSQL session mới.
- [ ] EndSession real PostgreSQL concurrency, auth registration atomicity và catalog contract vẫn PASS sau thay UoW API.

**Exit:** write handler không thể ghép repository ngoài scope; upload không giữ DB transaction trong stage; toàn bộ fault matrix và integration liên quan PASS.

## 4. V2 — Xóa signing fallback và hoàn tất runtime capabilities

**Owner:** Platform + CTO; QA kiểm contract.

- [ ] `MediaUrlSigner` là dependency bắt buộc cho nghiệp vụ tạo signed URL; xóa import `jplearn_api.signed_url`, `_signed_playback`, `_signed_hls` và fallback `(base_url, secret)` khỏi application handler.
- [ ] Base URL cần lưu metadata được biểu diễn bằng capability/config input không mang secret; không nhầm raw playback location với signed URL có expiry.
- [ ] HMAC, expiry clock và secret chỉ nằm trong security adapter được bootstrap cấu hình. Test handler dùng fake signer; integration/vector tests dùng adapter thật.
- [ ] Kiểm toàn bộ command/query/handler còn mang secret hoặc gọi time/ID mặc định; migrate sang configured security port và injected callable khi cần. Không giữ fallback chỉ để test cũ chạy được.
- [ ] Sửa tests qua public ports thay vì monkeypatch module ký URL; giữ JWT/HMAC vectors, expiry, HLS và OpenAPI parity.

**Exit:** inner layers không thể tự ký URL bằng secret truyền vào; test xác nhận mọi signing đi qua injected port, không ảnh hưởng URL/expiry contract.

## 5. V3 — Guard thực sự kiểm transitive imports và aliases

**Owner:** QA + Platform; review CTO.

- [ ] Tách scanner thành module độc lập; parse import graph của package và resolve modules, symbols/re-exports, relative imports và package `__init__`.
- [ ] Duyệt reachable dependencies từ domain/application với cycle detection; báo dependency chain đầy đủ tới outer layer/framework/env helper. Root helper không phải vùng miễn kiểm tra.
- [ ] Resolve constructor aliases: `from ... import Class as U`, `import ... as p; p.Class(...)`, re-export và assignment alias đơn giản. Không chỉ so tên text của call.
- [ ] Giới hạn dynamic import/execution trong inner layers; trường hợp không resolve được phải diagnostic/fail rõ ràng theo rule đã định, không im lặng bỏ qua. Không yêu cầu phân tích Python động tổng quát.
- [ ] Enforce composition ở toàn bộ production HTTP/CLI entrypoints; ghi chính xác các wiring modules hợp lệ. Concrete UoW được dựng repository nội bộ; không cấm wiring nội bộ đúng boundary này.
- [ ] Thêm mutation fixtures cho direct, relative, transitive root helper → SQLAlchemy/settings, re-export ORM, aliased constructor, module alias, dynamic-import alias; có valid/cyclic fixtures để kiểm false positive.
- [ ] Mỗi mutation assert rule ID/path/chain cụ thể. Chạy guard trong unit context không import FastAPI app qua conftest chung; import side-effect test chặn cả constructors engine/storage/client/task cần kiểm, không chỉ socket.

**Exit:** hai bypass đã audit đều fail: unchecked root helper dẫn ra infrastructure và `SqlAlchemyUnitOfWork as U; U(session)`. Có raw mutation output và positive cases PASS.

## 6. V4 — Mapping từng test và bằng chứng coverage

**Owner:** QA + BA.

- [ ] Collect pytest node IDs ở `2f5e200`, `4ae7673`, `b565b7b` và candidate bằng isolated checkout/dependencies đúng revision. Collect không chạy DB tests; ghi các giới hạn nếu baseline không collect được.
- [ ] Sinh JSON/CSV inventory giữ parameterized node IDs, file, revision; count tự tính, không nhập tay.
- [ ] Mỗi baseline case có mapping: unchanged/moved/replaced → candidate node ID(s), invariant/FR-Test ID, lý do thay và reviewer. Không để dòng baseline không có đích hoặc chỉ ghi “all preserved”.
- [ ] So sánh assertions của test sửa/thay; giữ node ID không chứng minh invariant cũ vẫn được kiểm. Negative/concurrency/rollback phải map rõ.
- [ ] Reconcile bảng test count, hiện có lệch architecture 13/14; generated report phải khớp collection thực.
- [ ] Cập nhật `test_mapping_and_reconciliation.md` bằng link inventory; lưu proof pure suite không bootstrap app/DB và negative state tests khi checklist yêu cầu.

**Exit:** tất cả baseline cases được giải thích, không mất invariant để tăng tổng count; báo cáo count khớp candidate.

## 7. V5 — Performance đối chứng có raw data

**Owner:** QA + Platform; CTO đánh giá regression.

- [ ] Chốt trước workload/config: baseline trước rewrite `2f5e200` và candidate; có thể thêm `b565b7b` để tách ảnh hưởng vòng sửa này. Cùng database fixture, CPU/memory limits, pool/concurrency, upload bytes và phiên bản công cụ đo.
- [ ] Workloads tối thiểu: auth login/role lookup, catalog với nhiều item/media, EndSession và MP4 upload. Session fixtures reset/renew đúng để không đo duplicate-end error path.
- [ ] Query count kiểm nhiều kích thước catalog để phát hiện N+1; latency p50/p95, sample count, warm-up, repeated runs và peak process/container memory ghi rõ phương pháp đo.
- [ ] Lưu raw samples/query counts/RSS cùng SHA, machine/tool versions, workload script/version và kết quả tổng hợp.
- [ ] Query count tăng phải giải thích; p95 hoặc peak memory tăng >10% theo plan trước cần lặp có kiểm soát, phân tích nhiễu/regression và quyết định CTO. Không đổi threshold sau khi thấy số đo.

**Exit:** có bảng baseline/candidate và raw data tái tạo được. Không có môi trường/baseline tương đương thì mục này pending, không tick dựa vào runtime tổng pytest.

## 8. V6 — Requalification đúng candidate và đóng tài liệu

**Owner:** QA + Ops; CTO quyết định, BA đối chiếu contract.

- [ ] Hoàn tất code/tests/build scripts rồi commit một candidate SHA duy nhất. Chạy bằng isolated clean worktree; không mang thay đổi local người dùng vào candidate.
- [ ] Sửa verifier để evidence/output lưu ngoài source checkout; chụp tracked và untracked paths trước build, sau gates. Nếu công cụ tạo artifact nội bộ thì chuyển output ra ngoài hoặc liệt kê provenance và chứng minh source không đổi; không ghi chung “clean” khi manifest dirty.
- [ ] Build image từ candidate; ghi image ID/digest thực sự được run, build context, timestamp và source SHA. Không xác nhận bằng tag mutable đơn thuần.
- [ ] Chạy repository guard, pure unit/architecture mutation, full pytest, semantic OpenAPI + mutation suite, PostgreSQL concurrency/media, Web E2E Chromium/WebKit và container gates.
- [ ] Lưu raw logs, commands, cwd, exit codes, timestamps, versions, candidate SHA, source status và image identity ngoài checkout. Gate thất bại phải hiện rõ trong manifest tổng.
- [ ] Sau candidate nếu có sửa code/test/harness như commit `b565b7b` vừa qua, tạo candidate mới và chạy lại gates chịu ảnh hưởng; không gắn kết quả candidate cũ cho HEAD mới.
- [ ] Commit evidence/docs sau test được phép có SHA khác: ghi `tested_code_sha` và `evidence_commit_sha` riêng; chứng minh diff chỉ docs/evidence, không dùng cặp SHA mơ hồ làm một candidate.
- [ ] Review checklist gốc và v2 bằng bảng code/test/raw artifact. Chỉ tick khi bằng chứng có thật; ghi người/agent review, ghế, scope, timestamp và kết luận thực tế.
- [ ] Cập nhật ADR/plan/walkthrough đồng nhất; engineering ACCEPTED chỉ khi V0–V6 đạt. R-09 vẫn HOLD và không bị dùng thay cho các gap engineering còn mở.

**Exit:** reviewer tái dựng được kết quả từ candidate và artifacts, biết chính xác gates nào chạy trên SHA nào.

## 9. Trình tự commit và Definition of Done

1. `docs(api): reopen remaining architecture verification gaps`
2. `refactor(api): scope repositories and upload transactions through uow`
3. `refactor(api): remove application signing fallbacks`
4. `test(api): enforce transitive imports and aliased composition rules`
5. `test(api): map baseline cases and measure rewrite performance`
6. `test(api): verify clean candidate with external evidence outputs`
7. `docs(api): record evidence-backed architecture acceptance`

V1 → V2 → V3 → V4/V5 → V6; V0 thực hiện đầu tiên. Mỗi code commit chạy targeted tests; candidate cuối chạy full gates. Revert theo commit nếu cần, không downgrade DDL.

- [ ] Transaction ownership và upload short scopes được kiểm bằng DB thật.
- [ ] Signing fallback không còn trong application.
- [ ] Guard bắt transitive/alias bypass với mutation fixtures.
- [ ] Baseline test inventory/mapping đầy đủ và count generated chính xác.
- [ ] Performance raw measurements có đối chứng và quyết định regression rõ ràng.
- [ ] Gates đúng clean candidate/image, logs đầy đủ; tài liệu thống nhất với code.
- [ ] Development DB/media/named volume và file local người dùng được bảo toàn.

Không đóng mục còn thiếu bằng sửa wording thành PASS. Nếu yêu cầu cần đổi contract/schema, BA/CTO tách quyết định đó trước khi mở rộng implementation.
