# FastAPI: sửa lỗi sau audit và hoàn thiện bằng chứng nghiệm thu

> Trạng thái: Proposed — chưa triển khai  
> Baseline: `codex/fastapi-backend-hardening` tại `1bc5abf`  
> Ngày: 2026-09-05  
> Chủ trì review: CTO; thực hiện: Platform/Backend; nghiệm thu: QA  
> Phối hợp: BA (contract), Ops (vận hành), Web/Mobile (playback)

## 1. Phạm vi và baseline

Plan này bổ sung cho `2026-09-05-fastapi-hardening-gap-closure.md`. Giữ nguyên
ID G-01…G-13 của plan gốc; dùng ID R-01…R-09 dưới đây cho các việc sửa sau audit.
Không đổi tên gap để biến một việc chưa hoàn tất thành việc khác đã hoàn tất.

Bằng chứng đã chạy lại sau khi Docker được bật:

- 112 pytest PASS, 2 warning deprecation, 17,24 giây.
- Web E2E Chromium + WebKit: tổng 10/10 PASS, 2,3 phút.
- Image hiện có `jplearn-api-python:hardened`: UID 10001, đọc baseline 10 bảng;
  `upgrade/current/stamp` chạy trên PostgreSQL test riêng; stamp DB rỗng bị chặn.
- Image ID đã kiểm tra:
  `sha256:5dc600261512b712de927563006235ab6a727c4c79cfc8afcd1fd06eedcb96e7`.
  Đây là image local đã kiểm tra, chưa phải bằng chứng CI build từ HEAD.
- Repository guard PASS; OpenAPI command exit 0 nhưng còn false-negative.

Mục tiêu có hai mốc độc lập: **engineering fixes verified** và **operational
acceptance verified**. Đạt mốc đầu không tự mở learner traffic.

## 2. Danh mục lỗi và thứ tự

| ID | Vấn đề đã quan sát | Ưu tiên | Phụ trách |
|---|---|---|---|
| R-01 | OpenAPI bỏ sót response content, extra query bắt buộc, missing type | P1 | Platform + BA + QA |
| R-02 | Production CORS vẫn cho `exp://` ngoài allowlist qua regex default | P1 | Platform + QA |
| R-03 | Readiness dùng chung file; 53/100 probe đồng thời thất bại trên storage khỏe | P1 | Platform + QA |
| R-04 | Streaming media mất byte-range: request 2 bytes nhận toàn bộ body/200 | P1 | Platform + Web/Mobile |
| R-05 | Orphan metadata thiếu vẫn eligible; force/retention flag vượt policy 24 giờ | P1 | Platform + BA/Ops |
| R-06 | E2E dùng chung `.next`, output và log dù port/DB đã tách | P2 | Platform + QA |
| R-07 | Upload write blocking và failure/cancellation cleanup chưa chứng minh đầy đủ | P2 | Platform + QA |
| R-08 | Container CLI/evidence và CI artifact gate chưa đầy đủ | P1 release | Platform + Ops |
| R-09 | Staging/performance/HTTPS/soak/rollback/native và chữ ký chưa đủ evidence | P1 release | Ops + QA + CTO |

Thứ tự: ghi nhận lại trạng thái -> R-01/R-02/R-03/R-05 -> R-04/R-07 -> R-06
-> R-08 -> R-09. Các việc có thể chia PR độc lập nhưng contract cần BA xác nhận
trước khi thay semantics. Mỗi lỗi bắt đầu bằng regression test tái hiện lỗi cũ.

## 3. R-01 — Contract gate bắt đúng drift

Files: `src/jplearn_api/openapi_diff.py`, `main.py`, router/schema liên quan,
`tests/test_openapi_mutation_suite.py`, `docs/sad/03-design/openapi.yaml`.

- [ ] Missing response content type/schema phải fail, kể cả response 2xx và 4xx.
- [ ] So parameter set hai chiều; extra required query phải fail. Middleware
      headers được bỏ qua chỉ qua allowlist ghi rõ lý do.
