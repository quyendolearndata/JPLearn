# Clean Architecture Rewrite — Audit Gap Closure

> Status: PLANNED — chưa triển khai, chưa nghiệm thu.  
> Baseline: `4ae7673`, branch `codex/fastapi-backend-hardening`.  
> Kế thừa: ADR-006 và `2026-09-05-fastapi-clean-architecture-rewrite.md`.  
> Tham chiếu: python-architecture, đặc biệt Unit of Work, Repository, DI/bootstrap và test gears.  
> CTO: kiến trúc và quyết định nghiệm thu; BA: invariant/contract/traceability; Platform: implementation; QA: bằng chứng; Ops: container và R-09.

## 1. Phạm vi và baseline thực tế

Đóng các khoảng trống của rewrite trước khi tuyên bố hoàn thành engineering milestone. Giữ public OpenAPI, DDL Alembic, dữ liệu phát triển và các invariant hiện tại. Không thêm broker, full CQRS hoặc framework DI.

Audit vừa chạy trên workspace có HEAD `4ae7673`:

- Repository guard PASS.
- Pytest: 173 passed, 2 warnings, 23.80s.
- Semantic OpenAPI diff PASS.
- Fault injection vào `media_repo.add()` sau promote: `.bin` còn lại, Fake UoW có `committed=False`, `rolled_back=False`.
- Web E2E/container chưa được chạy lại trong audit. Manifest hiện ghi SHA `3048dd6` và `git_dirty_files=2`; không phải bằng chứng clean checkout ở HEAD.
- `walkthrough.md` đang có thay đổi local; `landing_preview.html` untracked. Không ghi đè các thay đổi này khi bắt đầu implementation.

Test suite xanh xác nhận các assertion hiện có; không thay thế kiểm chứng những yêu cầu kiến trúc còn thiếu.

## 2. Thứ tự triển khai

| Block | Ưu tiên | Chủ trì | Phụ thuộc | Kết quả cần đạt |
|---|---|---|---|---|
| G0 | P2 | CTO + BA + QA | Không | Baseline, checklist trung thực, route matrix đúng |
| G1 | P1 | Platform + QA | G0 | Upload/UoW an toàn trên mọi failure boundary |
| G2 | P2 | Platform + CTO | G1 | Wiring tập trung, bỏ ORM/legacy coupling |
| G3 | P2 | Platform + QA | G2 | Clock/ID/security/error boundaries rõ ràng |
| G4 | P2 | QA + Platform | G1–G3 | Architecture guard và test fakes chứng minh được invariant |
| G5 | P2 | CTO + BA + QA | G2–G4 | Tài liệu và coverage mapping khớp code |
| G6 | P2 | QA + Ops + CTO | G5 | Requalification từ clean checkout, evidence đúng SHA |

## 3. G0 — Khóa scope và sửa trạng thái nghiệm thu

- [ ] Ghi SHA, dirty paths, runtime/test isolation và baseline commands vào evidence directory riêng.
- [ ] Đối chiếu plan rewrite từng checkbox; mở lại các mục chưa đạt ở Phase 5–8 và Definition of Done. Kiểm Phase 2/4 đối với clock/ID, events, fake coverage; không mặc định mọi mục đã đạt vì số test tăng.
- [ ] Cập nhật trạng thái đầu plan đang ghi PLAN trong khi toàn bộ checklist được tick; phản ánh chính xác phần đã triển khai và phần đang khắc phục.
- [ ] BA lập route matrix theo toàn bộ `operationId` trong OpenAPI và route thực: method/path, role, response/error, invariant, test ID. Sửa các path sai trong ADR-006, gồm media upload/HLS và staff catalog.
- [ ] Ghi rõ engineering acceptance đang chờ gap closure; R-09 là gate vận hành riêng.

**Exit:** mỗi phát hiện có mã G, owner, file/test liên quan; không thay contract để làm báo cáo khớp.

## 4. G1 — Upload transaction và compensation

Files chính: `application/handlers/media.py`, `application/ports/unit_of_work.py`, `adapters/persistence/unit_of_work.py`, `adapters/persistence/media_repository.py`.

