# Kế hoạch sửa các lỗi còn lại của Web Frontend

> Cập nhật cuối 2026-09-06: lỗi retry lock và HLS restore đã sửa trên working tree
> từ `564275e`; [evidence mới](../../qa/media-retry-fix-evidence-2026-09-06.md)
> xác định patch/checksum: E2E **44+44**, media repeat **42/42**, recovery repeat
> **12/12**, backend **217/217**, web unit **35/35**, guard/build PASS.
> F-03/C4 engineering đóng lại; **Design PARTIAL** giữ nguyên. Các SHA/số test bên
> dưới là lịch sử closeout trước đợt sửa này, không phải candidate mới.

Ngày: 2026-09-06. Trạng thái: **engineering PASS**, **Design PARTIAL** — không COMPLETED toàn bộ.
Còn chờ Design rà focus thủ công và thiết bị Safari/iPhone/iPad thật.
Candidate engineering: `41a4009` (code); evidence: `d1715d2`
([recovery-followup-evidence-2026-09-06.md](../../qa/recovery-followup-evidence-2026-09-06.md)).
Baseline được kiểm tra: `c2329a5` (mốc hồi quy F-01–F-04). Lịch sử closeout `fd838d2`
(217 / 21+21 / 7) giữ nguyên. Kế thừa: [remediation Mốc A/B](2026-09-06-web-frontend-remediation.md).

C4 đóng vì F-01–F-03 có bằng chứng. C5 keyboard/manual: engineering tests PASS,
Design PARTIAL. Không mở lại concurrency/migration backend đã xác thực.
Release gate hiện hành giữ nguyên (không production).

## 1. Mục tiêu và phạm vi

Học viên tải lại trang khi mạng lỗi phải còn đường xử lý phiên cũ. Khi máy chủ đã
kết thúc phiên, giao diện phải tải được tổng kết hoặc thông báo rõ đang thiếu dữ liệu.
Khi video lỗi hoặc nội dung bị gỡ, giao diện giữ đúng phiên và đúng nội dung đã chọn.

| ID | Ưu tiên | Kết quả cần đạt | Owner |
| --- | --- | --- | --- |
| F-01 | P1 | Không ghi đè phiên chưa xác nhận, không đổi key khi retry start | Web + QA |
| F-02 | P2 | Mọi đường xác nhận ended dùng cùng luồng tải tổng kết | Web + QA |
| F-03 | P2 | Làm mới URL có giới hạn, không tự thay clip bị gỡ bằng clip khác | Web + QA |
| F-04 | Bằng chứng | Kiểm hành vi bàn phím thực tế và thông báo lỗi | QA + Design |

**Vai trò:** BA đối chiếu acceptance với FR/UC hiện hành; Web sửa màn S-SESSION
và CiPlayer; QA viết test tái hiện rồi chạy hồi quy; Design rà focus/keyboard.
Platform chỉ tham gia nếu phát hiện lệch hợp đồng API trong lúc thực hiện.

**Traceability:** F-01 → FR-SES-001/003, UC-L03; F-02 → FR-SES-002,
FR-PRG-001/002, UC-L04/L05; F-03 → FR-LRN-001, FR-CMS-003, FR-CAT-002,
UC-L02/L10; F-04 → NFR-A11Y-001, S-LOGIN/S-SESSION.
Giữ test IDs `T-SES-REC-001`, `T-LRN-001`, `T-NFR-A1`, phân biệt bằng tên scenario.
Không thêm nghiệp vụ hay endpoint mới; cập nhật traceability bằng scenario thực tế.

## 2. Bằng chứng đầu vào

Đợt review trước khi lập plan đã chạy đạt: 217 backend tests, 42 E2E trên
Chromium/WebKit, 7 web unit tests, TypeScript, production build và guard.
Đây là baseline hồi quy, không chứng minh các scenario còn thiếu đã đạt.

Đã tái hiện bổ sung bằng trình duyệt và API giả lập lỗi có kiểm soát:

- Recovery `active` bị lỗi mạng → Start vẫn bật → record bị thay bằng phiên mới.
- Recovery `starting` bị lỗi mạng → Start gửi key khác với key đã persist.
- Mất response end, GET xác nhận ended → record bị xóa nhưng không GET progress,
  không có tổng kết trên màn hình.

