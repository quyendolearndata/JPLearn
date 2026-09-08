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
| S-SERIES | Series đã xuất bản và thứ tự episode | `/series`, `/series/[id]` | UC-L20, UC-T07 | Chỉ hiển thị item learner truy cập được; CTA mở đúng clip |
| S-LIBRARY | Cảnh đã lưu và bộ sưu tập cá nhân | `/library`, `/library/collections/[id]` | UC-L15, UC-L21 | Capability gate; đổi tên, sắp xếp và xóa dùng revision |
| S-HISTORY | Lịch sử xem và xóa theo deletion job | `/history` | UC-L19 | Cursor pagination; theo dõi trạng thái xóa; không xóa progress rollup |
| S-MY-REPORTS | Phản hồi nội dung của học viên | `/reports` | — | Capability gate; hiển thị trạng thái và public reply; content-report API đang thiếu UC/FR riêng trong SRS |
| S-STAFF-LIST | Danh sách nội dung CMS | `/staff` | UC-T02b | Lọc status/CI, phân trang; teacher/admin truy cập |
| S-STAFF-NEW | Tạo clip draft mới | `/staff/new` | UC-T02 | Form nhập `catalogWriteFields`; validation chặt chẽ |
| S-STAFF-EDIT | Chi tiết, sửa draft & media | `/staff/[id]` | UC-T03, UC-T04, UC-T05, UC-A01 | Sửa draft với revision; upload MP4; nộp QA; admin publish/unpublish |
| S-STAFF-STUDIO | Scenes, transcript Nhật và AI draft | `/staff/[id]/studio` | UC-T06, UC-T08, UC-T10 | Scene/content CAS; transcript revision + QA; AI chỉ tạo draft, không tự publish |
| S-STAFF-SERIES | Quản lý series và episode | `/staff/series`, `/staff/series/[id]` | UC-T07 | Metadata/items CAS; teacher nộp QA; admin publish/return/unpublish |
| S-STAFF-REPORTS | Hàng đợi báo lỗi nội dung | `/staff/reports` | — | Lọc trạng thái, phản hồi công khai, ghi chú nội bộ và audit log; chờ BA cấp UC/FR riêng |
| S-STAFF-JOBS | Tra cứu và xử lý content job | `/staff/jobs` | UC-T08 | Tra cứu theo job ID; cancel; apply có transcript revision và source validation |
| S-STAFF-AI-USAGE | Ledger và tổng hợp AI usage | `/staff/ai-usage` | UC-T08, UC-A03 | Teacher xem usage của mình; admin có tổng hợp; capability gate từ API |
| S-FLAGS-GATE | Ẩn UI nếu flag tắt | (toàn app) | UC-A02 | Không nút Nói / Thẻ / Ngữ pháp / Bản dịch |

## Web (lean-forward)

- Bố cục responsive 3 tầng: Public (Landing), Learner (Catalog, Series, Library, Session, Progress, History, Reports), Staff (`/staff/*`).
- Mẫu A+B (2026-09-07, tham chiếu: [design-ab.html](../../design/reference/design-ab.html)): nền kem, xanh sage, sidebar cố định; hero minh họa và lưới catalog 3 cột. Tiến độ xem tại route riêng.
- Tìm chủ đề lọc metadata đang tải ở client; lọc cấp CI gọi API. Minh họa SVG là hình chủ đề, có nhãn, không phải thumbnail video.
- Breakpoint ≥ 1024px cho staff bảng thao tác.


## Phone (on-the-go)

- Tab: Catalog | Phiên | Tiến độ.
- Web ≤650px: điều hướng trên cùng, catalog 2 cột; tap ảnh hoặc CTA mở phiên của đúng item.
- Không giả định iPad layout.

## iPad (lean-back)

- Catalog dạng lưới lớn; chrome mỏng.
- Vùng phiên rộng với player HLS/MP4 đang hoạt động; giữ nguyên cơ chế khôi phục phiên.
- Split view: không nhồi 2 cột quiz.

## Tokens (v1 design-system tối thiểu)

- Không dùng palette “gamification neon” kiểu streak lửa nếu gợi quiz.
- Motion chậm; không badge “+10 XP”.
- Type: UI Việt/Latin cho chrome; không giả Hán tự như điểm số.

Wireframe lo-fi đủ cổng SAD-3: năm màn S-* trên ba bề mặt (15 khung). File: [wireframes/README.md](wireframes/README.md).