- [ ] Viết test đỏ tái hiện `repo.add()` raise sau promote, trước khi sửa handler.
- [ ] Thiết kế một transaction scope sở hữu session và repositories tương ứng. Không cho handler ghép UoW với repository của session khác; không dùng singleton UoW.
- [ ] Bao phủ add/flush/pre-commit và context exit bằng rollback-by-default. Đưa tất cả failure sau promote vào cơ chế compensation có trạng thái tường minh.
- [ ] Phân biệt `COMMITTED`, `ROLLBACK_CONFIRMED`, `OUTCOME_UNKNOWN`. Chỉ xóa final object sau khi xác nhận rollback; nếu rollback lỗi/không rõ kết quả, giữ object và ghi recovery warning.
- [ ] Commit task phải kết thúc trước rollback/close trên cùng session. Xử lý cancellation có giới hạn và kiểm thử cleanup; không chỉ bọc handler bằng `async with` rồi để context exit chạy đua commit.
- [ ] Fail trước COMMIT không bị phân loại nhầm thành unknown chỉ vì cùng loại exception; lỗi sau COMMIT bắt đầu không suy diễn rollback chỉ từ tên exception.
- [ ] Cleanup thất bại ghi structured warning có asset/key/reason; không log secret, credential hoặc dữ liệu upload.
- [ ] Tránh giữ transaction/row lock trong suốt upload dài; dùng preflight read scope ngắn và transaction metadata riêng. Ràng buộc FK vẫn kiểm tại write transaction.

Ma trận kiểm thử bắt buộc:

| Failure boundary | Assertion |
|---|---|
| stage/open/write/promote | Handle/task được thu hồi; staging cleanup hoặc warning có thể điều tra |
| add/flush/pre-commit raise hoặc cancel | Không có DB mutation bền vững; rollback xác nhận thì xóa final object |
| rollback fail | Giữ final object; warning; không tuyên bố rollback thành công |
| commit thành công nhưng response bị cancel | DB row và object còn nguyên |
| commit in-flight lỗi/cancel/timeout | Không rollback/close đồng thời với commit; unknown giữ object |
| storage delete fail | Exception gốc được bảo toàn; cleanup warning quan sát được |
| uncommitted/early exit | Rollback mặc định và đóng session do UoW sở hữu |

**Exit:** fake-backed fault matrix và PostgreSQL/filesystem integration PASS; đối chiếu DB bằng session mới. Giữ các regression tests cancellation/unknown commit cũ.

## 5. G2 — Hoàn tất ports/adapters và composition root

- [ ] Chuyển lựa chọn concrete repositories/UoW/security/storage vào bootstrap và factory của nó. HTTP/CLI chỉ lấy capability đã wiring; persistence UoW có thể dựng repositories nội bộ cùng session.
- [ ] Media router gọi handler/query qua dependency đã inject. Bỏ `media_service.get()` trả ORM; HLS asset lookup dùng application query/read DTO.
- [ ] Chuyển reconciliation workflow sang application handler nhận read/query port, storage và clock; SQL lookup/recheck nằm trong persistence adapter. Giữ dry-run mặc định, retention tối thiểu 24h, age/reference recheck và bảo vệ `.part`/HLS/probe.
- [ ] Chuyển imports production/tests/migration scripts từ root ORM sang đúng adapter; xóa `models.py` alias và các legacy service/media-access alias khi không còn consumer.
- [ ] Đặt HTTP, security dependencies, schemas, probes, CLI và operational persistence đúng boundary; giữ các public CLI/module entrypoint cần tương thích dưới dạng wrapper mỏng, có danh sách rõ ràng. Wrapper không được làm lối tắt cho inner layer import infrastructure.
- [ ] Đọc lại từng route/CLI để xác nhận không còn query ORM hoặc orchestration nghiệp vụ nằm ở wrapper cũ.

**Exit:** trace được HTTP/CLI → handler → domain/port → adapter; không còn root ORM alias hoặc active legacy service. Tên thư mục riêng lẻ không phải bằng chứng đủ.

## 6. G3 — Explicit dependencies và application semantics