Đọc mã xác nhận: player chưa yêu cầu cấp URL mới khi nguồn hết hạn; `loadClip`
tự chọn clip khác nếu không tìm thấy item đang yêu cầu. Test hiện tại chỉ reload
catalog, chưa gây URL hết hạn hoặc gỡ item của phiên đang chạy.

## 3. F-01 — Bảo vệ phiên trong suốt quá trình recovery

**Tệp chính:** `apps/web/src/app/session/page.tsx`, `apps/web/src/lib/session-storage.ts`.
Có thể tách hook/helper quản lý phiên để các nhánh dùng chung quy tắc; tránh refactor
toàn bộ trang hoặc đổi cấu trúc lưu trữ khi không cần thiết.

- [x] Có trạng thái UI khởi tạo/đang xác minh/chưa xác minh riêng. Start chỉ bật khi
  đã đọc storage và xác nhận không còn phiên phải xử lý. Khóa nút ngay từ lần render
  đầu, cả trong lúc GET chưa trả về và sau khi GET lỗi.
- [x] Retry ở `starting` luôn lấy key, deviceClass và itemId từ record đã lưu;
  không sinh key mới vì remount hoặc vì ref trong bộ nhớ đã mất.
- [x] Retry ở `active`, `ending`, `outcome_unknown` xác minh cùng sessionId;
  active thì cho end, ended thì đi qua F-02. Không POST start trong các nhánh này.
- [x] Hiện nút “Thử khôi phục lại” khi mạng lỗi. Chống hai request recovery đồng thời;
  response cũ sau đổi user, chuyển trang hoặc retry mới không được ghi đè state mới.
- [x] Network error, 5xx hoặc response không hợp lệ giữ record/key và trạng thái chưa
  xác nhận. Không clear record chỉ vì `res.ok` false; phân loại lỗi theo OpenAPI.
- [x] 401 đi theo luồng đăng nhập hiện hành và giữ dữ liệu cần recovery của đúng user.
  GET 403/404 có xử lý terminal rõ ràng, không cho người khác sử dụng phiên đó.
- [x] Chỉ sinh key mới khi bắt đầu một phiên mới đã được phép. Bảo toàn storage theo
  user/tab; lưu active trước catalog; lỗi media không làm mất quyền kết thúc phiên.
- [x] Nếu replay POST trả session đã ended, xử lý ended thay vì dựng lại UI active.

**Acceptance test trước sửa phải thất bại:**

1. Chặn GET recovery chưa trả lời: Start disabled và không có POST mới.
2. Reload khi active/unknown và GET lỗi: record giữ nguyên; retry online khôi phục
   đúng ID; không tạo thêm session/event. Bao gồm lỗi mạng và HTTP 500.
3. Start đã commit nhưng mất response; reload; replay tiếp tục lỗi; bấm retry sau
   khi mạng trở lại: mọi POST dùng cùng key, server chỉ có một session/start event.
4. Replay bị 500 hoặc body sai: không mất key. Replay trả ended: không có nút end
   cho phiên đã kết thúc và không gửi end lần hai.
5. Các response đến muộn không phục hồi phiên vào user/trang không còn tương ứng.

**Exit:** các thao tác reload/retry không có đường ghi đè record chưa xác nhận hoặc
tạo phiên mới do mất key. Giữ các test hai tab/đổi user đang có.

## 4. F-02 — Dùng chung luồng hoàn tất và tải tổng kết

**Tệp chính:** `apps/web/src/app/session/page.tsx`, `apps/web/e2e/recovery.spec.ts`.

- [x] Hợp nhất xử lý ended từ POST end thành công, GET sau POST lỗi và GET khi reload.
  Session status và progress là hai bước riêng: đã xác nhận ended thì không retry end.
- [x] Đọc progress khi GET xác nhận ended; lấy duration từ response server khi có.
  Không dùng `0` thay dữ liệu chưa tải được rồi hiển thị như kết quả thật.
- [x] Nếu progress lỗi: hiện “Phiên đã kết thúc; chưa tải được tổng kết” và nút thử lại
  tổng kết. Lưu đủ tham chiếu để reload còn thử lại được; không giữ UI như phiên active.
