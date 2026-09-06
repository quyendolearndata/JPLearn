# Kế hoạch triển khai frontend web JPLearn

Ngày: 2026-09-06. Trạng thái: **Mốc A recovery IN PROGRESS** theo [recovery follow-up](2026-09-06-web-frontend-recovery-followup.md); Mốc B giữ kết quả hồi quy lịch sử tại `fd838d2`, không dựng lại workflow. Evidence lịch sử: [remediation-evidence-2026-09-06.md](../../qa/remediation-evidence-2026-09-06.md) §4. Mục còn mở được đánh dấu inline: 4 mục *PARTIAL (Design)* — artifact luồng/visual review, 1 mục *HOLD* reviewer theo gates.md, 1 mục *HOLD (CTO/Ops)* staging/R-09.
Baseline khảo sát: `00576eb`; backend FastAPI/Alembic, frontend Next.js hiện có.
Chủ trì: Web. BA phụ trách phạm vi/UC; Platform phụ trách hợp đồng API;
Design phụ trách giao diện; QA kiểm chứng; CTO/Ops phụ trách phát hành.
Phân công dưới đây không đại diện cho chữ ký nghiệm thu.

## 1. Kết quả cần đạt

**Mốc A — web học viên:** landing có CTA thật; đăng ký/đăng nhập; catalog theo cấp CI;
chọn nội dung, mở phiên, phát media, kết thúc và thấy tiến độ được backend xác nhận.
Refresh, chuyển trang và lỗi mạng có trạng thái rõ ràng, không báo thành công giả.

**Mốc B — CMS vận hành:** teacher tạo/sửa draft, upload và gửi QA; admin mở lại
nội dung từ danh sách để kiểm tra/publish/unpublish. Mọi bước tiếp tục được sau lần đăng nhập khác.

Ưu tiên Mốc A. Mốc A cần bổ sung tra cứu phiên và chống tạo trùng khi retry start;
Mốc B cần API quản lý nội dung. Các bổ sung này không đòi viết lại backend.
Giữ Next.js, React, FastAPI, shared domain/CMS schema và design tokens hiện có.

## 2. Căn cứ và lựa chọn mặc định

- [SRS](../../sad/01-survey-srs/srs.md), [use cases](../../sad/02-analysis/use-cases.md),
  [traceability](../../sad/03-design/traceability.md), [UI shell](../../sad/03-design/ui-shell.md),
  [API hiện hành](../../backend/api-usage.md) và [OpenAPI](../../sad/03-design/openapi.yaml).
- Baseline kiểm tra ngày 2026-09-06 trong phiên đánh giá: TypeScript PASS;
  harness build web + E2E PASS 10/10 Chromium/WebKit, gồm đồng bộ phút giữa hai browser context.
  Evidence local: `/tmp/jplearn-e2e-20260906112332_26278/` (tạm thời, không phải artifact CI bền vững).
  Đây là baseline, không phải kết quả nghiệm thu thay đổi trong kế hoạch này.
- `landing_preview.html` là tham khảo thẩm mỹ; `apps/web` là ứng dụng có API thật.
  Thiết kế đề xuất giữ nền ấm và nét Nhật hiện đại, ưu tiên tiếng Việt dễ đọc cho điều hướng.
- `/` là landing công khai; chuyển catalog từ `/` sang `/catalog`.
  `/login`, `/session`, `/progress` và `/staff` giữ ý nghĩa hiện tại.
  Cập nhật link, redirect và E2E cùng lần đổi route; không để hai trang cùng đóng vai catalog.
- Màn đã có: S-LOGIN, S-HOME (route `/catalog`), S-SESSION, S-PROGRESS, S-FLAGS-GATE.
  Màn landing và CMS list/detail/form sẽ được Design/BA định danh ở W0.
- Card học viên dùng topic, CI level, duration, media type, visual support hiện có.
  Ánh xạ topic ID thành nhãn tiếng Việt là UI chrome; không dùng `title_internal` làm tiêu đề học viên.
  Thumbnail/tiêu đề public chưa là yêu cầu của mốc đầu, không bịa dữ liệu trả từ API.
- Giữ phút tính theo thời gian server start→end, làm tròn và giới hạn 4 giờ như contract.
  Player pause không tự đổi công thức tính phút. Logout vẫn thu hồi token trên mọi thiết bị.
