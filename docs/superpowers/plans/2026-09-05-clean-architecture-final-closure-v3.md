# Clean Architecture — Final Closure v3

> Status: PLANNED — chưa triển khai hoặc nghiệm thu.  
> Baseline được audit: `b7804a5`, branch `codex/fastapi-backend-hardening`.  
> Kế thừa: ADR-006, `2026-09-05-clean-architecture-remaining-gaps-v2.md`.  
> Tham chiếu: python-architecture — UoW ownership, explicit transaction outcome, ports/adapters và kiểm thử invariant.  
> Platform thực hiện; CTO review kiến trúc; BA đối chiếu contract/invariant; QA kiểm chứng; Ops quản lý container evidence.

## 1. Baseline và phạm vi

Audit vừa xác nhận: 187 pytest PASS trong 24.30s, 2 warnings; repository guard và semantic OpenAPI diff PASS. Web E2E/container chưa chạy lại trong audit. Không dùng kết quả này để suy ra các failure boundary chưa có test đều an toàn.

Giữ các cải tiến đã có: upload ba scope, repositories thuộc UoW trên factory path, signing port và guard transitive/alias. Plan này sửa một lỗi cleanup đã tái hiện và hoàn tất bốn khoảng trống nghiệm thu; không mở rewrite mới, không đổi DDL, API contract hoặc business requirements.

Lỗi tái hiện: storage promote thành công → query recheck catalog trong write scope raise → UoW rollback thành công → final `.bin` vẫn tồn tại. Ngoài ra handler còn nhận `media_repo` độc lập và UoW instance tái sử dụng; mapping test chưa tới từng node ID; benchmark dùng baseline ước lượng; manifest ghi SHA `608f702` với 4 dirty files.

Workspace có `walkthrough.md` modified và `landing_preview.html` untracked. Bảo toàn thay đổi local; đọc và reconcile trước khi sửa file chồng lấn. Dùng isolated worktree để nghiệm thu, không dùng reset/clean hay đụng development DB/media/volume.

## 2. R0 — Mở lại đúng mục nghiệm thu

**Owner:** CTO + BA + QA.

- [ ] Ghi trạng thái engineering verification pending trong tài liệu liên quan, giữ nguyên kết quả gate lịch sử với SHA/phạm vi.
- [ ] Mở lại V1 cleanup/write boundary và API ownership; V4 node-ID mapping; V5 baseline measurement; V6 clean-candidate evidence.
- [ ] Tạo bảng mỗi requirement → code location → test ID → raw artifact → reviewer. Tick chỉ khi bằng chứng tương ứng tồn tại.

**Exit:** không có claim “all complete” trong khi R1–R5 còn mở. R-09 vận hành vẫn tách riêng.

## 3. R1 — Một vùng compensation bao phủ toàn bộ sau promote

**Owner:** Platform; QA fault matrix; CTO transaction review. **Ưu tiên P1.**

Files chính: `application/handlers/media.py`, `application/ports/unit_of_work.py`, `adapters/persistence/unit_of_work.py`, media tests và fake UoW.

- [ ] Viết test đỏ cho query recheck raise sau promote, assert rollback được xác nhận và final object được xóa. Giữ test như regression lâu dài.
- [ ] Theo dõi lifecycle từ promote tới kết quả transaction; bảo vệ cả tạo write UoW, `__aenter__`, recheck, add/flush, hook, commit và context exit. Không đặt các bước trước add ngoài vùng quản lý lỗi nữa.
- [ ] Dùng outcome tường minh: chưa bắt đầu write/commit, rollback-confirmed, committed, unknown. Với lỗi tạo/enter UoW, adapter xác định tài nguyên nào đã mở và liệu có mutation; chỉ xóa khi chứng minh không có durable write hoặc rollback đã xác nhận.
- [ ] Khi recheck lỗi, rollback/close write scope trước khi quyết định cleanup. Khi catalog không còn tồn tại, giữ đúng HTTP semantics đang có; khi query hỏng, bảo toàn exception gốc.
- [ ] Lỗi/cancel sau khi commit thành công không được chuyển sang rollback-confirmed; giữ final object. Commit in-flight phải settle hoặc được adapter kết thúc an toàn trước rollback/close, không thao tác đồng thời trên một session.
- [ ] `_rolled_back` chỉ phản ánh rollback thành công, không được đặt trước await rồi coi rollback thất bại là đã hoàn tất. Outcome không được suy ra từ boolean mang nghĩa “đã thử rollback”.
- [ ] Cleanup chạy có owner và bounded lifecycle khi cancellation lặp lại; không tạo shield task rồi bỏ mặc. Nếu không xác định kết quả, giữ object và recovery warning thay vì xóa.
- [ ] Storage delete/rollback/close failure ghi structured warning an toàn, giữ exception gốc; không nuốt lỗi cleanup mà không để lại evidence.

