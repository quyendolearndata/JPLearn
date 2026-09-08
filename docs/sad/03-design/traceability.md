# Ma trận truy vết

> Evidence cuối cho T-LRN-001 / T-SES-REC-001 F-03:
> [media retry/HLS fix](../../qa/media-retry-fix-evidence-2026-09-06.md), working-tree
> patch từ `564275e`, full E2E 44+44 PASS. Bao phủ retry sau chọn default và native
> HLS WebKit restore paused/playing. Các SHA closeout bên dưới giữ lịch sử;
> Design/device vẫn PARTIAL, không thêm FR/Test ID hoặc mở production gate.

Test IDs là mã truy vết yêu cầu, không phải pytest node IDs. Backend tests hiện
nằm trong `apps/api-python/tests/`; xem [development](../../backend/development.md)
và [mapping theo revision](../../qa/clean-architecture-audit/test_mapping_and_reconciliation.md).
Không suy ra mọi hàng PASS từ việc tồn tại file test; trạng thái cổng cần evidence đúng revision.

Kịch bản SAD-2 (bước chính / phụ, «include» / «extend»): [use-cases.md](../02-analysis/use-cases.md). Quan hệ UML: [diagrams.md](../02-analysis/diagrams.md) mục 1b. SAD-2 đã có class diagram (mục 6) và state diagram cho `CatalogItem.status` + `LearningSession` (mục 7). R0 bổ sung FR-FLG-003/T-FLG-003; test IDs là chỉ tiêu kiểm tra, chưa tự xác nhận PASS.