- Chưa đưa vào hai mốc: subscription/trial 7 ngày, biểu đồ lịch sử từng ngày, recommendation,
  lịch sử xem theo clip, upload MP3, pipeline transcode tự động, quiz/probe, grammar/flashcard/L1.
  Không dùng số 98,4%, nhãn live stream hoặc cam kết realtime khi chưa có chức năng/bằng chứng.

## 3. W0 — Chốt luồng, thiết kế và phạm vi hợp đồng

**Owner:** BA + Design; Web/Platform rà khả thi; Pedagogy rà trải nghiệm học.
**FR/UC:** FR-ID-001…004, FR-CAT-002…005, FR-SES-001…003, FR-PRG-001…004,
FR-CMS-001…004; FR-LRN-001/UC-L10 cho vòng học có chọn clip.

- [ ] Vẽ luồng learner và teacher/admin, gồm empty/loading/error/401/403 và trạng thái đang gửi.
  *PARTIAL (Design):* hành vi các state được kiểm qua E2E; chưa có artifact luồng riêng.
- [ ] Chốt bố cục desktop, phone web, tablet web riêng; desktop có catalog rộng và tổng tiến độ dễ thấy.
  *PARTIAL (Design):* `ui-shell.md` + wireframes S-* có; chưa có visual review thực tế 3 breakpoint.
- [ ] Chốt bản thiết kế landing, tài khoản, catalog, phiên, tiến độ, staff list/detail/form;
  tái sử dụng `packages/design-tokens` và component form/button/feedback thống nhất.
  *PARTIAL (Design):* wireframes chưa có landing và staff list/detail/form.
- [x] Làm rõ phần FR-LRN-001 đang deferred trong SRS: hoàn thành SAD vòng 2 cho
  chọn clip → mở phiên → xem/nghe → kết thúc, rồi triển khai tại W3.
  Không coi việc đã có player skeleton là đã duyệt toàn bộ vòng học.
- [x] Ghi delta về khôi phục phiên và CMS list/detail/edit vào UC, OpenAPI và traceability;
  bổ sung ID nếu có yêu cầu nghiệp vụ mới. FR-CAT-005 đã có ý sửa draft nhưng API chưa thực hiện.
- [ ] Chuẩn bị artifact và review theo `docs/company/gates.md` cho thiết kế/contract thay đổi;
  ghi người review thực tế, không sao chép chữ ký của baseline sang phạm vi mới.
  *HOLD:* evidence §4 ký theo ghế (QA/BA/Platform/Web); chưa ghi người review thực tế theo gates.md.

**Exit:** có thiết kế màn hình, state transitions, bảng field/API và acceptance criteria
đủ để Web/Platform triển khai. W1 sửa lỗi hiện hữu có thể tiến hành trong lúc W0 hoàn thiện.

## 4. W1 — Sửa nền tích hợp và tài khoản

**Owner:** Web; QA review. **FR:** FR-ID-001…004, FR-FLG-001/002, NFR-SEC-001/002, NFR-OBS-001.
**Bề mặt:** `apps/web/src/lib/`, login, Chrome, các call site API; cấu hình/env mẫu và docs web.

- [x] Đồng bộ fallback local API về `3002`, thêm env mẫu web; xác thực URL phù hợp khi build.
  `NEXT_PUBLIC_API_URL` phải đúng lúc build; `API_PUBLIC_URL` và CORS backend đúng origin khi triển khai.
- [x] API client phân biệt HTTP error, network error và response 204;
  dùng schema `{statusCode,message,error?}`, validation 400; không giả định FastAPI trả 422.
- [x] Xử lý 401 tập trung: xóa auth hết hạn, yêu cầu đăng nhập lại và giữ đích quay lại nội bộ hợp lệ.
  403 là thiếu quyền, không tự đánh đồng với hết phiên. Không log token/password/signed URL.
- [x] Khởi tạo auth bằng `/me`, điều hướng theo role; staff menu chỉ hiện cho teacher/admin.
  Không dùng role trong localStorage như nguồn xác thực cuối cùng; backend vẫn enforce quyền.
- [x] Có logout gọi API, thông báo rõ phạm vi mọi thiết bị; xóa trạng thái user/flags khi kết thúc.
  Nếu mất kết nối, phân biệt xóa phiên local với thu hồi trên server chưa xác nhận.