- [ ] Inject clock/ID generator vào use cases cần thời gian/identifier; callable đơn giản là đủ nếu chỉ có một operation. Tests dùng fixed clock/IDs, không monkeypatch import toàn cục.
- [ ] Chuyển ký/verify media URL qua application-owned security capability; cấu hình secret nằm ở adapter bootstrap, không nằm trong command nghiệp vụ hoặc DTO dễ bị log/repr.
- [ ] Loại bỏ kiểm tra tên class `IntegrityError` ở application. Adapter chuyển lỗi sang application-owned error/outcome có semantics xác định; giữ exception chain phục vụ chẩn đoán an toàn.
- [ ] Chuyển mapping HTTP status/headers/Range sang transport adapter phù hợp. Application trả kết quả có nghĩa về stream/range, không tự xây response HTTP.
- [ ] Đối chiếu events khai báo và cách persist: dùng domain facts thực sự trong learning workflow hoặc sửa ADR theo quyết định CTO/BA nếu là abstraction không sử dụng. Giữ atomic session/progress/two-event transaction.

**Exit:** application không phụ thuộc cách đặt tên exception của ORM, thuật toán ký URL concrete hoặc global clock/ID; public behavior không đổi.

## 7. G4 — Guard và test pyramid có khả năng bắt regression

- [ ] Guard resolve absolute/relative imports, bao gồm `from .. import module`, alias và root re-export; kiểm reachable imports từ domain/application để phát hiện phụ thuộc gián tiếp ra infrastructure.
- [ ] Hạn chế internal imports theo layer sở hữu thay vì chỉ denylist vài thư viện. Kiểm env access gián tiếp qua settings/helper; quy định dynamic import trong inner layers là không được phép nếu không phân tích được.
- [ ] Kiểm composition rules: production entrypoints không tự chọn/dựng concrete adapters ngoài wiring entrypoint được xác định; adapter không import transport thông qua helper root.
- [ ] Mutation tests trên source fixture tạm: forbidden absolute/relative/transitive import, env helper, ORM re-export và adapter construction ngoài bootstrap đều phải làm guard fail; có positive fixtures hợp lệ.
- [ ] Fake UoW/repositories dùng transaction-local state, commit publish state, rollback discard state; tests không chỉ assert boolean. Kiểm mutation nested objects/events không rò vào committed state.
- [ ] Thêm tests lỗi giữa từng bước register, catalog transition, end session và media; fake không giả lập PostgreSQL lock, concurrency vẫn test DB thật.
- [ ] Phân loại suite domain/application/integration/contract; unit suite có conftest độc lập và chạy được khi Docker không khả dụng. Không dùng conftest unit import FastAPI app rồi gọi đó là độc lập framework.
- [ ] Test import side effects trong subprocess mới với I/O constructors bị chặn; assert import domain/application không dựng engine/storage/client/task, thay cho chỉ `hasattr(bootstrap, ...)`.

**Exit:** có kết quả mutation fail đúng lý do, pure suite PASS không DB/framework bootstrap, adapter integration kiểm riêng lifecycle/mapping/locking.

## 8. G5 — Coverage và tài liệu khớp implementation

- [ ] Lập mapping test IDs từ baseline `2f5e200` (164 cases) và rewrite `4ae7673` (173 cases) sang suite mới; ghi rõ giữ/chuyển/thay thế và invariant tương ứng. Không dùng tổng số tests thay mapping.
- [ ] Bổ sung domain/application negative cases cho các use case còn thiếu; không tuyên bố “all use cases” dựa trên một happy-path test mỗi module.
- [ ] Cập nhật C4 Level 3, diagrams, ADR-006, README, route matrix và walkthrough theo code cuối cùng; giữ lịch sử bằng chứng cũ nhưng ghi rõ phạm vi/SHA.
- [ ] Tạo bảng checklist → code → test → evidence cho từng mục plan gốc và G0–G6. Mục chưa có bằng chứng giữ unchecked.
- [ ] Ghi review theo ghế CTO/BA/QA/Ops với người/agent thực hiện, phạm vi, kết luận và artifact; không ghi “accepted by” chỉ từ danh sách owner.

**Exit:** reviewer có thể kiểm lại mọi claim từ đường dẫn cụ thể; không còn route matrix hư cấu hoặc claim clean checkout sai.

## 9. G6 — Requalification và bằng chứng tái tạo được

