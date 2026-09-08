# Kết quả triển khai khắc phục backend

Ngày 2026-09-07; cập nhật 2026-09-08. Trạng thái: **R1–R6 đã có kiểm chứng local; R7 và R8 còn các gate được liệt kê bên dưới**. Phạm vi là working tree hiện tại, chưa deploy và chưa áp migration vào database phát triển của người dùng.

## Phần đã hoàn tất

- Playback dùng một writer/user, epoch + lease fencing, start/checkpoint/end idempotent và content-version pin. Receipt, resume, active-time, daily aggregate và trạng thái playback được commit cùng transaction. Gói muộn sau takeover, end hoặc deletion không cấp thêm credit hay hồi sinh dữ liệu.
- Active time dùng clock đơn điệu/cumulative, bị chặn bởi wall elapsed và drift toàn phiên; pause, seek, buffering, gap, final checkpoint và split qua ranh giới policy/ngày đã có hồi quy. Goal/timezone dùng effective policy version; topics áp dụng ngay. Activity trả current/longest streak và gộp nhiều policy bucket cùng ngày.
- Web và Mobile dùng cùng protocol: payload + idempotency key giữ nguyên qua retry, checkpoint tuần tự, final end đợi checkpoint đang chạy và reconciliation khi mất ACK. Mobile chọn phone/iPad device class và fallback `/sessions` khi capability tắt.
- Content version cấp số dưới catalog lock, không tạo draft từ GET, kiểm scene bounds/order/overlap và giữ snapshot cũ. Upload probe bằng ffprobe ngoài DB transaction; SHA-256 nguồn và measured duration được pin khi QA, kiểm lại khi publish; file nguồn bị đổi sẽ bị từ chối.
- Learner chỉ nhận scene metadata hoặc approved Japanese excerpt; full transcript nằm trong staff projection. Transcript save/submit/approve/return/apply dùng CAS ở database; stale AI apply bị chặn và search lọc authoritative published/approved eligibility.
- Capability matrix được thực thi phía server. Worker tắt hoặc thiếu provider không claim job; synthetic provider chỉ dùng explicit local/test. Search đã lọc ứng viên trong PostgreSQL trước khi xếp hạng/highlight trong ứng dụng.
- AI job reserve quota và insert job trong một transaction. Estimate lấy server-observed media duration và bảng giá server có `pricing_version`; `estimated_*` từ client chỉ còn là compatibility hint. Attempt có ID/provider idempotency/state/lease/usage riêng; provider call nằm ngoài transaction và connection DB.
- Timeout hoặc process crash chuyển attempt sang `outcome_unknown`, không blind retry và không tự nhả quota. Admin có API liệt kê/đối soát `billed` hoặc `not_billed` kèm evidence; cùng quyết định retry idempotent, quyết định khác trả conflict. Cancel/late result vẫn settle chi phí đúng một lần; sweeper cô lập attempt hết hạn.

## Migration và tương thích

| Revision | Nội dung |
|---|---|
| `0013_playback_recovery` | Preference policies, start receipts và playback recovery fencing |
| `0014_content_source_snapshot` | Snapshot source/provenance cho content version |
| `0015_ai_attempts` | Durable provider attempts và backfill job running thành unknown |
| `0016_media_probe` | `measured_duration_ms` và `source_sha256` cho asset/version |
| `0017_activity_policy_streak` | Daily aggregate theo `policy_revision`, hỗ trợ streak chính xác |
| `0018_hls_bundle_integrity` | Checksum HLS manifest và toàn bộ segment được tham chiếu |

Fresh install, packaged DDL snapshots và upgrade rehearsal từ `0012` lên `0018` chạy trên PostgreSQL test riêng. Rehearsal giữ dữ liệu preference/content/activity cũ, cô lập running AI job thành unknown và có thể chạy upgrade lại an toàn. Không reset database phát triển hoặc xóa named volume.

Rehearsal bổ sung bookmark, playback active và quota reservation cũ. HLS được pin bằng checksum manifest cùng các segment được tham chiếu; checksum không phụ thuộc ranh giới chunk của storage. Manifest chỉ tham chiếu vòng sang manifest khác nhưng không có media segment bị từ chối. CLI `inventory-media-integrity` liệt kê media/version legacy cần re-QA, chỉ đọc dữ liệu.

Legacy `/sessions` vẫn hoạt động. Start playback thiếu idempotency key vẫn được nhận để tương thích nhưng không có bảo đảm retry. Receipt hash cũ không tự chuyển sang fingerprint mới; rollout cần drain phiên cũ hoặc kiểm chứng cơ chế chuyển tiếp.

## Bằng chứng kiểm thử

Evidence tại [backend-remediation](evidence/backend-remediation/).

