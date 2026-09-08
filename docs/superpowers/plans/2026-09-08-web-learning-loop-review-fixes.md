# Kế hoạch sửa các điểm review Web learning loop — 2026-09-08

## Mục tiêu và nền thực hiện

Ứng viên: `codex/web-ui-learning-loop`, HEAD đã kiểm tra `f3be90b`, kế thừa main `908b6bb`. Worktree ứng viên sạch trước khi thêm kế hoạch này.

Thực hiện tại `.worktrees/codex-web-ui-learning-loop/`. Checkout gốc vẫn chứa thay đổi chưa commit; không dùng bản ở đó để ghi đè ứng viên. Giữ backup `/tmp/jplearn-backup-20260908/`; đợt review đã kiểm tra 32 mục checksum khớp.

Ghế BA: giữ yêu cầu FR-LRN-001, FR-WAT-001, FR-HIS-001, FR-REC-001, FR-ID-002 và NFR-A11Y-001. Ghế Web thực hiện mã client; QA xác minh hành vi và evidence. Không thêm API/schema, không đổi semantics phút phiên legacy hay tự xác nhận nghiệm thu production/thiết bị thật.

Kế hoạch sửa bốn vấn đề: phản hồi khác tài khoản, ngày theo timezone, E2E chưa chứng minh hạch toán, báo cáo/evidence không đồng nhất. Việc tạo plan không thực hiện sửa mã, commit hay push.

## R1 — P1: cô lập toàn bộ tác vụ bất đồng bộ theo phiên đăng nhập

Files chính: `apps/web/src/app/progress/page.tsx`, `apps/web/src/app/catalog/page.tsx`; thêm helper/test trong `apps/web/src/lib/` nếu giúp dùng chung logic thực tế.

### Hành vi cần đạt

Ví dụ: A gửi yêu cầu đổi mục tiêu hoặc xóa lịch sử; trước khi có phản hồi, người dùng chuyển sang B. Phản hồi của A có thể hợp lệ trên server nhưng không được sửa mục tiêu, danh sách lịch sử, cutoff, thông báo hay trạng thái loading của B. Không hủy hay đảo ngược thao tác server đã được chấp nhận cho A.

- [ ] Chụp owner cho mỗi request: auth epoch + user ID/token tại lúc gửi. Epoch phải đổi khi logout, đổi tài khoản, thay phiên đăng nhập; không chỉ so user ID vì A → B → A cũng có thể nhận phản hồi cũ.
- [ ] Phân biệt auth epoch, generation của lần đọc dữ liệu và operation ID của mutation. Focus refetch không được vô tình bỏ kết quả mutation hợp lệ của cùng phiên; request cũ không được tắt loading của request mới.
- [ ] Kiểm tra owner/generation **sau mọi await**, gồm parse body và nhánh refresh GET sau 409; bao phủ success, catch và finally trước mọi setState.
- [ ] PUT goal, DELETE history, GET capabilities, catalog/recommendations và toàn loadData phải theo cùng quy tắc. AbortController nếu dùng chỉ là tối ưu, không thay owner check.
- [ ] Khi auth đổi, xóa ngay dữ liệu người cũ: progress/preferences/activity/history/recommendations, capabilities theo cơ chế hiện hành, deletionCutoff, deletionNotice, goalError/historyError và busy flags. Clear cả chuyển trực tiếp A → B, không chỉ token null.
- [ ] Cleanup khi unmount phải làm vô hiệu hóa các tác vụ đang chờ; bảo đảm setup lại dưới React Strict Mode vẫn hoạt động.
- [ ] Kiểm tra token trước khi bật busy hoặc bảo đảm early return luôn trả lại trạng thái busy.
- [ ] Khi DELETE 202 được chấp nhận, cập nhật cutoff thuộc owner hiện tại và làm vô hiệu hóa GET history cũ **ngay trong luồng xử lý**, trước khi effect chạy. Không chỉ dựa vào state closure cập nhật ở render sau.
- [ ] Đối chiếu semantics cutoff với API hiện tại; ưu tiên projection server, không tự thêm quy tắc lọc khiến lịch sử phiên mới bị ẩn. Không tái sử dụng cutoff A cho B.
- [ ] PUT thay đổi mục tiêu chỉ gửi trường người dùng thực sự sửa. Không gửi current timezone hoặc danh sách topic cũ nếu điều đó ghi đè pending policy ngoài ý muốn.

### Kiểm thử bắt buộc

Dùng deferred responses/barrier để ép đúng thứ tự, không trông chờ click nhanh hay delay ngẫu nhiên:

- [ ] A PUT pending → chuyển B → trả response A; UI B giữ dữ liệu B. Lặp với 409 rồi GET refresh chậm.
- [ ] A DELETE pending → chuyển B → trả 202 A; history và cutoff B không đổi. Logout/login A lại không nhận state từ request của auth epoch trước.
- [ ] GET history cũ bị giữ → DELETE trả 202 → thả GET cũ; history không xuất hiện lại.
- [ ] GET capabilities/recommendations/body JSON chậm rồi logout/unmount; không ghi state cũ.
- [ ] Hai lần tải filter trả ngược thứ tự: chỉ filter cuối hiển thị; kiểm tra item ID và CI thực tế.
- [ ] Token mất trước mutation: nút không kẹt busy; request cũ không tắt busy của mutation mới.

