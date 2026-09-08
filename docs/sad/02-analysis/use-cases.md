# Use cases — nền tảng v1

Actors: **Learner**, **Teacher**, **Admin**, **LevelQA** (có thể trùng Teacher).

Sơ đồ Mermaid: [diagrams.md](diagrams.md) — mục 1 actor → UC; mục **1b** «include» / «extend». Kịch bản dưới đây là nguồn SAD-2; không mâu thuẫn [SRS](../01-survey-srs/srs.md), [processes.md](processes.md), sequence [SAD-3](../03-design/diagrams.md).

Không có UC flashcard, bài ngữ pháp, hay kênh dịch L1 trên client học viên (`FR-NEG-001`…`003`).

## Sơ đồ (nền tảng & Vòng học CI mở rộng)

```
Learner: UC-L01 Login, UC-L02 Browse catalog, UC-L03 Start session,
         UC-L04 End session, UC-L05 View progress, UC-L06 Sync devices,
         UC-L10 Complete session with clip,
         UC-L14 Scene navigation & subtitles, UC-L15 Save bookmarks & context,
         UC-L16 Resume playback, UC-L17 Active watch heartbeat,
         UC-L18 Daily goal & streak, UC-L19 Watch history,
         UC-L20 Smart stream recommendations, UC-L21 Personal collections,
         UC-L23 Study time reports, UC-L24 Single playback lease takeover
Teacher: UC-T01 Login staff, UC-T02 Create item, UC-T03 Upload media,
         UC-T04 Submit level QA, UC-T05 Edit draft metadata,
         UC-T06 Manage scenes & subtitles, UC-T07 Manage series & episodes,
         UC-T09 Freeze content version on QA submit
LevelQA: UC-Q01 Review CI rubric, UC-Q02 Approve or reject
Admin:   UC-A01 Publish, UC-A02 Manage flags, UC-A03 Manage roles
```

## Spec — Learner

### UC-L01 Đăng nhập

- **Actor:** Learner
- **FR / NFR:** FR-ID-001, FR-ID-002, FR-ID-003
- **Trigger:** Actor mở web hoặc Expo, cần vào shell học viên (`S-LOGIN`).
- **Tiền điều kiện:** Client gọi cùng API identity (web / phone / iPad). Tài khoản đã có, hoặc Actor đăng ký mới trên cùng form (FR-ID-001).
- **Hậu điều kiện (thành công):** Có `access_token` trên thiết bị hiện tại; Actor vào shell học viên; identity dùng được trên bề mặt khác (FR-ID-002). Đăng xuất vô hiệu hoá mọi `access_token` của user trên mọi thiết bị (FR-ID-003, `tokenVersion`).
- **Kịch bản chính:**
  1. Actor mở `S-LOGIN`.
  2. Actor nhập email + mật khẩu. Nếu chưa có tài khoản: Actor đăng ký → Hệ thống tạo user `role=learner`, trả session.
  3. Hệ thống tìm user, so khớp mật khẩu (không lưu plaintext).
  4. Hệ thống cấp `access_token` + user (kèm `roles`).
  5. Hệ thống đưa Actor vào shell học viên (không vào CMS).
  6. Actor chọn đăng xuất (từ thiết bị đang dùng).
  7. Hệ thống tăng `tokenVersion` — mọi token cũ của user (mọi thiết bị) 401; Actor về `S-LOGIN`.
- **Kịch bản phụ (extend):**
  - 3a. Sai mật khẩu — Hệ thống trả 401, không vào shell. «extend» UC-L01.
  - 5a. Hết hạn token khi gọi API được bảo vệ — Hệ thống yêu cầu login lại. «extend» UC-L01.
- **Ngoại lệ:** Token không ghi log. Không cấp session nếu xác thực thất bại.
- **Quan hệ:** Không include UC khác. Bị include bởi UC-L02, L03, L04, L05, L06. Extend: Sai mật khẩu; Hết hạn token.

Chặt UML thì login là precondition; v1 mô hình include vì mọi UC học viên bắt buộc đi qua L01.

### UC-L02 Xem catalog

- **Actor:** Learner
- **FR / NFR:** FR-CAT-002, FR-CAT-003, FR-CAT-004
- **Trigger:** Sau login, Actor mở `S-HOME`.
- **Tiền điều kiện:** UC-L01 đã thực hiện («include»). Item `published` do UC-A01 — **điều kiện tiên quyết dữ liệu**, không phải include. Catalog trống vẫn hợp lệ Q1.
- **Hậu điều kiện (thành công):** Actor thấy danh sách `status=published`, nhóm/lọc theo `ci_level`, không có text dịch L1. Draft / `level_qa` không lộ.
- **Kịch bản chính:**
  1. Actor mở catalog.
  2. Hệ thống nhận GET `/catalog` (Bearer).
  3. Hệ thống trả item `published`; client nhóm theo `ci_level` (lọc query nếu có).
  4. Hệ thống không kèm field dịch L1 (`has_l1_translation=false` trên published).
  5. Client không vẽ kênh đã tắt flag (Nói / Thẻ / Ngữ pháp) — FR-FLG-002.
- **Kịch bản phụ (extend):**
  - 3a. Catalog trống — Hệ thống / client hiện empty state (vẫn hợp lệ Q1). «extend» UC-L02.
- **Ngoại lệ:** Item không `published` không có trong list. Playback URL (nếu có) do API cấp, không hardcode CDN (FR-CMS-003 trên published).
- **Quan hệ:** «include» UC-L01. Bị include bởi UC-L06. Extend: Catalog trống. Không include UC-A01.

### UC-L03 Bắt đầu phiên

- **Actor:** Learner
- **FR / NFR:** FR-SES-001, FR-EVT-001
- **Trigger:** Actor chọn bắt đầu phiên trên `S-SESSION`.
- **Tiền điều kiện:** UC-L01 đã thực hiện («include»). Không bắt buộc đã play media (FR-SES-003 — skeleton).
- **Hậu điều kiện (thành công):** Có `LearningSession` với `started_at`, `device_class` (`web` \| `phone` \| `ipad`); event `session_started`.
- **Kịch bản chính:**
  1. Actor chọn “bắt đầu phiên”.
  2. Client gửi `device_class` của bề mặt đang dùng.
  3. Hệ thống tạo session, ghi `started_at`.
  4. Hệ thống ghi event `session_started`.
  5. Actor ở shell — hệ thống không bắt play video.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Phiên tồn tại dù catalog trống hoặc chưa có media. `level_exposed`: xem UC-L13 (deferred); OpenAPI có thể ghi kèm khi start với `current_ci_level`.