- [x] Bỏ mật khẩu demo điền sẵn; validation email/password, lỗi trùng email và sai mật khẩu rõ ràng.
- [x] Flags tải lại khi auth thay đổi, có fallback an toàn và bắt network error.
  Không hiển thị link tới route chưa triển khai khi flag bất ngờ bật.
- [x] Mọi mutation khóa khi đang gửi, chỉ cập nhật thành công từ response hợp lệ.
  Không tự retry POST start/create/upload khi chưa có cơ chế chống tạo trùng phía server.
- [x] Sửa ngay lỗi end/publish báo thành công giả; giữ ID và dữ liệu form khi thất bại để phục hồi.

**Exit:** login/register/logout/401/403 hoạt động; lỗi API không trở thành catalog trống,
progress giả hoặc trạng thái published/ended giả. Test regression trực tiếp các tình huống này.

## 5. W2 — Landing và giao diện nền tảng

**Owner:** Web + Design. **FR:** FR-CAT-002…004, FR-PRG-001…004, FR-FLG-002,
NFR-A11Y-001, NFR-XPLAT-002.
**Bề mặt:** app layouts/routes, Chrome, globals, shared components, design tokens.

- [x] Tách layout public, learner và staff; chuyển catalog sang `/catalog`.
- [x] Chuyển mẫu landing thành component Next.js; CTA đi tới tài khoản/catalog thật.
  Nội dung giới thiệu phản ánh CI và tổng phút tích lũy; bỏ cam kết chưa được sản phẩm hỗ trợ.
- [x] Catalog có filter CI bằng API, card từ field public hiện có;
  loading/empty/error/retry phân biệt, kể cả seed chưa có nội dung published.
- [x] S-PROGRESS hiển thị tổng phút/cấp hiện tại, cập nhật sau khi end đã xác nhận và khi quay lại trang.
- [ ] Desktop, phone và tablet có navigation/spacing phù hợp; CMS desktop ưu tiên bảng thao tác.
  *PARTIAL (Design):* CSS responsive có (`globals.css` breakpoints 768/960); chưa có visual review/ảnh QA.
- [x] Keyboard/focus, label, thông báo lỗi đọc được, contrast AA; trạng thái pending không gây nhảy bố cục lớn.
  Bằng chứng: `a11y.spec.ts` (axe + keyboard) tại `fd838d2`; không phải audit WCAG 2.2 AA toàn diện.

**Exit:** landing và các màn nền tảng chạy trên API thật, route mới được kiểm thử;
các layout đã có ảnh kiểm tra thực tế. W3 hoàn thiện hành vi chọn clip và khôi phục phiên.

## 6. W3 — Vòng học và khôi phục phiên (Mốc A recovery chưa đóng)

**Owner:** Web + Platform; BA/Pedagogy review ngữ nghĩa; QA kiểm chứng.
**FR:** FR-LRN-001/UC-L10 sau W0, FR-SES-001…003, FR-PRG-001/004, FR-CMS-003/004, NFR-PERF-002.

- [x] Chọn clip cụ thể từ catalog và mở đúng clip; kiểm tra lại item còn published trước phát.
  Dùng URL do catalog trả, không đưa token/signed URL vào query điều hướng hoặc lưu dài hạn.
- [x] Quản lý session ở phạm vi ứng dụng, lưu tham chiếu theo user và tab để survive điều hướng/reload.
  State tối thiểu: idle, starting, active, ending, outcome-unknown, ended.
  Không ghi đè ID đang active; không dùng start mới để xử lý lỗi tải lại catalog/player.
- [x] Bổ sung **API đề xuất mới** `GET /sessions/{id}` owner-only để đọc trạng thái
  started/ended. Không suy ra phiên đã end chỉ từ tổng `/progress`, vì phiên khác có thể vừa cập nhật.
- [x] Bổ sung **contract đề xuất mới** optional `Idempotency-Key` cho `POST /sessions`:
  web tạo/lưu key trước gửi; cùng user/key/body trả lại cùng phiên; khác body trả conflict;
  thực thi chống trùng bằng ràng buộc bền vững và transaction, không chỉ khóa nút phía web.
  Chốt thời gian lưu key và migration Alembic tại W0; client hiện tại không gửi header vẫn hoạt động.
  Không thêm giới hạn một phiên duy nhất trên mọi thiết bị.
