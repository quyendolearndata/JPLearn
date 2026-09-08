# Runbook Vận hành — Hệ thống Vòng học CI & AI Content Jobs

Tài liệu hướng dẫn đội ngũ Vận hành (Ops), Quản trị viên (Admin) và Kỹ thuật viên (DevOps) theo dõi, bảo trì và xử lý sự cố cho hệ thống Vòng học CI, hàng đợi dọn dẹp dữ liệu và AI Worker.

---

## 1. Thành phần Dịch vụ và Kiến trúc

1. **API Server (FastAPI)**:
   - Xử lý các nghiệp vụ HTTP/REST của học viên và nhân viên.
   - Chạy với Uvicorn/Gunicorn trong container `apps/api-python`.
2. **Maintenance Worker CLI (`jplearn-maintenance`)**:
   - Chạy định kỳ (CronJob hoặc Container Daemon) để thực hiện:
     - Xử lý các yêu cầu xóa lịch sử học tập (`DELETE /me/watch-history`) vượt quá thời điểm cutoff.
     - Dọn dẹp dữ liệu hết hạn (Retention Policy): Receipt quá 30 ngày, Checkpoints stale.
3. **AI Content Jobs Worker CLI (`jplearn-ai-worker`)**:
   - Nhận việc từ hàng đợi PostgreSQL `content_jobs` bằng cơ chế lease/attempt token (`SKIP LOCKED`).
   - Tương tác với AI Transcription Provider, thực hiện nhận diện âm thanh và chia cảnh tiếng Nhật.
   - Settle chi phí và giải phóng hạn mức Quota Ledger.
   - Không tự retry một lần gọi đã hết lease vì nhà cung cấp có thể đã tính phí.

---

## 2. Vận hành Maintenance CLI (`jplearn-maintenance`)

### 2.1. Lệnh thực thi cơ bản
```bash
# Chạy một chu kỳ kiểm tra và dọn dẹp các deletion job đang chờ
jplearn-maintenance purge-history --once

# Chạy daemon dọn lịch sử, polling mỗi 2 giây
jplearn-maintenance purge-history

# Đánh dấu các lần gọi AI hết lease là outcome_unknown; chạy được cả khi AI đang tắt
jplearn-maintenance sweep-ai-attempts --limit 100

# Liệt kê asset/version cũ thiếu duration hoặc checksum; lệnh chỉ đọc
jplearn-maintenance inventory-media-integrity --limit 100
```

### 2.2. Kiểm tra tiến độ và sự cố Deletion
- Khi người học yêu cầu xóa lịch sử (`DELETE /me/watch-history`), một bản ghi được tạo trong bảng `maintenance_jobs` với trạng thái `queued`.
- Nếu job bị kẹt ở trạng thái `running` do pod restart:
  - Hệ thống tự động thu hồi sau 300 giây (lease timeout) và cho phép worker khác claim lại với attempt mới.
  - Số lần thử tối đa: 3 attempts. Quá 3 lần job sẽ chuyển sang `failed` và ghi nhận `last_error`.

### 2.3. Kiểm kê tính toàn vẹn media trước rollout

Sau khi chạy migration `0018_hls_bundle_integrity`, chạy `inventory-media-integrity` trên từng môi trường đích và lưu JSON làm bằng chứng rollout. `candidate_count` là tổng số bản ghi cần xử lý; mảng `candidates` bị giới hạn bởi `--limit`, và `truncated=true` báo còn bản ghi chưa hiện trong output.

Một asset bị liệt kê khi thiếu duration đo bằng ffprobe, SHA-256 nguồn hoặc checksum bundle HLS. Một content version đã frozen/published bị liệt kê khi snapshot nguồn còn thiếu hoặc còn `duration_source=legacy_metadata`. Không điền checksum bằng SQL và không coi asset cũ đã được xác minh. Upload/register lại nguồn, tạo đủ manifest + segment HLS, đưa catalog item về workflow QA được phép, rồi submit QA/publish để hệ thống tự pin bằng chứng mới. Chỉ rollout nội dung đã chọn khi inventory tương ứng không còn candidate.

---

## 3. Vận hành AI Worker CLI (`jplearn-ai-worker`)

### 3.1. Lệnh thực thi cơ bản
```bash
# Chạy một lần xử lý job kế tiếp (nếu có) rồi thoát
jplearn-ai-worker --once

# Chạy worker daemon, kiểm tra hàng đợi mỗi 5 giây
jplearn-ai-worker --poll-interval 5
```

### 3.2. Quản lý Quota & Chi phí AI
- Khi tạo job, hệ thống khóa tài khoản quota (`ai_quota_accounts`) và ghi nhận bút toán `reservation` trong `ai_usage_ledger`.
- Khi worker hoàn thành:
  - Thực hiện ghi nhận chi phí thực tế (`settle`).
  - Tự động hoàn trả phần dự trù dư thừa (`release`).
- Khi gặp sự cố mạng hoặc timeout từ nhà cung cấp AI:
  - Worker ghi nhận trạng thái `outcome_unknown` (`reconcile`).
  - Phần ngân sách đã bảo lưu **không được giải phóng ngay lập tức** nhằm tránh việc gọi retry làm thâm hụt ngân sách của dự án.
  - Quản trị viên xem `GET /staff/content-jobs/{id}/attempts`, đối chiếu bảng điều khiển/hóa đơn của nhà cung cấp, rồi gửi `POST /staff/content-jobs/{id}/attempts/{attempt_id}/reconcile` với quyết định `billed` hoặc `not_billed` và bằng chứng. Gửi lại cùng payload là idempotent; payload khác trả 409.

---

## 4. Xử lý Sự cố Thường gặp (Troubleshooting)

| Triệu chứng | Nguyên nhân có thể | Cách khắc phục |
| :--- | :--- | :--- |
| **User nhận 409 khi Start Playback** | Thiết bị cũ vẫn giữ lease 45 giây chưa hết hạn. | Hướng dẫn client truyền `take_over: true` để thu hồi quyền phát sang thiết bị mới. |
| **API trả 403 Forbidden khi tạo Content Job** | Cờ `staff_ai_enabled` đang tắt trong cấu hình hệ thống. | Kiểm tra biến môi trường `STAFF_AI_ENABLED=true` trong cài đặt API container. |
| **Job bị báo QuotaExceededError** | Hạn mức `max_cost_micros` hoặc `max_audio_seconds` của tài khoản staff đã chạm trần. | Admin kiểm tra qua `GET /staff/ai-usage/summary` và tăng hạn mức trong bảng `ai_quota_accounts`. |
| **Search không trả về phân cảnh mới** | Transcript tiếng Nhật đã tạo nhưng chưa qua bước phê duyệt (`POST /approve`). | Giáo viên/Admin kiểm tra và nhấn Approve trong CMS để đưa transcript vào Search Projection. |
| **Publish trả conflict sau khi HLS đã QA** | Manifest hoặc một segment HLS đã đổi nên checksum bundle không còn khớp snapshot. | Dừng publish, dựng lại toàn bộ bundle từ nguồn đã pin, register HLS và lặp lại QA; không sửa checksum trực tiếp trong DB. |