- **Quan hệ:** «include» UC-L01. Không include L02/L04.

### UC-L04 Kết thúc phiên

- **Actor:** Learner
- **FR / NFR:** FR-SES-002, FR-PRG-001, FR-EVT-001, FR-EVT-002
- **Trigger:** Actor chọn kết thúc phiên trên `S-SESSION`.
- **Tiền điều kiện:** UC-L01 đã thực hiện («include»). Có session `started` của Actor trên thiết bị này.
- **Hậu điều kiện (thành công):** `ended_at` và `duration_seconds` được ghi. Event `session_ended`. Nếu duration hợp lệ ≤ 4 giờ: cộng floor phút vào `minutes_comprehensible` + event phút. Nếu zombie > 4 giờ: cộng 0 phút (vẫn ended).
- **Kịch bản chính:**
  1. Actor chọn kết thúc phiên.
  2. Client gọi kết thúc session (id phiên hiện tại).
  3. Hệ thống ghi `ended_at`, tính `duration_seconds`.
  4. Hệ thống xác nhận duration hợp lệ (`ended_at > started_at`, ≤ 4 giờ).
  5. Hệ thống cộng floor phút vào `minutes_comprehensible`, ghi event `session_ended` và `minutes_comprehensible`.
- **Kịch bản phụ (extend):**
  - 2a. Mất mạng lúc end — Client retry; không bịa `duration_seconds`. «extend» UC-L04. (*processes.md*)
  - 4a. Duration > 4 giờ (phiên zombie) — Hệ thống ended phiên, cộng **0** phút. «extend» UC-L04. (*processes.md*, sequence SAD-3, domain invariant)
- **Ngoại lệ:** Retry vẫn fail → phiên giữ `started`, không cộng phút, không silent-drop, không bịa duration. Không cộng phút cho phiên chưa end.
- **Quan hệ:** «include» UC-L01. Extend: Retry mất mạng; Phiên zombie >4h cộng 0 phút.

### UC-L05 Xem tiến độ

- **Actor:** Learner
- **FR / NFR:** FR-PRG-001, FR-PRG-002, FR-PRG-003
- **Trigger:** Actor mở `S-PROGRESS`.
- **Tiền điều kiện:** UC-L01 đã thực hiện («include»).
- **Hậu điều kiện (thành công):** Actor thấy `minutes_comprehensible` và `current_ci_level` (mặc định 0). Không điểm từ vựng, điểm ngữ pháp, hay % giáo trình.
- **Kịch bản chính:**
  1. Actor mở tiến độ.
  2. Hệ thống trả progress của user đang đăng nhập.
  3. Client hiển thị phút CI + cấp hiện tại.
  4. Hệ thống / schema không trả field điểm hay % bài (`additionalProperties: false`).
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** User mới: phút = 0, `current_ci_level` = 0 — vẫn màn hợp lệ.
- **Quan hệ:** «include» UC-L01. Bị include bởi UC-L06.

### UC-L06 Đồng bộ thiết bị

- **Actor:** Learner
- **FR / NFR:** FR-ID-002, FR-PRG-004
- **Trigger:** Cùng user mở client thứ hai (web / phone / iPad).
- **Tiền điều kiện:** Tài khoản đã tồn tại. UC-L01 trên thiết bị mới («include»).
- **Hậu điều kiện (thành công):** Cùng catalog `published` và cùng progress (`minutes_comprehensible`, `current_ci_level`) trên thiết bị khác.
- **Kịch bản chính:**
  1. Actor đăng nhập cùng email trên thiết bị B («include» UC-L01).
  2. Actor mở catalog trên B — Hệ thống trả cùng tập item `published` như thiết bị A («include» UC-L02).
  3. Actor mở tiến độ trên B — Hệ thống trả cùng progress («include» UC-L05).
- **Kịch bản phụ (extend):** không (các extend của L01/L02 áp dụng khi thực hiện include).
- **Ngoại lệ:** Layout iPad không phải phóng to phone (NFR-XPLAT-002 — không đổi API). Expo native máy thật: theo dõi #30; kịch bản phân tích không đổi.
- **Quan hệ:** «include» UC-L01, UC-L02, UC-L05.

## Spec — Teacher / QA / Admin

### UC-T01 Đăng nhập nhân sự

- **Actor:** Teacher hoặc Admin (LevelQA dùng cùng login staff).
- **FR / NFR:** FR-ID-001, FR-ID-004, NFR-SEC-002
- **Trigger:** Actor mở `S-LOGIN`, cần vào `/staff`.
- **Tiền điều kiện:** User có `role` `teacher` và/hoặc `admin`.
- **Hậu điều kiện (thành công):** Session staff; client route vào CMS theo role. Learner không gọi được API CMS mutate (403).
- **Kịch bản chính:**
  1. Actor mở `S-LOGIN` (cùng form học viên).
  2. Actor nhập email + mật khẩu staff.
  3. Hệ thống xác thực, trả token + `roles`.
  4. Hệ thống đưa Actor vào `/staff` (không nhầm shell học viên như kênh chính).
- **Kịch bản phụ (extend):** không (sai mật khẩu / hết hạn token là hành vi identity như L01; không cấp UC mới).
- **Ngoại lệ:** User chỉ `learner` gọi POST `/staff/*` → 403 (NFR-SEC-002). Không có role `level_qa` riêng — LevelQA là Teacher hoặc Pedagogy kiêm role hiện có.
- **Quan hệ:** Không include UC khác. Bị include bởi T02, T03, T04, Q01, Q02, A01, A02, A03.

### UC-T02 Tạo item draft