- [ ] Missing `type` phải fail; xử lý schema union/reference trước khi so.
- [ ] So constraint hai chiều: enum giữ đúng case/type; min/max/length/pattern,
      format, nullable, additionalProperties và required không bị âm thầm nới.
- [ ] Resolve response/request/parameter `$ref`; undefined reference phải báo lỗi.
- [ ] Bổ sung error schemas/status theo ADR-005; giữ các status đã ký và body 401
      riêng. Không sửa handwritten spec chỉ để làm comparator xanh.
- [ ] Khai báo chính xác media/HLS bearer OR signed-query authentication và kiểm
      effective security (bao gồm global security nếu có).
- [ ] Thêm mutation thay body 400 thành `{detail}` mà giữ nguyên status 400; bỏ
      từng security alternative ngay trên media/HLS, không thay bằng test `/me`.
- [ ] Toàn bộ mutation chạy qua CLI với generated spec được inject; mỗi mutant
      trả non-zero, diff chỉ đúng context. Baseline phải exit 0.

Nghiệm thu: ba mutation đã lọt audit và toàn bộ matrix trong plan trước đều đỏ;
generated schema đã loại 422 tại nguồn, không che drift trong comparator.

## 4. R-02 — CORS fail closed

Files: `settings.py`, `main.py`, `tests/test_obs.py` hoặc test CORS riêng.

- [ ] Staging/production yêu cầu explicit HTTPS origin allowlist; không kế thừa
      localhost/Expo mặc định. Parse/validate origin, không chỉ `startswith`.
- [ ] Tắt `cors_origin_regex` trong staging/production; từ chối regex rộng khi
      cấu hình production, trừ policy được duyệt riêng và có tests tương ứng.
- [ ] Test preflight và actual response qua middleware thật: approved origin
      được phép; `exp://unapproved.example.com`, localhost, HTTP, wildcard, null
      và lookalike domain không nhận permissive CORS headers.
- [ ] Local/test vẫn có cấu hình phù hợp cho Expo và dynamic E2E ports.

Nghiệm thu: production chỉ trả allow-origin cho origin đã duyệt; kiểm cả regex
default và regex truyền qua env. CORS không thay thế auth/authorization.

## 5. R-03 — Readiness an toàn khi concurrent/timeout

Files: `storage.py`, `routers/health.py`, readiness integration tests.

- [ ] Mỗi probe dùng key ngẫu nhiên riêng trong namespace dành cho probe; không
      dùng chung `__probe__/probe.tmp` giữa request/process/replica.
- [ ] Write/read/delete có `try/finally` để cleanup khi readback, fsync hoặc đọc
      lỗi. Cleanup error phải được quan sát, không báo healthy sai.
- [ ] Timeout không dừng thread I/O đang chạy: giới hạn số probe đang thực thi
      và thiết kế cleanup sau completion; không queue thread vô hạn khi disk treo.
- [ ] Quy định tổng timeout `/ready` cho DB + storage; không để client chờ vô hạn.
- [ ] Test 100 probe concurrent trên cùng root: 100 healthy, không còn probe file.
- [ ] Test root read-only, disk/write/delete error, timeout và cancellation;
      dependency hỏng -> 503; `/health` vẫn phục vụ liveness.

Nghiệm thu: không flapping do probe đụng nhau; timeout/cleanup có test cả adapter
thật và HTTP endpoint. Probe namespace không bị orphan reconciler xử lý nhầm.

## 6. R-04 — Khôi phục byte-range qua StoragePort

Files: `storage.py`, `media_service.py`, `routers/media.py`, media/HLS tests.

- [ ] BA/CTO ghi semantics cho single byte range, invalid/multiple range và
      conditional requests; Web/Mobile xác nhận yêu cầu seek/playback.
- [ ] Port nhận offset/length hoặc read-range capability; local adapter seek
      trực tiếp, không đọc bỏ toàn bộ bytes trước offset; fake adapter cùng contract.
- [ ] Không Range -> 200 đầy đủ; single satisfiable Range -> 206 đúng bytes,
      `Content-Range`, `Content-Length`, `Accept-Ranges: bytes`.
- [ ] Test closed/open-ended/suffix ranges, last byte, file rỗng và range vượt
      size (416 với `Content-Range: bytes */size`); ghi rõ policy malformed/multiple.
