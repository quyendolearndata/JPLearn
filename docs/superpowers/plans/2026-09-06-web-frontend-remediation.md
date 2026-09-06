# Kế hoạch khắc phục Web Frontend & Staff CMS

Ngày: 2026-09-06. Trạng thái: **REMEDIATION IN PROGRESS** — C4 được mở lại theo [kế hoạch recovery follow-up](2026-09-06-web-frontend-recovery-followup.md), vì F-01–F-03 chưa đủ bằng chứng; C5 keyboard/manual vẫn **PARTIAL**. Các kết quả lịch sử tại `fd838d2` được giữ nguyên, không mở lại R-01, R-02 hoặc R-04.
Kế thừa: [kế hoạch Mốc A/B](2026-09-06-web-frontend-implementation.md).
Baseline code đang review: `8bd0b44` (Task 1 closeout commits on `codex/fastapi-backend-hardening`).

Mục tiêu của đợt này là sửa các lỗi concurrency, migration và khôi phục phiên;
sau đó bổ sung bằng chứng đúng phạm vi để có thể đóng Mốc A và Mốc B.
Không mở thêm subscription, analytics theo ngày, MP3/audio upload, quiz, grammar,
flashcard hoặc bản dịch L1.

## 1. Trạng thái hiện tại

Luồng chính đã có code và bộ test hiện tại đã báo 208 pytest PASS, 5 Playwright
test trên Chromium và 5 test trên WebKit. Các kết quả này là baseline hồi quy,
chưa phải nghiệm thu cuối vì còn bốn lỗi P1 và thiếu các acceptance test của kế hoạch.

| ID | Mức | Khoảng trống phải đóng |
| --- | --- | --- |
| R-01 | P1 | PATCH catalog kiểm `revision` rồi update tách rời; hai request đồng thời có thể cùng thành công và ghi đè nhau |
| R-02 | P1 | Hai POST session đồng thời cùng idempotency key có thể đụng unique constraint và một request trả 500 |
| R-03 | P1 | Web chỉ lưu session sau khi POST và fetch catalog xong; mất response/reload có thể mất idempotency key, storage chưa tách user/tab |
| R-04 | P1 | Snapshot schema 0001 bị ghi đè bằng schema head, làm hỏng đường adopt DB Prisma cũ rồi upgrade 0002 |
| R-05 | P1 | Chưa có E2E cho CMS, recovery/mất response và các race nói trên |
| R-06 | P2 | Claim WCAG/guard trong walkthrough rộng hơn phạm vi công cụ đã đo |
| R-07 | P2 | UI nhận file audio nhưng upload API chỉ nhận `.mp4` + `video/mp4`; login xử lý 422 thay vì validation 400 |

## 2. Vai trò và nguyên tắc thực hiện

- **BA:** giữ FR/UC/traceability nhất quán, không cấp lại chữ ký cũ; xác nhận trạng thái
  Mốc A/B chỉ sau khi acceptance tương ứng có evidence.
- **Platform:** R-01, R-02, R-04; giữ FastAPI, Alembic, PostgreSQL và public semantics hiện tại.
- **Web:** R-03, R-07 và trạng thái UI khi lỗi/retry.
- **QA:** viết test race trước khi sửa, mở rộng Playwright, lưu evidence theo revision.
- **Design:** rà focus, keyboard, responsive và các state error/pending; không mở màn textbook.

Giữ nguyên các invariant: end lần hai trả 400 và không cộng phút; phút tính theo
server start→end; logout thu hồi token mọi thiết bị; teacher không publish; learner
không thấy draft/title nội bộ/L1; client cũ không gửi Idempotency-Key vẫn hoạt động.
Mọi test database chạy trên `/jplearn_test` hoặc Compose project riêng; không reset
DB dev, volume `jplearn_postgres_data` hoặc media dev.

## 3. C0 — Mở lại trạng thái và khóa tiêu chí nghiệm thu

**Owner:** BA + QA. **Phạm vi:** tài liệu, không đổi runtime.

- [x] Đổi trạng thái trong `walkthrough.md` từ “hoàn thành toàn diện” thành
  `REMEDIATION IN PROGRESS`; giữ nguyên số test đã chạy nhưng ghi rõ đó là baseline.
- [x] Sửa mô tả a11y thành: axe không phát hiện vi phạm tự động trên bốn learner route
  và state đã quét. Không dùng kết quả đó để tuyên bố toàn bộ WCAG 2.2 AA.
- [x] Tách bằng chứng `test:guard` (field/schema cấm) khỏi E2E banned chrome (text UI cấm).
- [x] Bổ sung test IDs cho catalog concurrency, session idempotency concurrency,
  migration adoption, session recovery và CMS handoff vào traceability trước khi đóng.