- **Actor:** Teacher
- **FR / NFR:** FR-CAT-001, FR-CAT-005
- **Trigger:** Actor tạo clip mới trên CMS.
- **Tiền điều kiện:** UC-T01 đã thực hiện («include»). Topic tồn tại (taxonomy).
- **Hậu điều kiện (thành công):** `CatalogItem` `status=draft`; metadata `ci_level`, `duration_seconds`, `media_type`, `topic_id`, `visual_support`; `has_l1_translation=false`; `spoken_language=ja`.
- **Kịch bản chính:**
  1. Actor mở form tạo item.
  2. Actor nhập metadata theo taxonomy (không title kiểu “Bài 12: thì quá khứ” trên learner card — title_internal chỉ CMS).
  3. Hệ thống tạo item `draft`, `has_l1_translation=false` (không checkbox “thêm bản dịch” v1).
  4. Hệ thống không expose item này trên GET `/catalog` học viên.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Learner → 403. Không nhảy `draft` → `published` từ màn này. Không include UC-T03 (upload là bước BPMN riêng, mục 5). Q1: `media_type=audio` giữ trong schema, UI vô hiệu hoá lựa chọn vì upload chỉ nhận MP4 (FR-CMS-001). BA quyết định 2026-09-06.
- **Quan hệ:** «include» UC-T01.

### UC-T03 Upload media

- **Actor:** Teacher
- **FR / NFR:** FR-CMS-001
- **Trigger:** Actor gắn file media vào item draft.
- **Tiền điều kiện:** UC-T01 («include»). Item tồn tại, thường `draft` (nhà máy mục 5).
- **Hậu điều kiện (thành công):** `MediaAsset` gắn item; file trên store; chưa `published` vì vậy chưa lộ learner.
- **Kịch bản chính:**
  1. Actor chọn item draft.
  2. Actor upload file.
  3. Hệ thống lưu asset, gắn `catalog_item_id`.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Learner → 403. Thiếu file: không đủ điều kiện publish sau này (A01), không tự published.
- **Quan hệ:** «include» UC-T01. Không include T02/T04.

### UC-T04 Gửi Level QA

- **Actor:** Teacher
- **FR / NFR:** FR-CMS-002
- **Trigger:** Actor nộp item để Level QA.
- **Tiền điều kiện:** UC-T01 («include»). Item `draft` (đã có metadata; media theo SOP).
- **Hậu điều kiện (thành công):** `status=level_qa`. Chưa `published`.
- **Kịch bản chính:**
  1. Actor chọn nộp Level QA.
  2. Hệ thống đổi `status=level_qa`.
  3. Hệ thống vẫn ẩn item khỏi catalog học viên.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Cấm `draft` → `published` bỏ QA (`processes.md`, SOP). Không include Q01/A01 — tuần tự nhà máy, không phải include.
- **Quan hệ:** «include» UC-T01.

### UC-Q01 Review CI rubric

- **Actor:** LevelQA (có thể trùng Teacher)
- **FR / NFR:** Không FR riêng. Rubric Pedagogy ([ci-rubric-clip.md](../../pedagogy/ci-rubric-clip.md)); chặn/cho phép bước FR-CMS-002 (cùng T04/A01). Không cấp FR mới.
- **Trigger:** Item `status=level_qa`.
- **Tiền điều kiện:** UC-T01 («include»). Item đã nộp QA (UC-T04 — BPMN, không include).
- **Hậu điều kiện (thành công):** Rubric đã được áp (Pass cả 5 mục, hoặc chuyển sang reject — extend). Lý do nội bộ không lộ learner.
- **Kịch bản chính:**
  1. Actor mở item `level_qa`.
  2. Actor đối chiếu clip với rubric: visual first; speech ít/lặp/gắn hình; `ci_level` 0–1 + `visual_support`; không kênh L1; metadata SOP.
  3. Actor ghi nhận Pass nội bộ (không hiện learner).
  4. Hệ thống giữ item sẵn sàng cho UC-Q02 Pass / UC-A01 — không tự `published`.
- **Kịch bản phụ (extend):**
  - 3a. Một mục rubric sai — **Rubric reject về draft** (cùng Q02). «extend» UC-Q01.
- **Ngoại lệ:** Không publish từ màn review. Không hiện lý do QA trên GET `/catalog`.
- **Quan hệ:** «include» UC-T01. Extend: Rubric reject về draft. Không include A01.

### UC-Q02 Approve hoặc reject

- **Actor:** LevelQA
- **FR / NFR:** Không FR riêng (như Q01). Approve = sẵn sàng publish; reject = về draft + lý do nội bộ.
- **Trigger:** Kết thúc review UC-Q01 trên item `level_qa`.
- **Tiền điều kiện:** UC-T01 («include»). Rubric đã xem (Q01 — BPMN, không include).

#### Pass (kịch bản chính)

- **Hậu điều kiện (thành công):** Item vẫn không `published` từ Q02; sẵn sàng để Admin chạy UC-A01. Không nhảy trạng thái bỏ QA.
- **Kịch bản chính:**
  1. Actor chọn Approve / Pass.
  2. Hệ thống ghi quyết định nội bộ (pass).
  3. Hệ thống giữ workflow: Teacher dừng tại `level_qa`; chỉ Admin publish (v1).
  4. Item chưa có trên GET `/catalog` học viên.
- **Kịch bản phụ (extend):** xem Reject.
- **Ngoại lệ:** Người kiêm Teacher+Admin vẫn phải đi hết trạng thái, không `draft` → `published` trừ ngoại lệ CEO có thời hạn (`processes.md`).

#### Reject (kịch bản phụ — extend)

- **Hậu điều kiện:** `status=draft`; lý do nội bộ (CMS comment / `qa_notes`) không expose learner.
- **Kịch bản phụ (extend):**
  - 1a. Actor chọn Reject (fail một mục rubric).
  - 2a. Hệ thống đặt `status=draft`.
  - 3a. Hệ thống lưu lý do nội bộ; không đưa vào `CatalogItemPublic`.
  - «extend» UC-Q02 (và UC-Q01). Teacher sửa / quay lại rồi T04 lại — BPMN mục 5, không include.
- **Ngoại lệ:** Không có UC/FR mới cho “reject API”; hành vi bám sequence SAD-3 (Reject → về draft).
- **Quan hệ:** «include» UC-T01. Extend: Rubric reject về draft.

### UC-A01 Publish

