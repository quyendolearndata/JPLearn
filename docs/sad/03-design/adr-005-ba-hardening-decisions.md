# ADR-005 — BA Decisions: Hardening Semantics, Media Boundary & Error Contract

- **Ghế chủ trì:** BA / System Analyst (`jplearn-ba`)
- **Ngày:** 2026-09-05
- **Trạng thái:** Accepted
- **Phối hợp:** CTO (`jplearn-cto`), Platform (`jplearn-platform`), QA (`jplearn-qa`), Ops (`jplearn-ops`)
- **Kế thừa & liên quan:** ADR-003, `docs/superpowers/plans/2026-09-05-fastapi-hardening-gap-closure.md`

---

## 1. Bối cảnh

Kế hoạch hardening backend FastAPI đặt ra các vấn đề về hành vi giao diện (contract semantics) và ranh giới nghiệp vụ cần BA chính thức ban hành quyết định để Platform thực thi và QA nghiệm thu:

1. Mã phản hồi HTTP khi gọi duplicate `POST /sessions/{id}/end` (400 vs 409).
2. Quy định ma trận MIME type, đuôi mở rộng (file extension), kích thước tối đa (max size) và content signature cho media upload.
3. Chính sách lưu giữ (retention window) và quyền xóa file orphan trong media storage.
4. Chuẩn hóa hình dạng public error body `{statusCode, message, error}` và các HTTP status codes bắt buộc trong OpenAPI contract.

---

## 2. Các quyết định chính thức của BA

### 2.1 Quyết định 1: Duplicate `EndSession` giữ HTTP 400 Bad Request

- **Vấn đề:** Khi một session đã được kết thúc thành công (`ended_at` khác null), nếu client gửi tiếp yêu cầu `POST /sessions/{id}/end`, backend nên trả `400 Bad Request` hay `409 Conflict`?
- **Quyết định của BA:** **Giữ HTTP 400 Bad Request**.
- **Lý do & Tác động:**
  - **Khả năng tương thích (Client Parity):** Client Web (`apps/web`) và Mobile (`apps/mobile`) hiện tại bắt mã `400` cho các lỗi phiên không hợp lệ (`Invalid session state` hoặc `Session already ended`). Đổi sang `409` sẽ tạo break contract phía client mà không mang lại giá trị gia tăng nghiệp vụ trong Sóng 1.
  - **Thông điệp:** Body trả về `{statusCode: 400, message: "Session already ended", error: "Bad Request"}`.
  - **Traceability:** Áp dụng cho `FR-SES-002`, `UC-L04`, `T-SES-002`.

### 2.2 Quyết định 2: Ma trận Media Upload & Phân giải HLS