- [x] Ghi rõ manual walkthrough là hướng dẫn thao tác; chỉ đổi thành evidence khi có
  người chạy, revision, môi trường, kết quả và lỗi quan sát được.

**Exit:** tài liệu không còn khẳng định PASS cho ca chưa kiểm; danh sách acceptance
ở C1–C5 đã map tới FR/UC hiện hành.

## 4. C1 — Khôi phục lịch sử migration và kiểm đường nâng cấp

**Owner:** Platform; QA kiểm chứng. **Ưu tiên thực hiện đầu tiên:** R-04.

### Thiết kế

- [x] Khôi phục `docs/qa/adr-004-schema-baseline.json` và packaged resource tương ứng
  đúng snapshot Prisma/`0001_prisma_baseline` bất biến tại `00576eb`.
- [x] Tạo snapshot mới cho schema **head/0002** với tên phân biệt rõ, ở docs và
  package resource. Không gọi snapshot head là “Prisma baseline”.
- [x] `stamp 0001_prisma_baseline` phải verify snapshot 0001; `stamp head` chỉ được
  verify snapshot head. `upgrade head` trên DB đã stamp 0001 phải thực thi 0002.
- [x] Giữ migration `0002_session_idem_rev.py` là migration tiến; không nhét cấu trúc
  0002 vào 0001 và không sửa lịch sử migration đã dùng.
- [x] Cập nhật test/schema helper để chọn expected snapshot theo revision thay vì dùng
  một file cho cả adoption và head.

### Test đỏ bắt buộc trước sửa

- [x] Dựng DB ở revision 0001, tạo dữ liệu đại diện, xóa riêng `alembic_version`,
  `stamp 0001`, rồi `upgrade head`; xác nhận dữ liệu còn nguyên, `revision=1`, bảng
  idempotency tồn tại và Alembic current là 0002.
- [x] DB đúng 0001 được stamp 0001; DB lệch 0001 bị từ chối.
- [x] DB đúng head được stamp head; DB chỉ ở 0001 bị từ chối khi stamp head.
- [x] Upgrade mới từ empty và downgrade/upgrade có chủ đích đều khớp snapshot đúng revision.

**Exit:** cả fresh install và đường Prisma adoption→0001→0002 PASS trên PostgreSQL test;
hai snapshot có checksum/evidence riêng.

## 5. C2 — Catalog optimistic concurrency nguyên tử

**Owner:** Platform; QA chạy race test. **FR/UC:** FR-CAT-005, UC-T02b/UC-T05. **Đóng:** R-01.

### Thiết kế

- [x] Thay `get → so revision → update` bằng compare-and-swap tại database cho PATCH:
  `UPDATE ... WHERE id=:id AND status='draft' AND revision=:expected`, đồng thời
  set metadata và `revision=revision+1`, dùng `RETURNING` để lấy kết quả.
- [x] Repository trả kết quả phân biệt `updated`, `not_found`, `wrong_status`,
  `revision_conflict`; handler map đúng 404/400/409 mà không dựa vào thông báo chuỗi.
- [x] Serialize các transition submit-QA, publish và unpublish bằng row lock hoặc CAS
  chung. Mọi transition tăng revision. PATCH đang chờ sau transition phải fail theo
  status/revision, không được ghi status cũ trở lại.
- [x] Media/publish invariant tiếp tục được kiểm trong cùng transaction; không giảm
  quyền admin publish hoặc bỏ kiểm storage.
- [x] Giữ port/application không phụ thuộc SQLAlchemy; thao tác nguyên tử nằm trong
  repository adapter với contract rõ.

### Test bắt buộc

- [x] Hai PATCH thật sự đồng thời cùng revision, dùng barrier thay cho sleep:
  đúng một 200, một 409; DB có revision tăng đúng một và metadata của winner.
- [x] Race PATCH với submit-QA: kết quả cuối chỉ là draft đã sửa hoặc level_qa từ
  bản đã serialize; không có level_qa với metadata/revision bị ghi ngược.
- [x] Race PATCH với publish/unpublish tương ứng; state machine và revision không lùi.
- [x] Test stale tuần tự, wrong status, not found và teacher/admin permissions vẫn PASS.

**Exit:** không có lost update; mọi catalog mutation cạnh tranh có một thứ tự commit
kiểm chứng được và response phản ánh đúng kết quả database.

## 6. C3 — Session idempotency chịu được request đồng thời

**Owner:** Platform; QA chạy concurrency/fault test. **FR:** FR-SES-001/003, FR-EVT-001/003. **Đóng:** R-02.

### Thiết kế

