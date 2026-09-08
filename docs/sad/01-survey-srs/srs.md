# SRS — Nền tảng JPLearn (v1)

Mã yêu cầu ổn định. Story sprint phải trích mã.  
Phạm vi: **nền tảng**. Yêu cầu học đầy đủ đánh dấu `Deferred-P5`.

**Cổng SAD-1:** CPO, Pedagogy, CTO ký [gates.md](../../company/gates.md).  
**Wording 2026-08-31 (ADR-003):** FR-ID-003 (logout mọi thiết bị) và FR-CMS-002 (chỉ Admin publish) — `INTENTIONAL_REQUIREMENT_CHANGE`, đã ký SAD-3.

## 1. Yêu cầu chức năng — nền tảng

### Identity

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-ID-001 | Người dùng đăng ký và đăng nhập bằng email + mật khẩu | P0 |
| FR-ID-002 | Một identity dùng chung web, iOS, iPad, Android | P0 |
| FR-ID-003 | Phiên đăng nhập hết hạn an toàn; đăng xuất vô hiệu hoá **mọi** access_token của user (mọi thiết bị). v1: `tokenVersion` trên User, không phiên per-device | P0 |
| FR-ID-004 | Tài khoản có `role`: `learner`, `teacher`, `admin` | P0 |

### Catalog

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-CAT-001 | Hệ thống lưu item catalog với `ci_level`, `duration_seconds`, `media_type`, `topic_id`, `visual_support`, `status` | P0 |
| FR-CAT-002 | Client học viên chỉ thấy item `status = published` | P0 |
| FR-CAT-003 | Lọc / nhóm catalog theo `ci_level` | P0 |
| FR-CAT-004 | Item học viên **không** kèm bản dịch L1 (`has_l1_translation = false`) | P0 |
| FR-CAT-005 | Giáo viên tạo/sửa item ở CMS (draft) | P0 |

### Session skeleton

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-SES-001 | Học viên bắt đầu phiên trên một thiết bị; hệ thống ghi `started_at`, `device_class` (`web` \| `phone` \| `ipad`) | P0 |
| FR-SES-002 | Học viên kết thúc phiên; hệ thống ghi `ended_at` và `duration_seconds` | P0 |
| FR-SES-003 | Phiên không bắt buộc phát media thành công mới tồn tại (skeleton cho phép “catalog only”) | P0 |

### Progress

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-PRG-001 | Hệ thống cộng dồn phút phiên vào `minutes_comprehensible` của học viên (v1: mọi phiên hợp lệ; Phase 5 có thể lọc theo probe) | P0 |
| FR-PRG-002 | Hệ thống lưu `current_ci_level` (mặc định 0) | P0 |
| FR-PRG-003 | Progress **không** gồm điểm từ vựng, điểm ngữ pháp, hay % giáo trình | P0 |
| FR-PRG-004 | Cùng user, progress đồng bộ trên 3 bề mặt | P0 |

### CMS và media

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-CMS-001 | Giáo viên upload media thô gắn với item | P0 |
| FR-CMS-002 | Sau Level QA, **chỉ admin** chuyển `status` sang `published` (Teacher dừng ở `level_qa`; khớp UC-A01) | P0 |
| FR-CMS-003 | Item published có URL media phát được trên web và mobile | P0 |
| FR-CMS-004 | Client lấy playback URL qua API, không hardcode CDN | P0 |

### Feature flags và sự kiện

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-FLG-001 | Cờ `speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled` mặc định `false` | P0 |
| FR-FLG-002 | Client không vẽ UI cho kênh đã tắt | P0 |
| FR-FLG-003 | Technical capabilities tách bốn cờ sư phạm, mặc định tắt, server kiểm cấu hình/allowlist và trả 403 CAPABILITY_DISABLED; khi tracking tắt vẫn cho end/reconcile không cấp credit | P1 |
| FR-EVT-001 | Ghi `session_started`, `session_ended` | P0 |
| FR-EVT-002 | Ghi `minutes_comprehensible` (số, theo user, cập nhật khi phiên kết thúc) | P0 |
| FR-EVT-003 | Ghi `level_exposed` khi user mở item một `ci_level` | P0 |

### Vòng học CI mở rộng & Thói quen (Phase 5 — Đợt A–C)

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-SCN-001 | Hệ thống quản lý scene breakdown và mốc thời gian (start/end timestamp, title, JP transcript) theo từng content version của video CI; full transcript chỉ staff, learner search chỉ nhận excerpt được duyệt riêng | P1 |
| FR-SER-001 | Hệ thống cấu trúc item theo Series & Episodes với thứ tự tự nhiên phục vụ binge CI | P1 |
| FR-RSM-001 | Hệ thống lưu vị trí phát (playback position) và cho phép tiếp tục phát (resume) liền mạch đa thiết bị | P1 |
| FR-WAT-001 | Hệ thống hạch toán kép: phân biệt `active_watch_seconds` (thời gian phát thực qua cumulative milliseconds, nhịp 15s, lease 45s; không nhân playback rate) và `minutes_comprehensible` (phút phiên legacy) | P1 |
| FR-HIS-001 | Hệ thống ghi nhận và cung cấp lịch sử xem (watch history) theo học viên, hỗ trợ dọn dẹp hoặc ẩn lịch sử | P1 |
| FR-GOL-001 | Học viên thiết lập daily goal 0–120 phút (0=tắt), chỉ dùng active_watch_seconds; goal/timezone đổi tại nửa đêm kế tiếp timezone đang áp dụng, topics áp dụng ngay; activity trả current/longest streak theo policy-version bucket | P1 |
| FR-REC-001 | Hệ thống gợi ý clip tiếp theo (Smart Stream) dựa trên trình độ CI (`current_ci_level`), chủ đề đang học và lịch sử xem | P1 |
| FR-BMK-001 | Học viên bookmark từ vựng và câu ngữ cảnh trong clip CI vào sổ tay cá nhân (không biến thành flashcard/SRS trắc nghiệm) | P1 |
| FR-COL-001 | Học viên tạo và quản lý bộ sưu tập/playlist cá nhân (lưu clip yêu thích, chia theo ngữ cảnh immersion) | P1 |
| FR-RPT-001 | Hệ thống tổng hợp báo cáo và thống kê thời gian học thực tế theo ngày, tuần, tháng cho học viên | P1 |

