# Review rubric CI — clip thí điểm (issue #32)

- Ghế: **Pedagogy** · Ngày: 2026-08-25 · Issue: [#32](https://github.com/quyendolearndata/JPLearn/issues/32)
- Phạm vi: chấm **mức rubric** cho batch thí điểm 10 clip ([issue-12-clips.md](issue-12-clips.md)) so với [bible](../pedagogy/bible.md) + [rubric](../pedagogy/ci-rubric-clip.md) + [taxonomy](../pedagogy/taxonomy.md). Không quyết định lại publish (Content đã chạy #13); pass/fail hình thức từng clip thuộc CI Level QA (#33).
- Cách xem: trích frame `ffmpeg fps=1/4` + đối chiếu script/brief. Spot-check 4 clip (≥3 yêu cầu, đủ 2 level): `level-0-wash-hands` (bắt buộc), `level-0-boil-water`, `level-1-open-door`, `level-1-pack-bag`.

## Chấm từng clip (5 tiêu chí rubric)

### `level-0-wash-hands.mp4` — 32s, Commons CC BY-SA 2.0 (hình người thật)

| Tiêu chí | Kết quả | Lý do một dòng |
|---|---|---|
| 1. Visual first | **PASS** | Tay + xà phòng + vòi nước + động tác chà; người không biết ja hiểu ngay "rửa tay". |
| 2. Speech | **PASS** | 「て・あらう・きれい」 lặp 2 lần, toàn vật/hành động đang thấy, không giảng. |
| 3. Level | **PASS** | `ci_level=0`, một việc một chỗ, `visual_support=high` đúng taxonomy. |
| 4. No L1 channel | **PASS** | Không caption, không chữ trên hình (nguồn y tế gốc không text). |
| 5. Metadata | **PASS** | #13 xác nhận `draft→level_qa→published` (nhảy QA bị 400), `has_l1_translation=false`, `spoken_language=ja`. |

### `level-0-boil-water.mp4` — 10s, Veo

| Tiêu chí | Kết quả | Lý do một dòng |
|---|---|---|
| 1. Visual first | **PASS** | Ấm trên bếp ga lửa xanh + hơi nước; tình huống "đun nước" đọc được bằng hình. |
| 2. Speech | **PASS (có ghi chú)** | 「おゆ・わく・あつい」 gắn hình; riêng 「あつい」 là cảm giác — khó hình hoá nhất bộ, hiện dựa vào hơi + lửa. |
| 3. Level | **PASS** | `ci_level=0`, `visual_support=high`. |
| 4. No L1 channel | **PASS** | Không caption (prompt Veo cấm caption, checklist #12). |
| 5. Metadata | **PASS** | Cùng pipeline #13; payload public không field dịch. |

### `level-1-open-door.mp4` — 10s, Veo

| Tiêu chí | Kết quả | Lý do một dòng |
|---|---|---|
| 1. Visual first | **PASS** | Genkan, cửa, giày, ô; nhân vật mở cửa bước ra — "ra khỏi nhà" rõ ràng. |
| 2. Speech | **PASS** | 「ドア・あける」 + cụm cố định 「いってきます」 gắn hành động rời nhà, đúng "here and now". |
| 3. Level | **PASS** | `ci_level=1`: một người một chỗ, cụm ngắn hiện tại. |
| 4. No L1 channel | **PASS** | Không caption/text. |
| 5. Metadata | **PASS** | Như trên. |

### `level-1-pack-bag.mp4` — 10s, Veo

| Tiêu chí | Kết quả | Lý do một dòng |
|---|---|---|
| 1. Visual first | **PASS** | Frame bắt đúng khoảnh khắc bỏ sách vào cặp; "xếp đồ đi học/đi làm" tự đọc được. |
| 2. Speech | **PASS** | 「かばん・ほん・いれる・いこう」 — vật + hành động đang thấy, lặp. |
| 3. Level | **PASS** | `ci_level=1`, `visual_support=high`. |
| 4. No L1 channel | **PASS** | Không caption/text. |
| 5. Metadata | **PASS** | Như trên. |

**Kết quả spot-check: 4/4 PASS cả 5 tiêu chí** (1 ghi chú nhẹ tại 「あつい」). 6 clip còn lại cùng pattern script (danh từ vật + động từ hành động, lặp 2 lần) và cùng pipeline sản xuất — rủi ro tương đương; CI Level QA (#33) chấm hình thức từng clip.

## Verdict batch so với bible §4 (cấm)

Không phát hiện mùi textbook nào trong 10 clip:

- **Flashcard/SRS từ vựng:** không — clip là tình huống hình + thoại, không thẻ.
- **Bài ngữ pháp / giải thích:** không — script không có một câu giảng nào ("đây là động từ…" vắng mặt).
- **Phụ đề Việt làm kênh hiểu:** không — cả 4 clip spot-check sạch chữ; prompt Veo cấm caption từ đầu.
- **Tiến độ tuyến tính kiểu SGK:** không áp dụng ở tầng nội dung; title internal (`level-0-*`) là nhãn sản xuất, không phải "Bài 12".

**Batch verdict: PASS ở mức rubric cho thí điểm** — đủ chuẩn "comprehensible" theo nghĩa người không biết tiếng Nhật vẫn nắm được việc nhờ hình (taxonomy §rubric). Đây **không** phải tuyên bố batch thay thế được clip người thật 70–95s.

## Gaps phải sửa trước clip người thật 70–95s

1. **10s ≠ 70–95s.** Clip Veo chỉ chứa 3 cụm lặp; chưa kiểm chứng được pacing chậm, nhịp nghỉ, và "một tình huống kéo dài" mà bible đòi. Rubric hiện chưa có tiêu chí độ dài/nhịp — cần bổ sung khi brief clip thật (khuyến nghị, không sửa rubric trong issue này).
2. **TTS Kyoko là giọng tổng hợp, phẳng.** Thiếu ngữ điệu caregiver speech (chậm, cao độ biến thiên, nhấn vào từ-khoá-hình). Chấp nhận cho thí điểm; clip thật phải là giọng người.
3. **Thiếu âm thanh môi trường.** Pipeline thay toàn bộ audio (không mix), nên level 0 mất lớp "âm thanh thế giới" (tiếng nước chảy, nước sôi) mà taxonomy ghi cho level 0. Clip thật cần giữ âm môi trường dưới thoại.
4. **Không có gesture/pointing redundancy.** Veo anime chỉ diễn hành động; không ai *chỉ* vào vật, không ánh nhìn neo nghĩa. Với 「あつい」(cảm giác, khó hình hoá) clip thật nên có hành động chạm-rụt tay thay vì chỉ hơi nước.
5. **Đơn điệu style.** 9/10 clip cùng một style anime Veo; chỉ wash-hands là footage thật — và chính nó cho visual support rõ nhất batch. Ưu tiên footage thật cho từ khó hình hoá.

## Đề nghị (ghi nhận, không sửa tài liệu trong issue này)

- Khi viết brief clip thật: thêm dòng "gesture chỉ vật + âm môi trường" vào mẫu brief một trang trong [sop-pipeline.md](../content-ops/sop-pipeline.md).
- Giữ nguyên cấm caption trong mọi prompt quay/dựng.

---

**Chữ ký:** Pedagogy — Quyen Do — 2026-08-25 — Batch 10 clip thí điểm PASS mức rubric (không mùi grammar/flashcard/L1); không thay thế clip người thật 70–95s; flags `speaking_enabled` / `l1_subtitles_enabled` / `grammar_enabled` / `flashcards_enabled` giữ **false**.
