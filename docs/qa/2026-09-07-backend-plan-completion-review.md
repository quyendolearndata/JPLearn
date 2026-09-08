# Kiểm tra hoàn thành kế hoạch API backend — 2026-09-07

**Kết luận: chưa đủ điều kiện xác nhận hoàn thành hoặc nghiệm thu A–D.** Nhiều endpoint, migration và test đã có, nhưng còn lỗi chức năng và bất biến dữ liệu. Đợt D hiện có worker dùng output mô phỏng, chưa chứng minh transcription thực tế.

Phạm vi: working tree hiện tại, đối chiếu `docs/superpowers/plans/2026-09-07-ejoy-inspired-backend-api.md`; rà soát theo ghế QA, BA, Platform và CTO. Đây là báo cáo kiểm tra, chưa sửa implementation.

## Kiểm chứng đã thực hiện

- `pnpm test:api`: **359 passed, 2 warnings**, 45.99 giây. Test DB dùng môi trường Docker test riêng.
- `pnpm test:guard`: **PASS**.
- `PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff` tại `apps/api-python`: **PASS**.
- Tái hiện bổ sung trong bộ nhớ bằng domain/handler/schema/repository thực với fake UoW hoặc mock session: serialization content, version number, lease playback, end sau xóa lịch sử, preference effective time, credit 2x, transcript revision và quota âm.
- Chưa chạy E2E Web/native, provider AI thật hoặc benchmark đồng thời theo corpus trong plan. Repro bằng fake/mock không thay thế kiểm chứng transaction/locking trên PostgreSQL thật.

Các test xanh không phủ hết các lỗi dưới đây; nhiều feature test hiện dùng fake repository/UoW.

## P1 — cần sửa trước nghiệm thu

### 1. Content response lỗi validation sau khi handler thành công

`apps/api-python/src/jplearn_api/entrypoints/http/routers/content.py:45` (cũng tại 66, 103) gọi `ContentVersionPublic.model_validate(version_dto)` với dataclass; schema không bật `from_attributes=True`. Repro trực tiếp nhận `ValidationError: model_type`. PUT commit trước khi dựng response nên có thể ghi thành công nhưng client nhận lỗi 500.

Sửa chuyển đổi DTO/schema và bổ sung HTTP integration test cho GET learner, GET staff, PUT content thành công.

### 2. Không tạo được content version tiếp theo

`apps/api-python/src/jplearn_api/application/handlers/content.py:80` và `:109` luôn tạo `version_number=1` khi không còn draft. Sau publish rồi trở lại draft, version mới có ID khác nhưng vẫn số 1, đụng UNIQUE `(catalog_item_id, version_number)` trong migration 0003. Fake repro xác nhận trùng số; lỗi constraint được suy ra từ DDL, chưa tái hiện chu kỳ này trên DB thật.

Cấp số phiên bản dưới catalog lock và kiểm thử publish → unpublish → sửa → publish lần hai với PostgreSQL.

### 3. Playback cũ có thể giành lại quyền ghi sau khi lease hết hạn

`apps/api-python/src/jplearn_api/application/handlers/playback.py:130` chỉ tăng epoch/supersede nếu lease còn hạn; checkpoint tại `:213` không kiểm active playback ID và lease. A hết hạn → B start cùng epoch → A checkpoint được chấp nhận và ghi đè lease của B tại `:285`.

Repro: `expired old playback stole lease=True`, `same epoch=True`. Mỗi lần chuyển owner phải vô hiệu hóa writer cũ; bổ sung kiểm thử cạnh tranh trên DB.

### 4. End đến muộn tái tạo resume sau xóa lịch sử

`apps/api-python/src/jplearn_api/application/handlers/playback.py:342` chỉ loại SUPERSEDED, vẫn xử lý ABANDONED; không kiểm final epoch/cutoff trước ghi checkpoint tại `:352`. Sau DELETE history, gói end muộn tạo resume mới. Purge tại `adapters/persistence/playback_repository.py:582` chỉ xóa checkpoint trước cutoff nên không xử lý checkpoint mới này.

