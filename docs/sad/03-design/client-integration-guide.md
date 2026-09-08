# Hướng dẫn tích hợp Client — Vòng học CI (Heartbeat, Checkpoint & Playback)

Tài liệu này đặc tả quy trình và quy tắc kỹ thuật để các ứng dụng Client (Web, iOS/iPad, Android) tích hợp vào hệ thống vòng học CI mới của JPLearn, tuân thủ ADR-007 và hợp đồng API OpenAPI 3.0.3.

---

## 1. Phân biệt `minutes_comprehensible` và `active_watch_seconds`

> [!IMPORTANT]
> **Không cộng gộp hai chỉ số này.** Chúng đo lường hai khái niệm sư phạm hoàn toàn khác nhau:
> - **`minutes_comprehensible` (Legacy Session)**: Tổng số phút tròn (floor minutes) của các phiên học hợp lệ từ `/sessions` đến `/sessions/{id}/end`. Giữ nguyên để tương thích ngược với các phiên bản client cũ.
> - **`active_watch_seconds` (Continuous Playback)**: Đo lường thời gian thực mà người học xem video trực tuyến ở trạng thái `playing` (loại bỏ tua/pause/buffer). Chỉ số này được ghi nhận theo từng bucket ngày trong `/me/activity` và so khớp với mục tiêu ngày (`daily_goal_minutes`).

---

## 2. Vòng đời một phiên phát (Playback Lifecycle)

### 2.1. Khởi tạo Playback (`POST /playbacks`)
- **Headers**: Bắt buộc có `Authorization: Bearer <token>` và `Idempotency-Key: <key>` ($\le 128$ ký tự).
- **Payload**:
  ```json
  {
    "catalog_item_id": "clip-01",
    "content_version_id": "ver-01",
    "device_class": "web",
    "client_instance_id": "cinst-9a8b-uuid",
    "take_over": false
  }
  ```
- **Xử lý Response**:
  - `201 Created`: Trả về `id` (playback ID), `epoch`, `server_time`, `heartbeat_interval_seconds` (mặc định 15 giây).
  - `409 Conflict`: Đang có một playback khác của cùng user đang chạy và còn hiệu lực lease (45s).
    - Client hiển thị hộp thoại: *"Bạn đang mở bài học này trên thiết bị khác. Bạn có muốn tiếp tục tại đây?"*
    - Nếu người dùng đồng ý: Gửi lại request với `take_over: true`. Server sẽ tăng `epoch` và vô hiệu hóa playback cũ (`superseded`).

### 2.2. Gửi Checkpoint định kỳ (`PUT /playbacks/{id}/checkpoints/{seq}`)
- **Chu kỳ**: Gửi mỗi **15 giây** khi đang phát và **ngay lập tức** khi có sự kiện: `pause`, `seek`, `buffer_start`.
- **Số thứ tự `seq`**: Bắt đầu từ 1 và tăng liên tiếp ($1, 2, 3, \dots$).
- **Payload**:
  ```json
  {
    "epoch": 1,
    "position_ms": 30000,
    "cumulative_active_ms": 15000,
    "player_state": "playing",
    "playback_rate": 1.0
  }
  ```
- **Quy tắc tính `cumulative_active_ms` tại Client**:
  - Chỉ tăng giá trị này khi video thực sự đang chạy (sự kiện `timeupdate` khi player đang `playing`).
  - **Không tăng** khi player đang `paused`, `buffering`, hoặc khi người dùng đang kéo tua (`seeking`).
  - Khi tua video tới trước 10 phút, `position_ms` nhảy từ 0 đến 600,000 nhưng `cumulative_active_ms` chỉ tăng tương ứng với thời gian thực tế đã xem.
- **Xử lý lỗi Checkpoint**:
  - `400 Bad Request`: Counter giảm hoặc delta vượt quá dung sai cho phép so với thời gian server $\to$ Client reset counter về 0.
  - `409 Conflict`: `epoch` bị cũ (do thiết bị khác takeover) hoặc `seq` bị lệch $\to$ Client dừng phát và gọi `GET /playbacks/{id}` để đồng bộ lại trạng thái.

### 2.3. Kết thúc Playback (`POST /playbacks/{id}/end`)
- Khi người học rời trang, đóng video hoặc bài học kết thúc:
  ```json
  {
    "epoch": 1,
    "final_checkpoint": {
      "seq": 4,
      "position_ms": 45000,
      "cumulative_active_ms": 45000,
      "player_state": "ended",
      "playback_rate": 1.0
    }
  }
  ```
- Endpoint này khóa toàn bộ phiên phát, ghi nhận checkpoint cuối và commit toàn bộ thời gian học vào hoạt động ngày.

---

## 3. Resume & Xử lý Trạng thái Cảnh (Scene Availability)

Khi hiển thị danh sách bài học gần đây hoặc cảnh đã lưu (`/me/resume`, `/me/saved-scenes`):
- `availability: "available"`: Nội dung và phiên bản vẫn khả dụng bình thường.
- `availability: "stale_version"`: Video đã được cập nhật phiên bản biên tập mới. Client hiển thị cảnh báo: *"Nội dung đã được cập nhật bản mới. Điểm dừng cũ có thể không hoàn toàn khớp"*.
- `availability: "unavailable"`: Clip đã bị gỡ hoặc unpublish. Client hiển thị dạng disabled (mờ đi) và không cho phép phát lại.

---

## 4. Kiểm tra Feature Capabilities (`GET /capabilities`)

Client gọi `GET /capabilities` sau khi đăng nhập để quyết định các tính năng hiển thị trên UI:
- `content_scenes`: Cho phép chọn và tua theo phân cảnh.
- `saved_scenes`: Cho phép bookmark phân cảnh.
- `personal_collections`: Cho phép tạo và sắp xếp bộ sưu tập cá nhân.
- `content_reports`: Cho phép gửi báo cáo góp ý nội dung theo cảnh.
- `playback_tracking`: Cho phép ghi nhận `active_watch_seconds` và resume.
- `activity`: Cho phép hiển thị bảng mục tiêu và lịch học tập.
- `scene_search`: Cho phép tìm kiếm câu/cảnh trong kho JPLearn.
