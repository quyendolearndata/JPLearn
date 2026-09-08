# ADR-007 — Hợp đồng Kiến trúc Vòng học Comprehensible Input & Thói quen (Đợt A–C)

- **Ghế chủ trì:** CTO (`jplearn-cto`)
- **Ngày:** 2026-09-07
- **Trạng thái:** R0 engineering amendment — A–C đã kiểm chứng local; chữ ký nghiệp vụ/sư phạm/Ops, pilot và cổng production vẫn pending.
- **Phối hợp:** BA (`jplearn-ba`), Platform (`jplearn-platform`), Head of Pedagogy (`jplearn-pedagogy`), Web (`jplearn-web`), Mobile (`jplearn-mobile`), QA (`jplearn-qa`)
- **Kế thừa & liên quan:** ADR-001 (Stack), ADR-003 (FastAPI Hardening), ADR-004 (DDL Alembic), ADR-006 (Clean Architecture), `docs/superpowers/plans/2026-09-07-ejoy-inspired-backend-api.md`

---

## 1. Bối cảnh & Vấn đề

Sau khi hoàn thiện nền tảng cốt lõi (Mốc A/B, Clean Architecture ADR-006), JPLearn tiến hành mở rộng năng lực phục vụ vòng học Comprehensible Input (CI) sâu sắc, lấy cảm hứng từ các tính năng tương tác tự nhiên của eJOY (phân cảnh, bookmark từ ngữ cảnh, theo dõi thời gian thực) và Mazii (bộ sưu tập cá nhân, báo cáo immersion), đồng thời **tuân thủ tuyệt đối giới hạn sư phạm** (`FR-NEG-001` đến `FR-NEG-004`):
- Không đưa vào flashcard / SRS trắc nghiệm từ vựng.
- Không giải thích ngữ pháp, chia thì hay bài tập điền từ.
- Không cung cấp phụ đề dịch tiếng mẹ đẻ L1 cho học viên.
- Không lưu điểm từ vựng hay tiến độ giáo trình truyền thống.

Để bảo đảm hệ thống phát triển ổn định, không làm gãy các client hiện hành (Web Next.js, Mobile Expo), và không gây nợ kỹ thuật cho cơ sở dữ liệu, tài liệu này chốt toàn bộ các quyết định kiến trúc và hợp đồng giao tiếp cho 3 đợt triển khai (Đợt A, B, C).

---

## 2. Các quyết định kiến trúc cốt lõi

### 2.1 Content Versioning & Scenes (Đợt A)

1. **Snapshot bất biến (Immutable Published Content):**
   - Nội dung video CI bao gồm: phân cảnh (`Scene`), mốc thời gian (`start_time_seconds`, `end_time_seconds`), tiêu đề cảnh tiếng Nhật (`title_jp`) và transcript gốc tiếng Nhật (`transcript_jp`).
   - Mọi chỉnh sửa kịch bản phân cảnh diễn ra trên phiên bản nháp (`ContentVersion` có `is_current_draft = true`).
   - Khi Admin xuất bản (`publish`), phiên bản nháp được gán cờ `is_published = true`, `published_at = now()`, trở thành snapshot bất biến. Học viên chỉ đọc metadata cảnh của snapshot current; full transcript chỉ staff. Search chỉ trả excerpt Nhật được duyệt riêng.
   - Khi cần chỉnh sửa nội dung đã xuất bản, hệ thống fork ra một `ContentVersion` nháp mới; phiên bản cũ giữ tham chiếu tối thiểu cho lịch sử; không tự cấp lại media hoặc full transcript cũ. Checkpoint mới vào version cũ trả 409.

2. **Khóa lạc quan (Optimistic Concurrency Control — CAS):**
   - `ContentVersion` chứa cột `revision: int`. Mọi thao tác `PUT /staff/catalog/{id}/content` bắt buộc gửi `version_revision`.
   - Nếu `version_revision != current_revision`, hệ thống trả về `409 Conflict`, buộc client tải lại dữ liệu mới nhất trước khi ghi đè.