- [x] Có thể giữ record `outcome_unknown` hiện hữu cho tới khi tổng kết tải xong;
  mỗi lần recovery phải GET status trước. Nếu thêm state mới thì cập nhật validator,
  khả năng đọc record cũ và unit tests cùng thay đổi.
- [x] Sau khi có tổng kết thật mới dọn dữ liệu recovery theo policy; không clear sớm
  làm mất đường tải lại. Tách rõ lỗi kết thúc phiên với lỗi tải progress.

**Acceptance:** mất response end sau commit → GET ended → GET progress → tổng kết
đúng duration/phút/cấp độ, một end event. Cùng kết quả sau reload. Nếu progress
500/offline, không hiện số giả, không POST end lại; retry và reload đều tải lại được.
Sửa test hiện tại để assert heading và số liệu, không chỉ assert dòng “Đã kết thúc phiên”.

## 5. F-03 — Khôi phục nguồn video và giữ đúng item

**Tệp chính:** `apps/web/src/components/ci-player.tsx`, `apps/web/src/app/session/page.tsx`,
`apps/web/e2e/recovery.spec.ts`, `apps/web/e2e/hls.spec.ts`.

- [x] CiPlayer báo lỗi nguồn không phục hồi được về trang cha, bao phủ HLS native,
  hls.js và MP4. Giữ fallback HLS→MP4 khi MP4 còn dùng được.
- [x] Trang cha gọi catalog lấy URL mới cho đúng itemId. Một chu kỳ lỗi chỉ có
  **tối đa một lần tự refetch catalog**; gộp các error event cùng chu kỳ. URL vẫn
  lỗi/không đổi thì dừng tự động, báo lỗi và cho retry thủ công, không lặp vô hạn.
- [x] Không reset ngân sách retry chỉ vì props URL đổi hoặc component render lại.
  Retry thủ công tạo một chu kỳ mới; hủy/bỏ qua kết quả sau end, đổi item hoặc unmount.
- [x] Với phiên không có itemId ban đầu, chỉ chọn mặc định lần đầu rồi persist ID
  thực tế. Với record cũ thiếu itemId, thực hiện cùng quy tắc một lần sau recovery.
- [x] Khi đã có targetItemId nhưng catalog không còn item đó, báo nội dung không còn
  khả dụng; không lấy item đầu tiên khác. Giữ sessionId và nút kết thúc hoạt động.
- [x] Sau đổi URL cùng item, khôi phục vị trí xem khi media hỗ trợ và không vượt
  duration; tôn trọng trạng thái pause và chính sách autoplay của trình duyệt.
- [x] Storage chỉ lưu ID/state; tuyệt đối không persist signed URL hoặc object catalog.

**Acceptance:**

1. URL cũ bị từ chối; catalog trả URL mới cho cùng item; video có thể phát tiếp,
   đúng sessionId/itemId và vị trí xem hợp lệ. Bao phủ MP4 và đường HLS tương ứng engine.
2. HLS lỗi nhưng MP4 còn tốt: fallback vẫn chạy. Cả hai lỗi: refresh có giới hạn;
   URL mới cũng lỗi thì hiện lỗi, số GET catalog không tăng vô hạn, end vẫn dùng được.
3. Unpublish item A trong khi catalog còn item B: báo A không khả dụng,
   không tải/phát B. Bao phủ start từ link A cũ, reload và refetch sau lỗi media.
4. Mọi scenario không sinh thêm session và không lưu URL vào sessionStorage.

Lỗi nguồn dùng fault injection để tái hiện ổn định; ít nhất một ca đổi URL phát
media thật và một ca unpublish qua API thật trên DB test cô lập. Không chờ TTL dài
hoặc dùng thời gian ngủ cố định làm bằng chứng URL hết hạn.
Phạm vi này không yêu cầu thu hồi tức thì signed URL đang còn hạn sau unpublish.

## 6. F-04 — Hoàn thiện bằng chứng keyboard/a11y