- [ ] So sánh baseline và candidate cùng môi trường, fixture, warm-up và số lần lặp: catalog/auth query count; latency p50/p95 và peak memory của các use case đại diện, gồm end session và upload. Ghi machine/tool versions và raw measurements.
- [ ] Ngưỡng kiểm tra ban đầu: không phát sinh N+1; query count tăng phải có giải thích; latency p95 hoặc peak memory tăng >10% cần kiểm tra lại nhiễu đo và phân tích trước nghiệm thu. Chốt workload trước khi đo, không lựa ngưỡng sau khi xem kết quả.
- [ ] Commit candidate code; chạy gates trong checkout/worktree sạch ở SHA đó, dùng PostgreSQL test riêng `/jplearn_test`. Không tác động development DB/named volume/media.
- [ ] Chạy repository guard, pure unit suite, full pytest, architecture mutation suite, semantic OpenAPI diff + mutation tests, Web E2E Chromium/WebKit và container verification.
- [ ] Lưu command, exit code, raw log, timestamp, candidate SHA, dirty tracked/untracked paths, image ID/digest, runtime versions và manifest. Evidence ghi ngoài source checkout trong khi đo để tránh tự làm dirty checkout.
- [ ] Container phải build từ candidate checkout, xác nhận image digest/ID của chính image được test. Không reuse tag mà thiếu đối chiếu image identity.
- [ ] Commit bằng chứng sau đó được phép khác candidate SHA nếu chỉ đổi docs/evidence; ghi rõ quan hệ hai SHA. Bất kỳ sửa code/config/test/build nào sau candidate đều cần chạy lại gates liên quan.
- [ ] Đối chiếu tất cả mục plan gốc rồi CTO/QA kết luận engineering acceptance. R-09 vẫn HOLD cho đến staging HTTPS/soak/canary/rollback và bằng chứng vận hành riêng.

Commands gốc cần giữ tương đương khi đổi test layout:

```bash
pnpm test:guard
cd apps/api-python
uv run pytest -q
PYTHONPATH=src uv run python -m jplearn_api.openapi_diff
./differential/web-e2e-python.sh --project=chromium --project=webkit
./scripts/verify-container.sh
```

**Exit:** mọi gate có raw evidence đúng candidate; lỗi không bị che bằng skip/xfail/allowlist tạm. Nếu baseline không tái tạo được phép đo nào, ghi rõ chưa đủ evidence và giữ mục đó mở.

## 10. Commit sequence và điều kiện hoàn tất

1. `docs(api): reopen clean architecture audit gaps`
2. `fix(api): close upload pre-commit rollback and cleanup gaps`
3. `refactor(api): complete application wiring and persistence boundaries`
4. `refactor(api): inject runtime capabilities and translate adapter errors`
5. `test(api): enforce dependency boundaries and transactional fakes`
6. `docs(api): reconcile architecture and behavior coverage`
7. `test(api): requalify audit closure on clean candidate`
8. `docs(api): record verified engineering acceptance`

Mỗi commit code chạy targeted tests; G1/G2 chạy PostgreSQL/media regression trước chuyển wiring. Chạy toàn bộ gates tại candidate cuối, chạy lại khi có thay đổi hoặc phát hiện mới liên quan.

- [ ] Không tái hiện được upload leak đã audit; rollback và commit-unknown đều có test.
- [ ] UoW/repositories chung transaction scope, cleanup có bằng chứng và không race COMMIT.
- [ ] Không còn coupling trái ADR hoặc alias che guard.
- [ ] Guard mutation và fake rollback tests thực sự bắt được lỗi.
- [ ] Contract/schema/baseline coverage được giữ và có mapping.
- [ ] Performance/query/memory evidence có đối chứng và giải thích regression.
- [ ] Checklist/ADR/walkthrough thống nhất; candidate SHA/image được truy vết.
- [ ] Engineering acceptance có review thực tế; operational acceptance R-09 vẫn tách riêng.

Nếu phát hiện cần thay FR/NFR, HTTP contract hoặc DDL, tách quyết định BA/CTO trước khi đưa thay đổi vào scope. Nếu cancellation/unknown outcome chưa chứng minh an toàn, dừng chuyển media route và giữ mục G1 mở.