| Kiểm tra | Kết quả |
|---|---|
| API toàn bộ suite trên PostgreSQL 16/schema `0018` | **400 passed**, 2 cảnh báo deprecation; 71,42 giây; log `api-final-0018-20260908.log` |
| AI quota/job/attempt + concurrency/OpenAPI mục tiêu | **65 passed** |
| Search normalization/filter/ranking | **17 passed** |
| Web typecheck + unit | **40/40 passed** |
| Mobile typecheck + unit | **12/12 passed** |
| Shared domain | **3/3 passed** |
| Pedagogy guard | PASS |
| Docker image | Build PASS; ffprobe 7.1.5; runtime UID 10001; 37 bảng schema 0018; image ID `sha256:34d404df2ac79c2ebacb0b88d6a45aa55375315d6cd335a3aef46957c152865c` |
| Web E2E | **92/92 passed** trên Chromium + WebKit, 2,5 phút, exit 0; artifact `/tmp/jplearn-e2e-20260908115114_5698` |

## Hiệu năng candidate local

Harness `apps/api-python/differential/remediation_load.py` tạo database test riêng có 1.000 clip, 10.000 scene + approved search projection, 100.000 playback lịch sử và 100 playback đồng thời. Mỗi user gửi bốn heartbeat cách nhau 15 giây; harness kiểm credit cumulative đạt đúng 60.000ms. Raw artifact ghi 400 mẫu cho checkpoint/content/activity/search và 100 mẫu job-create, cấu hình pool 50/0, PostgreSQL/platform và từng status/latency.

| Operation | Steady p95 | Burst p95 | Đánh giá |
|---|---:|---:|---|
| checkpoint | 32,36ms | 300,56ms | Steady đạt SLO 100ms; burst chưa đạt |
| content read | 18,73ms | 261,64ms | Số đo tham khảo |
| activity | 11,04ms | 208,14ms | Số đo tham khảo |
| search | 21,87ms | 205,91ms | Số đo tham khảo |
| job-create | 25,12ms | 335,95ms | Số đo tham khảo |

Đây là ASGI in-process candidate measurement, không phải network latency hoặc production capacity. Hai lượt có cùng instrumentation, 0 lỗi và 0 deadlock; aggregate và receipts đều đúng 6.000.000ms. Xóa history sau tải ẩn ngay chi tiết và giữ 60 giây activity của user được kiểm tra. Đây chưa phải bài deletion cạnh tranh heartbeat trong lúc tải.

Pool acquisition p95: steady 0,012ms; burst 96,02ms. Burst chạm 50 connection ở 59/4.756 mẫu; một mẫu ghi nhận 3 lock waiter. Sampling 10ms có thể bỏ sót wait ngắn. Query plans đại diện đo sau tải mất 0,005–1,912ms; chưa bao phủ chính xác toàn bộ SQL thực thi trong request. Số liệu cho thấy queue/pool có đóng góp vào độ trễ nhưng chưa đủ để quy toàn bộ nguyên nhân cho pool.

Thử pool 80 giữ riêng ở `load-burst-pool80-candidate.json`: checkpoint p95 378,81ms, job-create 522,83ms, không chọn làm candidate. Workload hoàn tất nhưng pipeline ghi log trả exit 1 vì sai đường dẫn `tee`; JSON kết quả vẫn được tạo. Cấu hình runtime mặc định chưa thay đổi theo thử nghiệm này. Còn baseline cùng harness, SQL trace đầy đủ và network/staging load trước nghiệm thu R8.

## Gate còn mở

1. **R0 approval/retention:** engineering contract đã đồng bộ nhưng chưa có chữ ký Pedagogy/Ops; retention vẫn giữ raw 90 ngày và aggregate vĩnh viễn đến khi có quyết định riêng.
2. **Legacy rollout:** công cụ inventory đã có; còn chạy trên môi trường đích và re-QA nội dung legacy thực tế trước rollout.
3. **R7 provider/language quality:** chưa có provider thật, credential/budget smoke staging hoặc corpus + ngưỡng do Teacher duyệt. Tokenizer hiện chỉ là Unicode tokenizer; reading Kanji đúng nghĩa và Japanese inflection relevance chưa được nghiệm thu. Capability D tiếp tục tắt an toàn.
4. **R8 performance/rollout:** synchronized burst chưa đạt; đã có lock/pool/query-plan evidence ban đầu, còn profiling và tuning. Còn Safari/iPad/Expo trên thiết bị thật, network/staging load và pilot A → B/C → D.
5. **Rolling compatibility:** cần rehearsal drain/upgrade với receipt của playback đang chạy trước rolling deployment.

Không mở capability AI hoặc ghi “hoàn thành toàn bộ plan” chỉ từ bằng chứng local trên.