- **Vấn đề:** `StoragePort` và router upload hiện tại chấp nhận `file.content_type` tùy ý từ client, tiềm ẩn nguy cơ bảo mật và lệch định dạng stream.
- **Quyết định của BA:**
  1. **Upload video (`POST /staff/catalog/{id}/media`):**
     - **MIME type cho phép:** duy nhất `video/mp4`.
     - **Extension cho phép:** `.mp4` (case-insensitive, chuẩn hóa thành chữ thường).
     - **Kích thước tối đa:** Bounded `500 MB` (524,288,000 bytes). File rỗng (0 bytes) hoặc vượt ngưỡng bị từ chối ngay với `400 Bad Request`.
     - **Content Signature (Magic Bytes):** Stream validator phải kiểm tra 8 bytes đầu tiên của file: bytes 4..8 phải chứa signature `ftyp` (chuẩn ISO Base Media File Format / MP4).
  2. **Tài nguyên HLS (`GET /media/{id}/hls/{file}`):**
     - **MIME mapping:**
       - `.m3u8` -> `application/vnd.apple.mpegurl`
       - `.ts` -> `video/mp2t`
       - `.m4s` -> `video/iso.segment`
       - `.mp4` -> `video/mp4`
       - `.vtt` -> `text/vtt`
     - **Filename Pattern:** Bắt buộc khớp regex `^[A-Za-z0-9._-]+$`. Cấm hoàn toàn ký tự path traversal (`..`, `/`, `\`). File không đúng định dạng trả `400 Bad Request`, không tồn tại trả `404 Not Found`.

### 2.3 Quyết định 3: Chính sách lưu giữ Orphan Media & Thẩm quyền xóa

- **Vấn đề:** Các file rác hoặc file dở dang do quá trình upload gián đoạn / lỗi DB có thể tích tụ trên storage.
- **Quyết định của BA & Ops:**
  1. **Cơ chế Staging Upload:** Bắt buộc stream qua `.part`. Nếu có bất kỳ exception nào (hủy kết nối, lỗi kích thước, lỗi DB commit), file `.part` hoặc file đích `.bin` phải được dọn dẹp ngay lập tức (compensation deletion).
  2. **Thời gian lưu giữ (Retention Window):** File orphan phát hiện bởi reconciliation process phải có thời gian lưu giữ an toàn tối thiểu **24 giờ** kể từ thời điểm tạo (mtime) trước khi được phép xem xét xóa, nhằm tránh xóa nhầm các file đang trong quá trình upload song song.
  3. **Thẩm quyền xóa:**
     - Lệnh reconciliation CLI mặc định chỉ chạy ở chế độ **báo cáo (report-only / dry-run)**.
     - Lệnh chỉ xóa vật lý khi truyền cờ tường minh `--delete` kèm tham số `--older-than 24h` và phải có sự phê duyệt từ ghế **Ops**.

### 2.4 Quyết định 4: Chuẩn hóa Public Error Body & OpenAPI Status Codes

- **Vấn đề:** FastAPI mặc định sinh status `422 Unprocessable Entity` với cấu trúc `{detail: [...]}` khi request validation thất bại, lệch với NestJS contract vốn dùng `400 Bad Request` với `{statusCode, message, error}`.
- **Quyết định của BA:**
  1. **Cấu trúc JSON phản hồi lỗi thống nhất:**
     ```json
     {
       "statusCode": 400,
       "message": "Error description or list of field errors",
       "error": "Bad Request"
     }
     ```
     *(Lưu ý: HTTP 401 theo NestJS giữ nguyên `{statusCode: 401, message: "..."}` không kèm thuộc tính `error`)*.
  2. **Loại bỏ 422 khỏi Public Contract:**
     - Endpoint validation lỗi phải trả về `400 Bad Request`.
     - Tuyệt đối không để lộ schema `422` trong public OpenAPI specification của API (`/openapi.json` hoặc `docs/sad/03-design/openapi.yaml`).
  3. **Các mã lỗi bắt buộc trong OpenAPI Spec:**
     - Các endpoint có xác thực: `401 Unauthorized`.
     - Các endpoint phân quyền staff/admin: `403 Forbidden`.
     - Các endpoint có parameter id / query / body: `400 Bad Request`, `404 Not Found` (nếu tra cứu entity).
     - Hệ thống: `500 Internal Server Error`.
     - Health check `/ready`: `200 OK` (dependencies up), `503 Service Unavailable` (dependencies down).

---

## 3. Trách nhiệm các ghế thực thi (RACI)

| Ghế | Trách nhiệm |
|---|---|
| **BA** | Giám sát tính nhất quán giữa SRS, Traceability, ADR-005 và OpenAPI contract. |
| **Platform** | Cập nhật `StoragePort`, `media_service.py`, `openapi_diff.py`, `errors.py`, `main.py` tuân thủ đúng các quyết định trên. |
| **QA** | Xây dựng mutation test suite cho OpenAPI contract, negative tests cho upload signature, traversal, và reconciliation report. |
| **Ops** | Tiếp nhận runbook reconciliation và phê duyệt chính sách xóa storage. |
