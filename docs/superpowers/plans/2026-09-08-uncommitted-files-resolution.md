# Kế hoạch xử lý các file chưa commit — 2026-09-08

## Kết luận và phạm vi

Đánh giá tĩnh trên checkout `codex/fastapi-backend-hardening` tại `d6b1d05`.
Remote `main` đã xác minh trực tiếp ở `908b6bb`. Có **17 file tracked bị sửa + 30 file untracked = 47 file** trước khi tạo tài liệu này; staged rỗng. Phần tracked có 1.391 dòng thêm / 310 dòng xóa. Không coi số dòng hay tổng test lịch sử là bằng chứng sẵn sàng commit.

Phần lớn là công việc Web A+B và tích hợp learning loop đáng giữ; chưa nên commit chung ngay. Tài liệu này chỉ lập kế hoạch, không sửa mã, stage, xóa, chuyển nhánh hay thay dữ liệu.

Ghế BA: đối chiếu FR-CAT-004, FR-LRN-001, FR-WAT-001, FR-HIS-001, FR-REC-001 và FR-FLG-002. Ghế Web: màn Catalog, Tiến độ, Phiên, Đăng nhập, trang chủ và shell; NFR-A11Y-001. Không thay chữ ký nghiệm thu Pedagogy/Design/Ops.

## Phát hiện cần xử lý

1. **P1 — Cần đưa thay đổi lên nền main trước khi đánh giá khả năng merge.** Nhánh hiện tại thiếu CMS QA và migration 0019. `recovery.spec.ts` và `staff.spec.ts` trên main có bước approve; bản local chưa có. Đây là khác biệt nền nhánh, không phải người dùng chủ động xóa QA. Chép nguyên file local lên main sẽ làm mất bước này. `sync.spec.ts` đã có cùng ý tưởng đọc lại danh mục trên main, chỉ khác khóa so sánh URL/ID.
2. **P1 — Phản hồi cũ có thể khôi phục dữ liệu tài khoản trước.** `progress/page.tsx` gọi loadData khi auth/focus đổi nhưng không có request generation/cancel hoặc kiểm tra identity trước setState. Yêu cầu cũ có thể hoàn tất sau logout/login; lỗi các API phụ không xóa state trước đó. Catalog có rủi ro phản hồi sai thứ tự khi đổi CI filter và giữ recommendations cũ khi request thất bại. Đây là kết luận từ luồng mã, chưa chạy tái hiện trên browser.
3. **P1 — Mục tiêu học và múi giờ chưa bám hợp đồng.** Progress chỉ đọc trường phẳng, bỏ `current_policy`/`pending_policy`; chọn mục tiêu không thể hiện thời điểm có hiệu lực. Khoảng ngày dùng `toISOString()` theo UTC thay vì policy timezone. Phải phân biệt active watch và phút phiên legacy; câu giới thiệu hiện khái quát thời gian phát cho toàn bộ tiến độ là chưa chính xác theo FR-WAT-001.
4. **P2 — Lỗi thao tác bị bỏ qua.** PUT mục tiêu gặp 409/4xx hoặc DELETE lịch sử gặp non-202 không có thông báo rõ; nhiều catch rỗng biến lỗi thành trạng thái trống. Sau 202 cần giữ deletion_id/cutoff/status, thông báo đúng việc ẩn ngay và xử lý nền; không tuyên bố đã xóa vật lý. Không để reload cũ điền lại history sau khi vừa ẩn.
5. **P2 — E2E mới chưa chứng minh hành vi nêu trong tên test.** `learning-loop.spec.ts` chỉ kiểm tra nút Phát có mặt, không click/kiểm tra thời gian thực; thao tác mục tiêu và xóa đặt trong `if isVisible`. Tài khoản mới không có lịch sử nên test xóa có thể PASS mà không gửi DELETE. Cần fixture bắt buộc và kiểm tra phản hồi/lưu lại sau reload.
6. **P2 — Tài liệu và evidence có phạm vi cũ.** UI A+B report ghi candidate trên `4ead713`, 35 unit/88 E2E, trong khi local hiện có thêm preferences/history/recommendations. Không dùng kết quả đó chứng nhận toàn bộ local. README nói 10 clip có sẵn, ffmpeg tùy chọn, AI worker hoạt động và guard bảo vệ toàn diện là quá rộng hoặc phụ thuộc môi trường; cần bám code/runbook hiện tại. Walkthrough có route transcript cũ và thao tác publish thiếu review. Số test lịch sử giữ kèm ngày/SHA, không sửa thành số mới nếu chưa chạy.
7. **P2 — Benchmark cũ không thể dùng đóng SLO.** `benchmark_perf.py` ghi checkpoint target 250ms; báo cáo PR7 kết luận PASS toàn bộ và không deadlock/pool saturation trong khi remediation dùng target 100ms, burst đã thất bại và có harness đo chi tiết trên main. Đưa cặp này vào lưu trữ lịch sử hoặc bỏ khỏi source sau khi đã bảo toàn, không chạy như gate hiện hành.
8. **P2 — Mockup đang nằm trong public.** `apps/web/public/design-ab.html` sẽ được phục vụ như trang tĩnh, chứa dữ liệu minh họa. Đề xuất chuyển vào docs/design/reference, cập nhật link. Chỉ giữ public nếu có chủ đích cung cấp demo và nhãn minh họa rõ ràng.