- **Actor:** Admin
- **FR / NFR:** FR-CMS-002, FR-CMS-003, FR-CMS-004, NFR-PERF-001
- **Trigger:** Admin publish item đã QA pass.
- **Tiền điều kiện:** UC-T01 («include»). Item `level_qa` (sau Q02 Pass); có nguồn playback. Policy v1: chỉ Admin publish.
- **Hậu điều kiện (thành công):** `status=published`, `has_l1_translation=false`. Client lấy playback URL qua API (không hardcode CDN). Ba client thấy item ≤ 5 phút (thí điểm ≤ 15 nếu runbook).
- **Kịch bản chính:**
  1. Actor chọn publish.
  2. Hệ thống kiểm `status=level_qa` và có media playback.
  3. Hệ thống đặt `published` + `has_l1_translation=false`.
  4. Learner GET `/catalog` thấy item; URL do API cấp.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Không `level_qa` hoặc không media → từ chối (không `draft` → `published`). Không phải Admin → 403. Điều kiện dữ liệu cho UC-L02 — **không** vẽ include L02.
- **Quan hệ:** «include» UC-T01.

### UC-A02 Feature flags

- **Actor:** Admin
- **FR / NFR:** FR-FLG-001, FR-FLG-002, FR-FLG-003
- **Trigger:** Admin xem/sửa cờ nền tảng.
- **Tiền điều kiện:** UC-T01 («include»).
- **Hậu điều kiện (thành công):** `speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled` mặc định `false`. Client không vẽ UI kênh đã tắt.
- **Kịch bản chính:**
  1. Actor mở quản lý flags.
  2. Hệ thống trả bốn cờ (mặc định false).
  3. Actor không bật textbook ở v1 trừ quyết định Pedagogy có chủ đích (cổng nền tảng).
  4. Client học viên ẩn Nói / Thẻ / Ngữ pháp khi flag false (`S-FLAGS-GATE`).
  5. Technical capabilities đọc qua GET /capabilities, cấu hình môi trường/allowlist độc lập. Server chặn route bị tắt bằng 403 CAPABILITY_DISABLED; end/reconcile playback vẫn hoạt động nhưng zero credit. Không mở rộng PATCH /staff/flags.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Không phải Admin → 403. Không có UC dương cho flashcard/grammar/dịch L1.
- **Quan hệ:** «include» UC-T01.

### UC-A03 Roles

- **Actor:** Admin
- **FR / NFR:** FR-ID-004
- **Trigger:** Cần gán quyền tài khoản.
- **Tiền điều kiện:** UC-T01 («include»).
- **Hậu điều kiện (thành công):** User có `role` thuộc `learner` / `teacher` / `admin` (một user nhiều role được).
- **Kịch bản chính:**
  1. Actor chọn user.
  2. Actor gán `learner` và/hoặc `teacher` và/hoặc `admin`.
  3. Hệ thống lưu `user_roles`.
  4. Lần login sau, route và phân quyền API theo role (learner cấm CMS mutate).
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Không invent role `level_qa`. Teacher không publish nếu policy chỉ Admin (A01) — đổi role không bỏ bước QA.
- **Quan hệ:** «include» UC-T01.

### UC-T02b Xem danh sách nội dung CMS

- **Actor:** Teacher hoặc Admin
- **FR / NFR:** FR-CAT-005, FR-CMS-001…004, NFR-SEC-002
- **Trigger:** Actor truy cập màn hình `/staff`.
- **Tiền điều kiện:** UC-T01 («include»).
- **Hậu điều kiện (thành công):** Danh sách item nội bộ với phân trang, lọc theo status (`draft`, `level_qa`, `published`, `archived`) và `ci_level`. Không lộ secret/storage_key.
- **Kịch bản chính:**
  1. Actor mở `/staff`.
  2. Hệ thống gọi `GET /staff/catalog` kèm query filter (status, ci_level).
  3. Hệ thống trả danh sách kèm `revision`, `status`, metadata nội bộ và cờ media.
  4. Client hiển thị bảng nội dung kèm hành động tương ứng với vai trò (Teacher: sửa draft, nộp QA; Admin: thêm publish, unpublish).
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** Learner gọi `GET /staff/catalog` → 403 Forbidden.
- **Quan hệ:** «include» UC-T01.

### UC-T05 Chỉnh sửa metadata draft

- **Actor:** Teacher hoặc Admin
- **FR / NFR:** FR-CAT-005
- **Trigger:** Actor chỉnh sửa metadata của item draft tại `/staff/[id]`.
- **Tiền điều kiện:** UC-T01 («include»). Item có `status=draft`.
- **Hậu điều kiện (thành công):** Metadata cập nhật thành công, `revision` tăng lên.
- **Kịch bản chính:**
  1. Actor mở item draft, sửa thông tin trong `catalogWriteFields` (topic, ci_level, duration, media_type, visual_support, title_internal).
  2. Client gửi `PATCH /staff/catalog/{id}` kèm body và `revision` hiện tại.
  3. Hệ thống kiểm tra trong transaction: nếu item là `draft` và `revision` khớp, cập nhật metadata và tăng `revision`.
  4. Hệ thống trả về item đã cập nhật.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:**
  - Item không ở trạng thái `draft` → 400 Bad Request.
  - `revision` không khớp (xung đột đồng thời do người khác vừa sửa) → 409 Conflict; client yêu cầu reload dữ liệu mới.
- **Quan hệ:** «include» UC-T01.

### UC-T06 Quản lý scenes & subtitles cho clip CI

- **Actor:** Teacher hoặc Admin
- **FR / NFR:** FR-SCN-001, FR-CAT-005
- **Trigger:** Actor chỉnh sửa kịch bản phân đoạn cảnh (scene breakdown) và transcript tiếng Nhật của clip CI tại `/staff/[id]/content`.
- **Tiền điều kiện:** UC-T01 («include»). Item ở trạng thái `draft`.
- **Hậu điều kiện (thành công):** Tạo hoặc cập nhật phiên bản nội dung nháp (`ContentVersion`) với danh sách các phân đoạn cảnh (`Scene`) có timestamp bắt đầu/kết thúc, tiêu đề cảnh và lời thoại JP. `revision` của content version tăng lên.
- **Kịch bản chính:**
  1. Actor mở trang biên soạn phân đoạn cho clip draft.
  2. Actor nhập danh sách cảnh: `scene_index`, `start_time_seconds`, `end_time_seconds`, `title_jp`, `transcript_jp`.
  3. Client gửi `PUT /staff/catalog/{id}/content` kèm body danh sách scenes và `version_revision` hiện tại.
  4. Hệ thống kiểm tra: item phải là `draft`, `start_time < end_time`, các cảnh không chồng lấn vô lý và nằm trong thời lượng clip, `version_revision` khớp với bản hiện hành.
  5. Hệ thống lưu phiên bản nháp và các cảnh liên kết trong một transaction, cập nhật `updated_at`.
  6. Hệ thống trả về content version mới cùng danh sách scenes.