3. **Đóng băng kiểm định (Level QA Freeze):**
   - Khi Teacher gọi `POST /staff/catalog/{id}/submit-qa`, `ContentVersion` nháp hiện tại lập tức được đóng băng (`is_frozen = true`).
   - Trong thời gian item ở trạng thái `level_qa`, không ai được phép sửa scenes hay metadata. Nếu cần chỉnh sửa, phải thông qua workflow `POST /staff/catalog/{id}/return-to-draft` để rã đông có kiểm soát và ghi audit log.

### 2.2 Playback accounting — R0 engineering amendment

Legacy `/sessions` và `minutes_comprehensible` giữ nguyên. API mới dùng `/playbacks`, cumulative active milliseconds, checkpoint seq liên tiếp; nhịp gợi ý 15 giây, gap trên 30 giây reset counter với credit 0, lease 45 giây. Đây là thời gian phát thực, không chứng minh hiểu bài; 60 giây ở 2x tối đa 60 giây cộng tolerance đã chốt, không nhân tốc độ.

Counter tăng là phần active thực đã xảy ra trước pause/end. Invalid delta/rate/position trả 400, không âm thầm clamp. End xử lý final checkpoint với cùng validation và transaction. Receipt theo canonical payload trả ACK đã lưu trước kiểm trạng thái live; payload khác cùng seq trả 409. Retry sau takeover/end/deletion không hồi sinh checkpoint hoặc cấp thêm credit.

### 2.3 Single writer, goals và privacy — R0 engineering amendment

Start yêu cầu `Idempotency-Key` scoped user+operation+payload gồm version và client instance. Retry trả cùng resource; body khác 409. Chỉ một writer/user; khóa user state trước playback; writer mới tăng epoch, yêu cầu takeover chủ động khi lease còn hạn. Checkpoint mới phải đúng active playback ID, epoch, lease và current published content version. Lease hết hạn yêu cầu start mới. Reconcile không tự cấp credit.

`/me/learning-preferences` dùng CAS và version effective_at UTC. Goal 0–120 phút (0=tắt), chỉ active_watch_seconds; goal/timezone áp dụng từ nửa đêm tiếp theo của timezone đang hiệu lực. Topics áp dụng ngay. Thay đổi pending trước effective thay thế bản pending dưới user lock, không thay bản current hoặc biên hiệu lực đã tính theo timezone current. Daily buckets giữ policy version/goal/timezone, không viết lại ngày cũ; interval qua effective boundary phải chia và bảo toàn milliseconds. Activity trả current/longest streak trong cửa sổ yêu cầu, gộp nhiều policy bucket cùng ngày và giữ streak hôm qua khi hôm nay còn mở.

DELETE `/me/watch-history` trả 202 + deletion ID, lập tức ẩn history/resume trước cutoff, fence active playback, giữ saved scenes và daily/legacy aggregates. Worker giữ receipt/tombstone tối thiểu cho retry, không tái tạo dữ liệu đã xóa. Retention theo NFR-RET-001 hiện tại: raw90d/aggregate vĩnh viễn; mốc mới chỉ proposal chờ BA/Ops. Không destructive retention theo proposal.

### 2.4 Sổ tay cá nhân, Bộ sưu tập & Cách ly dữ liệu (Đợt C)

1. **Bookmark từ vựng & Ngữ cảnh (Personal Bookmarks):**
   - Học viên có thể lưu cụm từ (`term`), câu ngữ cảnh (`context_sentence`), và mốc thời gian vào sổ tay.
   - Dữ liệu bookmark hoàn toàn thuộc sở hữu cá nhân (`user_id`).
   - Tuyệt đối cấm liên kết bookmark với bất kỳ hệ thống flashcard, điểm số, hoặc thuật toán spaced repetition nào vi phạm `FR-NEG-001`.