- [ ] Preserve auth/signature, MIME và `nosniff` cho MP4/HLS binary segments.
      Manifest đã rewrite signed URLs cần policy riêng, không dùng size bản gốc.
- [ ] Stream đóng file khi client disconnect; memory bounded, không buffer toàn file.
- [ ] Integration test qua HTTP thật xác nhận Range; browser test seek một MP4 dài
      hơn một chunk. Native playback giữ scope #30.

Nghiệm thu: request `bytes=0-1` trả 206 và đúng 2 bytes; tests chạy cùng local/fake
storage; HLS và 10 Web E2E vẫn xanh.

## 7. R-05 — Orphan deletion bảo vệ dữ liệu

Files: `reconciliation.py`, `storage.py`, ADR-005, reconciliation runbook/tests.

- [ ] Metadata error, thiếu/non-finite/future mtime -> protected/unknown, không
      eligible. Log lý do và trả báo cáo đủ để Ops điều tra.
- [ ] Retention tối thiểu 24 giờ; từ chối số âm, NaN, vô hạn và giá trị dưới policy.
- [ ] Bỏ `--force-delete` khỏi workflow thường; không cho flag vượt retention.
      Ngoại lệ khẩn cấp, nếu cần, là quy trình riêng được BA/Ops định nghĩa.
- [ ] Recheck tuổi/reference trước delete; phối hợp namespace/lifecycle để tránh
      xóa object mới được replace hoặc được tham chiếu sau snapshot đầu.
- [ ] Thống nhất flags giữa ADR-005, CLI và runbook. Default report-only; delete
      cần explicit execution/confirmation và danh sách target được ghi lại.
- [ ] Quy định xử lý `.part`, HLS và probe files thay vì bỏ qua toàn bộ vô điều
      kiện; file đang ghi phải được bảo vệ.
- [ ] Test unknown metadata, exactly-24h boundary, young/old orphan, live reference,
      metadata/read/delete failure và invalid flags bằng temp storage/test DB.

Nghiệm thu: không có đường delete file chưa chứng minh đủ tuổi và không được
tham chiếu; test không chạm `apps/api-python/storage` hoặc DB dev.

## 8. R-06/R-07 — E2E isolation và upload lifecycle

- [ ] Chọn cách nhỏ nhất bảo vệ E2E: serialize toàn runner bằng cross-process lock
      hoặc workspace/build directory riêng mỗi run. Dynamic port riêng chưa đủ.
- [ ] Build `.next`, Playwright output/report, API/web/build logs có scope theo run;
      identity chứa run ID và browser. Port allocation có retry khi collision.
- [ ] Cleanup chỉ tài nguyên của run; giữ log failed run đã redact để review.
- [ ] Chạy hai invocation: cả hai PASS độc lập hoặc thứ hai chờ lock rõ ràng.
- [ ] Offload upload filesystem writes với bounded concurrency/backpressure;
      không tạo task/thread riêng vô hạn cho từng chunk.
- [ ] Tái hiện cancel giữa stage/promote/DB commit; cleanup `.part`/final object
      theo trạng thái commit, tránh xóa file đã thuộc transaction thành công.
- [ ] Test injected event-insert failure trong EndSession rồi query bằng DB session
      mới để chứng minh session/progress/cả hai event rollback cùng nhau. Không
      chỉ patch hàm tính phút và gọi đó là event-write failure.

Nghiệm thu: memory/event-loop budget có số đo và ngưỡng trước khi chạy; failure
paths không để inconsistency không quan sát được. Giữ explicit commit và
request-scoped AsyncSession; chưa cần refactor UoW toàn backend.

## 9. R-08 — CI và migration evidence có thể tái tạo

- [ ] `migrate --help` trả 0; unknown command trả non-zero. Help không được tính
      là bằng chứng migration hoặc baseline verification.
- [ ] CI build image từ SHA review, lưu SHA/image digest và chạy image UID 10001.
- [ ] Test baseline resource từ wheel/container độc lập, không fallback repo làm
      che package resource bị thiếu/hỏng.
