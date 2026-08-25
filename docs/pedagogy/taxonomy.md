# Taxonomy nội dung CI

Owner: Content Director + Pedagogy  
Dùng cho CMS schema và `Catalog` bounded context.

## Cấp CI (v1)

Thang nội bộ, **không** map 1-1 JLPT trên UI học viên.

| `ci_level` | Tên nội bộ | Hình ảnh | Ngôn ngữ nói | Ghi chú |
|---|---|---|---|---|
| 0 | Silent world | Rõ, chậm, một việc | Rất ít từ, lặp | Gần như chỉ hình + âm thanh môi trường + vài từ |
| 1 | Here and now | Một người, một chỗ | Câu ngắn, bây giờ | Chỉ cái đang nhìn thấy |
| 2 | Simple story | 2–3 beat | Câu đơn, nối thì | Vẫn đoán được bằng hình |
| 3 | Familiar life | Tình huống đời thường | Tốc độ chậm-vừa | Ít khái niệm trừu tượng |
| 4 | Extended | Nhiều cảnh | Đoạn ngắn | Deferred library; schema cho phép, thí điểm Q1 không bắt buộc |

Học viên **không** tự chọn “N5”. Hệ thống gợi cấp theo giờ input + (Phase 5) probe. Catalog thí điểm Q1: chỉ level 0–2.

## Nhãn bắt buộc trên mỗi item

| Trường | Bắt buộc | Ghi chú |
|---|---|---|
| `id` | có | UUID |
| `ci_level` | có | 0–4 |
| `duration_seconds` | có | |
| `media_type` | có | `video` \| `audio` |
| `topic_id` | có | xem dưới |
| `visual_support` | có | `high` \| `medium` \| `low` — level 0–1 phải `high` |
| `has_l1_translation` | có | v1 phải `false` trên kênh học |
| `status` | có | `draft` \| `level_qa` \| `published` \| `archived` |
| `spoken_language` | có | luôn `ja` |

Cấm lưu `translation_vi` trên item học v1. Ghi chú sản xuất nội bộ được phép ở CMS staff-only, không lộ client học viên.

## Chủ đề (`topic`) v1 thí điểm

`daily_home`, `food`, `body`, `go_somewhere`, `nature`, `people` — vật cụ thể, không `keigo`, không `politics`.

## Rubric “có comprehensible không” (Level QA)

Pass khi **người không biết tiếng Nhật** (hoặc Pedagogy đóng vai) vẫn nắm được việc đang xảy ra nhờ hình. Fail nếu nghĩa chỉ tới từ chữ hoặc từ đã học trước.

Clip fail không `published`.
