# Biên bản Đo tải & Hiệu năng: PR7 (Vòng học A–C) [SUPERSEDED]

> [!WARNING]
> **Tài liệu lưu trữ lịch sử — Không dùng làm gate hiện hành:**
> Biên bản này ghi nhận kết quả đo thử nghiệm cục bộ trên PR7 với target 250ms. Trên nền nhánh chính hiện tại, chỉ tiêu SLO và kiểm thử hiệu năng chính thức được quy định tại `apps/api-python/differential/remediation_load.py` (target 100ms dưới tải đồng thời cao). Báo cáo này được giữ lại dưới dạng lưu trữ lịch sử để đối chiếu.

- **Thời điểm đo:** 2026-09-07T12:55:21.803535+00:00
- **Hạ tầng:** PostgreSQL test container (DDL Alembic 0009, 28 bảng), FastAPI async UoW
- **Kết quả tổng thể:** PASS (Đạt toàn bộ chỉ tiêu lịch sử)

## 1. Kết quả chi tiết theo tiêu chuẩn kiến trúc

| Endpoint / Hành vi | Số mẫu | Target p95 | p50 | p90 | p95 thực tế | p99 | Đánh giá |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `GET /me/activity` | 50 | $\le 300$ ms | 5.54 ms | 6.59 ms | **7.07 ms** | 18.11 ms | PASS |
| `PUT /playbacks/{id}/checkpoints/{seq}` | 50 | $\le 250$ ms | 9.51 ms | 10.84 ms | **11.14 ms** | 13.19 ms | PASS |
| `DELETE /me/watch-history` (202 Accepted) | 25 | $\le 500$ ms | 5.79 ms | 6.89 ms | **7.54 ms** | 9.05 ms | PASS |

## 2. Kết luận
- Toàn bộ các endpoints đo tải đều có p95 thấp hơn đáng kể so với ngưỡng trần quy định.
- Cơ chế single active lease và checkpointing đạt thông lượng cao, không phát hiện hiện tượng deadlock hay pool saturation.
