# Use cases — nền tảng v1

Actors: **Learner**, **Teacher**, **Admin**, **LevelQA** (có thể trùng Teacher).

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
- Actor: Learner  
- FR: FR-ID-001, FR-ID-002, FR-ID-003  
- Main: mở app/web → nhập email/mật khẩu → nhận session → vào shell.  
- Alt: sai mật khẩu → không vào.  
- Exception: hết hạn token → yêu cầu login lại.

### UC-L02 Xem catalog
- FR: FR-CAT-002, FR-CAT-003, FR-CAT-004  
- Main: sau login, thấy danh sách `published`, nhóm theo `ci_level`, không có text dịch L1.  
- Alt: catalog trống → empty state (vẫn hợp lệ Q1).

### UC-L03 Bắt đầu phiên
- FR: FR-SES-001, FR-EVT-001  
- Main: chọn “bắt đầu phiên” (shell) → API tạo session với `device_class`.  
- Không bắt buộc play video (skeleton).

### UC-L04 Kết thúc phiên
- FR: FR-SES-002, FR-PRG-001, FR-EVT-001, FR-EVT-002  
- Main: kết thúc → `duration_seconds` cộng vào `minutes_comprehensible`.

### UC-L05 Xem tiến độ
- FR: FR-PRG-001, FR-PRG-002, FR-PRG-003  
- Main: thấy phút CI và `current_ci_level`. Không điểm, không % bài.

### UC-L06 Đồng bộ thiết bị
- FR: FR-ID-002, FR-PRG-004  
- Main: login cùng user trên thiết bị khác → cùng catalog published và cùng progress.

## Spec — Teacher / QA / Admin

### UC-T01 Đăng nhập nhân sự
- FR: FR-ID-001, FR-ID-004, NFR-SEC-002  
- Role `teacher` hoặc `admin`.

### UC-T02 Tạo item draft
- FR: FR-CAT-001, FR-CAT-005  
- Nhập metadata theo taxonomy; `status=draft`; `has_l1_translation=false`.

### UC-T03 Upload media
- FR: FR-CMS-001  
- Gắn file vào item draft.

### UC-T04 Gửi Level QA
- FR: FR-CMS-002  
- `status=level_qa`.

### UC-Q01 / UC-Q02 Rubric CI
- Pedagogy taxonomy. Approve → sẵn sàng publish. Reject → về draft kèm lý do nội bộ (không lộ learner).

### UC-A01 Publish
- FR: FR-CMS-002, FR-CMS-003, FR-CMS-004, NFR-PERF-001  
- `status=published`; client lấy được qua API.

### UC-A02 Feature flags
- FR: FR-FLG-001, FR-FLG-002  
- Mặc định tắt speaking, L1 subtitles, grammar, flashcards.

### UC-A03 Roles
- FR: FR-ID-004  
- Gán `learner` / `teacher` / `admin`.

## Deferred (có ID, không vẽ UI v1)

| UC | FR | Tên |
|---|---|---|
| UC-L10 | FR-LRN-001 | Phát item CI trong phiên |
| UC-L11 | FR-LRN-002 | Chọn hình kiểm hiểu |
| UC-L12 | FR-LRN-003 | Cổng nói sau silent period |
| UC-L13 | FR-EVT-003 | `level_exposed` khi mở item (có thể làm sớm nếu catalog item mở được; v1 ghi khi user mở chi tiết item nếu shell có màn hình chi tiết) |

`level_exposed`: nếu shell v1 chỉ list không có detail, ghi event khi start session gắn `ci_level` mặc định của user — ghi trong OpenAPI.

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