- **Kịch bản phụ (extend):**
  - 4a. Xung đột đồng thời (`version_revision` không khớp): Hệ thống trả 409 Conflict; client thông báo nội dung đã được người khác chỉnh sửa và tải lại bản mới nhất.
- **Ngoại lệ:**
  - Item đã `level_qa` hoặc `published` → 400 Bad Request (nội dung đã freeze hoặc xuất bản, không được sửa trực tiếp; phải return to draft hoặc tạo revision mới).
- **Quan hệ:** «include» UC-T01.

### UC-T07 Quản lý series & episodes

- **Actor:** Teacher hoặc Admin
- **FR / NFR:** FR-SER-001, FR-CAT-005
- **Trigger:** Actor tổ chức các clip lẻ vào cùng một Series để học viên binge-watch CI có hệ thống.
- **Tiền điều kiện:** UC-T01 («include»). Series được tạo hoặc cập nhật trong CMS.
- **Hậu điều kiện (thành công):** Series lưu trữ thông tin tiêu đề, mô tả, độ khó CI mục tiêu; các CatalogItem được gán `series_id` và `episode_number` tăng dần.
- **Kịch bản chính:**
  1. Actor tạo mới Series qua `POST /staff/series` hoặc sửa qua `PATCH /staff/series/{id}`.
  2. Actor gán các clip vào Series và xếp thứ tự tập (`episode_number`).
  3. Hệ thống kiểm tra không trùng `episode_number` trong cùng một series.
  4. Hệ thống cập nhật liên kết và trả về thông tin series kèm danh sách tập.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:**
  - Gán tập vào series không tồn tại → 404 Not Found.
- **Quan hệ:** «include» UC-T01.

### UC-T09 Freeze content version khi submit Level QA

- **Actor:** Teacher
- **FR / NFR:** FR-SCN-001, FR-CMS-002
- **Trigger:** Teacher hoàn tất biên soạn video và scenes, gửi sang cho Level QA kiểm định.
- **Tiền điều kiện:** UC-T01 («include»). Item đang ở trạng thái `draft`.
- **Hậu điều kiện (thành công):** Phiên bản nội dung và scenes hiện tại chuyển sang trạng thái `frozen`; `item.status` chuyển thành `level_qa`. Không thể thay đổi nội dung nếu không bị reject trả về draft.
- **Kịch bản chính:**
  1. Teacher nhấn "Gửi kiểm định QA" (`POST /staff/catalog/{id}/submit-qa`).
  2. Hệ thống kiểm tra item có ít nhất 1 content version hợp lệ và media đầy đủ.
  3. Trong cùng transaction, hệ thống khóa version hiện tại (`is_frozen = true`), đổi `item.status = 'level_qa'`.
  4. Hệ thống ghi audit log và trả về item cập nhật.
- **Kịch bản phụ (extend):**
  - 1a. QA từ chối hoặc Admin yêu cầu sửa: Staff gọi `POST /staff/catalog/{id}/return-to-draft` để mở khóa sửa tiếp.
- **Ngoại lệ:**
  - Clip chưa có media hoặc metadata thiếu → 400 Bad Request.
- **Quan hệ:** «include» UC-T01, UC-T04.

## SAD Vòng 2 — Vòng học có chọn clip & Khôi phục phiên (Phase 5 / Mốc A)

### UC-L10 Vòng học hoàn chỉnh: chọn clip, mở phiên, phát CI và kết thúc

- **Actor:** Learner
- **FR / NFR:** FR-LRN-001, FR-SES-001…003, FR-PRG-001/004, NFR-PERF-002, NFR-A11Y-001
- **Trigger:** Actor chọn bài học từ danh mục hoặc mở `/session`.
- **Tiền điều kiện:** UC-L01 đã thực hiện («include»). Item được chọn phải có `status=published` và có media playback hợp lệ.
- **Hậu điều kiện (thành công):** Phiên học được ghi nhận, phát media mượt mà, kết thúc và cộng phút tích lũy chính xác trên server. Tiến độ hiển thị cập nhật.
- **Kịch bản chính:**
  1. Actor duyệt `/catalog`, chọn một clip CI cụ thể.
  2. Client chuyển sang giao diện `/session` gắn với clip đã chọn.
  3. Client sinh `Idempotency-Key`, gửi `POST /sessions` (kèm header `Idempotency-Key` và `device_class=web`).
  4. Hệ thống lưu phiên và ghi nhận idempotency key, trả về `session_id`.
  5. Client lưu tham chiếu phiên vào storage theo tab/user để tồn tại qua reload.
  6. Client khởi tạo trình phát `CiPlayer`: ưu tiên `hls_url` (HLS native hoặc hls.js), tự động fallback về `playback_url` (MP4) khi cần.
  7. Actor xem/nghe nội dung CI (điều khiển được bằng bàn phím theo NFR-A11Y-001). Tuyệt đối không có phụ đề tiếng Việt L1, không câu hỏi ngữ pháp, không flashcard.
  8. Actor bấm "Kết thúc phiên".
  9. Client gửi `POST /sessions/{id}/end`.
  10. Server xác nhận kết thúc, tính thời lượng, cộng floor phút vào `minutes_comprehensible`, trả về tiến độ mới.
  11. Client dọn sạch active session và hiển thị trạng thái hoàn thành.
- **Kịch bản phụ (extend):**
  - 4a. Mất kết nối lúc gửi Start: Client retry có chủ đích với cùng `Idempotency-Key`. Hệ thống trả về phiên đã tạo thay vì sinh phiên trùng.
  - 9a. Mất kết nối lúc gửi End: Client giữ nguyên `session_id`, gửi `GET /sessions/{id}` để tra cứu trạng thái. Nếu phiên đã kết thúc trên server, client cập nhật UI thành công và gọi `GET /progress`. Nếu phiên vẫn `active`, cho phép người dùng thử kết thúc lại.
  - 5a. Người dùng F5 / reload trình duyệt giữa phiên: Client đọc lại session active từ local storage, gọi `GET /sessions/{id}` để khôi phục trạng thái và tiếp tục phiên học.