Repro xác nhận resume được tạo lại. End phải tuân thủ cùng epoch, deletion cutoff và fencing như checkpoint.

### 5. Goal/timezone mới có hiệu lực sớm hơn API công bố

`application/handlers/activity.py:89` ghi đè preference, còn `application/handlers/playback.py:263` đọc ngay giá trị mới. `adapters/persistence/playback_repository.py:302` và `:338` còn cho phép thay goal của daily aggregate. Repro: effective_at vẫn ở tương lai nhưng aggregate đã dùng goal 120 và Pacific/Honolulu.

Cần lưu/chọn preference theo thời điểm hiệu lực, giữ nguyên goal đã snapshot của ngày cũ; OCC cần conditional update hoặc lock, không chỉ read–compare–write.

### 6. Active time không đúng thời gian thực

`application/handlers/playback.py:254` nhân trần elapsed với playback rate: 15 giây ở 2x chấp nhận 30.000 ms. Nhánh paused/buffering bỏ delta trước đó; end tại `:342` không áp dụng final cumulative vào accounting.

Trần phải theo wall time, đồng thời xử lý khoảng active cuối trước pause/end theo contract. Bổ sung test tốc độ 2x, pause giữa heartbeat và end ngay trước heartbeat.

### 7. Retry checkpoint mất tính idempotent sau takeover/end

`application/handlers/playback.py:207` kiểm trạng thái/epoch trước tra receipt tại `:221`. ACK đã commit nhưng mất response sẽ trở thành 409 nếu phiên vừa bị takeover/đóng. Request hash còn bỏ các trường có thể ảnh hưởng xử lý như playback rate.

Tra receipt sau ownership nhưng trước kiểm live state, dùng fingerprint payload đủ nghĩa; test commit → mất ACK → takeover/end → retry.

### 8. Media chưa được pin vào content snapshot đã QA

`application/handlers/media.py:483` đăng ký HLS không kiểm trạng thái QA/published hoặc catalog lock; ContentVersion chưa lưu media/source identity và duration snapshot. Có thể thay nguồn sau QA mà scenes/version vẫn giữ nguyên.

Ràng buộc media vào version, bắt buộc revision mới khi thay nguồn/timeline và kiểm measured duration ở submit/publish.

### 9. Capability tắt chưa chặn mutation ở server

Ví dụ `entrypoints/http/routers/collections.py:79` và content routes không kiểm feature setting; routes được đăng ký vô điều kiện. Cờ false ở `/capabilities` không ngăn request có token gọi API. ADR-007 cũng yêu cầu server từ chối khi capability tắt.

Bổ sung gate phía server và test flag-off cho từng endpoint tương ứng.

### 10. Transcript revision không được lưu tăng

`adapters/persistence/transcript_repository.py:125` cập nhật text nhưng không cập nhật `orm.revision`; thiếu atomic CAS. Repro với actual repository/mock session: input revision 2, persisted/returned revision vẫn 1, text đã đổi. Request stale có thể tiếp tục ghi đè.

Thực hiện UPDATE có điều kiện revision và kiểm số row thay đổi; test hai writer cùng expected revision trên DB thật.

### 11. Estimate âm có thể làm tăng quota khả dụng

`entrypoints/http/schemas.py:783` nhận estimate không ràng buộc; `application/handlers/content_jobs.py:127` dùng estimate client; `domain/quota.py:85` không loại số âm trước reserve. Repro estimate audio −100, cost −1.000.000: quota max 100 trở thành available 1.000.100.

Estimate phải do server tính từ media/model; chặn số âm ở schema/domain và bảo vệ bất biến ledger trong DB. Client tự khai estimate thấp/0 cũng không đủ để kiểm soát ngân sách.

### 12. Reserve quota và tạo job không atomic