- [x] Mất response start: retry có chủ đích bằng cùng key; mất response end: giữ ID,
  GET trạng thái phiên rồi lấy progress. Nếu còn active mới cho thử end lại;
  giữ response end lần hai = 400 như hiện tại, không cộng phút lần nữa.
- [x] Gặp 401 giữa phiên: cho đăng nhập lại và chỉ khôi phục khi đúng user; không chuyển phiên sang user khác.
- [x] Giữ HLS native/hls.js + fallback MP4. Khi URL hết hạn, lấy URL mới cho cùng item,
  retry có giới hạn, giữ phiên và vị trí phát khi khả thi; item bị unpublish phải báo không còn khả dụng.
  Ghi chú: recovery refetch catalog, không lưu signed URL (`recovery.spec.ts`); giữ vị trí phát chưa làm.
- [x] Có thông báo khi clip chưa phát được và nút kết thúc phiên vẫn dùng được.
  Không tự cộng phút frontend, không tự end bằng đồng hồ UI, không dựa unload request để đảm bảo ghi nhận.

**Exit Mốc A:** người dùng hoàn thành đăng nhập → chọn clip → học → end → tiến độ;
reload/điều hướng không mất tham chiếu; response loss có kiểm tra trạng thái chắc chắn;
không sinh thêm phiên khi retry cùng start key. API additions có contract tests và tương thích client cũ.

## 7. W4 — CMS vận hành (giữ kết quả hồi quy Mốc B)

**Owner:** Platform + Web; BA chốt workflow; QA kiểm quyền và trạng thái.
**FR:** FR-CAT-001/005, FR-CMS-001…004, NFR-SEC-002, NFR-PERF-001.

**API đề xuất — chưa có trong backend baseline:**

| Endpoint | Hành vi phải chốt/triển khai |
| --- | --- |
| `GET /staff/catalog` | Teacher/admin, lọc status/CI, phân trang và thứ tự ổn định để tìm lại draft/QA/published |
| `GET /staff/catalog/{id}` | Metadata nội bộ, status và trạng thái media đủ để tiếp tục thao tác; không đưa storage path/secret ra ngoài |
| `PATCH /staff/catalog/{id}` | Chỉ metadata trong `catalogWriteFields`, chỉ draft; kiểm quyền và trạng thái trong transaction, chặn sửa khi đã chuyển QA/published |

- [x] Mặc định giữ quyền theo role hiện tại: teacher/admin xem danh sách staff và sửa draft;
  không tự thêm giới hạn teacher chỉ được sửa item của mình. BA xác nhận policy này trong W0.
  Bổ sung `revision` cho staff DTO; PATCH gửi revision đã đọc, stale trả 409.
  Kiểm tra revision/status cùng transaction; submit/publish/unpublish làm revision thay đổi.
  Dùng migration Alembic mới và backfill rows cũ, không sửa migration baseline.
- [x] Cập nhật OpenAPI, schemas, UC-T02/T03/T04/A01 và traceability cùng API;
  giữ contract learner catalog không lộ title_internal hoặc bản dịch L1.
- [x] `/staff` là list; `/staff/new` tạo; `/staff/[id]` xem/sửa/thao tác theo state và role.
  Dùng URL item ID để reload hoặc bàn giao teacher→admin, không chỉ giữ item trong React state.
- [x] Form có nhãn nghiệp vụ, validation; upload hướng dẫn/chặn file không phải MP4;
  hiển thị trạng thái chờ/kết quả/lỗi, cho tiếp tục trên draft đã tạo khi upload thất bại.
  Metadata audio không được quảng cáo thành khả năng upload MP3.
- [x] Nối các API có sẵn: create, upload, submit QA, publish, unpublish.
  Teacher dừng ở QA; admin publish khi đạt điều kiện; UI dùng state backend xác nhận.
- [x] UC-Q02 đã mô tả reject về draft và lý do nội bộ nhưng chưa có endpoint đầy đủ:
  mốc đầu dùng quy trình review trong runbook; BA ghi nhận giới hạn này trong acceptance.
  Mốc B chưa hoàn thành UC-Q02 tự động; không thêm nút reject/approve thiếu API.
  Workflow reject có lưu lý do/audit là phần hoàn thiện UC-Q02 ở gói tiếp theo.
