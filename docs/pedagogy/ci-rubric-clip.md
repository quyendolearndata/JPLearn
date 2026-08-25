# Rubric CI — clip level 0–1

Owner: Head of Pedagogy. Dùng ở bước Level QA (UC-Q01/Q02).

## Pass (tất cả đúng)

1. **Visual first:** Người chưa biết tiếng Nhật vẫn hiểu tình huống chỉ qua hình/cử chỉ.
2. **Speech:** Ít, lặp, gắn vật đang thấy. Không giảng “đây là động từ …”.
3. **Level:** `ci_level` 0 hoặc 1; `visual_support` = high cho clip đầu.
4. **No L1 channel:** Không phụ đề Việt, không text dịch trên learner card.
5. **Metadata:** `has_l1_translation=false`, `spoken_language=ja`, status workflow đúng SOP.

## Fail (một mục sai → về draft)

- Burn-in phụ đề Việt làm kênh hiểu nghĩa.
- Thoại trừu tượng không có hình (chỉ nghe không thấy).
- Title/card kiểu “Bài 12: thì quá khứ”.
- Nhảy `draft` → `published`.

## Train clip 1–2

Pedagogy + Teacher xem 2 clip mẫu (hoặc storyboard) và ghi pass/fail + lý do nội bộ. Ghi vào CMS comment nội bộ, không hiện learner.