## Nhóm xử lý và thứ tự commit

### Bước 0 — Bảo toàn và dựng ứng viên trên main

- [ ] Lưu patch nhị phân tracked, bản sao đủ untracked, danh sách SHA256 và HEAD gốc ra thư mục ngoài repo; kiểm tra bản sao đọc được.
- [ ] Tạo nhánh `codex/web-ui-learning-loop` từ main mới nhất trong checkout riêng.
- [ ] Áp dụng patch ba chiều và copy untracked có chọn lọc; giữ main làm nguồn cho CMS review, migration, hợp đồng API và test approve.
- [ ] Đối chiếu recovery/staff/sync từng hunk. Giữ test đổi tài khoản bằng browser context riêng vì UI login mới ẩn form khi đã đăng nhập. Giữ đọc danh mục mới trong sync, chuyển sang data-item-id theo card A+B, bắt buộc ID không null và danh sách không rỗng.
- [ ] Không merge nhánh cũ bằng overwrite file; không reset/stash-pop lên checkout đang có thay đổi của người dùng.

### Commit 1 — Giao diện A+B và điều hướng

Scope: globals.css, layout, home, login, chrome, topic-art, phần trình bày catalog/progress/session/ci-player; test shell/a11y/staff/recovery/sync liên quan. Không gộp gọi API mới vào commit trình bày nếu có thể tách hunk sạch.

- [ ] Giữ hero, minh họa chủ đề, card dùng đúng item ID; tìm chủ đề được mô tả là lọc metadata local, không phải search câu/phân cảnh.
- [ ] Kiểm tra CSS ảnh hưởng CMS mới: textarea ghi chú, duyệt/từ chối, history, lỗi và disabled/loading.
- [ ] Rà CSS cũ bị override, biến màu và responsive; không dọn bằng xóa rộng khi chưa xác minh nơi sử dụng.
- [ ] Xác minh build với next/font/google và fallback; ghi rõ nếu build cần truy cập tải font.
- [ ] Chuyển mockup khỏi public vào docs/design/reference; sửa ui-shell.md và link evidence.
- [ ] Typecheck/unit/guard; E2E auth, catalog, session recovery, HLS, CMS approve/publish; axe + keyboard; ảnh desktop 1440, iPad 820, phone 390 và empty/error/loading/active.

### Commit 2 — Tích hợp API learning loop đúng hợp đồng

