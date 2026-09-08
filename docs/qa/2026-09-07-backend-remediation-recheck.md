# Kiểm tra lại bản sửa R0–R8

Ngày 2026-09-07. **Kết luận: đã sửa một phần, chưa đủ điều kiện nghiệm thu toàn bộ R0–R8.** Kiểm tra working tree hiện tại theo [plan khắc phục](../superpowers/plans/2026-09-07-backend-remediation-plan.md). Không sửa implementation hoặc dữ liệu phát triển trong lần kiểm tra này.

## Bằng chứng mới

- `pnpm test:api`: **372 passed, 2 warnings, 45.09s**. Có 4 test trong `test_remediation_concurrency.py` chạy với Docker PostgreSQL test riêng và đều đạt.
- `pnpm test:guard`: **PASS**.
- Tại `apps/api-python`, `PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff`: **PASS**. Không gọi với `--strict`, không suy diễn kết quả thành BA contract đã thống nhất.
- Repro bổ sung bằng handler thực và fixture fake trong bộ nhớ: final active 5.000ms cho kết quả total_active_ms=0; preference effective_at ở tương lai nhưng current read đã là 120/Pacific/Honolulu.
- Chưa chạy E2E Web/native, provider tính phí hoặc load benchmark trong lần này. Các reviewer phụ không hoàn thành do workspace hết credits; kết luận dưới đây được kiểm tra trực tiếp qua mã nguồn và test, không dựa vào đánh giá phụ chưa có.

## Các sửa đổi đã xác nhận

- Content response đã thêm chuyển đổi từ attributes; 2 HTTP tests content đạt.
- GET staff content không còn tự ghi draft; PUT dùng max version + 1 dưới catalog lock. Test tranh chấp content update trên PostgreSQL đạt; chưa coi đó là bằng chứng đầy đủ cho vòng publish/fork/media.
- Domain đã chặn overlap scenes bằng end của cảnh trước.
- Một số route đã có server capability gate, gồm content, collections và playback start.
- Playback start tăng epoch khi chuyển owner kể cả lease cũ hết hạn; receipt lookup đã chuyển trước kiểm live state. Test takeover/replay đạt.
- Trần checkpoint đã bỏ nhân playback rate; end đã thêm kiểm deletion cutoff.
- Transcript repository có conditional UPDATE revision và kiểm rowcount; test hai writer trên PostgreSQL đạt.
- Job create gọi reserve với `auto_commit=False`; chặn estimate âm và thêm estimate tối thiểu phía server. Test provider completion đồng thời cancel đạt.
- Web tracker dùng clock đơn điệu và bổ sung các event buffering/seek. Stub AI có guard môi trường, nhưng đây chưa phải provider thật.

## Findings còn mở

### [P1] F01 — End vẫn bỏ toàn bộ active time cuối phiên (R3/R4)

`apps/api-python/src/jplearn_api/application/handlers/playback.py:345`: end chỉ lưu position/seq rồi đóng phiên; không dùng final_client_cumulative_active_ms, không ghi daily activity hay receipt final. Repro: start → 5 giây → end(final cumulative=5000) trả total_active_ms=0. Clip ngắn kết thúc trước heartbeat có thể không ghi phút active nào.

End cũng chưa kiểm final epoch/active playback ID đầy đủ và chưa đi qua workflow checkpoint chung. Cần test end giữa heartbeat, stale epoch, duplicate end và end cạnh tranh checkpoint trên PostgreSQL.

### [P1] F02 — Preference future-effective chưa được triển khai (R4)

`application/handlers/activity.py:89` vẫn ghi đè một preference và gắn effective_at tương lai; `application/handlers/playback.py:259` đọc dùng ngay. `adapters/persistence/playback_repository.py:304` upsert không conditional revision; tại `:342` vẫn overwrite goal của daily aggregate.

Repro current read dùng 120/Pacific/Honolulu trong khi effective_at chưa đến. Cần version/pending policy, CAS và snapshot ngày; thêm ca nửa đêm/DST/hai update đồng thời. Việc chỉ bỏ nhân tốc độ không đóng P1.5 cũ.

### [P1] F03 — Retry client sau mất ACK vẫn đổi payload cùng seq (R4)

`apps/web/src/lib/playback-tracker.ts:225` dựng payload mới mỗi lần gọi; seq chỉ tăng khi nhận response thành công tại `:258`. Nếu server đã commit nhưng response mất, heartbeat kế tiếp dùng cùng seq với position/cumulative mới, bị server trả 409; client hiểu thành takeover và dừng video tại `:246`.

`end()` tại `:270` không chờ checkpoint in-flight, đặt active=false trước request và bỏ lỗi mạng tại `:299`, nên chưa có retry final đáng tin cậy. Cần lưu pending payload bất biến và tuần tự hóa end sau ACK/reconcile. Đây là kết luận theo control flow; chưa chạy trình duyệt tái hiện mạng mất ACK.

### [P1] F04 — Media chưa thuộc snapshot version bất biến (R2)

`domain/content.py:34` không có media/source identity/duration snapshot. `application/handlers/media.py:494` register HLS vẫn không catalog lock/status validation; chỉ kiểm manifest tồn tại rồi cập nhật asset. Upload draft guard đã thêm không bao phủ đường này hoặc bảo toàn source của version cũ.