2. **Cách ly phạm vi dữ liệu (Scope Isolation):**
   - Playlists (`collections`), lịch sử xem (`watch_history`), và sổ tay (`bookmarks`) được bảo vệ bằng quyền sở hữu tuyệt đối (`user_id = current_user.id`).
   - Mọi thao tác truy vấn, cập nhật, xóa phải áp dụng bộ lọc `user_id` ngay tại repository layer, trả về `404 Not Found` hoặc `403 Forbidden` nếu truy cập trái phép.

3. **Chính sách thu hồi & Tham chiếu toàn vẹn (No Blind Cascade Delete):**
   - Khi một CatalogItem hoặc ContentVersion bị gỡ bỏ hoặc cập nhật, hệ thống **không** thực hiện `CASCADE DELETE` làm mất bookmark hay lịch sử của học viên.
   - Bookmark sẽ duy trì snapshot nội dung tĩnh của câu ngữ cảnh ngay cả khi clip gốc bị gỡ.

### 2.5 Hệ thống Cờ năng lực (Capability Flags System)

1. **Tách biệt khỏi cờ sư phạm:**
   - Bảng `feature_flags` và model `Flags` hiện hành (`speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled`) được giữ nguyên tuyệt đối vì chúng đóng vai trò ranh giới sư phạm nền tảng.
   - Các tính năng mở rộng kỹ thuật được quản lý qua hệ thống `CapabilityFlags` độc lập, trả về qua endpoint `GET /capabilities`.

2. **Danh mục Capability Flags ban đầu:**
   - `video_scene_breakdown_enabled`: Bật tính năng phân đoạn cảnh và transcript đồng bộ.
   - `smart_stream_enabled`: Bật thuật toán gợi ý clip tiếp theo.
   - `interactive_dual_subs_enabled`: Mặc định `false` (bảo vệ FR-NEG-003; chỉ bật khi có chỉ thị từ Pedagogy cho mục đích thử nghiệm kiểm soát).
   - `immersion_lookup_enabled`: Bật tính năng tra cứu từ vựng không kèm bản dịch tiếng Việt trực tiếp (tra giải thích hình ảnh hoặc JP-JP).
   - `personal_collections_enabled`: Bật tính năng tạo playlist / bộ sưu tập cá nhân.
   - `content_reports_enabled`: Bật tính năng báo cáo nội dung không phù hợp hoặc lỗi kịch bản.
   - `playback_tracking_enabled`: Bật cơ chế heartbeat và ghi nhận active watch seconds.

3. **Thực thi phía máy chủ (Server-side Enforcement):**
   - Nếu một capability bị tắt trong cấu hình máy chủ, các endpoint tương ứng sẽ từ chối xử lý (`403 Forbidden`, mã `CAPABILITY_DISABLED`), không phụ thuộc đơn thuần vào việc ẩn UI trên client. Khi playback tracking tắt, start/checkpoint mới không được cấp credit; end/reconcile vẫn cho phép đóng lease với crediting_disabled. FR-FLG-003 giữ cấu hình môi trường/allowlist, không mở rộng PATCH /staff/flags.

---

## 3. Ma trận Hợp đồng API theo từng Đợt (Contract Matrix)

### Đợt A: Content Versioning, Scenes & Series (PR1, PR1b)