- [ ] Trong image: `upgrade`, `current`, adoption stamp trên DB có dữ liệu; empty
      DB và shape mismatch phải fail, không thay `alembic_version`.
- [ ] Kiểm app/CLI/seed environment resolver nhất quán theo plan trước; missing
      environment không cho destructive downgrade, `.env` precedence có test.
- [ ] Container `/ready` positive và negative: khi storage read-only thì DB vẫn
      healthy để cô lập nguyên nhân, và ngược lại.
- [ ] CI chạy guard, pytest, mutation CLI và Web E2E theo scope; giữ artifacts khi
      fail; image không được đánh release-ready nếu gate thiếu hoặc đỏ.

Nghiệm thu: reviewer có thể dựng lại từ clean checkout và chứng minh image được
test chính là digest release. Local image tag mutable chưa đủ.

## 10. R-09 — Bằng chứng vận hành và sửa trạng thái nghiệm thu

- [ ] Ngay PR đầu, reopen các checkbox chưa có evidence trong plan closure và
      walkthrough; đồng bộ board/gates, giữ lịch sử audit và các phần đã PASS.
- [ ] Không tự ký thay ghế khác. Mỗi acceptance ghi người/ghế, ngày, scope,
      commit/digest và link raw evidence; exception có phạm vi, owner và hạn xử lý.
- [ ] Ops cung cấp staging target, ingress/domain/TLS, cấu hình secrets, resources,
      persistent storage, backup destination và release job trước khi deploy.
- [ ] QA/BA ký workload T-NFR-P1: publish đến ba client thấy item <= 5 phút;
      pilot <= 15 phút chỉ khi có exception tương ứng.
- [ ] HTTPS T-NFR-S1 chạy từ external client; lưu kết quả TLS/HTTP policy và CORS.
- [ ] CTO/Ops ký duration/threshold cho soak trước khi chạy; lưu 5xx, latency,
      pool, memory, storage và progress/event reconciliation theo thời gian.
- [ ] Canary nội bộ, application rollback sang image trước, backup/restore clone
      có dữ liệu users/catalog/progress/events; kiểm counts, FK và nội dung mẫu,
      timestamps/RPO/RTO theo runbook. Không dùng schema downgrade làm restore.
- [ ] #30 trên iPhone/iPad/Android thật hoặc exception đúng phạm vi; Expo web/
      WebKit không được gọi là native acceptance.
- [ ] Evidence theo run gồm SHA/digest, commands/exit codes, timestamps, config
      không chứa secret và log/report thực tế. Markdown tóm tắt phải dẫn nguồn.

Nghiệm thu: chỉ đóng operational gate khi tất cả mục có evidence hoặc exception
được thẩm quyền chấp nhận. Thiếu staging/device/owner decision thì ghi BLOCKED
cho đúng mục; engineering fixes vẫn có thể review/merge theo quy trình repo.

## 11. Kiểm chứng và Definition of Done

Lệnh baseline (chạy từ repo root; E2E sau khi runner khác đã kết thúc/được lock):

```bash
pnpm test:guard
(cd apps/api-python && uv run pytest -q)
(cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.openapi_diff)
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

- [ ] R-01…R-07 có regression tests fail trước fix, PASS sau fix và evidence review.
- [ ] Không giảm coverage chỉ để giữ con số 112; số test mới được ghi từ run thật.
- [ ] 10 Web E2E PASS; two-run isolation test PASS/serialize được chứng minh.
- [ ] CI image/migration/readiness theo R-08 PASS tại SHA cuối.
- [ ] R-09 đóng bằng evidence/exception đúng ghế; không suy ra production-ready
      từ test local.
- [ ] Repo không lộ secret, không chỉnh/xóa DB dev, media dev hoặc dirty files
      ngoài scope; chỉ cleanup tài nguyên test do run tạo.

PR khuyến nghị: (1) reopen acceptance status, (2) contract + CORS, (3) readiness và
retention, (4) range + upload lifecycle, (5) E2E isolation, (6) CI image gate,
(7) staging evidence + acceptance. Review mỗi PR theo owner ở bảng mục 2.
