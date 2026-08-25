# SOP nhà máy nội dung thí điểm

Bám [BPMN](../sad/02-analysis/processes.md). Mục tiêu Q1: **pipeline chạy** 10–20 clip level 0–1, không ra mắt thư viện.

## Vai trên một clip

| Bước | Vai | DoD |
|---|---|---|
| 1. Brief | Pedagogy + Teacher | `topic_id`, `ci_level` 0–1, `visual_support=high`, không thoại trừu tượng |
| 2. Quay | Production / Teacher | Quyền người xuất hiện đã ký |
| 3. Draft CMS | Teacher | UC-T02 metadata; `has_l1_translation=false` |
| 4. Upload | Teacher | UC-T03 |
| 5. Nộp QA | Teacher | UC-T04 `level_qa` |
| 6. Rubric | Level QA / Pedagogy | Pass = người không biết tiếng Nhật vẫn nắm việc nhờ hình |
| 7. Publish | Admin | UC-A01; kiểm 3 client ≤ NFR-PERF-001 |
| 8. Archive nếu hỏng quyền | Admin | `archived` |

Cấm nhảy `draft` → `published` bỏ bước 6.

## Brief một trang

- Tình huống một câu (nội bộ, tiếng Việt hoặc Anh): “Người rót nước, uống.”
- Cấm: dạy “đây là động từ uống”.
- Thoại: ít, lặp, gắn vật đang nhìn thấy.

## Lịch thí điểm

Không calendar marketing. Work-in-progress: 2 clip/tuần khi Sóng 1 đủ Teacher part-time.

## Schema CMS

Xem [cms-schema.md](cms-schema.md) — khớp data dictionary, không thêm field dịch công khai.
