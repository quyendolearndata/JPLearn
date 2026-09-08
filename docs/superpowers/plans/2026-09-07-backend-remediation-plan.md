# Kế hoạch khắc phục backend sau kiểm tra A–D

Ngày: 2026-09-07. Cập nhật: 2026-09-08. Trạng thái: **IN PROGRESS — R1–R6 đã đạt kiểm chứng local; R7 còn provider/Teacher và R8 còn tải burst/pilot/thiết bị thật.**

Cập nhật triển khai: xem [báo cáo kết quả](../../qa/2026-09-07-backend-remediation-implementation.md). R0 đã có engineering amendment trong ADR-007; không thay chữ ký Pedagogy/Ops. Policy retention mới trong plan cũ chưa áp dụng; giữ SRS raw 90 ngày và aggregate vĩnh viễn cho đến quyết định riêng.

Ghế chủ trì: CTO. BA phụ trách hợp đồng nghiệp vụ và truy vết; Platform thực hiện backend/migration; Web/Mobile sửa tích hợp playback; QA kiểm chứng; Teacher/Pedagogy đánh giá tiếng Nhật và phạm vi transcript; Ops phụ trách rollout/provider.

Đầu vào: [kế hoạch tính năng](2026-09-07-ejoy-inspired-backend-api.md), [báo cáo kiểm tra](../../qa/2026-09-07-backend-plan-completion-review.md), SRS, ADR-004/006/007, OpenAPI và working tree hiện tại. Số mục P1/P2 bên dưới tham chiếu báo cáo kiểm tra. Baseline 359 tests xanh là bằng chứng trước sửa, không phải nghiệm thu kế hoạch này.

## 1. Mục tiêu và giới hạn

Khắc phục toàn bộ 13 nhóm P1, validation cảnh, thiếu provider thực, chất lượng language/search và thiếu bằng chứng tải/pilot. Có thể nghiệm thu A–C trước; chỉ nghiệm thu D khi workflow AI thật và ledger đạt yêu cầu. Đợt E, AI speaking, dịch L1, flashcard và grammar drill vẫn ngoài phạm vi.

Giữ API legacy `/sessions` và `/progress` theo hợp đồng hiện hành. Mỗi thay đổi contract mới phải có mapping client, response/error và test tương ứng. Không dùng việc sửa tài liệu để bỏ qua lỗi đã tái hiện hoặc hạ tiêu chí nhằm làm test xanh.

## 2. Thứ tự PR và phụ thuộc

| PR | Nội dung | Chủ trì | Phụ thuộc | Kết quả bắt buộc |
|---|---|---|---|---|
| R0 | Chốt contract, FR/UC/test và trạng thái nghiệm thu | BA + CTO | — | Một ma trận contract thống nhất, không còn yêu cầu đối nghịch |
| R1 | Response content và capability gates | Platform | R0 | Content HTTP thành công; flag-off chặn đúng API |
| R2 | Version lifecycle, media snapshot và scene validation | Platform | R0, R1 | Publish nhiều vòng an toàn, snapshot bất biến |
| R3 | Playback lease, idempotency và deletion fencing | Platform | R0, R2 | Một writer; retry ổn định; gói muộn không hồi sinh dữ liệu |
| R4 | Accounting, preference effective time và client tracker | Platform + Web/Mobile | R3 | Thời gian thực đúng; ranh giới ngày đúng; client retry đúng |
| R5 | Transcript CAS và projection được duyệt | Platform | R0, R2 | Stale edit bị từ chối; learner nhận đúng projection |
| R6 | Quota, job transaction và attempt reconciliation | Platform | R0 | Không âm quota, không reservation mồ côi, không mất usage |
| R7 | Provider thật, segmentation và chất lượng search/language | Platform + Teacher | R5, R6 | D có output thực, apply đúng version, đạt bộ đánh giá |
| R8 | Load, migration rehearsal, E2E và rollout | QA + Ops | R1–R7 | Bằng chứng trên candidate cuối, mở cờ theo đợt |

R5 và R6 có thể phát triển độc lập với R3–R4 khi có người phụ trách riêng; mọi migration được tuần tự hóa khi tích hợp. R8 cho A–C có thể chạy trước R7, nhưng không được tuyên bố D hoàn thành.

## 3. Công việc và kiểm chứng từng PR

### R0 — Thống nhất hợp đồng trước sửa