`application/handlers/content_jobs.py:121` gọi helper reserve; `application/handlers/ai_usage.py:69` commit trước khi job insert tại `content_jobs.py:161`. Crash hoặc unique conflict sau commit có thể để lại reservation không có job để settle/release. Đây là kết luận từ transaction flow, chưa fault-injection trên DB.

Gom reserve và job insert vào một transaction; test rollback và concurrent duplicate create.

### 13. Cancel/takeover AI job có thể làm mất ghi nhận chi phí

`adapters/persistence/content_job_repository.py:127` reclaim running job hết lease để gọi lại provider. `application/handlers/content_jobs.py:358` bỏ kết quả khi token đổi trước settle usage; cancel cũng xóa token. Kết quả trả muộn có thể đã phát sinh phí nhưng không được ghi nhận, hoặc reservation bị treo.

Theo dõi usage/outcome theo attempt độc lập với quyền apply result; reconcile outcome chưa rõ trước retry billable work. Cần provider giả lập timeout/late-success/cancel để kiểm thử.

## P2 và khoảng trống nghiệm thu

- **AI chưa phải implementation thực tế:** `entrypoints/cli/ai_worker.py:46` trả cố định `こんにちは、世界！`, scene ID `scene-1`, token/cost hardcoded; default worker dùng stub, không đọc media. Cần provider thật hoặc công bố D chưa hoàn thành. Segmentation và language analysis hiện cũng chưa chứng minh chất lượng như yêu cầu; analysis mới gom ký tự, không có Kanji reading thực tế.
- **Validation scene:** `domain/content.py:96` so start với start trước nên cho phép `[0,30]`, `[10,40]` overlap; duration thay đổi sau PUT không được revalidate đầy đủ ở QA/publish.
- **Bằng chứng performance chưa đạt plan:** `apps/api-python/differential/benchmark_perf.py:120` chạy tuần tự 50 GET activity, 50 checkpoint, 25 DELETE trên dữ liệu seed nhỏ. Không đại diện corpus 1.000 clips/10.000 scenes/100.000 playbacks và 100 người đồng thời. Vì vậy kết luận PASS rộng trong `docs/qa/evidence/pr7-performance-benchmark.md` chưa đủ chứng minh mục tiêu tải/lock/pool.
- **Mâu thuẫn contract:** plan giới hạn transcript đầy đủ cho staff, nhưng ADR-007 Accepted cho learner nhận transcript JP. Cần BA chốt contract và đồng bộ plan/ADR/OpenAPI/tests; chưa coi riêng khác biệt này là lỗi code đã xác nhận.
- **Pilot và relevance:** chưa có kiểm chứng trong lần audit này về native/E2E, nguồn AI thật, độ phù hợp search tiếng Nhật và tiêu chí đánh giá Teacher. Không suy ra các mục này đạt từ unit tests.

## Trạng thái theo đợt và thứ tự xử lý

| Đợt | Đánh giá |
|---|---|
| A — content/scenes/series/saved scenes/collections/reports | Có implementation; bị chặn bởi response validation, version lifecycle, media snapshot và capability gates |
| B — playback/resume/accounting | Có implementation; bị chặn bởi lease, deletion fencing, accounting và retry |
| C — preferences/activity/history/recommendation | Có implementation; chưa đạt effective-time/deletion invariants và bằng chứng tải |
| D — jobs/transcript/search/quota | Có khung triển khai; còn lỗi CAS/quota/transaction/reconciliation, provider mặc định mô phỏng |
| E và AI speaking | Deferred theo plan; không tính là lỗi thiếu delivery A–D |

Ưu tiên sửa lỗi response và version lifecycle; sau đó playback/deletion/accounting; tiếp theo transcript CAS, quota và job transactions. Bổ sung regression tests bằng PostgreSQL cho race/constraint/rollback trước khi chạy lại toàn bộ suite. Chỉ kết luận hoàn thành sau khi chốt contract khác biệt, xác minh provider thực và bổ sung bằng chứng performance/pilot đúng phạm vi.