| Method | Path | Quyền hạn | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/catalog/{id}/content` | Learner / All | Lấy current published version kèm scene metadata; không full transcript JP | 200, 404 |
| `GET` | `/staff/catalog/{id}/content` | Teacher / Admin | Lấy phiên bản nháp hiện hành kèm scenes | 200, 404 |
| `PUT` | `/staff/catalog/{id}/content` | Teacher / Admin | Cập nhật scenes kịch bản nháp (CAS `version_revision`) | 200, 400, 404, 409 |
| `POST` | `/staff/catalog/{id}/return-to-draft` | Teacher / Admin | Rã đông item từ `level_qa` về `draft` | 200, 400, 404 |
| `GET` | `/series` | Learner / All | Danh sách series và các tập đã xuất bản | 200 |
| `GET` | `/series/{id}` | Learner / All | Chi tiết series kèm thứ tự tập | 200, 404 |
| `POST` | `/staff/series` | Teacher / Admin | Tạo series mới | 201, 400 |
| `PATCH` | `/staff/series/{id}` | Teacher / Admin | Cập nhật metadata series | 200, 400, 404 |

### Đợt B: Contract sửa R0 (đã kiểm chứng local; rollout pending)

| Method | Path | Contract |
|---|---|---|
| POST | /playbacks | Idempotency-Key, pinned content version, device instance, takeover |
| GET | /playbacks/{id} | Owner reconcile |
| PUT | /playbacks/{id}/checkpoints/{seq} | Cumulative active ms, epoch, position, receipt |
| POST | /playbacks/{id}/end | Atomic final checkpoint + close, retry ACK |
| GET | /me/resume và /me/resume/{catalog_item_id} | Published/current-version eligibility và deletion cutoff |
| GET/DELETE | /me/watch-history | Cursor; DELETE 202 + deletion ID |
| GET | /me/history-deletions/{id} | Owner job status |
| GET/PUT | /me/learning-preferences | Current/pending, revision, effective_at, topics |
| GET | /me/activity | Inclusive tối đa 90 ngày, policy-version buckets, active-only |
| GET | /me/recommendations | Published/current CI, history sau cutoff |

### Đợt C: Personal Library, Bookmarks, Reports & Search (PR3, PR4, PR5)

| Method | Path | Quyền hạn | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/bookmarks` | Learner | Danh sách từ vựng/ngữ cảnh đã bookmark | 200 |
| `POST` | `/bookmarks` | Learner | Thêm bookmark ngữ cảnh từ clip/cảnh | 201, 400, 404 |
| `DELETE` | `/bookmarks/{id}` | Learner | Xóa bookmark khỏi sổ tay | 204, 404 |
| `GET` | `/collections` | Learner | Danh sách bộ sưu tập cá nhân | 200 |
| `POST` | `/collections` | Learner | Tạo bộ sưu tập mới | 201, 400 |
| `GET` | `/collections/{id}` | Learner | Chi tiết bộ sưu tập kèm danh sách clip | 200, 404 |
| `POST` | `/collections/{id}/items` | Learner | Thêm clip vào bộ sưu tập | 200, 400, 404 |
| `DELETE` | `/collections/{id}/items/{item_id}` | Learner | Xóa clip khỏi bộ sưu tập | 204, 404 |
| `DELETE` | `/collections/{id}` | Learner | Xóa toàn bộ bộ sưu tập | 204, 404 |
| `GET` | `/reports/study-time` | Learner | Báo cáo thống kê thời gian học thực tế | 200, 400 |
| `POST` | `/reports/content` | Learner | Gửi báo cáo phản hồi về nội dung clip | 201, 400, 404 |
| `GET` | `/staff/reports/content` | Staff / Admin | Xem danh sách báo cáo nội dung | 200 |

---

## 4. Kế hoạch Hiện thực & Tuân thủ Clean Architecture

Mọi mã nguồn bổ sung theo ADR-007 phải tuân thủ nghiêm ngặt quy tắc của ADR-006:
1. **Domain Layer:** Chứa entities thuần túy (`ContentVersion`, `Scene`, `Series`, `Bookmark`, `Collection`, `PlaybackLease`, `StudyGoal`), không phụ thuộc vào SQLAlchemy hay Pydantic.
2. **Application Layer:** Các commands và queries được điều phối qua handlers độc lập và Unit of Work port.
3. **Adapters Layer:** Các bảng mới được ánh xạ qua SQLAlchemy models trong `persistence/models.py`; migrations viết tay qua Alembic (`migrations/versions/0003_...py`) tuân thủ ADR-004.
4. **Entrypoints Layer:** Router chỉ parse request, gọi handler qua UoW, và định dạng response DTO.