## R2 — P2: xử lý ngày lịch độc lập với thời điểm UTC

Files: helper ngày mới trong `apps/web/src/lib/`, test tương ứng, `progress/page.tsx`.

Lỗi đã xác minh: `new Date("2026-09-08")` rồi format ở `America/Los_Angeles` hiển thị 7/9, trong khi API đã trả ngày hoạt động 8/9.

- [ ] Tách hai kiểu dữ liệu: ngày lịch `YYYY-MM-DD` và timestamp có offset. Ngày lịch của activity không được chuyển qua UTC rồi đổi timezone lần nữa.
- [ ] Format nhãn activity từ chính năm/tháng/ngày API trả; có thể dùng UTC làm mốc kỹ thuật khi hiển thị nhưng phải giữ nguyên ngày lịch. Xử lý giá trị không hợp lệ rõ ràng.
- [ ] Timestamp `effective_at` vẫn format theo timezone phù hợp; không áp dụng cách xử lý date-only cho timestamp.
- [ ] Khoảng bảy ngày: lấy ngày hiện tại theo current policy timezone, trừ sáu **ngày lịch**, không trừ cố định 144 giờ qua DST. Ưu tiên formatToParts để tạo YYYY-MM-DD độc lập locale.
- [ ] Khi thiếu policy, không âm thầm giả định timezone khiến hiển thị sai; dùng fallback được contract xác nhận hoặc trạng thái chưa tải được.
- [ ] Không đổi cách backend tổng hợp ngày, goal hay streak.

### Kiểm thử bắt buộc

- [ ] Activity `2026-09-08` hiển thị 8/9 ở Los Angeles, Honolulu, Tokyo, Hồ Chí Minh.
- [ ] Khoảng from/to đúng bảy ngày gồm hôm nay, qua DST spring/fall ở America/New_York và qua đầu tháng/năm.
- [ ] Current policy và pending timezone khác nhau: hoạt động hiện tại dùng policy đang có hiệu lực; nhãn pending giữ thời điểm có hiệu lực đúng.
- [ ] Timestamp gần nửa đêm được hiển thị đúng ngày địa phương; date-only không bị đổi ngày.

## R3 — P2: E2E chứng minh phát video, checkpoint và bảo toàn số liệu

Files: `apps/web/e2e/learning-loop.spec.ts`, test race riêng nếu cần; harness `apps/api-python/differential/web-e2e-python.sh` chỉ sửa khi cần chọn capability matrix.

- [ ] Fixture clip published đi qua submit QA → review → publish, có media thật và content version hợp lệ. Tài khoản test/DB test riêng, không dùng dữ liệu dev.
- [ ] Test chính mở đúng item, bấm Bắt đầu và **bấm Phát**. Xác nhận video currentTime tăng và trạng thái playing; không thay bằng seedPlayback/take_over trực tiếp qua API.
- [ ] Đăng ký waitForResponse trước hành động; chờ `/playbacks` và checkpoint thật có `accepted_delta_ms > 0` hoặc acknowledged active tăng. GET API được phép dùng để đối chiếu, không thay hành vi UI đang kiểm chứng.
- [ ] Dừng phát/kết thúc, chờ biên nhận và trạng thái ổn định trước đo baseline. Kiểm tra history chứa đúng item, active time > 0.
- [ ] Thiết lập baseline legacy progress không bằng 0 bằng phiên thật; tách rõ legacy minutes và active watch. Không tăng đồng hồ/giả dữ liệu trong test hạch toán end-to-end.
- [ ] Đổi goal: xác nhận PUT thành công, current policy chưa bị đổi sớm, pending đúng; reload vẫn đúng.
- [ ] Trước DELETE chụp **giá trị số** progress và activity, không chỉ nhãn. Chờ response DELETE đúng 202, có deletion_id/cutoff/status; reload thấy history bị ẩn nhưng progress/activity bằng baseline.
- [ ] Không tuyên bố records xóa vật lý từ việc history đã ẩn. Nếu kiểm tra completed job thì phải chờ status API riêng.
- [ ] Không dùng điều kiện if bỏ qua hành vi bắt buộc. Đặt timeout phù hợp chu kỳ heartbeat và thời gian phiên thật; dùng điều kiện chờ thay sleep tùy ý.
- [ ] Test race filter ép trả response ngược thứ tự và xác nhận dữ liệu thuộc filter cuối; thêm các test identity/deletion ở R1.
- [ ] Test 403/capability disabled, 409, 500/offline có phản hồi UI đúng; giữ regression CMS QA, recovery, HLS và sync.
- [ ] Chạy toàn bộ E2E trên cả Chromium và WebKit với capability bật; kiểm tra fallback khi playback/smart-stream tắt. Ghi rõ engine/cấu hình/tổng số test, không cộng kết quả từ nhiều candidate thành một PASS.

