# Tổng kết Web UI và learning loop

Candidate chính thức: `codex/web-ui-learning-loop`. Base đã fetch lại:
`origin/main` tại `908b6bb`. Source được kiểm chứng: `f446c88`, tree `cb94a5c`.

Báo cáo chi tiết và raw evidence mới nhất:

- [Web learning-loop review fixes](docs/qa/2026-09-08-web-learning-loop-review-fixes.md)
- [Evidence follow-up 2026-09-08](docs/qa/evidence/web-learning-loop-review-fixes-20260908/followup/README.md)
- [Kế hoạch đã thực hiện](docs/superpowers/plans/2026-09-08-web-learning-loop-review-fixes.md)

## Kết quả hiện tại

- Catalog và Progress cô lập mọi response theo auth epoch, user/token và operation
  generation; response của tài khoản hoặc request cũ không được cập nhật state mới.
- Đổi mục tiêu chỉ gửi trường được sửa; 409 tải revision mới trong cùng operation.
- DELETE history nhận 202, vô hiệu hóa read cũ ngay lập tức và dùng projection server.
- Ngày activity giữ nguyên `YYYY-MM-DD`; range bảy ngày dùng current policy timezone và
  ngày lịch qua DST. Pending `effective_at` hiển thị theo timezone của pending policy.
- Learning-loop E2E phát clip thật qua UI, nhận checkpoint có active time dương, tạo
  progress legacy bằng phiên hơn 60 giây, rồi chứng minh progress/activity không đổi
  sau khi history bị ẩn.
- CMS fixture vẫn đi qua upload, submit QA, review approve và publish; HLS, recovery,
  accessibility, auth, staff và sync giữ hồi quy.

## Verification

| Kiểm tra | Kết quả |
|---|---:|
| Domain | 3/3 PASS ở `18c9e02`; không đổi, không chạy lại |
| Web typecheck + unit | 54/54 PASS |
| Web production build | PASS, 10 route |
| Architecture guard | 20/20 PASS |
| Anti-textbook guard | PASS |
| Full E2E Chromium + WebKit | 106/106 PASS |
| Capability off Chromium + WebKit | 16/16 PASS |

Các evidence 2026-09-06 và 2026-09-07 trong repo là lịch sử của candidate cũ; chúng
không được dùng để chứng nhận các sửa auth/date/playback hiện tại. Follow-up thêm
race UI đổi tài khoản khi focus và reset state/busy; A → B → A, body deferred và
unmount được kiểm tra ở unit ownership gate. Backend/schema không đổi; không chạy lại toàn API suite.

Engineering PASS không thay thế nghiệm thu Safari/iPhone/iPad vật lý và không phải xác
nhận production. DELETE mới được chứng minh ở projection; chưa khẳng định worker đã xóa
vật lý record. Checkout gốc còn thay đổi chưa commit và được giữ nguyên; trạng thái sạch
chỉ áp dụng cho candidate sau commit evidence.