- **Ngoại lệ:**
  - Clip bị gỡ (unpublish) trong lúc học: Báo lỗi nội dung không còn khả dụng, nhưng vẫn cho phép bấm kết thúc phiên để ghi nhận phút học trước đó.
  - 401 hết hạn token giữa phiên: Yêu cầu đăng nhập lại, chỉ khôi phục phiên nếu đúng tài khoản sở hữu ban đầu.
- **Quan hệ:** «include» UC-L01, UC-L02, UC-L05.

### UC-L14 Xem clip kèm scene navigation & subtitle đồng bộ

- **Actor:** Learner
- **FR / NFR:** FR-SCN-001, FR-LRN-001, NFR-A11Y-001
- **Trigger:** Trong khi xem clip CI tại `/session`, Actor muốn tua nhanh/chậm theo cảnh hoặc đọc kịch bản tiếng Nhật đồng bộ.
- **Tiền điều kiện:** UC-L01, UC-L10 («include»). Clip có `published_content_version` kèm danh sách cảnh.
- **Hậu điều kiện (thành công):** Trình phát hiển thị danh sách cảnh; khi video phát đến đâu, cảnh hiện tại tự động được highlight; Actor bấm vào cảnh nào thì video nhảy đến mốc thời gian đó. Tuyệt đối không có phụ đề tiếng mẹ đẻ L1.
- **Kịch bản chính:**
  1. Client tải nội dung clip qua `GET /catalog/{id}/content`.
  2. Client hiển thị danh sách scene tabs bên dưới hoặc cạnh video player.
  3. Khi phát video, thanh tiến trình cập nhật; cảnh tương ứng với thời điểm hiện tại (`start_time <= current_time < end_time`) được đánh dấu active.
  4. Actor chọn một cảnh khác: player tua đến `scene.start_time_seconds`.
- **Kịch bản phụ (extend):**
  - 1a. Clip không có scene breakdown (clip ngắn hoặc phiên bản cũ): Client ẩn bảng phân cảnh và phát video bình thường.
- **Ngoại lệ:** không.
- **Quan hệ:** «include» UC-L10.

### UC-L15 Lưu từ vựng & câu ngữ cảnh vào sổ tay

- **Actor:** Learner
- **FR / NFR:** FR-BMK-001, FR-NEG-001, FR-NEG-003
- **Trigger:** Actor gặp một từ hoặc câu ấn tượng trong clip CI và bấm "Lưu vào sổ tay cá nhân".
- **Tiền điều kiện:** UC-L01 («include»). Đang xem clip hoặc xem lại phân cảnh.
- **Hậu điều kiện (thành công):** Bản ghi Bookmark được lưu trữ với từ vựng/cụm từ, câu ngữ cảnh tiếng Nhật trích xuất từ transcript của scene, timestamp và liên kết tới clip. Không sinh flashcard hay thuật toán lặp lại ngắt quãng (SRS) trắc nghiệm.
- **Kịch bản chính:**
  1. Actor chọn từ hoặc bấm lưu câu thoại hiện tại.
  2. Client gửi `POST /bookmarks` kèm `catalog_item_id`, `scene_id`, `term`, `context_sentence`, `timestamp_seconds`.
  3. Hệ thống xác thực quyền sở hữu và lưu bản ghi vào sổ tay cá nhân của học viên.
  4. Hệ thống trả về bản ghi đã tạo.
  5. Actor có thể xem danh sách đã lưu qua `GET /bookmarks`.
- **Kịch bản phụ (extend):**
  - 1a. Actor xóa bookmark: Client gửi `DELETE /bookmarks/{id}` → Hệ thống xóa bản ghi khỏi sổ tay.
- **Ngoại lệ:**
  - Lưu trùng lặp cùng một cụm từ trong cùng cảnh: Hệ thống trả về bản ghi hiện có (idempotent), không tạo bản ghi rác.
- **Quan hệ:** «include» UC-L01.

### UC-L16 Tiếp tục xem từ vị trí dừng

- **Actor:** Learner — **FR/NFR:** FR-RSM-001, FR-LRN-001, NFR-XPLAT-001.
- **Tiền điều kiện:** UC-L01; đã có checkpoint.
- **Kịch bản:** GET `/me/resume/{catalog_item_id}` hoặc list `/me/resume`; chỉ trả resume hợp lệ sau deletion cutoff, gắn content version và availability. Start dùng position của đúng version current; không chuyển mốc cũ sang media mới. Không dùng max(position) vì tua lùi là hợp lệ.
- **Hậu điều kiện:** Client biết vị trí có thể tiếp tục; version stale/unpublished không được cấp media cũ. Mặc định 0 khi không có checkpoint hợp lệ. Không tự áp dụng quy tắc 95% chưa được chốt.

### UC-L17 Ghi nhận thời gian phát thực

- **Actor:** Learner/client — **FR/NFR:** FR-WAT-001, NFR-LAT-001, NFR-CONCUR-001.
- **Tiền điều kiện:** UC-L01, UC-L10; playback current published và writer lease hợp lệ.
- **Kịch bản:** POST `/playbacks` với Idempotency-Key; client gửi PUT `/playbacks/{id}/checkpoints/{seq}` mỗi khoảng 15s và khi pause/end, cumulative active milliseconds, epoch, position/rate. Server kiểm receipt trước trạng thái live, rồi active writer ID/lease45s/epoch/current version/seq/counter dưới user lock; atomic receipt+resume+daily credit.
- **Hậu điều kiện:** Active theo wall time, không nhân playback rate; pause/end nhận phần active thực trước chuyển trạng thái. Legacy sessions/progress không thay đổi.
- **Ngoại lệ:** Delta/rate/position sai trả 400; conflict seq/body/version/epoch trả 409; gap>30s reset mốc với credit0; lease hết hạn phải start mới. GET `/playbacks/{id}` reconcile; POST end dùng final checkpoint cùng validation, receipt retry không ghi lại credit/resume sau deletion.

### UC-L18 Mục tiêu ngày và preferences