- [x] Đối chiếu SRS → UC → traceability → ADR → OpenAPI → routes; ghi bảng khác biệt và quyết định thay thế rõ ràng. Không mặc định ADR Accepted bao phủ D khi ADR chỉ ghi A–C.
- [ ] Chốt transcript learner: toàn bộ JP hay chỉ approved snippet; BA/Pedagogy quyết định theo SRS. Dùng schema staff/learner riêng, không dựa vào việc client ẩn trường. Khi chưa chốt, giữ capability liên quan tắt.
- [x] Chốt một giao thức playback: endpoint thực tế, content version pin, start idempotency key, cumulative active ms, seq, epoch, heartbeat/lease, gap, final checkpoint, receipt retention và mã lỗi. Đề xuất giữ hướng plan 15 giây/45 giây và cumulative; cập nhật ADR 30 giây/90 giây/delta chỉ sau quyết định được ghi nhận.
- [x] Chốt policy nửa đêm theo timezone đang có hiệu lực, topic có hiệu lực ngay; rule pause/buffering/end; delete giữ aggregate/legacy và saved scenes theo phạm vi đã công bố.
- [x] Chốt capability → endpoints/worker matrix: thao tác mới bị chặn bằng lỗi thống nhất; retry receipt đã commit, kết thúc phiên và deletion vẫn có đường xử lý an toàn khi tắt cờ.
- [x] Chốt SLO: traceability hiện có p95 heartbeat <100ms, plan đề xuất ≤250ms. Giữ yêu cầu SRS đang hiệu lực đến khi có quyết định thay đổi; không chọn ngưỡng dễ đạt hơn. Tương tự chốt retention, quyền return-to-draft, scene bookmark so với term bookmark.
- [x] Chốt goal range và streak: UC-L18 hiện 1–720 phút, active hoặc legacy và có streak; plan 0–120, active-only. Không âm thầm bỏ streak hoặc đổi nghĩa legacy; nếu hoãn phải ghi phạm vi được quyết định.
- [ ] Chốt retention theo từng loại dữ liệu: SRS raw 90 ngày/aggregate vĩnh viễn khác plan receipt 30 ngày/history-resume 180 ngày/aggregate 24 tháng. Chưa áp lịch purge phá hủy dữ liệu theo policy mới khi chưa thống nhất; deletion do người dùng yêu cầu vẫn triển khai độc lập.
- [x] Cập nhật FR/UC và test IDs thật. Các mã `T-REM-*` trong kế hoạch này là ID hồi quy đề xuất, chưa thay chữ ký/truy vết SAD.

Files: `docs/sad/01-survey-srs/srs.md`, `02-analysis/use-cases.md`, `03-design/traceability.md`, `03-design/adr-007-ci-learning-loop-contracts.md`, `03-design/openapi.yaml` và tài liệu sử dụng API.

Gate: BA/CTO có decision log, mỗi mục audit có FR/NFR + UC + test + owner; không yêu cầu người dùng quyết định lại các chi tiết kỹ thuật thông thường.

Mapping BA đã đối chiếu, cần cập nhật endpoint trong traceability khi chốt R0:

| Nhóm | FR/NFR hiện có | UC |
|---|---|---|
| Lease/receipt/accounting | FR-WAT-001, NFR-CONCUR-001 | UC-L17, UC-L24 |
| Content/resume | FR-SCN-001, FR-RSM-001 | UC-T06, UC-T09, UC-L14, UC-L16 |
| History/deletion | FR-HIS-001, NFR-RET-001, NFR-PRIV-001 | UC-L19 |
| Goal/activity | FR-GOL-001, FR-WAT-001, FR-RPT-001 | UC-L18, UC-L17, UC-L23 |
| Recommendation | FR-REC-001 | UC-L20 |
| Collection/bookmark | FR-COL-001, FR-BMK-001 | UC-L21, UC-L15 |

Technical capabilities chưa có FR riêng tương đương bốn cờ sư phạm: BA cấp ID sau kiểm tra trùng và mở rộng UC-A02. Jobs/quota/approved-search ở D cũng cần đối chiếu và bổ sung requirement coverage riêng; không suy ra ADR-007 A–C đã ký cho D. FR-NEG-003 cấm dịch L1, không tự nó cấm transcript JP.

### R1 — Content response và gates (P1.1, P1.9)

- [x] Sửa chuyển đổi dataclass → response, gồm nested scenes và return-to-draft; không thay schema permissive chỉ để bỏ validation.
- [x] Dùng dependency/policy chung thực thi capability phía server theo ma trận R0; kiểm mọi route liên quan, không chỉ collections. Worker không claim job mới khi capability bị tắt, nhưng vẫn settle attempt đang chạy.
- [x] HTTP test qua router với persistence thật cho GET learner/staff, PUT content, response sau commit; kiểm field visibility/ownership.