Ma trận cần kiểm:

| Boundary sau promote | Bằng chứng cần có |
|---|---|
| Factory / UoW enter lỗi | Không leak session; chứng minh chưa write hoặc outcome unknown; cleanup đúng classification |
| Recheck raise/cancel | Rollback xác nhận → final bị xóa; không còn metadata |
| Catalog bị xóa | Write rollback, compensation và response contract đúng |
| Add/flush/hook lỗi | Giữ regression hiện tại, không partial DB state |
| Rollback fail | Final còn; warning; trạng thái không báo rollback-confirmed |
| Commit success / response cancel | Row và object còn nguyên |
| Commit timeout/error/cancel | Không overlap commit/rollback/close; unknown giữ object |
| Delete/close lỗi | Exception gốc còn, warning có asset/key/reason |

**Exit:** fake fault matrix PASS và PostgreSQL/filesystem integration PASS; đọc DB bằng session mới. Test query recheck failure phải chuyển từ đỏ sang xanh. Không chỉ thêm happy-path test.

## 4. R2 — Xóa đường gọi phá ownership

**Owner:** Platform + CTO; QA kiểm các caller.

- [ ] `handle_upload_media` nhận duy nhất UoW factory bắt buộc, storage và signer bắt buộc; xóa optional `media_repo`, UoW instance fallback và nhiều cách truyền factory tương đương.
- [ ] Mỗi lần vào scope tạo UoW mới; repository lấy sau `__aenter__` từ scope đang hoạt động, không cache repository trước enter hoặc dùng lại repository của preflight.
- [ ] Migrate production routes, CLI và tests về một API. Fake factory tạo scope mới dùng chung committed store; không giữ compatibility bypass để test cũ xanh.
- [ ] Rà write handlers còn nhận repository độc lập: chuyển về UoW-owned repositories hoặc ghi rõ đó là read-only query capability ngoài transaction. Không mở rộng generic repository.
- [ ] Test factory invocation/scopes/repository identity; test rollback của scope mới không sửa state đã commit ở scope trước.
- [ ] Bổ sung kiểm HTTP upload thực qua auth dependency + storage barrier: auth/preflight connection trả pool trước stage. Phân biệt “không có transaction active” với “không checkout connection”; kiểm cả pool checkout instrumentation và activity của request được định danh.
- [ ] Giữ EndSession concurrency và registration atomicity PASS nếu đổi shared UoW API.

**Exit:** không còn caller ghép UoW với repository ngoài scope; ba scope được chứng minh trên HTTP path, không chỉ gọi handler trực tiếp.

## 5. R3 — Mapping baseline bằng dữ liệu thu thập thực

**Owner:** QA + BA.

- [ ] Viết công cụ collect node IDs bằng pytest collection ở `2f5e200`, `4ae7673`, `b565b7b`, `b7804a5` và candidate; giữ parameterized IDs. Chạy isolated checkouts đúng lockfile, không chạy DB mutations khi collect.
- [ ] Lưu inventory JSON/CSV, command, revision, exit code; nếu collect fail, giữ mục pending và nêu nguyên nhân.
- [ ] Sinh mapping từng baseline node ID → candidate node ID(s), trạng thái unchanged/moved/replaced, invariant/FR-Test ID, lý do và reviewer.
- [ ] Review assertion diff cho các test bị sửa/thay, không chỉ so tên hàm. Case không có replacement phải hiện là missing và làm coverage gate fail.
- [ ] Tự tính count, unmapped/deleted/skipped; thêm kiểm inventory/mapping nhất quán. Không nhập tổng 164/187 thủ công làm nguồn chân lý.
- [ ] Cập nhật `test_mapping_and_reconciliation.md` bằng link artifacts và summary generated.

**Exit:** mỗi baseline case truy được tới test hiện tại và invariant; báo cáo zero missing có thể tái tính từ inventory.

## 6. R4 — Benchmark baseline thực, không dùng expected values

**Owner:** QA + Platform; CTO quyết định regression.