- **Actor:** Learner — **FR/NFR:** FR-GOL-001, FR-WAT-001.
- **Kịch bản:** GET/PUT `/me/learning-preferences`, expected_revision, goal0–120 phút (0=tắt), IANA timezone, topics tồn tại. Goal/timezone pending từ nửa đêm tiếp theo của timezone current; topics áp dụng ngay. Trước effective, sửa lại thay pending dưới user lock, giữ boundary tính theo current. CAS stale trả409.
- **Hậu điều kiện:** GET `/me/activity` tính goal chỉ từ active_watch_seconds, trả bucket ngày/timezone/policy version; goal/timezone lịch sử không overwrite. Range inclusive tối đa90 ngày. Goal0 không báo hoàn thành mục tiêu. Response trả `current_streak_days` và `longest_streak_days` trong cửa sổ được hỏi; một ngày có nhiều policy bucket chỉ được tính một lần. Nếu ngày cuối là hôm nay và chưa đạt goal, streak tới hôm qua vẫn còn hiệu lực đến hết ngày.
- **Phạm vi nghiệm thu:** Không có streak freeze mặc định. Không cộng legacy với active.

### UC-L19 Xem và xóa lịch sử

- **Actor:** Learner — **FR/NFR:** FR-HIS-001, NFR-RET-001, NFR-PRIV-001.
- **Kịch bản:** GET `/me/watch-history` cursor; DELETE toàn bộ trả202 + deletion ID/cutoff/scope/retained_data. GET `/me/history-deletions/{id}` theo dõi queued/running/completed/failed.
- **Hậu điều kiện:** History/resume trước cutoff ẩn ngay và loại khỏi recommendation; active playback bị fence, gói late không tái tạo. Worker dọn chi tiết, giữ receipt/tombstone chống retry trong cửa sổ đã chốt, giữ saved scenes và daily/legacy aggregates.
- **Ngoại lệ/phạm vi:** Owner isolation; không xóa tài khoản, reset progress hoặc endpoint xóa một mục lịch sử trong phạm vi này. NFR-RET-001 raw90d/aggregate vĩnh viễn giữ nguyên; policy mới chưa được duyệt.

### UC-L20 Xem danh sách gợi ý clip tiếp theo (Smart Stream)

- **Actor:** Learner
- **FR / NFR:** FR-REC-001, FR-PRG-002
- **Trigger:** Sau khi kết thúc một clip hoặc tại trang chủ, Actor muốn hệ thống tự động gợi ý clip CI tiếp theo phù hợp với trình độ.
- **Tiền điều kiện:** UC-L01 («include»).
- **Hậu điều kiện (thành công):** Trả về luồng đề xuất clip thông minh dựa trên `current_ci_level`, các chủ đề học viên thường xem, ưu tiên các tập tiếp theo trong cùng series nếu đang xem dở, hoặc clip cùng cấp độ.
- **Kịch bản chính:**
  1. Client gửi `GET /me/recommendations`.
  2. Hệ thống kiểm tra `current_ci_level` của học viên và lịch sử xem gần đây.
  3. Thuật toán chọn lựa các clip published phù hợp:
     - Ưu tiên 1: Tập tiếp theo trong series đang xem.
     - Ưu tiên 2: Clip cùng level CI nhưng chưa xem hết.
     - Ưu tiên 3: Clip cùng topic ở level phù hợp.
  4. Hệ thống trả về danh sách gợi ý kèm lý do gợi ý (ví dụ: "Tập tiếp theo của series X", "Phù hợp với trình độ L1").
- **Kịch bản phụ (extend):**
  - 2a. Chưa có lịch sử xem (học viên mới): Đề xuất các clip phổ biến nhất ở level mặc định (0 hoặc 1).
- **Ngoại lệ:** không.
- **Quan hệ:** «include» UC-L01.

### UC-L21 Quản lý playlist & bộ sưu tập cá nhân

- **Actor:** Learner
- **FR / NFR:** FR-COL-001
- **Trigger:** Actor muốn nhóm các clip theo chủ đề riêng (ví dụ: "Hội thoại đời thường", "Ẩm thực Nhật Bản", "Nghe lúc lái xe").
- **Tiền điều kiện:** UC-L01 («include»).
- **Hậu điều kiện (thành công):** Playlist cá nhân được tạo, cho phép thêm/bớt clip và sắp xếp thứ tự nghe.
- **Kịch bản chính:**
  1. Actor tạo playlist mới qua `POST /collections` kèm tên và mô tả.
  2. Actor thêm clip vào playlist qua `POST /collections/{id}/items`.
  3. Client gọi `GET /collections` hoặc `GET /collections/{id}` để duyệt danh sách.
  4. Actor có thể xóa clip khỏi playlist hoặc xóa cả playlist (`DELETE /collections/{id}`).
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:**
  - Thêm clip không tồn tại hoặc chưa published → 404/400.
  - Sửa hoặc xóa collection của người khác → 403/404 (cách ly phạm vi dữ liệu).
- **Quan hệ:** «include» UC-L01.

### UC-L23 Xem báo cáo thống kê thời gian học

- **Actor:** Learner
- **FR / NFR:** FR-RPT-001, FR-WAT-001, NFR-RET-001
- **Trigger:** Actor mở trang Báo cáo / Thống kê để đánh giá nỗ lực học tập immersion của mình.
- **Tiền điều kiện:** UC-L01 («include»).
- **Hậu điều kiện (thành công):** Trả về biểu đồ phân tích thời gian học: số phút/giờ học mỗi ngày trong tuần/tháng, tỷ lệ hoàn thành mục tiêu, tổng thời gian tích lũy theo cả 2 chỉ số (`minutes_comprehensible` và `active_watch_seconds`).
- **Kịch bản chính:**
  1. Actor mở tab Báo cáo.
  2. Client gửi `GET /reports/study-time?period=week` (hoặc `month`).
  3. Hệ thống truy vấn dữ liệu tổng hợp theo ngày của học viên trong khoảng thời gian yêu cầu.
  4. Hệ thống trả về mảng dữ liệu thống kê ngày: `{date, active_seconds, legacy_minutes, completed_items_count}`.
  5. Client vẽ biểu đồ trực quan (cột / đường) thể hiện mức độ chuyên cần.
- **Kịch bản phụ (extend):** không.
- **Ngoại lệ:** không.
- **Quan hệ:** «include» UC-L01.

### UC-L24 Đơn phiên phát đồng thời (Single playback lease takeover)