- [x] Serialize theo `(user_id, idempotency_key)` trong transaction trước khi đọc/tạo.
  Chọn một primitive PostgreSQL có ownership theo transaction (ví dụ keyed advisory
  transaction lock) hoặc atomic reservation có kết quả `claimed/existing/conflict`.
  Encapsulate primitive trong persistence adapter; application dùng contract port.
- [x] Sau khi giành quyền, đọc lại key: cùng request hash trả đúng session đã lưu;
  khác hash trả 409; key chưa có mới tạo session, events và key trong cùng transaction.
- [x] Không bắt `IntegrityError` rồi tiếp tục dùng session SQLAlchemy đã failed.
  Nếu dùng unique conflict làm arbitration, rollback/savepoint và đọc winner bằng
  transaction hợp lệ trước khi trả response.
- [x] Response replay dùng cùng session DTO và không phát thêm `session_started`,
  `level_exposed`, không ghi lại device/progress ngoài semantics đã chốt.
- [x] Giới hạn/validate độ dài Idempotency-Key và document thời gian lưu; giữ header optional.

### Test bắt buộc

- [x] Hai request đồng thời cùng user/key/body: cả hai trả thành công cùng session ID;
  DB chỉ có một session, một idempotency row và đúng một cặp event start/level.
- [x] Cùng key nhưng body khác chạy đồng thời/tuần tự: một winner, request khác 409.
- [x] Cùng key ở hai user tạo hai session độc lập; không rò session giữa user.
- [x] Inject lỗi trước commit: không để key mồ côi hoặc session/event nửa vời; retry sau
  rollback tạo đúng một session.
- [x] Request không có key giữ hành vi hiện hành và contract cũ.

**Exit:** retry đồng thời không trả 500 và không tạo/emit trùng; evidence kiểm trực tiếp
row/event, không chỉ so response ID.

## 7. C4 — Web session recovery theo user và tab (**REOPENED**)

**Owner:** Web; Platform hỗ trợ contract; QA E2E. **Màn:** S-SESSION. **Đóng:** R-03.

> Các checkbox và test dưới đây ghi nhận lịch sử remediation tại `fd838d2`, không
> phải bằng chứng đóng lại các acceptance F-01–F-03. C4 chỉ được đóng sau khi
> follow-up xác nhận không ghi đè session chưa xác nhận, mọi ended path tải
> progress, và media recovery giữ đúng item.

### State và storage

- [x] Dùng `sessionStorage` để tách tab, key có user ID đã xác thực, ví dụ
  `jplearn.session:<userId>`. Không dùng một `jplearn_active_session` chung toàn trình duyệt.
- [x] Record có version và state: `starting | active | ending | outcome_unknown`,
  gồm idempotencyKey, itemId, sessionId nếu đã biết và startedAt sau response.
- [x] Sinh key bằng `crypto.randomUUID()` và persist state `starting` **trước** POST.
  Không lưu object catalog hoặc signed playback/HLS URL; recovery luôn đọc catalog mới.
- [x] Nếu reload ở `starting`, gửi lại POST với đúng key. Nếu có sessionId, gọi
  `GET /sessions/{id}` để xác nhận active/ended trước khi vẽ nút.
- [x] Persist `active` ngay sau khi nhận session response, trước khi fetch catalog.
  Lỗi catalog/player không được làm mất quyền end session.
- [x] Khi POST end mất response do network, chuyển `outcome_unknown`, gọi GET session;
  ended thì đọc progress và clear record, active thì giữ ID/cho retry end, GET cũng lỗi
  thì giữ record và hiển thị trạng thái chưa xác nhận.
- [x] Login user khác trong cùng tab không đọc/clear record user cũ; logout chỉ clear
  auth và record của user hiện tại theo policy đã ghi. Server owner check vẫn là nguồn quyền.
- [x] Validate redirect chỉ nhận path nội bộ có đúng một leading slash; từ chối `//host`.

### Test Playwright bắt buộc

- [x] Chặn response start sau khi server commit → reload → client retry cùng key →
  một session, UI khôi phục đúng ID.
- [x] Start thành công → reload/chuyển route/quay lại → active session và nút end còn đúng.
- [x] Chặn response end sau commit → GET xác nhận ended → progress đúng, không end/event lần hai.
- [x] Mất mạng cả end và recovery GET → không báo ended, record còn để thử lại.
- [x] Hai tab cùng user không ghi đè record; đổi user không nhận phiên của user trước.
- [x] URL media hết hạn/item unpublish: refetch catalog có giới hạn; không dùng lại signed URL đã lưu.