Tests `T-REM-CONTENT-HTTP`, `T-REM-FLAG-MATRIX`: request hợp lệ trả response đúng; flag-off không ghi dữ liệu mới, không chạy provider; auth/ownership vẫn được kiểm tra. Không sửa runtime flags của môi trường người dùng trong PR này.

### R2 — Version/media lifecycle (P1.2, P1.8, P2 validation)

- [x] Cấp version number dưới catalog lock, unique constraint là lớp bảo vệ cuối. Fork copy đúng snapshot, cấp scene identity theo contract và giữ tham chiếu bookmark/playback cũ.
- [x] GET staff không âm thầm tạo draft; chuyển tạo/fork sang write workflow rõ ràng, cập nhật client nếu cần.
- [x] Pin media source identity bất biến, manifest/source revision và measured duration vào version. SHA-256 nguồn, duration từ ffprobe và checksum toàn bộ HLS bundle được pin khi QA; publish đọc lại mọi file được manifest tham chiếu và từ chối khi nguồn/segment thay đổi.
- [x] Upload/register/submit/publish dùng cùng catalog lock order và revalidate version/media. Không giữ DB transaction trong upload/probe ngoài hệ thống.
- [x] Validate start < end, bounds, thứ tự, không overlap; kiểm lại khi submit/publish và khi duration/source đổi.

Tests `T-REM-VERSION-CYCLE`, `T-REM-MEDIA-FREEZE`: publish v1 → fork → publish v2; hai writer fork đồng thời; stale revision; media change cạnh tranh submit; scene overlap/out-of-bounds; playback/bookmark v1 còn nguyên. Chạy các ca constraint/race trên PostgreSQL thật.

### R3 — Lease, receipts và deletion (P1.3, P1.4, P1.7)

- [x] Start dùng idempotency key scoped theo user + payload fingerprint chứa content version/device; duplicate trả cùng playback, khác payload trả conflict. Chốt compatibility cho client cũ ở R0.
- [x] Dưới user playback lock, mỗi lần đổi writer đều tăng epoch và supersede owner trước kể cả lease đã hết hạn. Checkpoint/end mới kiểm active playback ID, epoch, trạng thái và lease/deletion generation.
- [x] Tra receipt sau ownership và trước live-state checks; fingerprint đủ các trường ảnh hưởng xử lý. Duplicate chỉ trả receipt tối thiểu đã ghi, không cấp lại media hoặc khôi phục history sau deletion.
- [x] Commit receipt + resume + accounting + state trong cùng UoW. End dùng final checkpoint chung và idempotent; stale end không hoàn tất phiên mới.
- [x] DELETE ghi cutoff/generation và đóng phiên bị xóa ngay dưới cùng lock. Worker claim riêng, purge theo phạm vi, retry an toàn; không giữ job lock trong lúc chờ user lock. Áp dụng cùng quy tắc cho retention.

Tests `T-REM-LEASE-RACE`, `T-REM-RECEIPT-RETRY`, `T-REM-DELETE-FENCE`: A hết lease → B start → A ghi; mất ACK rồi takeover/end/unpublish; đổi payload cùng key; start đồng thời DELETE; end/checkpoint trước và sau purge; chạy purge hai lần. Kết quả: không double credit, không resume/history tái xuất hiện, saved scenes/aggregate/legacy giữ đúng scope.

### R4 — Active time và preference (P1.5, P1.6)

- [x] Trần active theo wall elapsed, không nhân tốc độ phát; giới hạn drift cộng dồn toàn phiên để tolerance từng heartbeat không tích thành overcredit.
- [x] Cumulative đơn điệu; pause/end vẫn tiếp nhận phần active đã xảy ra trước chuyển trạng thái. Gap dài áp dụng policy R0, không đoán thời gian bị thiếu. Split interval qua ranh giới ngày/effective_at với tổng credit bảo toàn.
- [x] Preference versions có effective_at UTC, chọn bản đang hiệu lực dưới user lock; update dùng CAS. Thay đổi pending trước nửa đêm có quy tắc replace rõ ràng; topics tách áp dụng ngay. Daily aggregate snapshot goal/timezone không bị overwrite.
- [x] Sửa `apps/web/src/lib/playback-tracker.ts`: clock đơn điệu; xử lý playing/waiting/seeking/seeked/pause/end; một checkpoint in-flight, retry giữ nguyên payload/seq; end thất bại không bị bỏ mất. Đồng bộ giao thức ở Mobile; kiểm chứng simulator/thiết bị thật nằm ở R8.