| Req | Use case | Thiết kế | Test |
|---|---|---|---|
| FR-ID-001 | UC-L01, UC-T01 | POST /auth/register, /auth/login | T-ID-001 register+login, T-AUTH-ERR-001 login 400 hiển thị, T-AUTH-SEC-001 redirect an toàn |
| FR-ID-002 | UC-L01, UC-L06 | cùng token schema 3 client | T-ID-002 same user 3 surfaces |
| FR-ID-003 | UC-L01 | POST /auth/logout (tăng `tokenVersion`; mọi token cũ 401) | T-ID-003 logout mọi thiết bị |
| FR-ID-004 | UC-T01, UC-A03 | User.roles | T-ID-004 learner forbidden staff |
| FR-CAT-001 | UC-T02 | catalog_items + POST /staff/catalog | T-CAT-001 |
| FR-CAT-002 | UC-L02 | GET /catalog chỉ published | T-CAT-002 draft hidden; scenario F-03 item đã chọn không được thay bằng item khác (engineering PASS `41a4009`/`d1715d2`) |
| FR-CAT-003 | UC-L02 | query ci_level | T-CAT-003 |
| FR-CAT-004 | UC-L02, UC-T02 | CatalogItemPublic không field dịch | T-CAT-004 schema |
| FR-CAT-005 | UC-T02, UC-T02b, UC-T05 | staff create, GET /staff/catalog, PATCH /staff/catalog/{id} | T-CAT-005 staff list & edit, T-CAT-005-CAS atomic CAS |
| FR-SES-001 | UC-L03, UC-L10 | POST /sessions (Idempotency-Key), GET /sessions/{id} | T-SES-001 start, T-SES-004 idempotency & status, T-SES-003-IDEM-CONCUR concurrency lock; T-SES-REC-001; scenario F-01 không ghi đè phiên chưa xác nhận (engineering PASS `41a4009`/`d1715d2`) |
| FR-SES-002 | UC-L04 | POST /sessions/{id}/end | T-SES-002; T-SES-REC-001; scenario F-02 ended path dùng chung luồng tổng kết (engineering PASS `41a4009`/`d1715d2`) |
| FR-SES-003 | UC-L03 | session không cần media | T-SES-003; T-SES-REC-001; scenario F-01 giữ key/state khi retry (engineering PASS `41a4009`/`d1715d2`) |
| FR-PRG-001 | UC-L04, UC-L05 | minutes tăng khi end. ADR-003 D10 resolved tại FastAPI hardening: `SELECT ... FOR UPDATE` exactly-once | T-PRG-001; scenario F-02 tải progress sau ended (engineering PASS `41a4009`/`d1715d2`) |
| FR-PRG-002 | UC-L05 | current_ci_level | T-PRG-002; scenario F-02 tổng kết có dữ liệu progress thật (engineering PASS `41a4009`/`d1715d2`) |
| FR-PRG-003 | UC-L05 | OpenAPI additionalProperties false | T-PRG-003 no extra scores |
| FR-PRG-004 | UC-L06 | GET /progress | T-PRG-004 |
| FR-CMS-001 | UC-T03 | upload media | T-CMS-001 |
| FR-CMS-002 | UC-T04, UC-A01 | submit-qa, publish | T-CMS-002, T-CMS-E2E-001 full lifecycle |
| FR-CMS-003 | UC-A01, UC-L02, UC-L10 | playback_url HMAC `exp`+`sig` | T-CMS-003; scenario F-03 refresh URL cho đúng item (engineering PASS `41a4009`/`d1715d2`; WebKit HLS = engine, không phải iPhone) |
| FR-CMS-004 | UC-A01 | URL từ API (không CDN hardcode) | T-CMS-004 |
| FR-FLG-001 | UC-A02 | GET /flags defaults false | T-FLG-001 |
| FR-FLG-002 | UC-A02 | UI ẩn | T-FLG-002 client |
| FR-FLG-003 | UC-A02, UC-L17, UC-L24 | GET /capabilities; server gates/allowlist, end/reconcile zero-credit khi off | T-FLG-003 capability matrix |
| FR-EVT-001 | UC-L03, UC-L04 | learning_events table | T-EVT-001 |
| FR-EVT-002 | UC-L04 | minutes event | T-EVT-002 |
| FR-EVT-003 | UC-L03 | level_exposed on start | T-EVT-003 |
| FR-NEG-001 | — | không route flashcard | T-NEG-001 |
| FR-NEG-002 | — | không route grammar | T-NEG-002 |
| FR-NEG-003 | — | không translation trên public item | T-NEG-003 |
| FR-NEG-004 | — | ERD cấm cột | T-NEG-004 |
| NFR-XPLAT-001 | UC-L06 | C4 3 client 1 API | T-NFR-X1 |
| NFR-XPLAT-002 | — | ui-shell iPad | T-NFR-X2 visual |
| NFR-PERF-001 | UC-A01 | runbook publish | T-NFR-P1 |
| NFR-PERF-002 | — | ADR media | T-NFR-P2 |
| NFR-SEC-001 | — | HTTPS, hash | T-NFR-S1 |
| NFR-SEC-002 | UC-T01 | 403 learner staff | T-NFR-S2 |
| NFR-PRIV-001 | — | PII tối thiểu | T-NFR-PR1 |
| NFR-A11Y-001 | S-LOGIN, S-SESSION | keyboard pause (P5 play) / chrome AA | T-NFR-A1 axe 8 routes + error/active/summary/staff-detail; keyboard form/player; scenario F-04 keyboard thực tế (engineering PASS `41a4009`/`d1715d2`; Design PARTIAL — chưa Safari/device) |
| NFR-OBS-001 | — | request id + alert webhook 5xx (stub, `ALERT_WEBHOOK_URL`) | T-NFR-O1 echo `x-request-id`; T-NFR-O2 alert 5xx env bật/tắt, 4xx im |
| FR-LRN-001 | UC-L10 | web `<video>` / CiPlayer trong phiên, HLS/MP4, signed URL | T-LRN-001 player clip, T-NFR-A1 keyboard controls, T-SES-REC-001 session recovery; scenario F-03 giữ đúng item khi refresh media (engineering PASS `41a4009`/`d1715d2`; WebKit HLS = engine) |
| FR-LRN-002…004 | UC-L11–12 | chưa | T-P5-hold |
| FR-SCN-001 | UC-T06, UC-T09, UC-L14 | content_versions, scenes + PUT /staff/catalog/{id}/content, GET /catalog/{id}/content | T-SCN-001 scene breakdown & transcript, T-SCN-CAS concurrency |
| FR-SER-001 | UC-T07 | series, episodes + POST/PATCH /staff/series | T-SER-001 series ordering & lookup |
| FR-RSM-001 | UC-L16 | playback checkpoints + GET /me/resume/{catalog_item_id} | T-RSM-001 position resume cross-device |
| FR-WAT-001 | UC-L17, UC-L24 | playbacks + PUT /playbacks/{id}/checkpoints/{seq}; POST start/end; cumulative15s/lease45s | T-WAT-001 active watch accounting, T-WAT-002 lease takeover |
| FR-HIS-001 | UC-L19 | GET/DELETE /me/watch-history + deletion job/cutoff/tombstone | T-HIS-001 history cursor pagination & clear |
| FR-GOL-001 | UC-L18 | effective preference versions + GET/PUT /me/learning-preferences; policy-aware GET /me/activity with current/longest streak | T-GOL-001 goal & streak tracking |
| FR-REC-001 | UC-L20 | GET /me/recommendations | T-REC-001 level & topic stream recommendations |
| FR-BMK-001 | UC-L15 | bookmarks + POST/GET/DELETE /bookmarks | T-BMK-001 context bookmarking (no SRS) |
| FR-COL-001 | UC-L21 | collections, collection_items + /collections | T-COL-001 custom playlists & library isolation |
| FR-RPT-001 | UC-L23 | GET /me/activity; legacy progress separate | T-RPT-001 aggregated reports dual-metric |
| NFR-LAT-001 | UC-L17 | atomic checkpoint transaction; steady ASGI candidate đạt, synchronized burst chưa đạt | T-NFR-LAT-001 p95 heartbeat < 100ms |
| NFR-RET-001 | UC-L19, UC-L23 | raw playback 90d retention, rollup permanent | T-NFR-RET-001 event retention policy |
| NFR-CONCUR-001 | UC-L17, UC-L24 | lease epoch CAS, session lock SELECT FOR UPDATE | T-NFR-CONCUR-001 concurrent heartbeat & takeover safety |
| NFR-MIG-001 | — | Alembic migration & Prisma adoption | T-MIG-002-ADOPT |

