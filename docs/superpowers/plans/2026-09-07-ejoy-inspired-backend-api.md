# Kế hoạch backend API — vòng học CI lấy cảm hứng từ eJOY và Mazii

Ngày: 2026-09-07. Trạng thái: **IMPLEMENTED — NEEDS REMEDIATION. Có triển khai A–D nhưng chưa đủ điều kiện nghiệm thu theo kiểm tra ngày 2026-09-07.** 359 tests xanh và OpenAPI không lệch chưa bao phủ các lỗi đã tái hiện. Xem [báo cáo kiểm tra](../../qa/2026-09-07-backend-plan-completion-review.md) và [kế hoạch khắc phục R0–R8](2026-09-07-backend-remediation-plan.md). Các sáng kiến mở rộng (5.8 AI hội thoại và 5.13 Luyện đọc/Offline) vẫn được bảo lưu cho Đợt E.

Cập nhật triển khai: [kết quả khắc phục](../../qa/2026-09-07-backend-remediation-implementation.md). Các con số retention ở đây là đề xuất lịch sử; policy hiện hành theo amendment ADR-007/SRS, chưa tự áp dụng purge 24 tháng.

Cập nhật 2026-09-07: bổ sung khảo sát Mazii; giữ đường dẫn file để các liên kết hiện có tiếp tục hoạt động. Phạm vi mới được tích hợp vào API, dữ liệu, PR và kiểm thử bên dưới; không phải yêu cầu đã được ký trong SRS.

Ghế chủ trì: CTO. Phối hợp: BA / System Analyst, Platform; Pedagogy giữ quyết định phương pháp học. QA và Ops tham gia nghiệm thu theo từng đợt. Kế hoạch dựa trên mã nguồn hiện có, gồm cả working tree; không coi kết quả kiểm thử lịch sử là bằng chứng của lần triển khai sắp tới.

## 1. Kết quả cần đạt và phạm vi

Người học mở chuỗi “Đi konbini”, xem một clip đúng cấp CI, nghe lại một cảnh, lưu cảnh đó rồi tiếp tục trên iPad. Backend trả đúng phiên bản nội dung, lưu vị trí và ghi nhận thời gian phát mà không cộng trùng khi mạng chập chờn hoặc chuyển thiết bị.

Các nhóm API:

1. Phiên bản nội dung và cảnh có timestamp; phát lại/tốc độ do client điều khiển.
2. Series video biên tập theo tình huống.
3. Bộ sưu tập cảnh đã lưu.
4. Phiên phát và xem tiếp xuyên thiết bị.
5. Thời gian phát được server chấp nhận, lịch hoạt động và mục tiêu ngày.
6. Gợi ý video bằng quy tắc CI/chủ đề/lịch sử.
7. AI hỗ trợ staff tạo transcript tiếng Nhật và gợi ý chia cảnh, ở đợt sau.
8. AI hội thoại và gửi bản ghi cho giáo viên: initiative sau, chỉ ghi điều kiện mở trong plan này.
9. Bộ sưu tập cá nhân có tên và thứ tự; mở rộng saved scenes, tách biệt series biên tập.
10. Góp ý lỗi theo cảnh và hàng đợi staff xử lý.
11. Transcript Nhật được duyệt, hỗ trợ cách đọc cho staff và tìm câu/cảnh trong kho JPLearn.
12. Bài đọc có hình/furigana và gói nội dung offline: initiative sau, chưa triển khai trong A–D.

Đợt đầu không triển khai dịch L1, flashcard/SRS từ vựng, grammar drill, chấm phát âm, nhập URL YouTube tùy ý, offline telemetry, push notification, thanh toán, hay ML recommendation. Transcript đầy đủ phục vụ staff; chỉ trích đoạn Nhật được duyệt riêng mới được trả trong search ở đợt D. Phụ đề toàn video, furigana cho learner, bài đọc và probe chọn hình là phạm vi SAD riêng. Không tự bật bốn cờ sư phạm hiện có.