- [ ] Giữ báo cáo cũ như historical observation, gỡ kết luận phần trăm regression dựa trên `Baseline Expected` ước lượng.
- [ ] Commit benchmark runner/workload và định nghĩa phương pháp trước khi đo. Baseline chính `2f5e200`; candidate SHA cụ thể; có thể thêm `b7804a5` để tách tác động vòng fix.
- [ ] Cùng fixture, DB engine/version, CPU/memory, pool, concurrency, payload, warm-up và số lần lặp giữa revisions. Chạy luân phiên/lặp để đánh giá nhiễu.
- [ ] Workload HTTP thực: auth login với role lookup, catalog ở nhiều kích thước, session start/end/progress với session mới mỗi iteration, upload cùng payload. Crypto microbenchmark chỉ là số phụ, không thay login workflow.
- [ ] Lưu raw per-iteration latency/query count, SQL fingerprints đã sanitize, RSS/process identity, workload size, timestamps, revision và tool versions. JSON percentile tổng hợp không được gọi là raw samples.
- [ ] Đo p50/p95 và peak memory cùng phương pháp; query count theo nhiều catalog sizes để kiểm N+1. Giải thích từng query bằng trace thực thay vì mô tả suy đoán.
- [ ] Áp ngưỡng plan v2: query increase phải giải thích; p95/peak memory tăng >10% cần phân tích/review. Không thay bằng ngưỡng RAM tuyệt đối 350 MB để kết luận không regression.
- [ ] Nếu baseline không chạy được hoặc dữ liệu không tương đương, ghi NOT VERIFIED; không nội suy baseline rồi tính overhead.

**Exit:** report có measured baseline/candidate đúng SHA, raw samples, script tái chạy và kết luận có căn cứ.

## 7. R5 — Candidate sạch và evidence truy vết được

**Owner:** QA + Ops; review CTO/BA.

- [ ] Hoàn tất code/test/harness/verifier, commit candidate rồi tạo detached isolated worktree từ chính SHA đó. Bảo toàn dirty files trong workspace người dùng.
- [ ] Verifier nhận output directory ngoài checkout; manifest/raw logs lưu ở đó. Ghi tracked và untracked source paths trước build và sau gates; không tóm tắt dirty count mà thiếu path/provenance.
- [ ] Nghiệm thu source tree sạch; nếu tool tạo output nội bộ, chuyển output ra ngoài hoặc phân loại chính xác artifact phát sinh và kiểm source không đổi. Không tuyên bố clean nếu chưa giải thích dirty files.
- [ ] Build/run đúng image ID/digest từ candidate build context. Manifest có `tested_code_sha`, source status, image identity, command/cwd/version/start/end/exit code cho từng gate.
- [ ] Chạy repository guard, architecture mutation/pure unit, full pytest, OpenAPI diff/mutations, PostgreSQL/media regression, Web E2E Chromium/WebKit, container 7 gates và benchmark theo R4.
- [ ] Sau sửa code/test/differential harness/build config, tạo candidate mới và chạy lại gate chịu ảnh hưởng. Đặc biệt theo dõi `differential/db.py` thay đổi sau candidate lịch sử `608f702`.
- [ ] Commit evidence/docs sau gates riêng; ghi quan hệ tested-code SHA và evidence SHA. Kiểm diff chỉ docs/artifacts trước khi reuse kết quả candidate.
- [ ] Review checklist v1/v2/v3 còn pending bằng code/test/raw evidence; chữ ký phải có reviewer thực, ghế, thời điểm và phạm vi, không chỉ danh sách owner.

**Exit:** mọi gate gắn đúng source/image; đủ evidence R1–R4. Engineering ACCEPTED chỉ sau review; R-09 staging/HTTPS/soak/canary/rollback vẫn gate riêng.

## 8. Sequence và điều kiện hoàn tất

Thực hiện R0 → R1 → R2 → R3/R4 → R5. Mỗi commit code chạy targeted tests; full gates ở candidate cuối. Không lặp broad tests khi không có thay đổi hoặc nghi vấn mới.

Commit đề xuất:

1. `docs(api): reopen verified remaining closure gaps`
2. `fix(api): cover all post-promote transaction failures`
3. `refactor(api): require scoped uow factories for upload`
4. `test(api): generate baseline test inventories and mappings`
5. `test(api): add reproducible baseline performance comparison`
6. `test(api): qualify clean candidate with traceable artifacts`
7. `docs(api): record reviewed final closure evidence`

- [ ] Recheck failure không còn leak object sau rollback xác nhận.
- [ ] UoW enter/commit/cancel/cleanup classification được kiểm đủ, không race.
- [ ] Không còn repository/UoW instance fallback trong upload API.
- [ ] HTTP streaming barrier chứng minh đúng connection/transaction behavior.
- [ ] Mapping từng baseline case đầy đủ, assertions đã review.
- [ ] Performance measured trên hai revisions, có raw samples.
- [ ] Clean source/image/gates được truy vết; tài liệu không overclaim.
- [ ] File người dùng và development resources không bị thay đổi ngoài scope.

Nếu một mục thiếu điều kiện kiểm chứng, để pending và ghi blocker cụ thể. Không biến việc tick checklist hoặc tăng test count thành bằng chứng nghiệm thu.