Tests `T-REM-WALLTIME`, `T-REM-PREFERENCE-BOUNDARY`: 60 giây ở 2x không thành 120; pause/end giữa heartbeat; buffering/seek không tính thừa; duplicate không cộng; cumulative giảm; nửa đêm, DST, đổi timezone, hai update cùng revision. PostgreSQL concurrency test và Web E2E dùng clock điều khiển khi phù hợp.

### R5 — Transcript CAS/projection (P1.10, P2 contract)

- [x] Conditional UPDATE theo ID + expected revision + quyền/status, tăng revision atomic; zero row trả conflict. Apply AI và approve/reject cùng tôn trọng CAS, không chỉ sửa `orm.revision`.
- [x] Learner projection theo quyết định R0, chỉ index đúng approved revision; unpublish/revoke làm kết quả không còn truy cập được dù index chưa dọn. Query lọc eligibility authoritative.
- [x] Manual edit trong khi job chạy khiến apply stale bị từ chối; result/usage vẫn được lưu để staff xử lý.

Tests `T-REM-TRANSCRIPT-CAS`, `T-REM-SEARCH-VISIBILITY`: hai writer revision n chỉ một thành công, revision n+1; race approve/edit/apply; staff-only fields không xuất hiện ngoài projection; unpublish/revoke trước khi reindex.

### R6 — Quota và durable attempts (P1.11–13)

- [x] Server tính estimate từ media duration/model và bảng giá cấu hình có version; client không quyết định khoản reserve. Chặn số âm ở schema/domain/DB; validate overflow và upper bounds.
- [x] Khóa quota bucket, reserve và insert job/idempotency receipt trong một transaction; helper không commit. Unique conflict/exception rollback toàn bộ; duplicate create trả job cũ không reserve lần hai.
- [x] Ghi attempt ID, provider request/idempotency ID, state, reservation và usage ledger riêng. Claim commit ngắn → gọi provider ngoài transaction/DB connection → ghi outcome/settle transaction ngắn.
- [x] Cancel tách quyền apply result khỏi nghĩa vụ ghi actual usage. Token cũ không được ghi transcript nhưng vẫn có thể settle attempt đúng một lần.
- [x] Timeout/lease expiry thành outcome unknown, reconcile trước gọi lại billable work. Nếu provider không hỗ trợ tra cứu/idempotency, đưa hàng đợi đối soát thủ công, không blind retry.
- [x] Actual vượt estimate vẫn ghi đầy đủ usage và overage, không tạo available âm để tiếp tục dùng; chặn job mới theo quota policy. Sweeper xử lý reservation/attempt treo và phát metric cảnh báo.

Tests `T-REM-QUOTA-ATOMIC`, `T-REM-JOB-ATTEMPTS`: âm/0/client estimate thấp; hai job tranh budget; lỗi insert sau reserve; crash sau provider success trước settle; cancel trong call; lease takeover, late success, duplicate callback, actual > estimate. Dùng provider giả lập xác định và PostgreSQL thật; chứng minh mỗi attempt settle tối đa một lần, không thất lạc chi phí đã biết.

### R7 — Hoàn thiện D thực tế (P2 AI/language/search)

- [x] Stub chỉ dùng test hoặc chế độ local explicit; worker thiếu provider config phải báo unavailable, không trả success synthetic.
- [ ] Provider adapter đọc media version đã pin, lưu provenance/model/usage/request ID và xử lý giới hạn audio/timeouts. Chạy smoke staging bằng clip được phép sử dụng, không dùng dữ liệu người học tùy ý.
- [ ] Transcript output ánh xạ scene thật; segmentation tạo đề xuất timeline có bounds/overlap validation; apply chỉ vào draft đúng revision qua workflow riêng, không giả làm save transcript.
- [ ] Dùng tokenizer/reading adapter có nguồn và phiên bản rõ; unknown reading trả unknown. Search đã lọc ứng viên trong PostgreSQL trước khi xếp hạng; tokenizer/reading và corpus Teacher vẫn chưa đạt gate.
- [x] Nếu thiếu credential/budget hoặc đánh giá Teacher, giữ D tắt và ghi pending đúng phần; không ảnh hưởng nghiệm thu A–C đã đạt.

Tests `T-REM-AI-REAL`, `T-REM-JP-RELEVANCE`: hai clip khác nhau cho output bám nội dung, scene IDs hợp lệ, provider usage đối chiếu được; stale apply bị chặn; report relevance và reading theo bộ mẫu đã chốt. Mock tests không thay thế smoke provider thật.

### R8 — Nghiệm thu và rollout