- [x] HLS tiếp tục theo pipeline offline/runbook hiện có; upload MP4 không đồng nghĩa tự transcode.

**Exit Mốc B:** teacher tạo/upload/submit, logout; admin login, tìm đúng item, kiểm tra và publish;
learner thấy nội dung; unpublish loại nội dung khỏi catalog. Reload từng bước vẫn tiếp tục được.

> Mốc B giữ kết quả hồi quy tại `fd838d2`; recovery follow-up không dựng lại
> workflow CMS.

## 8. W5 — Kiểm chứng và bàn giao, áp dụng cho từng mốc

**Owner:** QA + Web/Platform; Design visual review; CTO/Ops phát hành.

| Nhóm | Trường hợp bắt buộc |
| --- | --- |
| Auth | Register/login; trùng email; validation; token hết hạn; `/me` đổi role; logout mọi thiết bị; redirect nội bộ |
| Catalog/UI | Lọc CI; chưa published; catalog rỗng khác lỗi; navigation/flags sau login; responsive/keyboard/AA |
| Phiên | Start/end bình thường; double click; reload/chuyển trang; response start/end bị mất; concurrent cùng key; sai user; end lặp không cộng lại |
| Media | MP4, HLS native/hls.js, fallback; URL hết hạn; item unpublish; play/pause bằng bàn phím |
| Progress | Server end xác nhận rồi mới cập nhật; floor phút; >4h; hai client cùng user; không dùng tổng phút để suy ra trạng thái phiên |
| CMS | Teacher/admin khác lượt đăng nhập; learner 403; upload lỗi; publish thiếu media; edit ngoài draft; race edit/submit; unpublish |
| Contract | APIs mới không phá mobile/client cũ; optional start key; schema lỗi/204; negative routes/chrome |

- [x] Chạy `pnpm --filter @jplearn/web test`, production build, `pnpm test:guard` và
  `apps/api-python/differential/web-e2e-python.sh` trên Chromium + WebKit.
- [x] Khi sửa API: `pnpm test:api`, architecture/contract checks tương ứng và kiểm migration trên DB test;
  cập nhật expected OpenAPI thay đổi có chủ đích. Không dùng baseline parity lịch sử làm chứng cứ API mới.
- [x] Chỉ thêm tests cho hành vi/rủi ro, không test lặp markup thuần trang trí.
  Lưu revision, config không chứa secret, commands/exit codes, logs và ảnh QA vào evidence của từng mốc.
  Ghi chú: evidence `docs/qa/evidence/remediation-closeout-20260906-140329/` có log/exit/SHA; chưa có ảnh QA.
- [x] Cập nhật README hướng dẫn web/env/routes và ma trận FR→UC→test.
  Tiêu chí đồng bộ 3 bề mặt tách riêng: browser emulation không được báo là đã kiểm trên thiết bị native.
- [x] DB test `/jplearn_test` và media test cô lập; bảo toàn DB dev/volumes và hai file
  `walkthrough.md`, `landing_preview.html` đang có thay đổi của người dùng.
- [ ] Chuẩn bị staging config, HTTPS/CORS/media URL, smoke checklist, rollback build trước;
  phát hành khi đáp ứng điều kiện CTO/Ops và R-09 hiện hành. Không coi local PASS là production acceptance.
  *HOLD (CTO/Ops):* ngoài phạm vi COMPLETED local/test; R-09 chưa mở.

## 9. Thứ tự thực hiện và điều kiện hoàn tất

1. W0 bắt đầu trước; W1 sửa lỗi hiện tại và W0 thiết kế có thể chạy song song theo ghế.
2. W2 triển khai sau khi chốt IA; Platform chuẩn bị API khôi phục phiên đã review trong W0.
3. W3 tích hợp learner; chạy W5 cho Mốc A, bàn giao web học viên local/test.
4. W4 hoàn thiện CMS sau contract review; chuẩn bị contract có thể song song với W2/W3.
5. Chạy W5 cho Mốc B; staging/production thực hiện theo điều kiện phát hành thực tế.

Mỗi gói thay đổi phải có phạm vi, FR/UC, dependency và evidence riêng.
Mốc A không chờ CMS list/edit; Mốc B không yêu cầu subscription hoặc analytics ngày.
Không ấn định ngày phát hành khi chưa hoàn tất W0 và biết điều kiện staging.