## 2. Yêu cầu phủ định (cấm v1)

| ID | Yêu cầu |
|---|---|
| FR-NEG-001 | Hệ thống không cung cấp flashcard / SRS từ vựng như kênh chính |
| FR-NEG-002 | Hệ thống không cung cấp bài ngữ pháp, quiz điền hạt, hay giải thích quy tắc |
| FR-NEG-003 | Hệ thống không dùng cặp dịch L1–JP làm cách hiểu nghĩa mặc định trên client học viên |
| FR-NEG-004 | Hệ thống không lưu `vocabulary_score` hay `grammar_lesson_id` trên schema progress v1 |

## 3. Yêu cầu phi chức năng

| ID | Yêu cầu |
|---|---|
| NFR-XPLAT-001 | Web, iPhone, iPad, Android dùng cùng API và cùng identity |
| NFR-XPLAT-002 | Layout iPad không phải phóng to layout phone; có navigation/spacing riêng |
| NFR-PERF-001 | Từ lúc CMS `published` đến lúc 3 client thấy item: ≤ 5 phút (thí điểm được ≤ 15 phút nếu ghi trong runbook) |
| NFR-PERF-002 | Trước cổng nền tảng: playback video thích ứng (HLS) trên web và iPad; Q1 thí điểm được MP4 nếu ADR cho phép, phải nâng HLS trước P5 |
| NFR-SEC-001 | Mật khẩu không lưu plaintext; token không log; HTTPS |
| NFR-SEC-002 | Phân quyền: `learner` không gọi API CMS mutate |
| NFR-SEC-003 | Đăng nhập bị giới hạn 10 lần / 60 giây theo IP+email, trả 429 | P0 |
| NFR-PRIV-001 | PII tối thiểu: email, id; không bán dữ liệu Q1 |
| NFR-A11Y-001 | Shell web: contrast đạt WCAG AA cho text chrome; media có control pause/play bằng bàn phím |
| NFR-OBS-001 | API có request id; lỗi 5xx alertable trên staging |
| NFR-LAT-001 | Độ trễ API: P95 endpoint heartbeat ≤ 100ms dưới tải đồng thời tiêu chuẩn |
| NFR-RET-001 | Lưu trữ dữ liệu: Sự kiện playback raw lưu giữ 90 ngày; tiến độ tích lũy và báo cáo tổng hợp lưu giữ vĩnh viễn |
| NFR-CONCUR-001 | Đồng thời: Heartbeat và session takeover xử lý an toàn qua lease/epoch CAS, không gây race condition hoặc double-counting thời gian |

## 4. Deferred — Phase 5 (có ID, không thiết kế UI v1)

| ID | Yêu cầu | Ghi chú |
|---|---|---|
| FR-LRN-001 | Học viên phát item CI (xem/nghe) trong phiên | Cần SAD vòng 2 (đã triển khai Mốc A) |
| FR-LRN-002 | Probe hiểu không lời: chọn đúng hình | Schema `ComprehensionProbe` chừa chỗ |
| FR-LRN-003 | Silent period: không ép nói cho đến khi Pedagogy bật flag | Bám FR-FLG-001 |
| FR-LRN-004 | Recast, không bảng ngữ pháp | Chỉ nguyên tắc |

## 5. Tiêu chí chấp nhận SRS

- Mỗi FR nền tảng có ≥1 use case trong SAD-2.
- Mỗi NFR có hướng kiểm trong ma trận truy vết SAD-3.
- Không có yêu cầu “làm app học tiếng Nhật” không mã.

> **R0 — Engineering decision, 2026-09-07; local verification 2026-09-08:** Hợp đồng sửa đã có kiểm chứng local. Đây không phải chữ ký BA/CTO/Pedagogy/Ops hoặc cho phép production.

NFR-RET-001 hiện giữ nguyên raw playback 90 ngày và aggregate vĩnh viễn. Đề xuất retention khác chưa được duyệt; không chạy destructive retention theo mốc đề xuất. Xóa history theo yêu cầu người dùng là use case riêng.

## CMS clarification — ADR-008 (integrated 2026-09-08)

FR-CAT-005 includes staff list/detail and editing draft metadata. FR-CMS-002 requires a
persisted approve/reject decision for the current submission, with internal rejection notes.
Only Admin publishes; Teacher/Admin may act as LevelQA under existing roles. Metadata/media
changes require draft and a fresh submission/review before republish. See ADR-008 for acceptance.

Integration retains mandatory revision-based PATCH concurrency control and merges both migration histories at `0019_merge_cms_reviews`.