- [x] Mở rộng `apps/web/e2e/a11y.spec.ts`: đi đến player bằng bàn phím, thực hiện
  phát/dừng bằng bàn phím và assert `paused`/`currentTime` thay đổi đúng.
  Không dùng `video.focus()` hoặc gọi `play()` bằng script thay cho hành động cần đo.
  **Engineering PASS** tại `41a4009` / `d1715d2` (Tab→Phát/Tạm dừng + `role=alert`).
- [x] Kiểm thứ tự focus ở các điều khiển web thuộc phạm vi, Enter submit và thông báo
  lỗi recovery/tổng kết có semantics phù hợp (`role=alert` cho lỗi cần thông báo).
- [x] Chạy trên cả Chromium/WebKit. Native media keys: `tab-to-video=false`,
  `spaceChangedPaused=false` trên cả hai engine. WebKit HLS = engine, không phải
  iPhone/Safari thật. Không skip.
- [ ] Design ghi người kiểm/ngày/revision/kết quả rà focus thủ công trên thiết bị
  Safari/iPhone/iPad thật. **Design PARTIAL** — chưa có rà Safari/device; axe đạt
  không thay thế audit WCAG 2.2 AA.

## 7. Thứ tự thực hiện và kiểm thử

1. **BA/QA:** mở lại C4 và cập nhật trạng thái walkthrough thành remediation đang
   thực hiện, dẫn plan này; giữ nguyên lịch sử test đã chạy và phần backend đã đạt.
2. **F-01:** viết scenario đỏ, sửa quản lý trạng thái/retry, chạy focused recovery.
3. **F-02:** hợp nhất ended flow, kiểm progress lỗi và reload bằng test số liệu thật.
4. **F-03:** nối callback media, refresh có giới hạn và item unavailable; chạy media tests.
5. **F-04:** keyboard/alert + rà Design; BA đối chiếu từng acceptance với assertion.
6. **QA:** chạy hồi quy một lần trên candidate cuối; chỉ chạy lại khi có thay đổi/failure.

Kiểm tra cuối gồm `pnpm test:guard`, `pnpm --filter @jplearn/web test`,
`pnpm --filter @jplearn/web build`, `pnpm test:api` và
`apps/api-python/differential/web-e2e-python.sh` trên Chromium + WebKit.
Backend suite giữ coverage OpenAPI, DDL và concurrency đang có; không thêm migration
hoặc backend tests chỉ để phản chiếu thay đổi UI. Unit tests mới tập trung transition,
key invariants, retry budget; E2E kiểm hành vi và kết quả server, tránh chỉ kiểm text.

Mọi DB test phải cô lập ở `/jplearn_test`/Compose project riêng. Không reset DB dev,
volume `jplearn_postgres_data` hoặc media dev. Dọn riêng process/container test đã tạo.

## 8. Điều kiện đóng và bàn giao

- [x] F-01/F-02/F-03 có test từng thất bại trên baseline và đạt sau sửa, không skip
  scenario bắt buộc. Lưu rõ ca mock fault và ca tích hợp API/media thật.
  **Engineering PASS** — F-01/F-02/F-03 tại `41a4009` / evidence `d1715d2`.
- [x] Hồi quy đạt; số test thực tế: pytest **217 passed**; Playwright **42+42**
  Chromium/WebKit; web unit **35**; guard **0 banned**; build **10 routes**.
  Lịch sử `fd838d2` giữ **217 / 21+21 / 7**.
- [x] Evidence trong `docs/qa/recovery-followup-evidence-2026-09-06.md` và
  `docs/qa/evidence/recovery-followup-20260906-170905/` (SHA, dirty, env, lệnh,
  exit, duration, raw logs đã loại secret).
- [x] BA xác nhận coverage và cập nhật plan trước/traceability/walkthrough theo kết quả.
  **C4 đóng** vì F-01–03 đủ bằng chứng. C5 keyboard/manual: engineering tests PASS,
  Design PARTIAL (focus thủ công + Safari/device).
- [ ] Không ghi COMPLETED toàn bộ: **engineering PASS**, **Design PARTIAL**, còn chờ
  Design rà focus thủ công và thiết bị Safari/iPhone/iPad thật.

Mốc B CMS giữ kết quả hồi quy lịch sử `fd838d2`, không dựng lại workflow. Hoàn tất
plan này không tự đồng nghĩa được triển khai production; release gate hiện hành
giữ nguyên (không production).