- [x] Migration fresh install và upgrade từ head hiện có với fixture đại diện: published content, bookmark cũ, playback active, running job và quota reservation. Rehearsal `0012 → 0018` giữ nguyên dữ liệu, cô lập attempt cũ thành `outcome_unknown` và chạy lại idempotent trên PostgreSQL test riêng.
- [ ] Load có 1.000 clips, 10.000 scenes, 100.000 playback rows, 100 playback đồng thời heartbeat mỗi 15 giây và burst. Cùng harness cuối: steady p95 11,04–32,36ms đạt; burst p95 205,92–335,95ms, checkpoint 300,56ms chưa đạt SLO <100ms.
- [ ] Ghi raw latency/error/credit samples, config máy/DB/pool, lock waits/deadlocks, query plans, baseline và candidate cùng harness. Candidate local đã có các trường này: credit/receipt đúng 6.000.000ms, deletion ẩn history nhưng giữ activity, 0 lỗi/deadlock; còn baseline cùng harness và network/staging evidence.
- [ ] Chạy regression legacy, API/guard/OpenAPI và Web Chromium/WebKit; local đã đạt API 400, Web E2E 92/92, Mobile 12/12; còn Safari/iPad/Expo trên thiết bị thật.
- [ ] Pilot A → B/C → D theo capability riêng; có checklist rollback ứng dụng và dừng worker, metric 5xx/conflict/quota/unknown attempts. Chỉ mở D sau R7 và reconciliation gate.
- [x] Lưu evidence mới ở `docs/qa/evidence/backend-remediation/`: dirty diff/content hash, exit code, raw artifacts và kết luận theo FR/NFR. Giữ báo cáo benchmark cũ như lịch sử, thêm chú thích phạm vi thay vì sửa số đo cũ.

## 4. Migration và dữ liệu đã tồn tại

- Kiểm tra Alembic head lúc triển khai; thêm revision mới sau head thực tế (audit thấy 0012), không sửa migration đã áp dụng. Cập nhật packaged DDL snapshots, head mapping và migration tests cùng PR.
- Schema dự kiến: version media snapshot; preference versions; receipt/start idempotency và deletion generation nếu thiếu; job attempts/usage uniqueness/check constraints. Chốt tên/cột/index sau xem schema thực tế, không tạo bảng trùng chức năng.
- Dùng expand → backfill có thể chạy lại → validate → enforce. Version cũ thiếu source identity không tự coi đã verified; lập danh sách cần re-QA. Preference cũ chỉ seed baseline từ thời điểm đã biết, không bịa lịch sử effective time.
- Sau migration `0018`, chạy `jplearn-maintenance inventory-media-integrity` trên môi trường đích. Lệnh chỉ đọc; asset/version được liệt kê phải upload/register lại và lặp lại QA, không điền checksum trực tiếp bằng SQL.
- Quota âm/reservation mồ côi phải inventory và đối soát ledger trước thêm constraints; không xóa usage. Accounting cũ chỉ sửa khi đủ raw evidence, không tự suy ra rồi ghi đè aggregate/legacy.
- Test/migration rehearsal chỉ dùng DB test riêng theo `docs/backend/development.md`; không reset development DB hoặc xóa persistent volume. Rollback ưu tiên tắt capability/rollback app tương thích additive schema; không downgrade phá dữ liệu mới.

## 5. Lệnh kiểm tra và định nghĩa hoàn tất

Trong mỗi PR chạy test hồi quy đúng phạm vi; race/transaction bắt buộc PostgreSQL, không chỉ fake. Gate tích hợp:

```bash
pnpm test:api
pnpm test:guard
```

Tại `apps/api-python`:

```bash
PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff
```

Khi tích hợp client, từ root:

```bash
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
pnpm --filter @jplearn/mobile test
```

Hoàn tất A–C khi P1 liên quan đã có regression PASS trên candidate, schema upgrade an toàn, contract thống nhất và load/client gates đạt. Hoàn tất D cần thêm transcript CAS, quota/attempt fault tests, provider thật, relevance và vận hành worker đạt. Không chấp nhận skipped/blocked thành PASS; mọi ngoại lệ có phạm vi/owner và vẫn hiển thị trong bảng nghiệm thu.

## 6. Ước lượng để phân bổ công việc

Ước lượng sơ bộ ngày công kỹ thuật, cần hiệu chỉnh sau R0: R0 1–2; R1 1–2; R2 2–4; R3 3–5; R4 3–5; R5 1–2; R6 3–5; R7 3–6; R8 2–4. Tổng 19–35 ngày công, chưa tính thời gian chờ credential, Teacher hoặc thiết bị pilot. Đây không phải cam kết ngày hoàn thành; ưu tiên R0 → R1 → R2 → R3 trước.
