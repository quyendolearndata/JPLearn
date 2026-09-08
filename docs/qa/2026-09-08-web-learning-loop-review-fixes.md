# Web learning-loop review fixes — 2026-09-08

Trạng thái: **Engineering PASS** trên source commit `f446c88`, tree `cb94a5c`.
Candidate `codex/web-ui-learning-loop` kế thừa `origin/main` `908b6bb`; remote ref đã
được fetch lại trước khi chốt và base này vẫn là tổ tiên trực tiếp của candidate.

Ghế BA giữ phạm vi FR-ID-002, FR-LRN-001, FR-WAT-001, FR-HIS-001 và FR-REC-001.
Ghế Web sửa Catalog (S-L02), Phiên (S-L03) và Tiến độ (S-L04). QA kiểm chứng trên
PostgreSQL test tách biệt; không thay API, schema hay backend semantics.

## Thay đổi đã thực hiện

- Mỗi request ở Catalog/Progress có owner gồm auth epoch, user ID, token, scope và
  generation. Logout, đổi tài khoản, A → B → A, unmount và request mới đều làm response
  cũ mất quyền cập nhật state. `catch` và `finally` cũng kiểm tra owner nên thao tác cũ
  không thể tắt busy state của thao tác mới.
- Auth change xóa ngay progress, preferences, activity, history, recommendations,
  capability, notice/error và busy state. React Strict Mode có vòng activate/dispose
  riêng để setup lần hai vẫn dùng được.
- DELETE 202 vô hiệu hóa read generation ngay khi response được chấp nhận, xóa history
  trên UI và đọc lại projection server. Client không còn tự lọc bằng cutoff closure.
- PUT goal chỉ gửi `expected_revision` và `daily_goal_minutes`; timezone/topic hiện tại
  không bị gửi lại ngoài ý muốn. Refresh sau 409 vẫn thuộc operation ban đầu.
- Ngày lịch `YYYY-MM-DD` không đi qua `new Date(dateOnly)`. Khoảng 7 ngày lấy ngày hiện
  tại theo current policy timezone rồi trừ sáu ngày lịch, nên giữ đúng qua DST và ranh
  giới tháng/năm. `effective_at` vẫn được format như timestamp theo timezone của pending
  policy.
- E2E chính bỏ seed playback trực tiếp. Test bấm Phát, xác nhận `currentTime` tăng,
  checkpoint nhận active time dương, playback end thành công, phiên legacy thực vượt
  60 giây, history đúng item và hai số progress/activity được giữ nguyên qua DELETE 202
  và reload.
- Race filter dùng response barrier để CI0 trả sau CI4. Các ca capability off/403,
  conflict 409, HTTP 500 và offline kiểm tra thông báo/fallback cụ thể.
- Follow-up sửa Progress khi tài khoản trong storage thay đổi và cửa sổ nhận focus:
  xóa state/busy của người cũ và tăng auth epoch trước khi tải dữ liệu mới. Thêm năm
  ca race E2E mỗi engine: PUT, refresh sau 409, DELETE trả chậm khi đổi A → B,
  GET history cũ sau DELETE 202 và mất token trước mutation.

## Kết quả kiểm chứng cuối

| Hạng mục | Kết quả |
|---|---:|
| Domain test | 3/3 PASS ở `18c9e02`; không đổi domain, không chạy lại |
| Web typecheck + unit | 54/54 PASS |
| Next.js production build | PASS, 10 route |
| Architecture guard | 20/20 PASS |
| Anti-textbook guard | PASS |
| Full E2E Chromium + WebKit | 106/106 PASS, 53 mỗi engine |
| Capability off Chromium + WebKit | 16/16 PASS, 8 mỗi engine |

Log, command và SHA cuối nằm tại
[evidence follow-up](evidence/web-learning-loop-review-fixes-20260908/followup/README.md).
Ảnh pending goal/409 và log lần trước giữ tại [evidence `18c9e02`](evidence/web-learning-loop-review-fixes-20260908/README.md);
không dùng ảnh cũ chứng nhận race mới. Backend/schema không đổi, không chạy lại toàn bộ API suite.

## Lịch sử candidate

Source đã kiểm chứng có 9 commit sau main:

1. `2d145e0` — UI A+B và accessible shell.
2. `578f410` — tích hợp learning-loop API.
3. `2f68462` — tài liệu/evidence UI ban đầu.
4. `66ef201` — lưu trữ benchmark cũ.
5. `f3be90b` — cấu hình runner và assertion learning-loop ban đầu.
6. `1693379` — cô lập request theo auth và giữ đúng ngày policy.
7. `18c9e02` — E2E playback credit và deletion invariants.
8. `931b458` — báo cáo/evidence vòng kiểm chứng trước.
9. `f446c88` — reset identity khi focus và regression race bổ sung.

Commit evidence tiếp theo chỉ chứa README, walkthrough, plan/docs/evidence; mã nguồn
và test được kiểm chứng không đổi.

## Giới hạn

- Chromium và WebKit là browser engine tự động; chưa thay thế nghiệm thu Safari,
  iPhone hoặc iPad vật lý và chưa chứng nhận production.
- Race UI dùng response barrier/mock để kiểm tra state, tách khỏi test hạch toán thật.
  A → B → A, body deferred, unmount và Strict Mode kiểm tra ở ownership-gate unit;
  chưa kiểm tra browser streaming JSON hoặc thiết bị thật cho các ca này.
- DELETE được chứng minh ẩn history ở projection ngay lập tức và giữ progress/activity.
  Lượt này không chờ worker để khẳng định record đã bị xóa vật lý.
- Checkout gốc còn 28 status entry và được giữ nguyên. Backup
  `/tmp/jplearn-backup-20260908/` vẫn tồn tại; báo cáo không tuyên bố toàn workspace sạch.
