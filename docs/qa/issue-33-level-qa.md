# Level QA hồi tố — 10 clip thí điểm (issue #33)

- Ghế: **CI Level QA** · Ngày: 2026-08-25 · Issue: [#33](https://github.com/quyendolearndata/JPLearn/issues/33)
- Test mapping: **UC-Q01 / UC-Q02** (rubric CI, approve/reject — lý do nội bộ, không lộ learner)
- Rubric: [ci-rubric-clip.md](../pedagogy/ci-rubric-clip.md) · Taxonomy: [taxonomy.md](../pedagogy/taxonomy.md) · SOP: [sop-pipeline.md](../content-ops/sop-pipeline.md)
- Tính chất: **retrospective Level QA**. 10 clip đã bị đẩy `draft` → `published` qua CMS API trong phiên upload thí điểm (ghế Content), trước khi bước `level_qa` hình thức tồn tại. Quyết định này chấm nội dung như thể item đang ở `level_qa`; ghế QA **không** gọi publish endpoint.

## Bằng chứng & phương pháp

1. **Hình ảnh:** trích 3–4 frame mỗi clip bằng `ffmpeg` (đầu/giữa/cuối; riêng `fold-clothes` và `bedtime` trích thêm frame ~8,5s để kiểm hành động kết thúc), chấm test "người xem không biết tiếng Nhật": nhìn hình có nắm được việc đang xảy ra không.
2. **Thoại:** đối chiếu bảng script tại [issue-12-clips.md](issue-12-clips.md) (Kyoko TTS, khớp brief) — kiểm ít từ, lặp, gắn vật đang thấy, không giảng giải.
3. **Metadata:** API `:3001` đang chạy (`/health` ok). Public shape `GET /catalog` chỉ lộ `id, ci_level, duration_seconds, media_type, topic_id, visual_support, playback_url` — **không** có trường dịch L1 nào lộ ra client (đạt "no L1 channel" ở tầng API). Kiểm chéo DB qua Prisma: cả 10 item `has_l1_translation=false`, `spoken_language=ja`, `visual_support=high`, `ci_level ∈ {0,1}`, `status=published`, `titleInternal` khớp tên file. Map file ↔ item bằng md5 (10/10 khớp).
4. **Burn-in:** không phát hiện chữ/caption trên 32 frame đã xem (đúng checklist #12: prompt Veo cấm caption; clip rửa tay Commons không phụ đề).

## Bảng chấm (10 clip)

PASS/FAIL từng tiêu chí; verdict theo nội dung clip. Cột Metadata = các trường dữ liệu (`has_l1_translation`, `spoken_language`, `ci_level`/`visual_support`, topic hợp taxonomy). Thứ tự workflow xử lý riêng ở mục sau.

| # | File (clip) | Visual first | Speech sparse | Level + visual_support | No L1 | Metadata | Verdict | Lý do FAIL |
|---|---|---|---|---|---|---|---|---|
| 1 | `level-0-breakfast.mp4` | PASS — người uống nước, bàn ăn sáng có bánh mì | PASS — みず/のむ/パン lặp, gắn vật đang thấy | PASS — 0 + high | PASS — không chữ | PASS | **PASS** | — |
| 2 | `level-0-kitchen.mp4` | PASS — đặt cốc lên bàn, cận cốc cạnh bếp | PASS — コップ/テーブル/おく | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 3 | `level-0-wash-hands.mp4` | PASS — xoa xà phòng, xả tay dưới vòi (32s, Commons CC BY-SA 2.0) | PASS — て/あらう/きれい; "きれい" là kết quả nhìn thấy của hành động, chấp nhận ở L0 | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 4 | `level-0-put-on-jacket.mp4` | PASS — xỏ tay áo khoác, cài nút | PASS — ジャケット/きる/ボタン | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 5 | `level-0-fold-clothes.mp4` | PASS — gấp áo trên giường → cất vào tủ (xác nhận frame 8,5s) | PASS — シャツ/たたむ/しまう; "しまう" có hành động cất tương ứng cuối clip | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 6 | `level-0-boil-water.mp4` | PASS — ấm trên bếp, hơi nước bốc mạnh | PASS — おゆ/わく/あつい; "あつい" neo vào hơi bốc, chấp nhận ở L0 | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 7 | `level-0-bedtime.mp4` | PASS — xỏ dép → ngồi giường → tay tắt đèn | PASS — スリッパ/けす/おやすみ; "おやすみ" là chào xã giao đúng ngữ cảnh tắt đèn đi ngủ | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 8 | `level-0-tidy-books.mp4` | PASS — xếp sách lên kệ, kệ sách ngăn nắp | PASS — ほん/ならべる/たな, 100% vật/hành động đang thấy | PASS — 0 + high | PASS | PASS | **PASS** | — |
| 9 | `level-1-open-door.mp4` | PASS — cầm túi mở cửa bước ra, cận tay nắm cửa | PASS — ドア/あける/いってきます; cụm chào khi ra khỏi nhà khớp hình | PASS — 1 + high | PASS | PASS | **PASS** | — |
| 10 | `level-1-pack-bag.mp4` | PASS — bày sách cạnh ba lô → nhét sách vào ba lô | PASS — かばん/ほん/いれる/いこう; 4 cụm vẫn thưa, lặp, gắn vật (L1 cho phép câu ngắn) | PASS — 1 + high | PASS | PASS | **PASS** | — |

## Ghi chú workflow (nợ quy trình)

- SOP bước 5→6→7 cấm nhảy `draft` → `published` bỏ Level QA; rubric cũng liệt "nhảy draft → published" vào danh sách Fail. Pilot **đã vi phạm thứ tự này** cho cả 10 clip (một phiên API, trước khi ghế Level QA chấm hình thức). Đây là **nợ workflow của pipeline**, không phải lỗi nội dung clip; quyết định hồi tố này chính thức hóa bước 6 bị bỏ qua.
- Vì nội dung 10/10 đạt 5 tiêu chí rubric, hành động bắt buộc theo từng clip: **keep published — giữ nguyên published, không unpublish, không quay lại.** Nợ workflow ghi nhận một lần tại đây; từ nay mọi item mới bắt buộc qua `level_qa` (không còn ngoại lệ).
- Nếu clip nào FAIL nội dung, hành động sẽ là: unpublish → về `draft` kèm lý do nội bộ, hoặc re-shoot. Đợt này không có clip FAIL.

## Nợ riêng (không phải rubric fail)

- **Duration debt:** 9 clip Veo dài 10s (clip rửa tay 32s) — mỏng hơn chuẩn clip người thật 70–95s đã hoãn trong #12. Clip 10s đạt chuẩn *pilot level 0* (một việc, ít từ lặp), nhưng không đủ cho kho chính thức. Ghi nợ để Production/Content theo dõi, không ảnh hưởng verdict.
- **Item ngoài phạm vi #33:** DB còn `seed-ci0-daily-home` (`published`, 30s, **không có playback_url**) và `seed-draft-food` (`draft`, đúng trạng thái). Item published không media là bất thường — đề nghị Admin kiểm/unpublish hoặc gắn media; không thuộc thẩm quyền quyết định của QA trong issue này.

## Tổng kết

- **10/10 PASS nội dung** (cả 5 tiêu chí rubric, test "người xem không biết tiếng Nhật" đạt trên frame trích xuất).
- **Workflow debt đã ghi nhận:** pilot bypass `level_qa`; tài liệu này là quyết định Level QA hồi tố thay thế, nội dung đủ chuẩn để publish đứng yên.
- **Clip FAIL:** không có.
- Hành động tiếp theo: không đổi trạng thái CMS; Content/Admin tham chiếu quyết định này nếu cần bằng chứng UC-Q01/Q02 cho 10 item; xử lý `seed-ci0-daily-home` (Admin).