Scope: phần logic catalog/progress + learning-loop.spec.ts; nếu cần thêm helper nhỏ và test race/policy trong lib. Ưu tiên dùng DTO chung trong packages/domain sau khi đối chiếu OpenAPI main; bỏ type giả định không đúng thay vì ép kiểu che sai lệch.

- [ ] Chặn stale request theo generation và identity, clear dữ liệu cũ khi auth đổi; unmount/focus/filter không gây ghi đè.
- [ ] GET capabilities theo thiết kế hiện hành để phân biệt disabled với empty/error; fallback legacy có nhãn đúng.
- [ ] Hiển thị current_policy và pending_policy/effective_at riêng; 409 yêu cầu tải revision mới và cho người dùng thử lại, không tự ghi đè.
- [ ] Tính khoảng 7 ngày theo timezone policy; kiểm tra qua nửa đêm, UTC/local khác ngày và đổi timezone.
- [ ] DELETE 202: hiển thị trạng thái ẩn/cutoff đúng, theo dõi job nếu cần báo hoàn tất; retry không làm hiện lại lịch sử cũ, tổng phút/activity được giữ.
- [ ] E2E tạo dữ liệu thật bắt buộc: phát video và nhận checkpoint, có history trước xóa, API trả 202, reload history vắng nhưng activity/progress còn. Không dùng if để bỏ qua hành vi chính.
- [ ] Test mục tiêu thay đổi sang pending, reload vẫn đúng; lỗi 403/409/500/offline; đổi tài khoản trong khi API đang chậm; đổi filter nhanh; tắt capability.
- [ ] Kiểm tra recommendation item/CTA/reason đúng dữ liệu và trạng thái disabled/empty/error.

### Commit 3 — Tài liệu và bằng chứng có nguồn rõ ràng

Scope: README, walkthrough, ui-shell, UI evidence report, local-demo report/evidence và ảnh/log lựa chọn.

- [ ] README giữ hướng dẫn cài đặt tái lập, ffprobe bắt buộc cho đường upload đo media; giới hạn provider/feature flags và trạng thái nghiệm thu đúng; không nói clone mới tự có 10 clip local.
- [ ] Walkthrough đối chiếu API hiện tại, thêm bước ghi nhận QA trước publish; chuyển thông tin tài khoản demo thành hướng dẫn bootstrap, không dựa vào mật khẩu có sẵn.
- [ ] Local-demo/catalog.json/playback.json/ảnh: giữ như snapshot lịch sử local, ghi ngày, dữ liệu và điều kiện chạy, không chứng minh nguồn bản quyền/sư phạm bằng test playback.
- [ ] Evidence UI cũ giữ nguyên số và phạm vi; thêm evidence mới cho candidate trên main, kèm commit/tree hash và lệnh/check exit. Không giả chữ ký nghiệm thu thiết bị thật.
- [ ] Rà secret/token/PII/đường dẫn riêng trong JSON/log/ảnh trước commit; xem ảnh thực tế để xác nhận đúng trạng thái. Đánh giá hiện tại mới kiểm kê tên/dung lượng và đọc văn bản, chưa QA lại hình ảnh.
- [ ] Giữ 15 screenshot nếu cần truy vết toàn ma trận; chỉ giảm số bản sao khi đã xác định trùng, không kết luận chúng là rác.

### Bước 4 — Benchmark lịch sử và chốt working tree

- [ ] Chọn lưu trữ cặp benchmark cũ dưới docs/qa/archive với nhãn superseded và link remediation_load.py, hoặc loại khỏi repo sau khi có bản sao. Không commit như gate PASS hiện hành.
- [ ] Kiểm tra tất cả file được gán vào commit hoặc nơi lưu trữ; không bỏ quên thư mục untracked.
- [ ] Chạy kiểm tra cuối trên ứng viên đã ghép main: Web unit/typecheck, shared domain nếu DTO đổi, guard/build và toàn E2E. Chạy API suite nếu sửa backend/contract hoặc CI bắt buộc; mọi DB test dùng Docker riêng `/jplearn_test`.
- [ ] Commit theo nhóm có FR/NFR và evidence. Không push/merge trong pha chỉ đánh giá; thao tác tiếp theo thực hiện khi người dùng yêu cầu triển khai kế hoạch.
- [ ] Sau khi xác minh bản đã commit/lưu trữ, mới dọn bản gốc theo phạm vi người dùng cho phép; không xóa database, volume hay media nguồn.