**Exit Mốc A về recovery (lịch sử `fd838d2`, hiện chưa đạt lại):** mọi trạng thái mất
response/reload có đường xử lý xác định; không tạo session mới vì mất key và không báo
thành công khi server chưa được xác nhận. F-01/F-02/F-03 của follow-up phải có
evidence mới trước khi đóng C4.

## 8. C5 — Hoàn thiện CMS/UI và phạm vi kiểm thử

**Owner:** Web + QA; BA xác nhận workflow. **Đóng:** R-05, R-06, R-07.

- [x] Form new/detail chỉ nhận `video/mp4` cho upload; kiểm extension/MIME phía client
  để báo sớm, backend tiếp tục là nguồn validation cuối. Có thể giữ metadata `audio`
  nhưng UI phải ghi rõ chưa hỗ trợ tải file audio, hoặc ẩn lựa chọn theo quyết định BA.
- [x] Login xử lý validation 400 đúng OpenAPI; giữ 401 sai credential, 409 email trùng.
- [x] Bổ sung `staff.spec.ts`: learner bị chặn; teacher tạo draft + upload MP4 + submit QA;
  logout; admin đăng nhập lần khác, tìm item qua list/detail, publish; learner thấy item;
  admin unpublish và learner không còn thấy. Mỗi bước có reload để chứng minh persistence.
- [x] E2E CMS kiểm upload fail giữ draft, publish thiếu media không báo thành công,
  stale revision 409 có reload, teacher không thấy/không gọi được publish.
- [x] Harness tạo teacher/admin test riêng trong DB cô lập; không dùng credential hoặc DB dev.
- [x] Mở rộng axe scan tới landing và các CMS route/state đại diện. Kiểm Playwright
  keyboard cho focus order, submit form, player controls và `role=alert`. Rà focus
  thủ công ngoài spec: PARTIAL, owner Design.
- [x] Giữ wording chính xác: axe tự động không thay thế toàn bộ audit WCAG; Chromium/WebKit
  là browser engines, không được gọi là kiểm thiết bị iPhone/iPad thật.
- [x] Sửa guard evidence: `pnpm test:guard` xác nhận field/schema cấm; `shell.spec.ts`
  xác nhận chrome không hiện text kênh tắt.

**Exit Mốc B:** teacher→admin workflow chạy qua UI/API thật trên hai engine; error,
reload, permission và conflict paths có evidence. A11y claim khớp đúng route/state đã đo.

## 9. C6 — Regression, evidence và đóng kế hoạch

**Owner:** QA; Platform/Web sửa failure; BA review coverage; CTO/Ops giữ release gate.

Chạy trên working tree sạch hoặc isolated worktree từ candidate SHA, lưu logs và manifest:

1. Focused tests C1–C5, gồm race/fault tests có barriers.
2. `pnpm test:guard`.
3. `pnpm test:api` trên Docker PostgreSQL test cô lập.
4. OpenAPI semantic diff/mutation và DDL snapshot/adoption suite.
5. `pnpm --filter @jplearn/web test` và production build.
6. Full Playwright Chromium + WebKit, gồm learner, recovery và CMS mới.
7. Kiểm container/process/network test không còn sót; xác nhận DB dev row counts không đổi
   nếu verification có khả năng chạm cùng Docker host.

- [x] Ghi candidate SHA, dirty state trước/sau, config đã sanitize, command, exit code,
  test count/duration và đường dẫn raw logs vào evidence bền vững trong `docs/qa/`.
- [x] Cập nhật OpenAPI, API usage, migration guide, traceability và walkthrough theo
  code cuối; bỏ số test cũ nếu suite count đã thay đổi.
- [x] Chỉ đổi kế hoạch Mốc A/B và remediation sang `COMPLETED` khi mọi exit ở trên PASS.
  Nếu còn exception, ghi `PARTIAL/HOLD` cùng owner và điều kiện đóng cụ thể.
- [x] Local/test engineering PASS không tự mở R-09; staging/production vẫn cần cấu hình
  HTTPS/CORS/media, smoke/rollback và authorization CTO/Ops theo gate hiện hành.

## 10. Thứ tự triển khai

1. **C0 + C1** — sửa trạng thái báo cáo và bảo vệ đường migration trước mọi thay đổi DDL khác.
2. **C2 + C3** — viết race tests đỏ, sửa hai lỗi concurrency, chạy focused backend suite.
3. **C4** — sửa state machine/storage web và recovery E2E.
4. **C5** — hoàn thiện CMS E2E, validation và a11y scope.
5. **C6** — chạy full regression, lưu evidence, review đa ghế và đóng trạng thái.

Không chia commit theo số file. Mỗi commit phải đóng một invariant có test tương ứng,
cite FR/NFR phù hợp và tuân thủ quy ước message của các ghế dự án.
