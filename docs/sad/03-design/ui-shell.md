# UI / IA shell — ba bề mặt

Design Lead. Mỗi màn hình map use case. **Không** vẽ màn hình ngữ pháp, flashcard, hay phụ đề Việt.

Onboarding/cài đặt: tiếng Việt. Chrome học: tối giản, không giải thích grammar.

## Màn hình chung (mọi bề mặt)

| ID màn | Việc | UC | Ghi chú |
|---|---|---|---|
| S-LOGIN | Email / mật khẩu | UC-L01, UC-T01 | Staff và learner cùng login; route sau role |
| S-HOME | Catalog theo `ci_level` | UC-L02 | Empty state hợp lệ |
| S-SESSION | Bắt đầu / kết thúc phiên | UC-L03, UC-L04 | Nút rõ; không bắt play video |
| S-PROGRESS | Phút CI + cấp hiện tại | UC-L05 | Không điểm, không % bài |
| S-FLAGS-GATE | Ẩn UI nếu flag tắt | UC-A02 | Không nút Nói / Thẻ / Ngữ pháp |

## Web (lean-forward)

- Cột catalog rộng, tiến độ luôn nhìn thấy.
- `/staff/*`: CMS list, tạo item, upload, submit QA, publish (admin).
- Breakpoint ≥ 1024px cho staff bảng.

## Phone (on-the-go)

- Tab: Catalog | Phiên | Tiến độ.
- Catalog một cột, tap item (nếu có) không mở dịch.
- Không giả định iPad layout.

## iPad (lean-back)

- Catalog dạng lưới lớn; chrome mỏng.
- Vùng phiên chiếm phần lớn màn (chỗ dành Phase 5 video).
- Split view: không nhồi 2 cột quiz.

## Tokens (v1 design-system tối thiểu)

- Không dùng palette “gamification neon” kiểu streak lửa nếu gợi quiz.
- Motion chậm; không badge “+10 XP”.
- Type: UI Việt/Latin cho chrome; không giả Hán tự như điểm số.

Wireframe lo-fi đủ cổng SAD-3: năm màn S-* trên ba bề mặt (15 khung). File: [wireframes/README.md](wireframes/README.md).
