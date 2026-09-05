# Use cases — nền tảng v1

Actors: **Learner**, **Teacher**, **Admin**, **LevelQA** (có thể trùng Teacher).

Sơ đồ Mermaid: [diagrams.md](diagrams.md) — mục 1 actor → UC; mục **1b** «include» / «extend». Kịch bản dưới đây là nguồn SAD-2; không mâu thuẫn [SRS](../01-survey-srs/srs.md), [processes.md](processes.md), sequence [SAD-3](../03-design/diagrams.md).

Không có UC flashcard, bài ngữ pháp, hay kênh dịch L1 trên client học viên (`FR-NEG-001`…`003`).

## Sơ đồ (nền tảng)

```
Learner: UC-L01 Login, UC-L02 Browse catalog, UC-L03 Start session,
         UC-L04 End session, UC-L05 View progress, UC-L06 Sync devices
Teacher: UC-T01 Login staff, UC-T02 Create item, UC-T03 Upload media,
         UC-T04 Submit level QA
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
- **Ngoại lệ:** Learner → 403. Không nhảy `draft` → `published` từ màn này. Không include UC-T03 (upload là bước BPMN riêng, mục 5).
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
- **FR / NFR:** FR-FLG-001, FR-FLG-002
- **Trigger:** Admin xem/sửa cờ nền tảng.
- **Tiền điều kiện:** UC-T01 («include»).
- **Hậu điều kiện (thành công):** `speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled` mặc định `false`. Client không vẽ UI kênh đã tắt.
- **Kịch bản chính:**
  1. Actor mở quản lý flags.
  2. Hệ thống trả bốn cờ (mặc định false).
  3. Actor không bật textbook ở v1 trừ quyết định Pedagogy có chủ đích (cổng nền tảng).
  4. Client học viên ẩn Nói / Thẻ / Ngữ pháp khi flag false (`S-FLAGS-GATE`).
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

## Deferred — Kịch bản Phase 5 (chưa thiết kế UI v1)

Không vẽ `UC-L10`…`UC-L13` trên sơ đồ v1 (mục 1 / 1b). Mỗi UC: một kịch bản chính; UI vòng học = SAD Phase 5.

### UC-L10 Phát item CI trong phiên

- **Actor:** Learner — **FR:** FR-LRN-001
- **Tiền:** Phiên đã start (UC-L03); item `published` có URL media.
- **Kịch bản chính:** Actor chọn phát item trong phiên → Hệ thống cấp playback URL (ký) → Client phát xem/nghe CI. Không phụ đề L1, không flashcard, không bài ngữ pháp.
- **Hiện trạng (không đổi FR):** Web đã có player skeleton sau cổng nền tảng. Expo native gộp #30. Chưa thiết kế UI v1 đầy đủ / HLS trên mọi client (NFR-PERF-002).

### UC-L11 Chọn hình kiểm hiểu

- **Actor:** Learner — **FR:** FR-LRN-002
- **Kịch bản chính:** Trong/ sau input CI, Actor chọn hình đúng nghĩa (probe không lời) → Hệ thống ghi kết quả probe. Schema `ComprehensionProbe` chừa chỗ; **không** UI v1. Không quiz điền hạt / điểm ngữ pháp.

### UC-L12 Cổng nói sau silent period

- **Actor:** Learner — **FR:** FR-LRN-003 (bám FR-FLG-001)
- **Kịch bản chính:** Pedagogy bật output có chủ đích → Hệ thống chỉ khi đó cho kênh nói. Mặc định v1: chỉ nhận, không micro, không prompt “nói theo”. **Chưa thiết kế UI v1.**

### UC-L13 `level_exposed` khi mở item

- **Actor:** Learner — **FR:** FR-EVT-003
- **Kịch bản chính:** Actor mở item một `ci_level` → Hệ thống ghi event `level_exposed` (`ci_level`). Nếu shell v1 chỉ list, không màn chi tiết: ghi khi start session với `current_ci_level` của user (ghi OpenAPI). Có thể làm sớm khi có detail; **chưa thiết kế UI v1.**

## Truy vết FR → UC (nền tảng)

| FR | UC |
|---|---|
| FR-ID-001 | UC-L01, UC-T01 |
| FR-ID-002 | UC-L01, UC-L06 |
| FR-ID-003 | UC-L01 |
| FR-ID-004 | UC-T01, UC-A03 |
| FR-CAT-001 | UC-T02 |
| FR-CAT-002 | UC-L02 |
| FR-CAT-003 | UC-L02 |
| FR-CAT-004 | UC-L02, UC-T02 |
| FR-CAT-005 | UC-T02 |
| FR-SES-001 | UC-L03 |
| FR-SES-002 | UC-L04 |
| FR-SES-003 | UC-L03 |
| FR-PRG-001 | UC-L04, UC-L05 |
| FR-PRG-002 | UC-L05 |
| FR-PRG-003 | UC-L05 |
| FR-PRG-004 | UC-L06 |
| FR-CMS-001 | UC-T03 |
| FR-CMS-002 | UC-T04, UC-A01 |
| FR-CMS-003 | UC-A01, UC-L02 |
| FR-CMS-004 | UC-A01 |
| FR-FLG-001 | UC-A02 |
| FR-FLG-002 | UC-A02, UC-L02 |
| FR-EVT-001 | UC-L03, UC-L04 |
| FR-EVT-002 | UC-L04 |
| FR-EVT-003 | UC-L13 (tối thiểu: session start với current level) |
| FR-NEG-* | Không có UC dương; QA kiểm vắng feature |