Lỗ = hàng FR nền tảng không có UC hoặc không có thiết kế. Cổng nền tảng 2026-08-25: exception HLS player / native UC-L06 / alert 5xx còn mở.

### Ghi chú scenario recovery follow-up (2026-09-06)

Không thêm FR/Test ID. Candidate code `41a4009`, evidence `d1715d2`
([recovery-followup-evidence-2026-09-06.md](../../qa/recovery-followup-evidence-2026-09-06.md)).
Lịch sử closeout `fd838d2` (217 / 21+21 / 7) giữ nguyên.

- F-01 (FR-SES-001/003, T-SES-REC-001): engineering PASS — không ghi đè phiên chưa xác nhận; giữ key khi retry.
- F-02 (FR-SES-002, FR-PRG-001/002, T-SES-REC-001): engineering PASS — ended path dùng chung luồng tổng kết.
- F-03 (FR-LRN-001, FR-CMS-003, FR-CAT-002, T-LRN-001): engineering PASS — refresh URL đúng item; WebKit HLS = engine, không phải iPhone/Safari thật.
- F-04 (NFR-A11Y-001, T-NFR-A1): engineering PASS + Design PARTIAL — axe/keyboard Playwright Chromium/WebKit; chưa rà Safari/device; không claim WCAG 2.2 AA.
- Mốc B CMS: giữ hồi quy lịch sử `fd838d2`; không dựng lại workflow.
- Release gate: không đổi (không production).

### Trạng thái hiện thực (2026-08-25)

| Hạng | Trạng thái |
|---|---|
| FR v1 identity/catalog/session/progress/flags/events | PASS API + web |
| FR-CMS-003/004 signed URL | PASS API (HMAC query; JWT vẫn được) |
| FR-FLG-002 | PASS web `useFlags()`; kênh tắt không vẽ |
| FR-LRN-001 | ENGINEERING PASS — Web và Expo tracker; thiết bị thật ở rollout gate |
| UC-L06 native | PARTIAL — API + Expo code/test; máy thật chưa |
| NFR-PERF-002 HLS trên client | GAP |
| NFR-A11Y-001 contrast đo | GAP |
| NFR-OBS-001 alert 5xx staging | PASS (stub) — webhook `ALERT_WEBHOOK_URL`, default tắt; URL kênh thật (Slack) chờ Ops cấp |

### R0 engineering amendment — 2026-09-07

Playback/goal/history rows reference the remediation contract and local engineering evidence. T-WAT-001/002 cover final checkpoint, lease expiry, takeover and receipt retry; T-GOL-001 covers current/pending policy, midnight/DST, active-only và streak; T-HIS-001 covers late packets and deletion cutoff; T-SCN-001 covers staff-only transcript and separately approved learner excerpt. PostgreSQL concurrency, Web E2E và Mobile unit/typecheck đã đạt; thiết bị thật/staging/pilot vẫn thuộc rollout gate. NFR-RET-001 is unchanged pending a separate BA/Ops policy decision.

## CMS completion — ADR-008

| Req | UC | API / model | Tests |
|---|---|---|---|
| FR-CAT-005 | UC-T02 | GET staff catalog/list/detail; PATCH draft | test_cms_workflow.py |
| FR-CMS-002 | UC-T04/Q01/Q02/A01 | POST review; catalog_reviews; qa_round; publish approval gate | test_cms_workflow.py |
| FR-CMS-001, NFR-SEC-002 | UC-T03 | Draft-only upload/HLS; staff authorization | test_cms_workflow.py |

Integration retains mandatory revision-based PATCH concurrency control and merges both migration histories at `0019_merge_cms_reviews`.