Cần pin nguồn và duration đã kiểm chứng, kiểm lifecycle tại submit/publish/register. Chưa có migration mới cho phần snapshot trong working tree được kiểm tra.

### [P1] F05 — Playback start chưa idempotent và client chưa pin version (R3)

`entrypoints/http/routers/playbacks.py:69` không nhận idempotency key hoặc content version từ client. Handler mỗi lần start tạo ID mới tại `application/handlers/playback.py:146`; retry cùng thiết bị có thể supersede phiên vừa tạo thay vì trả lại phiên cũ. Client có contentVersionId nhưng không gửi trong start.

Cần receipt start scoped user/payload và version pin, test commit rồi mất response, retry sau thay published version.

### [P1] F06 — AI lease hết hạn vẫn gọi lại công việc có khả năng tính phí (R6)

`adapters/persistence/content_job_repository.py:132` claim cả running job hết lease để thực hiện attempt mới. Worker tại `application/handlers/content_jobs.py:351` gọi provider lại; chưa có durable attempt/outcome reconciliation trước bước này. Settle trước token guard đã sửa ca cancel đơn giản, nhưng chưa chứng minh nhiều attempt billable được đối soát đúng một lần. Worker đọc media hiện tại từ catalog tại `:343`, chưa dùng nguồn đã pin của job.

Cần fault tests provider chậm hơn lease, worker crash sau provider success, hai completion và reconcile outcome unknown. Không đóng P1.13 chỉ bằng test cancel hiện có.

### [P1] F07 — Kill switch chưa kiểm soát toàn bộ worker/accounting (R1)

`entrypoints/cli/ai_worker.py:99` tiếp tục claim mà không kiểm staff_ai_enabled. Checkpoint router tại `entrypoints/http/routers/playbacks.py:184` và handler accounting không đọc tracking flag, nên tắt flag sau start vẫn có thể ghi active time mới. Cho phép reconcile/end khi cờ tắt là hợp lý, nhưng phải phân biệt cleanup/replay với tiếp tục hoạt động mới theo ma trận R0.

### [P2] F08 — R0 vẫn mâu thuẫn, tài liệu kết luận quá phạm vi

`docs/sad/03-design/adr-007-ci-learning-loop-contracts.md:45` vẫn ghi heartbeat 30 giây/delta_seconds và `:57` lease 90 giây, khác implementation 15/45/cumulative. Chưa thấy decision log thay thế toàn bộ contract, preference và retention như R0 yêu cầu.

`walkthrough.md:193` tuyên bố tất cả P1/P2 đã giải quyết; các F01–F07 cho thấy chưa đúng. Giữ kết quả test thực tế nhưng sửa trạng thái nghiệm thu theo từng gate.

### [P2] F09 — R7/R8 chưa có deliverable đầy đủ

`entrypoints/cli/ai_worker.py:61` vẫn trả text cố định, scene-1 và usage hardcoded; constructor mặc định tại `:95` chưa tích hợp provider thật. Guard stub chỉ là một phần R7, không thay transcription/segmentation và đánh giá Teacher.

`apps/api-python/differential/benchmark_perf.py:120`, `:147`, `:167` vẫn là các vòng tuần tự 50/50/25 request. Chưa chứng minh corpus 1.000 clips/10.000 scenes/100.000 playbacks, 100 người đồng thời, migration rehearsal có dữ liệu và pilot native/iPad theo R8.

### [P2] F10 — Receipt fingerprint và trần drift chưa đủ (R3/R4)

`application/handlers/playback.py:212` hash chỉ position/state/cumulative, bỏ epoch/duration/rate/scene. Tại `:254` cộng tolerance cho mỗi heartbeat, chưa giới hạn drift tích lũy toàn phiên như R4 yêu cầu. Cần test payload đổi cùng seq và nhiều heartbeat gửi dồn có cumulative vượt wall time; không suy ra correctness từ test 2x riêng lẻ.

## Trạng thái kế hoạch sau kiểm tra

| Mục | Trạng thái |
|---|---|
| R0 | Chưa đạt — contract và trạng thái nghiệm thu chưa thống nhất |
| R1 | Một phần — response/gates có sửa; worker/accounting gate còn thiếu |
| R2 | Một phần — numbering/GET/overlap có sửa; media snapshot còn thiếu |
| R3 | Một phần — epoch/replay cải thiện; start/final protocol chưa đủ |
| R4 | Chưa đạt — preference, final accounting và client retry còn lỗi |
| R5 | CAS có bằng chứng PostgreSQL; projection/contract chưa đủ bằng chứng đóng toàn R5 |
| R6 | Một phần — reserve transaction/cancel cải thiện; attempt reconciliation chưa đạt |
| R7 | Chưa hoàn thành provider thực và chất lượng tiếng Nhật |
| R8 | 4 DB regression tests đạt; chưa đủ load/migration/pilot gates |

Ưu tiên sửa F01/F02/F03, sau đó F04–F07; bổ sung regression tương ứng trước khi chạy lại suite. Có thể nghiệm thu riêng từng sửa đổi đã có bằng chứng, chưa dùng 372 tests xanh để đóng toàn bộ remediation.