- **Actor:** Learner (thao tác trên 2 thiết bị khác nhau)
- **FR / NFR:** FR-WAT-001, NFR-CONCUR-001
- **Trigger:** Học viên đang xem clip trên máy tính, sau đó mở app trên điện thoại để tiếp tục xem cùng một clip hoặc clip khác.
- **Tiền điều kiện:** UC-L01 («include»). Thiết bị A đang nắm giữ active playback lease.
- **Hậu điều kiện (thành công):** Thiết bị B chiếm quyền phát (lease takeover) với epoch mới. Thiết bị A bị thu hồi quyền phát, heartbeat tiếp theo của thiết bị A bị từ chối và thiết bị A chuyển sang trạng thái tạm dừng với thông báo rõ ràng.
- **Kịch bản chính:**
  1. Thiết bị B gửi yêu cầu bắt đầu phát hoặc mở phiên mới (`POST /playbacks` kèm Idempotency-Key và take_over khi cần).
  2. Hệ thống kiểm tra thấy user đã có lease trên thiết bị A.
  3. Hệ thống tăng `lease_epoch` (ví dụ từ 1 lên 2), gán `current_device_class` cho thiết bị B, ghi nhận thời gian lease mới.
  4. Thiết bị B nhận lease token và epoch 2, bắt đầu phát video và gửi heartbeat.
  5. Thiết bị A gửi heartbeat định kỳ với epoch 1.
  6. Hệ thống kiểm tra `heartbeat.epoch (1) < current_lease.epoch (2)` → Trả về 409 Conflict (`code: "LEASE_TAKEN_OVER"`).
  7. Trình phát trên thiết bị A lập tức tạm dừng (pause video) và hiển thị thông báo: "Tài khoản của bạn đang phát trên một thiết bị khác".
- **Kịch bản phụ (extend):**
  - 7a. Người dùng trên thiết bị A muốn tiếp tục trên thiết bị A: Bấm nút "Phát tại đây" → Thiết bị A gửi yêu cầu lease takeover mới (epoch tăng lên 3), chiếm lại quyền phát từ thiết bị B.
- **Ngoại lệ:** không.
- **Quan hệ:** «include» UC-L10, UC-L17.

## Deferred — Kịch bản Phase 5 mở rộng (chưa thiết kế UI v1)

Không vẽ `UC-L11`…`UC-L13` trên sơ đồ v1.

### UC-L11 Chọn hình kiểm hiểu

- **Actor:** Learner — **FR:** FR-LRN-002
- **Kịch bản chính:** Trong/ sau input CI, Actor chọn hình đúng nghĩa (probe không lời) → Hệ thống ghi kết quả probe. Schema `ComprehensionProbe` chừa chỗ; **không** UI v1. Không quiz điền hạt / điểm ngữ pháp.

### UC-L12 Cổng nói sau silent period

- **Actor:** Learner — **FR:** FR-LRN-003 (bám FR-FLG-001)
- **Kịch bản chính:** Pedagogy bật output có chủ đích → Hệ thống chỉ khi đó cho kênh nói. Mặc định v1: chỉ nhận, không micro, không prompt “nói theo”. **Chưa thiết kế UI v1.**

### UC-L13 `level_exposed` khi mở item

- **Actor:** Learner — **FR:** FR-EVT-003
- **Kịch bản chính:** Actor mở item một `ci_level` → Hệ thống ghi event `level_exposed` (`ci_level`). Nếu shell v1 chỉ list, không màn chi tiết: ghi khi start session với `current_ci_level` của user (ghi OpenAPI). Có thể làm sớm khi có detail; **chưa thiết kế UI v1.**

## Truy vết FR → UC (nền tảng & Mốc A/B)

| FR | UC |
|---|---|
| FR-ID-001 | UC-L01, UC-T01 |
| FR-ID-002 | UC-L01, UC-L06 |
| FR-ID-003 | UC-L01 |
| FR-ID-004 | UC-T01, UC-A03 |
| FR-CAT-001 | UC-T02 |
| FR-CAT-002 | UC-L02, UC-L10 |
| FR-CAT-003 | UC-L02 |
| FR-CAT-004 | UC-L02, UC-T02 |
| FR-CAT-005 | UC-T02, UC-T02b, UC-T05, UC-T06, UC-T07 |
| FR-SES-001 | UC-L03, UC-L10, UC-L24 |
| FR-SES-002 | UC-L04, UC-L10 |
| FR-SES-003 | UC-L03, UC-L10 |
| FR-LRN-001 | UC-L10, UC-L14, UC-L16 |
| FR-PRG-001 | UC-L04, UC-L05, UC-L10, UC-L17 |
| FR-PRG-002 | UC-L05, UC-L20 |
| FR-PRG-003 | UC-L05 |
| FR-PRG-004 | UC-L06 |
| FR-CMS-001 | UC-T03, UC-T02b |
| FR-CMS-002 | UC-T04, UC-A01, UC-T02b, UC-T09 |
| FR-CMS-003 | UC-A01, UC-L02, UC-L10 |
| FR-CMS-004 | UC-A01 |
| FR-FLG-001 | UC-A02 |
| FR-FLG-002 | UC-A02, UC-L02 |
| FR-FLG-003 | UC-A02, UC-L17, UC-L24 |
| FR-EVT-001 | UC-L03, UC-L04, UC-L10 |
| FR-EVT-002 | UC-L04, UC-L10, UC-L17 |
| FR-EVT-003 | UC-L13 (tối thiểu: session start với current level) |
| FR-SCN-001 | UC-T06, UC-T09, UC-L14 |
| FR-SER-001 | UC-T07 |
| FR-RSM-001 | UC-L16 |
| FR-WAT-001 | UC-L17, UC-L24 |
| FR-HIS-001 | UC-L19 |
| FR-GOL-001 | UC-L18 |
| FR-REC-001 | UC-L20 |
| FR-BMK-001 | UC-L15 |
| FR-COL-001 | UC-L21 |
| FR-RPT-001 | UC-L23 |
| NFR-LAT-001 | UC-L17 |
| NFR-RET-001 | UC-L19, UC-L23 |
| NFR-CONCUR-001 | UC-L17, UC-L24 |
| FR-NEG-* | Không có UC dương; QA kiểm vắng feature |

> R0 engineering amendment 2026-09-07; local verification 2026-09-08: contract trên đã có API/Web/Mobile engineering evidence nhưng không thay chữ ký BA/CTO/Pedagogy/Ops hoặc cho phép production. Full transcript chỉ staff; learner scene metadata không full transcript, search chỉ excerpt Nhật đã duyệt.