Nguồn ý tưởng: [eJOY cập nhật](https://ejoy-english.com/en/extension/whats-new), [Dictation & Shadowing](https://ejoy-english.com/dictation/en), [sản phẩm eJOY](https://ejoy-english.com/en). Các API dưới đây là **thiết kế đề xuất của JPLearn**, không phải API của eJOY.

Khảo sát Mazii ngày 2026-09-07: [Learning Hub](https://mazii.net/vi-VN/learning-hub) có sổ tay và khám phá nội dung; [bài luyện đọc đã xem](https://mazii.net/news/b5e58950de07bf5a9f47ad90c76a5aa4) có furigana và ghi nguồn Todaii Japanese; [từ điển mở](https://mazii.net/vi-VN/opendict) và [mô tả ứng dụng chính thức](https://play.google.com/store/apps/details?id=com.mazii.dictionary) giới thiệu đóng góp cộng đồng, tra cứu nhiều cách, đồng bộ sổ tay và offline. Bản cập nhật Android ghi 03/09/2026 giới thiệu AI hội thoại theo tình huống và tra từ ngay trong hội thoại. Chưa kiểm thử chất lượng AI/OCR/offline hoặc tính năng trả phí. Tìm cảnh và workflow báo lỗi dưới đây là cách chuyển hóa cho JPLearn, không khẳng định Mazii có cùng chức năng/API. Không thu thập lại kho từ điển, bài báo hoặc sổ tay Mazii để làm dữ liệu dự án.

## 2. Nền hiện tại đã đối chiếu

| Thành phần | Hiện trạng và hệ quả |
| --- | --- |
| Runtime | FastAPI/Python, SQLAlchemy async, PostgreSQL; `apps/api-python` là backend duy nhất |
| Kiến trúc | Router → command/query → handler → domain → repository/UoW; bootstrap nối adapters theo ADR-006 |
| Migration | Alembic viết tay; head đang là `0002_session_idem_rev`. CLI còn ánh xạ head tới snapshot 0002, cần cập nhật theo revision mới |
| Catalog | Published filtering, staff draft edit bằng `expected_revision`, QA/admin publish; `revision` metadata không phải version timeline |
| Media | MP4/HLS và signed URL đã có; HLS có thể đăng ký trên cùng asset. Không dùng asset ID hoặc signed URL đơn độc làm version cảnh |
| Session cũ | Start có Idempotency-Key; end khóa session/progress và ghi event trong UoW; duplicate end trả 400 |
| Progress cũ | `minutes_comprehensible` = tổng floor phút của từng phiên start→end hợp lệ; phiên >4 giờ nhận 0. Chưa phải measured watch time |
| Thiết bị | `devices` chỉ unique `(user_id, device_class)`; không dùng nó làm định danh một playback cụ thể |
| Client | Web có HLS/MP4, control và hồi phục nguồn; chưa có saved scenes, content version, server resume hay heartbeat |

Bằng chứng: [learning domain](../../../apps/api-python/src/jplearn_api/domain/learning.py), [session router](../../../apps/api-python/src/jplearn_api/entrypoints/http/routers/sessions.py), [catalog domain](../../../apps/api-python/src/jplearn_api/domain/catalog.py), [models](../../../apps/api-python/src/jplearn_api/adapters/persistence/models.py), [bootstrap](../../../apps/api-python/src/jplearn_api/bootstrap.py), [migrate CLI](../../../apps/api-python/src/jplearn_api/entrypoints/cli/migrate.py).

[SRS](../../sad/01-survey-srs/srs.md), [ADR-005](../../sad/03-design/adr-005-ba-hardening-decisions.md), [ADR-006](../../sad/03-design/adr-006-clean-architecture.md), [ADR-004](../../sad/03-design/adr-004-ddl-alembic.md), [development](../../backend/development.md) là đầu vào. ERD còn tên migration lịch sử; một số bảng mô tả route còn đếm 20 operations. Khi chốt contract phải đối chiếu router và OpenAPI hiện hành, sửa phần mô tả hiện hành, giữ nguyên evidence lịch sử.

## 3. Truy vết yêu cầu dự kiến

**Mọi ID ở bảng này là đề xuất, chưa được cấp trong SRS.** BA kiểm tra trùng mã, chốt wording, cập nhật SRS → UC/data dictionary → traceability/ERD/diagrams → OpenAPI trước code domain mới. Plan này không tự ký thay các ghế.

| FR dự kiến | UC dự kiến | Acceptance chính | Owner nghiệp vụ |
| --- | --- | --- | --- |
| FR-SCN-001 | UC-T06, UC-L14 | Cảnh thuộc content version; timestamp hợp lệ; learner chỉ đọc bản được duyệt/published | BA + Pedagogy + Content |
| FR-SER-001 | UC-T07, UC-L15 | Series có thứ tự, QA và admin publish; không lộ clip draft | BA + Content |
| FR-BMK-001 | UC-L16 | Lưu/xóa lặp không tạo trùng; đúng user; cảnh cũ có trạng thái stale/unavailable | BA |
| FR-RSM-001 | UC-L17 | Xem tiếp đúng version; thiết bị cũ/request cũ không ghi đè checkpoint mới | BA |
| FR-WAT-001 | UC-L18 | Pause/buffer/seek không tự tăng credit; retry và nhiều thiết bị không cộng đôi | BA + Data |
| FR-GOL-001 | UC-L19 | Mục tiêu theo giây hoạt động; ngày theo IANA timezone; thay đổi không viết lại quá khứ | BA |
| FR-HIS-001 | UC-L20 | Lịch sử riêng tư, phân trang, xóa chi tiết được; không reset legacy progress ngầm | BA + Ops |
| FR-REC-001 | UC-L21 | Gợi ý published theo quy tắc giải thích được, có fallback; không tự nâng CI level | BA + Pedagogy |
| FR-AIC-001 | UC-T08 | Job bền vững, kết quả nháp gắn version, người duyệt, không tự publish | Content + Pedagogy |
| FR-AIS-001 | UC-L22 | Deferred; đồng ý ghi âm, retention riêng, speaking gate và phản hồi phù hợp CI | Pedagogy |
| FR-COL-001 | UC-L23 | Bộ sưu tập riêng tư có tên/thứ tự; xóa collection không xóa saved scene | BA |
| FR-RPT-001 | UC-L24, UC-T09 | Góp ý gắn scene/version; staff xử lý có audit, không sửa nội dung published trực tiếp | BA + Content |
| FR-JPA-001 | UC-T10 | Transcript/cách đọc Nhật có revision, provenance và người duyệt; AI không bắt buộc | BA + Pedagogy |
| FR-SCH-001 | UC-L25 | Tìm câu/cảnh trong nội dung hiện published; snippet được duyệt riêng, không lộ transcript staff | BA + Pedagogy |
| FR-RDG-001 | UC-L26 | Deferred: truyện ngắn có hình/furigana/audio, cấp và tiến độ đọc riêng | Pedagogy |
| FR-OFF-001 | UC-L27 | Deferred: gói tải có version/quyền/hạn dùng; chính sách sync offline riêng | BA + Ops |

Liên quan FR hiện có: FR-CAT-001…005, FR-CMS-001…004, FR-SES-001…003, FR-PRG-001…004, FR-LRN-001/003/004, FR-FLG, FR-NEG và NFR bảo mật/đa thiết bị/quan sát. Liên quan không có nghĩa FR cũ đã bao trùm tính năng mới. NFR mới về latency, quota, retention và concurrency được chốt trong PR thiết kế.

## 4. Quyết định kiến trúc và compatibility

- Giữ một backend và một PostgreSQL. Thêm module nghiệp vụ trong cấu trúc hiện tại; chưa thêm Redis, Kafka, microservice, full CQRS hoặc event sourcing.
- Domain/application thuần Python; framework, SQL, AI SDK ở entrypoints/adapters. Mọi write dùng UoW riêng, commit rõ ràng; không giữ transaction trong khi gọi AI hoặc xử lý file lâu.
- Giữ contract `/sessions`, `/sessions/{id}/end`, `/progress` và event legacy. Không thay duplicate-end 400, không đổi công thức phút cũ hoặc backfill chúng thành watch time.
- Tạo `/playbacks` và `/me/activity` độc lập. `active_watch_seconds` không cộng vào `minutes_comprehensible`; hai chỉ số đo hai thứ khác nhau. Client cũ vẫn dùng session cũ; client mới có thể gọi cả hai nhưng không cộng hai số để hiển thị một tổng.
- Bản nháp nội dung được sửa bằng catalog CAS; submit-qa đóng băng source identity, timeline và scenes thành content version bất biến để duyệt. Publish chỉ chọn đúng version/revision đã QA, không lấy bản nháp mới nhất tùy ý. `catalog_items.revision` tiếp tục dùng CAS quản trị. Thay timeline/media tạo bản nháp/version mới; transcode chỉ được giữ version nếu xác nhận cùng nội dung/timeline. Không overwrite media đang được version published tham chiếu.
- Bản đầu lưu cảnh do staff định nghĩa; chưa cho learner chọn A–B tùy ý. Một scene ID thuộc đúng một version; sửa mốc sau publish tạo version và scene ID mới.
- Reuse hạ tầng phát và cấp URL hiện có; không cắt/tạo file cho mỗi cảnh. Kiểm published trước khi cấp URL mới. Unpublish không bảo đảm URL đã ký mất hiệu lực ngay trước TTL; nếu cần thu hồi tức thời phải có thiết kế media authorization riêng.
- Các endpoint mới theo error envelope ADR-005, validation 400, auth 401, role/ownership 403 theo convention hiện tại, missing/not-visible catalog 404, conflict 409, quota 429 + Retry-After, dependency unavailable 503. Không lộ 422 mặc định.
- `POST` tạo playback/job bắt buộc `Idempotency-Key` ≤128 ký tự, scoped user + operation + key; cùng body trả lại resource/status cũ, body khác 409. PUT/DELETE phải an toàn khi lặp; write biên tập dùng `expected_revision` và trả 409 khi stale.
- List mới dùng cursor opaque với tie-breaker ID, `limit` mặc định 20, tối đa 100. Không thay pagination của endpoint legacy trong cùng việc này. Không lưu signed URL/JWT trong bookmark/history/event/job.

## 5. Danh mục API dự kiến

Mọi đường dẫn ở mục này là **mới và dự kiến**, trừ endpoint catalog workflow được ghi rõ là tái sử dụng. Learner resource luôn suy ra user từ token, không nhận `user_id` để chọn chủ dữ liệu. Staff không được đọc lịch sử learner theo quyền teacher/admin thông thường.

### 5.1 Phiên bản nội dung và scenes — đợt A

| Method / path | Quyền | Input/output chính |
| --- | --- | --- |
| GET `/staff/catalog/{id}/content` | Teacher/Admin | Bản nháp hiện tại, version published, media và scenes; phục vụ biên tập |
| PUT `/staff/catalog/{id}/content` | Teacher/Admin | `expected_revision`, `media_asset_id`, danh sách `{scene_id?, start_ms, end_ms, order}`; ghi trọn bản nháp trong transaction |
| POST `/staff/catalog/{id}/return-to-draft` | Admin | Từ level_qa về draft khi cần sửa; expected_revision, lý do; hủy hiệu lực ứng viên QA, tăng revision |
| GET `/catalog/{id}/content` | Authenticated | `content_version`, `duration_ms`, `scenes`, playback URL/HLS URL có hạn; chỉ published |

Tái sử dụng `/staff/catalog/{id}/submit-qa`, `/publish`, `/unpublish`: bổ sung validation và chuyển published content version atomically trong catalog lock, không tạo một đường publish cảnh bỏ qua Level QA. Chỉ sửa nội dung khi catalog draft; muốn thay nội dung published phải unpublish → draft → QA → publish như workflow hiện tại.

Mọi mutation media/HLS hiện có cũng phải lấy catalog lock và kiểm version đã pin. Khi level_qa, thay source/timeline bị từ chối cho đến khi Admin return-to-draft; khi published phải unpublish trước. Cập nhật transcode cùng timeline chỉ được phép theo quy tắc kiểm chứng ở PR0, không được sửa file nguồn bất biến tại chỗ. Đây là delta contract của media/CMS phải ghi vào SRS/OpenAPI và regression tests, không chỉ validation riêng ở PUT content.

Quy tắc: `0 <= start_ms < end_ms <= duration_ms`; scenes có thứ tự ổn định, không trùng order, không overlap trong bản đầu; khoảng trống được phép. Giới hạn ban đầu 100 scenes/clip, staff tự kiểm toàn cảnh có nghĩa. Duration phải được kiểm chứng từ media trước khi publish segmentation; metadata catalog cũ không được tự coi là thời lượng đo thật. Media thay khi QA đang chạy làm bản QA stale, phải duyệt lại.

Backfill content version ban đầu cho clip hiện có bằng migration/job idempotent, không tạo scenes giả, không đổi trạng thái publish. Ghi nguồn duration là legacy metadata; khả năng phát cũ giữ nguyên, segmentation mới chỉ được publish sau khi xác minh duration. Không đưa `title_internal` hoặc transcript staff vào response learner.

### 5.2 Series tình huống — đợt A

| Method / path | Quyền | Chức năng |
| --- | --- | --- |
| POST `/staff/series` | Teacher/Admin | Tạo series draft; title hiển thị, topic, CI và mô tả ngắn |
| GET `/staff/series`, GET `/staff/series/{id}` | Teacher/Admin | Danh sách/detail để biên tập |
| PATCH `/staff/series/{id}` | Teacher/Admin | Sửa metadata draft bằng expected_revision |
| PUT `/staff/series/{id}/items` | Teacher/Admin | Thay toàn bộ thứ tự item trong transaction; tối đa 100, không lặp clip |
| POST `/staff/series/{id}/submit-qa` | Teacher/Admin | Draft → level_qa |
| POST `/staff/series/{id}/publish`, `/unpublish` | Admin | Workflow cùng nguyên tắc catalog |
| GET `/series`, GET `/series/{id}` | Authenticated | Series published, danh sách clip khả dụng theo thứ tự; filter CI/topic |

Chỉ publish series có ít nhất một clip và mọi thành viên đều published tại thời điểm kiểm. Sau đó nếu clip bị unpublish, query learner loại clip đó và trả `available_item_count`; không lộ metadata của clip bị gỡ. Nếu không còn clip khả dụng thì series không xuất hiện trong list, detail trả 404. Không tự thay clip hay tự nâng cấp người học; series không phải giáo trình khóa tuyến tính.

### 5.3 Cảnh đã lưu — đợt A

| Method / path | Quyền | Chức năng |
| --- | --- | --- |
| PUT `/me/saved-scenes/{scene_id}` | Chủ tài khoản | Lưu scene của published current version; cùng scene không tạo trùng |
| GET `/me/saved-scenes` | Chủ tài khoản | Cursor pagination; `saved_at`, `availability`, cảnh còn khả dụng |
| DELETE `/me/saved-scenes/{scene_id}` | Chủ tài khoản | Xóa hoặc đã không tồn tại đều 204 |

Availability: `available`, `stale_version`, `unavailable`. Bookmark stale không tự chuyển sang timestamp của version mới. Trả stub tối thiểu và lý do khi unavailable; không cấp URL hoặc transcript cũ. DB lưu scene/version identity, không lưu URL có chữ ký. PUT tồn tại trả 200 không đổi thời điểm lưu; lần đầu 201.

### 5.4 Playback, checkpoint và đo thời gian — đợt B

| Method / path | Quyền | Chức năng |
| --- | --- | --- |
| POST `/playbacks` | Chủ tài khoản | `{catalog_item_id, content_version, device_class, client_instance_id, take_over?}`; trả ID, epoch, checkpoint, thời gian server, heartbeat policy |
| GET `/playbacks/{id}` | Chủ tài khoản | Reconcile sau timeout: status, last_seq, active total, last checkpoint |
| PUT `/playbacks/{id}/checkpoints/{seq}` | Chủ tài khoản | Gửi vị trí, cumulative active elapsed, trạng thái player và epoch; trả accepted delta/total, checkpoint mới |
| POST `/playbacks/{id}/end` | Chủ tài khoản | Đóng playback và áp dụng checkpoint cuối trong cùng UoW; retry cùng payload trả kết quả đã lưu |
| GET `/me/resume` | Chủ tài khoản | Danh sách clip có checkpoint mới nhất, phân trang |
| GET `/me/resume/{catalog_item_id}` | Chủ tài khoản | Checkpoint theo version hiện tại hoặc trạng thái stale; chưa có trả 200 với `checkpoint: null` |

Ví dụ payload checkpoint đề xuất:

```json
{
  "epoch": 7,
  "position_ms": 42000,
  "cumulative_active_ms": 30000,
  "player_state": "playing",
  "playback_rate": 1.0
}
```

`seq` bắt đầu 1, tăng liên tiếp. Endpoint end nhận `final_checkpoint` theo cùng schema kèm seq; có thể dùng lại checkpoint đã ACK hoặc seq kế tiếp. Không tự tính thêm elapsed từ lần checkpoint cuối đến request end. Seq trùng với body khác trả 409. Sau end, GET/retry đã lưu vẫn hoạt động, checkpoint mới trả 409.

Quy tắc accounting và chuyển thiết bị phải được test bằng clock giả định:

1. Start playback tạo mốc server, bộ đếm client bằng 0. Checkpoint đầu có thể nhận credit từ mốc start theo cùng validation; chỉ cấp credit cho khoảng online có bằng chứng client hợp lệ.
2. Client gửi khoảng 15 giây/lần và khi pause/seek/end. Server không lấy chênh lệch `position_ms` làm thời gian: tua tới 5 phút không tạo 5 phút học; nghe 60 giây ở 2x nhận tối đa 60 giây; loop tiếp tục được ghi nhận theo thời gian thực.
3. Delta active = hiệu số cumulative counter. Counter giảm, tốc độ ngoài khoảng cho phép hoặc delta lớn hơn elapsed server vượt tolerance đã chốt → 400, không credit. Clock client không quyết định ngày. Retry cùng seq/body trả lại receipt, không cập nhật mốc server hoặc credit lần nữa.
4. Mỗi user chỉ có một playback đang giữ quyền ghi credit/checkpoint. Khóa row `learner_playback_state` trong mọi start/checkpoint/end; lease dự kiến 45 giây. Start khi lease còn hạn trả 409 trừ `take_over=true` do người học chủ động. Takeover tăng epoch và đánh dấu playback cũ superseded; gói cũ không được ghi đè/cộng thời gian.
5. Seq khác last_seq+1 trả 409 và client reconcile qua GET; trong một playback chỉ một request checkpoint đang gửi. Cùng seq và payload khác là conflict, không phải “last writer wins”. `position_ms` có thể giảm khi tua lùi hợp lệ; không dùng max(position) cho resume.
6. Khi khoảng heartbeat vượt 30 giây, checkpoint hợp lệ chỉ thiết lập lại mốc/counter với credit 0, không bù thời gian mất mạng. Lease đã mất hoặc playback superseded thì tạo playback mới. Bản đầu không nhận batch offline; undercount ngắn do mạng được báo trong contract.
7. Trong khoảng ngắn hợp lệ, server chấp nhận client counter có giới hạn, không thể chứng minh người học chú ý hay hiểu. Tên đo là `active_watch_seconds`, không tự suy ra CI level hoặc năng lực. Pause/buffer/seek phải được client loại khỏi cumulative counter và kiểm bằng integration tests.
8. Lock order cố định: learner playback state → playback → content state khi cần → receipt/checkpoint → daily aggregates. Kiểm lại published/current version trong write; version đổi trả 409, clip gỡ trả 404 và không credit. Receipt, checkpoint và credit commit cùng nhau.
9. Lưu milliseconds bằng integer đủ lớn, chỉ chuyển seconds/phút ở query; không floor từng heartbeat. Client mới truyền ID instance ngẫu nhiên, không fingerprint thiết bị hoặc dùng device_class làm ID.

Thứ tự xử lý retry: xác thực/ownership → tìm receipt và so request hash → trả ACK đã lưu nếu khớp; chỉ request mới kiểm lease/epoch/current content và ghi. Vì vậy retry một checkpoint đã commit vẫn nhận ACK sau khi clip bị gỡ hoặc thiết bị khác takeover. ACK chỉ chứa accounting/checkpoint tối thiểu, không cấp lại media URL hay metadata cũ. Sau yêu cầu xóa history, receipt còn giữ chỉ trả trạng thái đã xử lý/credit trước đó, không khôi phục checkpoint đã xóa. Quy tắc này áp dụng nhất quán cho end và checkpoint.

API cần contract với Web/Mobile để đo được thời gian phát; backend hoàn tất đơn lẻ chưa chứng minh goal/history đúng trên máy thật.

### 5.5 Mục tiêu, lịch hoạt động, quyền xóa — đợt C

| Method / path | Quyền | Chức năng |
| --- | --- | --- |
| GET `/me/learning-preferences` | Chủ tài khoản | Timezone IANA, daily_goal_minutes, preferred_topic_ids và revision |
| PUT `/me/learning-preferences` | Chủ tài khoản | expected_revision, timezone, mục tiêu 0–120 phút (0=tắt), topics tồn tại |
| GET `/me/activity?from=...&to=...` | Chủ tài khoản | Ngày, timezone áp dụng, active_watch_seconds, goal_seconds, goal_met; tối đa 90 ngày/lần |
| GET `/me/watch-history` | Chủ tài khoản | Các playback đã chốt hoặc đang chạy, content version, trạng thái khả dụng, cursor |
| DELETE `/me/watch-history` | Chủ tài khoản | Xóa toàn bộ history chi tiết trước cutoff server, trả 202 + deletion ID |
| GET `/me/history-deletions/{id}` | Chủ tài khoản | Poll deletion queued/running/completed/failed, retry được |

Timezone đề xuất mặc định Asia/Ho_Chi_Minh theo sản phẩm cho người Việt, người học có thể đổi. Lưu UTC timestamps mới bằng timestamptz; không đổi loại thời gian legacy trong cùng migration. Mục tiêu/timezone đổi có hiệu lực vào nửa đêm kế tiếp của timezone đang áp dụng; lưu effective_at UTC và goal/timezone version, không tính lại ngày cũ. Topics có hiệu lực ngay.

Khoảng active đi qua nửa đêm được chia theo thời gian server; nếu checkpoint chỉ có tổng active cho khoảng, phân bổ tỷ lệ theo độ dài hai phần và đánh dấu đây là quy tắc phân bổ, không phải timestamp chi tiết client. Client cố gắng flush ở ranh giới ngày. Ngày có thay đổi timezone phải trả timezone/policy version trong từng bucket; query không gộp mù các bucket cùng nhãn ngày. Tổng active milliseconds phải được bảo toàn qua phép chia/làm tròn.

Retention đề xuất để BA/Ops chốt trước rollout: receipt chi tiết 30 ngày sau khi playback đóng; history 180 ngày; resume tối đa 180 ngày không hoạt động; daily aggregates/goal history tối đa 24 tháng; saved scenes đến khi user xóa hoặc tài khoản bị xóa. Tombstone/idempotency cho playback đã đóng giữ ít nhất hết cửa sổ retry 30 ngày; sau cửa sổ này ghi vào ID cũ bị từ chối, không tạo credit mới. Job dọn theo cutoff, giới hạn batch, có dry-run.

Xóa history lập tức ẩn phần trước cutoff và loại khỏi recommendation; worker dọn chi tiết rồi báo hoàn tất. Đóng playback đang active thuộc phạm vi xóa để gói đến muộn không tái tạo history; receipt chống trùng còn trong thời hạn được giữ tối thiểu, không dùng cá nhân hóa. Xóa cả resume liên quan; giữ saved scenes và aggregate ngày/legacy progress, ghi rõ `deletion_scope`/`retained_data` trong response. Xóa toàn bộ tài khoản/reset tiến độ là use case riêng, không ngầm gọi từ nút xóa lịch sử. Worker phục vụ retention/deletion có thể dùng cùng cơ chế job PostgreSQL ở mục 5.7, nhưng triển khai trước AI.

Preference update, deletion và retention khi chạm playback đều khóa learner_playback_state trước, theo cùng lock order với checkpoint. Clock/effective preference version được đọc nhất quán trong user lock. Worker claim job trong transaction ngắn riêng; không giữ job lock rồi chờ learner lock trong transaction xóa. PR4 phải có daily aggregate và preference policy mặc định có version/effective_at để accounting hoạt động độc lập; PR5 mới thêm API cập nhật/đọc chính thức và worker.

### 5.6 Gợi ý nội dung — đợt C

GET `/me/recommendations?limit=10` trả `{items, strategy_version}`; mỗi item có reason thuộc enum ngắn như `same_level`, `preferred_topic`, `continue_series`, `editor_pick`.

Lọc published và current CI trước, sau đó xếp theo series đang xem/chủ đề thích/nội dung chưa xem gần đây; tie-breaker ổn định theo ID. Không tự đẩy CI level cao hơn. Thiếu lịch sử dùng series biên tập cùng cấp; không có ứng viên trả list rỗng hợp lệ. Kiểm eligibility lại trước cấp URL. Không cần model ML hoặc lưu một bảng recommendation riêng ở bản đầu. API không trả title_internal hay dữ liệu người khác; không thêm điểm từ vựng.

### 5.7 AI hỗ trợ staff — đợt D

| Method / path | Quyền | Chức năng |
| --- | --- | --- |
| POST `/staff/catalog/{id}/content-jobs` | Teacher/Admin | Version/source đã đăng ký, task transcript/segmentation, language=ja; 202 + job ID |
| GET `/staff/content-jobs/{id}` | Teacher/Admin theo quyền nội dung | Status, progress, provenance, draft result khi xong |
| POST `/staff/content-jobs/{id}/cancel` | Teacher/Admin theo quyền nội dung | Yêu cầu hủy; không hứa thu hồi chi phí provider đã phát sinh |
| POST `/staff/content-jobs/{id}/apply` | Teacher/Admin theo quyền nội dung | expected_revision + phần kết quả đã sửa; áp dụng vào catalog draft, không publish |

AI port trong application; provider adapter cụ thể được chọn sau thử chất lượng tiếng Nhật và chi phí. Chỉ nhận media asset đã có trong CMS và được phép xử lý; không nhận URL tùy ý hoặc gửi email/lịch sử learner vào prompt. Transcript đầy đủ là staff-only; learner content endpoint dùng allowlist fields.

Durable job queue trong PostgreSQL + worker CLI độc lập cùng codebase. Trạng thái `queued → running → succeeded/failed/cancelled`; apply ghi trạng thái riêng. Worker claim ngắn có lease/attempt token; gọi provider ngoài transaction, completion CAS theo attempt/version để worker cũ không ghi kết quả khi lease mất. Retry có backoff, giới hạn attempts, cancel và timeout rõ. Job thất bại vẫn đọc được; không chạy việc dài bằng background task trong process HTTP.

Job create dedup theo user/operation/idempotency key và một job active cùng source version/task/config. Kết quả pin source hash, content version, provider/model/config. Source đổi trong lúc chạy khiến apply trả 409; apply cùng kết quả lặp không nhân đôi scenes. Không hứa exactly-once billing nếu provider timeout sau khi đã nhận request: dùng provider request ID nếu có, ghi trạng thái outcome_unknown để reconcile trước retry có phí.

Quota cấu hình theo staff và tổng dự án, giới hạn thời lượng media/job, concurrent jobs, retries và ngân sách. Tắt AI nếu chưa có budget/provider cấu hình. Nhật ký không chứa credential, signed URL hoặc transcript đầy đủ. Thu metric tuổi job queued, failure rate, attempts, lượng audio xử lý, chi phí provider thực nếu có và thời gian Teacher chỉnh sửa. Kết quả AI không thay Level QA/admin publish.

### 5.8 AI hội thoại/giáo viên — initiative sau

Chưa tạo route/bảng audio rỗng cho phần này. Điều kiện mở: FR-AIS-001 và UC-L22 được chốt cùng FR-LRN-003/004; Pedagogy xác định ai/khi nào được mở nói; hợp đồng đồng ý ghi âm, thời hạn lưu/xóa, quyền giáo viên được người học chọn, ngân sách và chất lượng tiếng Nhật được kiểm chứng.

Khi đủ điều kiện mới thiết kế conversation session, lượt nói/upload audio, job phản hồi và request feedback gửi đúng giáo viên. Mặc định speaking vẫn false. Không chọn provider, chi phí hay endpoint chính thức trong plan backend đợt A–D.

### 5.9 Bộ sưu tập cá nhân — A mở rộng, sau saved scenes

| Method / path | Quyền | Contract dự kiến |
| --- | --- | --- |
| POST `/me/collections` | Chủ tài khoản | `{name}` + Idempotency-Key; 201, retry trả resource cũ |
| GET `/me/collections`, GET `/me/collections/{id}` | Chủ tài khoản | Cursor pagination; revision, số cảnh, danh sách với availability |
| PATCH `/me/collections/{id}` | Chủ tài khoản | Đổi name bằng expected_revision |
| PUT `/me/collections/{id}/scenes` | Chủ tài khoản | `{expected_revision, scene_ids}` thay trọn danh sách có thứ tự trong UoW |
| DELETE `/me/collections/{id}` | Chủ tài khoản | 204 cả khi đã xóa; không xóa bookmark gốc hoặc lịch sử |

Collection mặc định và luôn private trong bản đầu; không public link, chia sẻ, theo dõi người dùng hoặc bảng xếp hạng. Name 1–80 ký tự sau trim, tối đa 50 collections/user, 200 scenes/collection; không trùng scene trong cùng collection. Một saved scene được nằm trong nhiều collections. Chỉ cho thêm scene đã có trong saved-scenes của cùng user; chưa lưu thì trả 400 và client gọi save trước. Cảnh stale đã có được giữ dạng stub, nhưng không thêm scene stale mới. PUT kiểm owner trước, khóa row trạng thái thư viện theo user rồi collection; stale revision trả 409, không ghi dở thứ tự.

Xóa saved scene gốc xóa cả membership của user trong cùng transaction và tăng revision các collection bị ảnh hưởng. Đổi tên/reorder/xóa collection/save-delete đều dùng cùng library user lock để tránh race giữa kiểm tồn tại và ghi membership. FK/unique phải ngăn membership trỏ bookmark của user khác. Xóa collection không xóa cảnh gốc; xóa history giữ collections như giữ saved scenes. Không tự chuyển cảnh sang version mới. Collection mới và capability tắt không làm thay đổi response saved-scenes cũ.

### 5.10 Góp ý lỗi theo cảnh — A mở rộng

| Method / path | Quyền | Contract dự kiến |
| --- | --- | --- |
| POST `/catalog/{id}/reports` | Authenticated | Idempotency-Key; `{content_version, scene_id?, position_ms?, category, description}`; 201 |
| GET `/me/content-reports`, GET `/me/content-reports/{id}` | Người gửi | Trạng thái và câu trả lời staff đã đánh dấu public; không lộ ghi chú nội bộ |
| GET `/staff/content-reports`, GET `/staff/content-reports/{id}` | Teacher/Admin | Lọc status/category/item; hàng đợi phân trang |
| PATCH `/staff/content-reports/{id}` | Teacher/Admin | expected_revision, assignee, status, public_reply/internal_note, resolution_version_id? |

Category ban đầu: `audio_quality`, `scene_timing`, `visual_mismatch`, `too_difficult`, `other`. Description tối đa 1.000 ký tự, text thuần, không file/HTML/URL nhúng; giới hạn đề xuất 10 report/user/ngày và rate limit burst. Scene phải thuộc đúng item/version, position trong thời lượng; chỉ nhận trên phiên bản hiện published khi tạo mới. Retry đã tạo được nhận lại receipt tối thiểu sau unpublish; không cấp media URL cũ. Report không phải đánh giá điểm năng lực và không tự đổi CI level.

Workflow `open → in_review → resolved | dismissed`; staff có thể mở lại với lý do, mọi thay đổi ghi audit actor/time/revision. Người gửi chỉ thấy report của mình; staff chỉ thấy dữ liệu cần xử lý, không email/history học. Không đăng report công khai. Nếu sửa nội dung, staff tạo draft/version qua CMS và QA như mục 5.1; resolved do đã sửa phải trỏ version thay thế và ghi public_reply. Feedback too_difficult không buộc sửa video; staff có thể trả lời hướng dẫn chọn cấp. Bản cũ/unpublished chỉ giữ reference tối thiểu, không phục hồi quyền phát cũ.

Retention đề xuất: report và audit tối đa 180 ngày sau lần cập nhật cuối, do BA/Ops chốt; job bảo trì dọn theo policy và dry-run. Report là dữ liệu hỗ trợ riêng, không bị xóa bởi DELETE watch-history; việc xóa tài khoản phải xử lý report/PII theo policy riêng. Metric: số report theo category, tuổi backlog, thời gian xử lý, tỷ lệ mở lại; không log nguyên mô tả vào metrics.

### 5.11 Transcript Nhật, hỗ trợ biên tập và tìm câu/cảnh — đợt D

Đây là phần mới so với AI tạo nháp ở 5.7: transcript được Teacher nhập/sửa thủ công cũng dùng được, không phải đợi mua AI. Tách nhận dạng giọng nói ra khỏi việc tách từ/gợi ý cách đọc; không chọn thư viện tokenizer/OCR hoặc provider trước thử nghiệm trên tiếng Nhật của dự án.

| Method / path | Quyền | Contract dự kiến |
| --- | --- | --- |
| GET `/staff/catalog/{id}/transcript` | Teacher/Admin | Transcript Nhật theo content_version, revision, trạng thái duyệt và provenance |
| PUT `/staff/catalog/{id}/transcript` | Teacher/Admin | expected_revision + content_version + segments `{scene_id, text_ja}`; bản nháp staff |
| POST `/staff/catalog/{id}/language-analysis-jobs` | Teacher/Admin | Idempotency-Key, transcript_revision; 202, chạy qua durable job infrastructure |
| GET `/staff/language-analysis-jobs/{id}` | Teacher/Admin | Token spans, lemma, reading gợi ý, tool/version và các mục cần kiểm tra |
| POST `/staff/catalog/{id}/transcript/submit-qa` | Teacher/Admin | Đóng băng revision ứng viên, không tự duyệt snippets |
| POST `/staff/catalog/{id}/transcript/approve` | Admin | Revision/content_version được Teacher/Pedagogy rà; phê duyệt các snippet Nhật cho search |
| POST `/staff/catalog/{id}/transcript/return-to-draft` | Admin | Lý do + expected_revision; vô hiệu quyền search của bản duyệt hiện hành cho đến khi duyệt lại |
| GET `/catalog/search?q=...&ci_level=...&cursor=...` | Authenticated | Scene/item/version, đoạn Nhật đã duyệt, timestamp, match_kind và next_cursor |

Text đầy đủ/cách đọc gợi ý vẫn staff-only; search projection chỉ có snippet được duyệt cho learner, không có dịch Việt, giải thích grammar, title_internal hoặc toàn transcript. Việc duyệt transcript không publish catalog và không sửa timeline/scenes bất biến. Thay text sau QA tạo transcript revision mới; bản draft mới không thay bản approved đang phục vụ cho đến lần approve tiếp theo. Với sửa lỗi cần thu hồi ngay, Admin return-to-draft thu hồi eligibility của bản cũ. Content version thay hoặc catalog unpublish làm search cũ unavailable ngay ở query.

Segment phải tham chiếu scene đúng version; tối đa 100 segments, 500 ký tự/segment, tổng 20.000 ký tự/clip ở bản đầu. Phân tích trả offset theo Unicode code point, reading/lemma có provenance; kiểm alignment trước khi dùng, không suy ra mọi Kanji có một cách đọc cố định. Teacher cần rà tên riêng, số/đếm và từ đồng hình. AI job apply ở 5.7 chỉ cập nhật transcript draft qua cùng use case/CAS, không bypass approve. Job hoàn tất trên transcript revision cũ bị đánh dấu stale, không ghi đè sửa tay.

Search bản đầu nhận 1–100 ký tự, chuẩn hóa Unicode/khoảng trắng/Kana có kiểm thử; ưu tiên exact phrase rồi token/lemma. Không bật mở rộng ngữ nghĩa/romaji tùy ý trong MVP. Tokenization Nhật phải được đánh giá riêng, không mặc nhiên dùng English stemming. Query adapter/index ở PostgreSQL, chưa thêm search service. Giữ original text để highlight đúng, mapping normalization phải có test. q chỉ dùng tìm trong kho JPLearn có quyền; không gọi dictionary Mazii hoặc gửi q sang AI bên ngoài.

Approve ghi projection đã duyệt cùng trạng thái trong UoW nếu corpus nhỏ; nếu cần worker reindex, query luôn join current approved revision + current content version + published trước trả kết quả. Chấp nhận thiếu kết quả trong lúc reindex, không chấp nhận lộ bản đã thu hồi. Cursor pin index generation để refresh/reindex không gây phân trang sai; generation thay trả 409 yêu cầu tìm lại. Không cache signed URLs trong index. Chốt GET `/catalog/search` trước route động `/catalog/{id}` và kiểm route precedence.

Kết quả giới hạn cùng/bên dưới cấp người học mặc định; filter CI là lựa chọn nội dung, không thay current_ci_level. Không lịch sử search riêng ở bản đầu; telemetry chỉ latency/zero-results và lỗi đã sanitize, không log q nguyên văn mặc định. Capability `scene-search` tách `staff-language-tools`; search chỉ mở sau duyệt sư phạm cho snippet. Phụ đề toàn video/furigana learner không tự được mở bởi capability này.

### 5.12 Làm rõ quota và sổ theo dõi AI — đợt D

Mục 5.7 đã có budget/quota nên đây là hoàn thiện thiết kế, không tính là một module sản phẩm mới từ Mazii. Thêm GET `/staff/ai-usage` cho staff xem usage của mình và GET `/staff/ai-usage/summary` Admin xem tổng dự án theo khoảng ngày tối đa 90 ngày; không trả transcript/prompt/credential. Phân biệt audio seconds, input/output tokens và cost theo provider/currency; không coi token là tiền hoặc so token mọi model như nhau.

Trong job-create UoW, reserve ngân sách dưới quota-account lock rồi tạo job. Cùng idempotency key không reserve lại. Worker settle actual usage theo provider request/attempt một lần, release phần còn lại khi biết chắc không bị tính phí. Outcome unknown giữ reservation và reconcile; không tự release rồi retry gây vượt ngân sách. Policy version lưu theo thời điểm reserve, kiểm giới hạn concurrency trên nhiều workers. Đây là ledger vận hành nội bộ, chưa phải ví mua token/thanh toán cho learner.

### 5.13 Luyện đọc và offline — initiative E, sau A–D

**Luyện đọc:** nghiên cứu truyện ngắn có hình đúng cấp CI, furigana tùy chọn và audio được duyệt. Cần FR-RDG-001, content type riêng, block/paragraph IDs, reading annotation theo revision và quyền nguồn; bài báo Todaii/Mazii chỉ là tham khảo, không nhập lại nội dung. Dự kiến có read catalog/detail và reading checkpoint, nhưng chưa chốt route/schema trước SAD. Reading activity phải tách watch-time; không tính thời gian mở tab thành hiểu bài, không tự quy JLPT thành CI. Cần Pedagogy định nghĩa mức mở đọc và đo thử khả năng hiểu trước triển khai.

**Offline:** cần FR-OFF-001, manifest chứa content version/checksum/size, quyền tải/hạn dùng, giới hạn thiết bị/dung lượng, renew/revoke và cleanup client. Signed streaming URL hiện có không thay offline entitlement; unpublish không thể thu hồi ngay bytes đã tải khi máy mất mạng. Chỉ chọn nội dung có quyền offline. Backend/client phải đặc tả tải gián đoạn, version cũ, logout và gỡ gói. Offline telemetry là contract riêng về dedup, clock, overlap nhiều thiết bị và mức tin cậy; không gửi batch offline vào checkpoint online 5.4 để nhận credit. Chưa tạo bảng/route hoặc đưa E vào ước lượng A–D.

## 6. Dữ liệu và transaction dự kiến

Tên bảng là dự kiến; khóa liên kết bảng hiện có dùng cùng kiểu TEXT ID, không đổi legacy sang UUID type trong lần này. Timestamp mới UTC/timestamptz. Các bảng được thêm đúng đợt, không tạo trước toàn bộ AI schema.

| Đợt | Bảng/nhóm dữ liệu | Constraint/index quan trọng |
| --- | --- | --- |
| A | catalog_content_versions + catalog_scenes; current/draft version reference | unique(item, version); scenes thuộc version; CHECK bounds nội bộ; kiểm duration/order/overlap trong UoW; index(version, order) |
| A | content_series + series_items | unique(series, position), unique(series, item); revision CAS; status/CI/topic index |
| A | saved_scenes | unique(user, scene); index(user, saved_at, id); không cascade xóa version đang được tham chiếu |
| B | playbacks + playback_receipts | owner/version/instance/epoch/state; unique(user, create key); unique(playback, seq); request hash và response ACK |
| B | learner_playback_state + playback_checkpoints | một lease row/user; checkpoint unique(user,item,version); epoch/seq ngăn stale write |
| B | learner_daily_activity + learning_preference_versions | integer active_ms; unique(user, day, timezone policy); effective_at/revision; index(user,day); policy mặc định có ngay khi bật accounting |
| C | maintenance_jobs/deletion cutoff | job durable, scope/cutoff, attempts/lease; query history loại dữ liệu đã được yêu cầu xóa |
| D | content_jobs + staff_transcript_drafts | source/version/task/config hash, attempt token/lease, result refs, provenance; index(status,next_attempt_at) |
| A mở rộng | learner_library_state + personal_collections + collection_scenes | user lock; unique(collection, scene/order); FK theo ownership bookmark; collection revision |
| A mở rộng | content_reports + content_report_audit | owner/item/version/scene, category/status/revision; index(status,updated_at,id), index(user,created_at,id) |
| D | transcript_revisions + approved_scene_texts + language_analysis_jobs | unique(item,content_version,revision); approved pointer/projection; stale analysis không apply; index theo generation |
| D | ai_quota_accounts + ai_usage_ledger | reservation theo job; settlement unique(provider request,attempt,kind); lưu đơn vị/policy version |

Không cần thêm event enum legacy cho mỗi heartbeat. Receipt và daily aggregate là ledger/projected state riêng trong cùng transaction, không event sourcing. Activity query đọc aggregate, history đọc playbacks; recommendation query dùng history đã được phép. Nếu thêm business events mới sau này cần migration enum/data dictionary riêng, không ghi type lạ vào enum EventType hiện tại.

Transaction chính: save draft + revision; publish + current version pointer; reorder series; bookmark upsert; checkpoint + receipt + resume + credit; preference revision/effective boundary; job state transition. Tất cả rollback-by-default. Không query/gọi AI khi đang giữ row lock.

## 7. Cấu trúc code và thứ tự PR

Mỗi module thêm theo vertical slice, kèm contract và test; đường dẫn dưới `apps/api-python/src/jplearn_api/`:

- `domain/`: content/scenes, series, library, playback, activity, recommendations; content_jobs ở đợt D.
- `application/handlers/`: các use case tương ứng; cập nhật commands/queries/read_models, repository/UoW ports. Tách port mới theo nhóm khi cần, không tạo một repository khổng lồ.
- `adapters/persistence/`: models/repositories/query adapters/UoW; worker persistence từ đợt C, provider adapter từ đợt D.
- `entrypoints/http/routers/`: content, series, library, playback, activity, recommendations, content_jobs; schemas/error mapping riêng theo feature nếu file chung quá lớn.
- `entrypoints/cli/`: maintenance worker từ C, AI worker từ D; composition root ở `bootstrap.py`, runtime knobs ở `settings.py`.
- `migrations/versions/`, `resources/`, CLI migration target mapping và schema snapshot tests theo từng revision.

| PR | Nội dung | Điều kiện hoàn tất |
| --- | --- | --- |
| 0 | Chốt FR/UC/NFR draft thành contract; ghi quyết định accounting/version/timezone/retention/flags | SRS→traceability→OpenAPI thống nhất; review nghiệp vụ/kiến trúc theo gates, không giả chữ ký |
| 1 | Content version và scenes, staff draft và learner read, publish integration | Bounds/version/QA/replace-media/concurrent-publish tests; migration từ head hiện hành |
| 2 | Series biên tập và learner list/detail | Order CAS, published filtering, clip bị gỡ |
| 3 | Saved scenes | Idempotency, ownership, stale/unavailable, pagination |
| 3a | Collections riêng tư có tên/thứ tự | Xóa collection giữ bookmark; xóa bookmark cập nhật memberships/revision; race/ownership/quota |
| 3b | Báo lỗi scene và staff moderation | Dedup, privacy/audit, không bypass QA; resolved link đúng version |
| 4 | Playback create/status/checkpoint/end/resume + receipts + daily aggregates + default preference policy | Retry/reorder/takeover/atomic rollback/clock boundary tests |
| 5 | Preferences, daily activity, history và deletion/retention worker | Timezone/midnight/rounding/deletion/cutoff; legacy progress không đổi |
| 6 | Recommendation rules + reason + fallback | Deterministic, đúng CI/published, loại history đã xóa |
| 7 | Pilot A–C với client integration và đo tải | Evidence cùng candidate, không chỉ API unit tests; đóng các lỗi tìm thấy |
| 8 | AI jobs/provider trial/worker/apply draft | Restart/lease/retry/unknown outcome/stale version/quota/human review |
| 8a | Transcript nhập tay/duyệt và language tools staff | Revision/CAS, Japanese alignment, stale job; có thể làm trước 8 bằng cơ chế nhập tay |
| 8b | Search projection và tìm câu/cảnh | Phụ thuộc 8a + scenes; exact/token relevance, no stale exposure, route precedence |
| 8c | Usage ledger và reserve/settle/reconcile | Hoàn tất trước mở provider có phí của PR8; dedup và budget race được kiểm |

PR1–3b là đợt A mở rộng; PR4 là B; PR5–7 là C; PR8/8a/8b/8c là D. Các nhãn PR là nhãn phạm vi, không bắt buộc thứ tự số: 8a nhập tay → 8b search có thể đi trước AI; 8c là điều kiện mở provider có phí ở 8. PR3a phụ thuộc 3, PR3b phụ thuộc 1; PR2 và PR4 có thể phát triển độc lập sau content contract nhưng migration vẫn đi một chuỗi. Hạ tầng moderation không cần chờ AI. Module collections/reports mở rộng library và thêm content_feedback; Japanese analysis/search và usage ledger thêm ports/query adapters ở D, vẫn theo ADR-006. Không gán số migration 0003… cố định trước khi kiểm lại head lúc thực hiện.

Ước lượng lập kế hoạch cập nhật sau Mazii, chưa phải cam kết: với một backend chính, BA/QA part-time và Web/Mobile phối hợp contract, A mở rộng khoảng 3–4 tuần; B 2–3 tuần; C 1–2 tuần; D mở rộng 2–4 tuần tùy chất lượng transcript/tokenization và provider. Tổng A–C khoảng 6–9 tuần; tổng A–D khoảng 8–13 tuần. Ước lượng cũ 5–8 tuần A–C không bao gồm collections/moderation mới. Không bao gồm E, thời gian chờ thiết bị/staging, review lớn hoặc UI đầy đủ; cập nhật lại sau PR0/PR1 và thử nghiệm tiếng Nhật.

## 8. Migration, tương thích client và rollout

1. Thêm DDL theo ADR-004; không autogenerate/create_all. Giữ baseline 0001 và snapshot 0002; thêm expected snapshot theo revision mới, cập nhật resource đóng gói và `migrate.py` mapping cho head/stamp rõ ràng. Unsupported revision phải fail closed.
2. Kiểm upgrade từ DB trống, từ 0002 có fixture dữ liệu và adoption đúng revision; CLI/package/container tests không còn hardcode số bảng cũ. Backfill content versions idempotent theo batch; không đổi published status, không reset dữ liệu dev.
3. Dùng expand-only trong rollout: thêm bảng/cột nullable cần thiết, backfill/verify rồi mới buộc invariant mới. Không đổi response required fields legacy khiến client cũ hỏng. Thay media selection và signed URL resolution phải có regression test với catalog cũ lẫn version mới.
4. Feature switches mới phía backend và capability read riêng `GET /capabilities` cho authenticated client, ví dụ content/scenes, saved-scenes, playback-tracking, activity, recommendations, staff-ai. Không mở rộng mù model PATCH `/staff/flags` đang cố định bốn cờ vì client cũ có thể reset default. Bản đầu cấu hình trong settings theo môi trường và pilot allowlist, không cần admin API mới; PR0 chốt schema capability và audit thay đổi cấu hình. Mặc định tắt feature mới, server thực thi việc tắt (không chỉ ẩn UI).
5. Deploy schema → code tương thích flags tắt → backfill → smoke → pilot nội bộ → theo dõi → bật từng capability. Khi tắt playback-tracking, từ chối tạo playback mới, ngừng cấp credit; cho phép end/reconcile đóng lease và báo trạng thái crediting_disabled rõ ràng. Resume/history đã lưu vẫn đọc theo policy, không để client tưởng đang được ghi nhận.
6. Rollback bằng tắt capability và deploy code đã kiểm tương thích schema mở rộng; giữ dữ liệu mới. Không downgrade xóa bảng history trong môi trường có dữ liệu. Restore backup là thao tác sự cố riêng theo Ops runbook, không tự động chạy trong rollback feature.
7. Cổng nền tảng đã cho phép SAD vòng học; hồ sơ vận hành vẫn có nợ native máy thật/staging/performance. Pilot/production phải đối chiếu gates/evidence tại thời điểm mở traffic, không suy ra production-ready từ plan hoặc local PASS.

## 9. Kiểm thử và tiêu chí nghiệm thu

| Nhóm | Ca kiểm bắt buộc |
| --- | --- |
| Content/series | Bounds, overlapping scenes, reorder conflict, teacher không publish, media đổi khi đang QA, published/unpublish đồng thời, không lộ draft/title_internal |
| Library/resume | User khác, duplicate save/delete, stale content, cursor ổn định, seek lùi hợp lệ, checkpoint muộn từ thiết bị cũ |
| Collections/moderation | Concurrent reorder/delete/save, membership khác chủ, xóa collection không mất bookmark; report duplicate/spam, revision conflict, public reply không lộ internal note, resolution không bypass QA |
| Japanese/search | Kana width/Unicode, tên riêng và số, offset/highlight, phrase/lemma relevance; transcript draft không lộ, thu hồi/unpublish/reindex đồng thời, route search không bị parse thành item ID |
| AI accounting | Reserve đồng thời, duplicate create/callback/settlement, worker chết sau provider call, unknown outcome không giải phóng budget sớm; phân biệt đơn vị/currency |
| Playback accounting | Retry cùng/khác payload, reordered/missing seq, duplicate end, response mất sau commit, rollback trước commit, hai thiết bị, lease expiry, counter reset, pause/buffer/seek, 2x/loop, disconnect, shutdown |
| Activity/privacy | Qua nửa đêm, timezone/DST, đổi goal tương lai, tổng milliseconds bảo toàn, lịch sử legacy không backfill, deletion pending/completed/retry và gói late không tái tạo dữ liệu |
| Jobs | Worker chết sau claim/call/commit; lease takeover; provider outcome unknown; cancel race; quota; apply lại; source stale; transcript staff không lộ learner |
| Compatibility | Auth/logout/flags legacy, session idempotency, duplicate legacy end 400, `/progress` công thức/body cũ, catalog/media/HLS và URL expiry vẫn đúng |
| Architecture/schema | Domain/application không import ORM/framework/provider, UoW rollback, migration/adoption/packaged snapshot/CLI fail-closed, FR-NEG còn được kiểm |

Unit tests cho policy thuần Python, handler tests với fake ports/clock; integration tests dùng PostgreSQL thật để chứng minh lock/unique/atomicity. Web/Mobile phải kiểm client cumulative counter từ video events; mock heartbeat không thay kiểm chứng đó.

Các lệnh hiện có, chạy lúc triển khai từ repo root trừ chỗ ghi khác:

```bash
pnpm test:guard
pnpm test:api
```

Trong `apps/api-python`:

```bash
uv run pytest tests/test_architecture_guard.py tests/test_package_layout.py -q
PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff
uv run pytest tests/test_openapi_diff.py tests/test_openapi_mutation_suite.py -q
```

E2E từ repo root: `apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit`. Container verification theo [development](../../backend/development.md), dùng OUTPUT_DIR/IMAGE_TAG riêng. Test DB Docker phải là instance chuyên dụng `/jplearn_test`; không đụng volume DB phát triển. Tên test feature mới được tạo theo behavior, không giả định chúng đã tồn tại hôm nay.

Mục tiêu hiệu năng **đề xuất cần đo và chốt ở PR0**: read metadata/activity p95 ≤300ms, checkpoint p95 ≤250ms, create job trả 202 p95 ≤500ms, không tính thời gian AI chạy. Dataset/load ban đầu: 1.000 clips, 10.000 scenes, 100.000 playback rows và 100 playbacks đồng thời gửi mỗi 15 giây (~6,7 checkpoint/s, có burst). Đây là workload thử nghiệm, không dự báo traffic. Ghi cấu hình máy/PostgreSQL, raw samples, baseline và candidate cùng harness; kiểm index/query plan, pool saturation, lock wait và regression endpoint cũ. Không coi target đã đạt.

Metric vận hành: checkpoint accepted/duplicate/conflict/rejected, lease takeover, credit gap, stale content, API 5xx/latency/lock wait, worker queue age/retries, deletion backlog và AI usage. Không dùng user ID làm metric label cardinality cao; log request ID và mã lỗi đã sanitize. Báo động theo ngưỡng pilot được Ops chốt, không mặc nhiên spam từng request lỗi nghiệp vụ.

Bổ sung rollout Mazii: capabilities `personal-collections`, `content-reports`, `staff-language-tools`, `scene-search` và `staff-ai-usage` được kiểm phía server, tách khỏi bốn flags sư phạm. Tắt nhận report mới vẫn cho người gửi đọc trạng thái và staff xử lý backlog. Tắt search không xóa transcript đã duyệt; tắt AI vẫn cho reconcile job/usage đang tồn tại. Collections private tồn tại đến khi user xóa/tài khoản bị xóa; transcript revision và search projection có policy lưu/thu hồi theo content version, BA/Ops chốt ở PR0, không dọn version còn được bookmark/report tham chiếu bằng cascade mù.

Nghiệm thu search bổ sung: Teacher chuẩn bị bộ query Nhật và expected scenes, gồm cách viết Kana/Kanji, tên riêng, số và query không có kết quả; chốt ngưỡng relevance trước benchmark. Đo p95 mục tiêu đề xuất ≤300ms trên corpus 10.000 scenes với projection đã duyệt, đồng thời thử unpublish/reindex; không chỉ đo tốc độ trên dữ liệu trống. Chất lượng reading/lemma phải được kiểm trước mở cho learner, không suy ra từ tokenizer chạy không lỗi.

## 10. Đầu ra cần bàn giao trước khi chuyển sang đợt kế tiếp

- FR/UC/OpenAPI và request/response/error examples đã review, operation IDs ổn định; contracts TypeScript trong `packages/domain`/clients cập nhật có chủ đích.
- Migration + schema snapshots + hướng nâng cấp/rollback tương thích, kiểm dữ liệu cũ còn nguyên.
- Evidence test của candidate hiện hành, cùng revision/dirty status, command/exit code; không tái sử dụng PASS cũ.
- Bộ dữ liệu pilot nhỏ: một series tình huống và scenes được Pedagogy/Content duyệt, có quyền media; QA dùng fixture tổng hợp riêng.
- Hướng dẫn client heartbeat/retry/takeover/unavailable/capabilities; phân biệt phút legacy và active seconds.
- Runbook pilot, retention/deletion, worker và giới hạn AI khi đến đợt D.
- Contract collections/report và ownership/audit; bộ câu Nhật thử search có đáp án mong đợi do Teacher duyệt; báo cáo zero-results/latency và kiểm không lộ bản thu hồi.
- Usage ledger đối soát provider; các điều kiện mở E được ghi riêng, không tự bật đọc/offline/speaking trong nghiệm thu A–D.

**Bước triển khai đầu tiên:** PR0 chốt contract cho A–C; sau đó PR1 content version + scenes. Bản plan này chỉ thêm tài liệu, không thay SRS/OpenAPI chính thức, runtime, schema hoặc dữ liệu.