## R4 — P2: một báo cáo chính thức và evidence gắn với candidate

Files: `walkthrough.md` trong worktree ứng viên; report mới `docs/qa/2026-09-08-web-learning-loop-review-fixes.md`; evidence mới dưới `docs/qa/evidence/web-learning-loop-review-fixes-20260908/`.

- [ ] Bản báo cáo chính thức là bản tracked trong ứng viên. Đối chiếu bản tổng kết chưa commit ở checkout gốc như nguồn tham khảo, không copy nguyên các tuyên bố “triệt để/100%” khi còn thiếu kiểm chứng.
- [ ] Giữ báo cáo gốc để bảo toàn; không xóa, overwrite hay stage file checkout gốc trong tác vụ này.
- [ ] Sửa danh sách commit: hiện có **5 commit**, bốn nhóm công việc. Liệt kê commit sửa mới khi có; không nhầm grouped work với số commit Git.
- [ ] Rà route transcript/CLI theo OpenAPI và code hiện hành, quy trình CMS phải có review. Dùng link repo tương đối trong tài liệu, bỏ file:// và đường dẫn chỉ có trên máy.
- [ ] Evidence 2026-09-07 giữ nhãn lịch sử; không lấy ảnh/log đó chứng nhận UI/policy/race của candidate mới. Chụp lại các trạng thái đã thay đổi cần đối chiếu hình ảnh, gồm pending goal và lỗi thao tác.
- [ ] Ghi HEAD, tree/source hash, dirty status, thời điểm, lệnh, engine, flags, exit code và log thô cho mỗi lần chạy; không lưu token/mật khẩu hoặc dữ liệu người dùng thật.
- [ ] Commit code/test trước lần kiểm chứng cuối để có SHA rõ. Evidence-only commit sau đó phải chỉ đổi docs/evidence; xác nhận không thay source từ SHA đã test. Nếu có sửa code giữa các lượt chạy, kiểm chứng lại phần bị ảnh hưởng và cập nhật nguồn evidence.
- [ ] Chuẩn hóa log lưu repo để git diff --check sạch (CR/EOF whitespace), giữ nguyên nội dung kết quả; ghi chú nếu log được chuẩn hóa/redact. Không sửa số liệu hay biến failure thành PASS.
- [ ] Báo cáo phân biệt bản ứng viên sạch với checkout gốc còn dirty; không tuyên bố toàn bộ workspace đã sạch.

## Trình tự thực hiện và commit đề xuất

1. Kiểm tra HEAD/status ứng viên, main và backup; giữ riêng các thay đổi phát sinh của người dùng. Nếu main đổi thì ghép main trước kiểm chứng cuối, bảo toàn QA.
2. `fix(web): isolate learning requests by auth session` — R1 + regression tests; dùng FR-ID-002/FR-HIS-001.
3. `fix(web): preserve policy calendar dates` — R2 + test timezone/DST; dùng FR-WAT-001.
4. `test(web): verify playback credit and deletion invariants` — R3, bao gồm hành vi UI thật và race được điều khiển; dùng FR-LRN-001/FR-WAT-001/FR-HIS-001.
5. Chạy kiểm chứng cuối, sau đó `docs(qa): record reviewed learning loop evidence` — R4 và tick checklist theo kết quả thực tế.

Không viết lại các commit cũ chỉ để làm đẹp lịch sử. Không cần thay backend/schema cho bốn lỗi này; nếu phát hiện yêu cầu backend mới thì ghi phạm vi và regression tương ứng trước khi mở rộng.

## Gate kiểm chứng cuối

- [ ] Web typecheck + unit (gồm regression mới), shared domain nếu DTO thay đổi, pedagogy guard và production build PASS.
- [ ] Toàn bộ E2E Chromium/WebKit: auth, shell, a11y, CMS QA, recovery, HLS, sync, learning loop PASS trên cùng source; cấu hình capabilities rõ.
- [ ] API/architecture tests chạy theo scope backend/harness thay đổi và CI; không dùng PASS architecture thay bằng PASS toàn API. Nếu backend source không đổi, ghi rõ phạm vi không chạy lại.
- [ ] Test database dùng Docker cô lập `/jplearn_test`; không reset dev DB, không xóa named volume dữ liệu hay media nguồn.
- [ ] Không còn ghi state khác owner, date-only không lệch ngày, history không tái hiện do response cũ, số liệu trước/sau DELETE được kiểm chứng bằng số dương.
- [ ] Report duy nhất trong branch ứng viên dẫn tới evidence đúng SHA; không còn kết luận vượt quá bằng chứng.
- [ ] Candidate sạch sau commit; nguồn checkout gốc được giữ nguyên. Push/merge theo yêu cầu tiếp theo của người dùng, không thuộc lượt lập plan.