## Điều kiện hoàn tất

Mỗi file trong inventory có quyết định rõ; nhánh ứng viên kế thừa main mới nhất; không mất bước duyệt QA; các lỗi policy/identity/history được kiểm thử; evidence đúng candidate; UI hoạt động trên các viewport và CMS mới. Repo không còn thay đổi chưa được giải thích. Production/physical-device/Pedagogy gates vẫn theo báo cáo riêng.

## Inventory đủ 47 file trước khi tạo plan

| File | Nhóm xử lý |
|---|---|
| `README.md` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `apps/web/e2e/a11y.spec.ts` | 0 + 1 — ghép với main, giữ QA và cập nhật locator |
| `apps/web/e2e/recovery.spec.ts` | 0 + 1 — ghép với main, giữ QA và cập nhật locator |
| `apps/web/e2e/shell.spec.ts` | 0 + 1 — ghép với main, giữ QA và cập nhật locator |
| `apps/web/e2e/staff.spec.ts` | 0 + 1 — ghép với main, giữ QA và cập nhật locator |
| `apps/web/e2e/sync.spec.ts` | 0 + 1 — ghép với main, giữ QA và cập nhật locator |
| `apps/web/src/app/catalog/page.tsx` | 1 + 2 — tách giao diện và logic API |
| `apps/web/src/app/globals.css` | 1 — giao diện A+B |
| `apps/web/src/app/layout.tsx` | 1 — giao diện A+B |
| `apps/web/src/app/login/page.tsx` | 1 — giao diện A+B |
| `apps/web/src/app/page.tsx` | 1 — giao diện A+B |
| `apps/web/src/app/progress/page.tsx` | 1 + 2 — tách giao diện và logic API |
| `apps/web/src/app/session/page.tsx` | 1 — giao diện A+B |
| `apps/web/src/components/chrome.tsx` | 1 — giao diện A+B |
| `apps/web/src/components/ci-player.tsx` | 1 — giao diện A+B |
| `docs/sad/03-design/ui-shell.md` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `walkthrough.md` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `apps/api-python/differential/benchmark_perf.py` | 4 — benchmark lịch sử, không gate hiện hành |
| `apps/web/e2e/learning-loop.spec.ts` | 2 — viết lại test hành vi bắt buộc |
| `apps/web/public/design-ab.html` | 1/3 — chuyển mockup sang docs |
| `apps/web/src/components/topic-art.tsx` | 1 — giao diện A+B |
| `docs/qa/evidence/local-demo-20260907/catalog.json` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/local-demo-20260907/catalog.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/local-demo-20260907/playback.json` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/pr7-performance-benchmark.md` | 4 — benchmark lịch sử, không gate hiện hành |
| `docs/qa/evidence/ui-ab-20260907/build.log` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/desktop-catalog.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/desktop-home.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/desktop-progress.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/desktop-session-active.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/desktop-session.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/e2e.log` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/guard.log` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/ipad-catalog.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/ipad-home.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/ipad-progress.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/ipad-session-active.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/ipad-session.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/phone-catalog.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/phone-home.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/phone-progress.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/phone-session-active.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/phone-session.png` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/unit.log` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/visual-active-check.json` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/evidence/ui-ab-20260907/visual-check.json` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
| `docs/qa/ui-ab-evidence-2026-09-07.md` | 3 — tài liệu/evidence; giữ nguồn và giới hạn |
