# UI / IA shell — ba bề mặt

Design Lead. Mỗi màn hình map use case. **Không** vẽ màn hình ngữ pháp, flashcard, hay phụ đề Việt.

Onboarding/cài đặt: tiếng Việt. Chrome học: tối giản, không giải thích grammar.

## Màn hình chung (mọi bề mặt)

| ID màn | Việc | Route | UC | Ghi chú |
|---|---|---|---|---|
| S-LANDING | Giới thiệu phương pháp CI & CTA | `/` | — | Landing công khai, thẩm mỹ Tonmana Nhật đương đại, cam kết trung thực |
| S-LOGIN | Email / mật khẩu / đăng ký / đăng xuất | `/login` | UC-L01, UC-T01 | Staff và learner cùng login; route sau role; thông báo logout mọi thiết bị |
| S-CATALOG | Catalog theo `ci_level` (S-HOME) | `/catalog` | UC-L02, UC-L10 | Bộ lọc CI qua API; card từ metadata public; empty/error/retry phân biệt |
| S-SESSION | Vòng học & phiên phát CI | `/session` | UC-L03, UC-L04, UC-L10 | Phát clip đã chọn; record `sessionStorage` theo user/tab, không lưu clip/signed URL; logout xoá record UI của user hiện tại, không end server session; hỗ trợ Idempotency & khôi phục |
| S-PROGRESS | Phút CI + cấp hiện tại | `/progress` | UC-L05 | Tự làm mới sau khi end; không điểm, không % bài |
| S-STAFF-LIST | Danh sách nội dung CMS | `/staff` | UC-T02b | Lọc status/CI, phân trang; teacher/admin truy cập |
| S-STAFF-NEW | Tạo clip draft mới | `/staff/new` | UC-T02 | Form nhập `catalogWriteFields`; validation chặt chẽ |
| S-STAFF-EDIT | Chi tiết, sửa draft & media | `/staff/[id]` | UC-T03, UC-T04, UC-T05, UC-A01 | Sửa draft với revision; upload MP4; nộp QA; admin publish/unpublish |
| S-FLAGS-GATE | Ẩn UI nếu flag tắt | (toàn app) | UC-A02 | Không nút Nói / Thẻ / Ngữ pháp / Bản dịch |

## Web (lean-forward)

- Bố cục responsive 3 tầng: Public (Landing), Learner (Catalog, Session, Progress), Staff (/staff/*).
- Cột catalog rộng, tiến độ luôn nhìn thấy.
- Breakpoint ≥ 1024px cho staff bảng thao tác.


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
