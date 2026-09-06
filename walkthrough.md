# Báo Cáo Thực Thi: Web Frontend & Staff CMS (Mốc A & Mốc B)

Kế hoạch [docs/superpowers/plans/2026-09-06-web-frontend-implementation.md](file:///Users/quyendo/Documents/Learn/JPLearn/docs/superpowers/plans/2026-09-06-web-frontend-implementation.md) đã được hoàn thành toàn diện trên toàn bộ các vai trò (BA, Design, Web, Platform, QA).

---

## 1. Tổng Quan Kết Quả Đạt Được

### Mốc A — Learner Web (Trải Nghiệm Người Học)
- **Landing Page ([apps/web/src/app/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/page.tsx)):** Thiết kế Tonmana ấm áp, chuẩn khoa học Comprehensible Input (CI) dựa trên bản mockup `landing_preview.html`, bảng so sánh phương pháp và hero trực quan.
- **Hệ Thống Xác Thực ([apps/web/src/app/login/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/login/page.tsx)):** Hỗ trợ Đăng ký/Đăng nhập, điều hướng bảo vệ qua query `redirect`, hiển thị tài khoản hiện tại, và hàm `logout()` thu hồi phiên triệt để trên máy chủ (`POST /auth/logout`).
- **Danh Mục Bài Học ([apps/web/src/app/catalog/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/catalog/page.tsx)):** Lọc nhanh theo cấp độ CI (Cấp 0 – 4), hiển thị thẻ clip CI kèm metadata trực quan và điều hướng vào phiên học theo clip được chọn (`/session?item_id=...`).
- **Phiên Học Trực Tiếp ([apps/web/src/app/session/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/session/page.tsx)):**
  - Trình phát media `<CiPlayer>` linh hoạt: ưu tiên luồng thích ứng HLS (`.m3u8`), tự động fallback MP4.
  - Chống trùng lặp yêu cầu qua header `Idempotency-Key` trên `POST /sessions`.
  - Khôi phục phiên học gián đoạn qua `localStorage` (`jplearn_active_session`) và xác thực trạng thái máy chủ `GET /sessions/{id}`.
  - Đồng hồ đếm thời gian thực khi học, nút Bắt đầu / Kết thúc rõ ràng, và bảng tổng kết tiến độ ngay sau phiên.
- **Tiến Độ Học Tập ([apps/web/src/app/progress/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/progress/page.tsx)):** Hiển thị số phút CI tích luỹ và cấp độ hiện tại, tự động đồng bộ khi quay lại trang.

### Mốc B — Staff CMS (Cổng Quản Trị & Biên Tập Nội Dung)
- **Danh Sách Nội Dung Staff ([apps/web/src/app/staff/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/page.tsx)):** Cổng biên tập dành cho vai trò `teacher` / `admin`, lọc theo trạng thái (`draft`, `level_qa`, `published`, `archived`) và cấp độ CI, bảng chi tiết hiển thị revision và thời lượng.
- **Tạo Mới Bản Thảo ([apps/web/src/app/staff/new/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/new/page.tsx)):** Biểu mẫu tạo mới bản thảo theo chuẩn `catalogWriteFields`, tải kèm tệp MP4 ban đầu và chuyển hướng ngay vào màn hình biên tập.
- **Biên Tập & Kiểm Duyệt ([apps/web/src/app/staff/[id]/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/%5Bid%5D/page.tsx)):**
  - Chỉnh sửa thông tin metadata bản thảo với cơ chế khoá lạc quan (optimistic locking) qua trường `revision` (bắt lỗi xung đột 409 Conflict và hỗ trợ tải lại dữ liệu mới nhất).
  - Tải lên video MP4 thay thế (`POST /staff/catalog/{id}/media`).
  - Nộp kiểm duyệt chất lượng (`POST /staff/catalog/{id}/submit-qa`).
  - Xuất bản (`publish`) và gỡ bài (`unpublish`) dành riêng cho quyền quản trị (`admin`).

### Platform & Backend
- **Migration & Database ([apps/api-python/src/jplearn_api/migrations/versions/0002_session_idem_rev.py](file:///Users/quyendo/Documents/Learn/JPLearn/apps/api-python/src/jplearn_api/migrations/versions/0002_session_idem_rev.py)):**
  - Tạo bảng `session_idempotency_keys` lưu trữ khoá chống lặp phiên học.
  - Bổ sung cột `revision` (integer, default 1) trên bảng `catalog_items`.
  - Cập nhật baseline [docs/qa/adr-004-schema-baseline.json](file:///Users/quyendo/Documents/Learn/JPLearn/docs/qa/adr-004-schema-baseline.json).
- **API & OpenAPI:**
  - Cập nhật [docs/sad/03-design/openapi.yaml](file:///Users/quyendo/Documents/Learn/JPLearn/docs/sad/03-design/openapi.yaml) đồng bộ 100% với mã nguồn.
  - Hỗ trợ `GET /sessions/{id}`, `Idempotency-Key` trên `POST /sessions`, `GET /staff/catalog`, `GET /staff/catalog/{id}`, và `PATCH /staff/catalog/{id}`.
- **Tài Liệu Phân Tích (BA & SAD):**
  - Cập nhật `use-cases.md` (UC-L10, UC-T02b, UC-T05).
  - Cập nhật `traceability.md` và `ui-shell.md`.

---

## 2. Bằng Chứng Kiểm Thử (Verification Evidence)

### A. Guard Anti-Textbook
```bash
pnpm test:guard
```
- **Kết quả:** `0 errors` — Không chứa bất kỳ từ khoá hoặc cột chrome bị cấm (`Ngữ pháp`, `Flashcard`, `Bản dịch`).

### B. Kiểm Thử Kiểu Dữ Liệu & Bản Dựng Web
```bash
pnpm --filter @jplearn/web exec tsc --noEmit
pnpm --filter @jplearn/web build
```
- **Kết quả:** 
  - `tsc`: 0 lỗi biên dịch TypeScript.
  - `next build`: 10 route tĩnh và động được tạo thành công tối ưu.

### C. Bộ Kiểm Thử Pytest Backend (FastAPI)
```bash
cd apps/api-python && uv run pytest
```
- **Kết quả:** `208 passed` trong 25.3s.
  - `tests/test_openapi_diff.py`: 7/7 PASSED (0 sai lệch giữa contract OpenAPI và FastAPI router).
  - `tests/test_schema_ddl.py`: 8/8 PASSED (0 sai lệch cấu trúc bảng DDL so với baseline ADR-004).
  - `tests/test_sessions.py`: 11/11 PASSED (kiểm thử chống lặp Idempotency-Key và endpoint khôi phục).
  - `tests/test_catalog.py`: 7/7 PASSED (kiểm thử optimistic locking revision và CRUD staff).

### D. Kiểm Thử E2E Playwright Trên Trình Duyệt Thật (Chromium)
```bash
./apps/api-python/differential/web-e2e-python.sh --project=chromium
```
- **Kết quả:** `5 passed (2.3m)`
  - `hls.spec.ts`: Phát luồng HLS thật `.m3u8` qua `CiPlayer` thành công (`2.2s`).
  - `shell.spec.ts (login & progress)`: Vượt qua xác nhận không chứa banned chrome (`7.9s`).
  - `shell.spec.ts (catalog)`: Hiển thị đúng nội dung đã xuất bản, ẩn bản thảo (`1.3s`).
  - `a11y.spec.ts`: Đạt toàn bộ chuẩn WCAG 2 AA contrast ratio, tiêu đề trang và ARIA semantic trên toàn bộ route người học (`9.7s`).
  - `sync.spec.ts`: Chạy phiên học kéo dài thật >60s giữa 2 ngữ cảnh trình duyệt riêng biệt, đồng bộ chính xác từng phút tích luỹ (`2.3m`).

### E. Kiểm Thử E2E Playwright Trên WebKit (Safari Engine)
```bash
./apps/api-python/differential/web-e2e-python.sh --project=webkit
```
- **Kết quả:** `5 passed (2.2m)` — Vượt qua 100% các ca kiểm thử tương tự trên WebKit.

---

## 3. Hướng Dẫn Trải Nghiệm Thủ Công (Manual Walkthrough)

1. **Khởi chạy ứng dụng:**
   - Terminal 1 (API): `cd apps/api-python && PYTHONPATH=src uv run uvicorn jplearn_api.entrypoints.http.app:app --port 3002`
   - Terminal 2 (Web): `cd apps/web && pnpm dev` (mở tại `http://localhost:3000`)
2. **Khám phá giao diện người học (Learner):**
   - Vào `http://localhost:3000/` để xem trang giới thiệu phong cách Tonmana.
   - Vào `/login` để đăng ký tài khoản mới (hoặc đăng nhập).
   - Vào `/catalog` để xem các bài học CI được lọc theo cấp độ.
   - Nhấn "Học clip này" để chuyển tới `/session`, bấm "Bắt đầu phiên" để thưởng thức video kèm âm thanh, theo dõi đồng hồ chạy và bấm "Kết thúc phiên".
   - Vào `/progress` để kiểm tra số phút học vừa được hệ thống tích luỹ chính xác.
3. **Trải nghiệm cổng quản trị Staff CMS:**
   - Đăng nhập bằng tài khoản `admin@jplearn.local` / `password10`.
   - Vào `http://localhost:3000/staff` để xem danh sách nội dung và bộ lọc trạng thái.
   - Bấm "Tạo bản thảo mới" (`/staff/new`), nhập thông tin và tải lên tệp MP4.
   - Tại màn hình chi tiết (`/staff/[id]`), thử cập nhật metadata, bấm "Nộp kiểm duyệt (QA)", và "Xuất bản ngay" để đưa clip ra ngoài Catalog người học.
