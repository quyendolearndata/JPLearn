# Ma trận truy vết

Test ID sẽ dùng khi có repo test. Cột Test = tên dự kiến.

| Req | Use case | Thiết kế | Test |
|---|---|---|---|
| FR-ID-001 | UC-L01, UC-T01 | POST /auth/register, /auth/login | T-ID-001 register+login |
| FR-ID-002 | UC-L01, UC-L06 | cùng token schema 3 client | T-ID-002 same user 3 surfaces |
| FR-ID-003 | UC-L01 | POST /auth/logout | T-ID-003 logout |
| FR-ID-004 | UC-T01, UC-A03 | User.roles | T-ID-004 learner forbidden staff |
| FR-CAT-001 | UC-T02 | catalog_items + POST /staff/catalog | T-CAT-001 |
| FR-CAT-002 | UC-L02 | GET /catalog chỉ published | T-CAT-002 draft hidden |
| FR-CAT-003 | UC-L02 | query ci_level | T-CAT-003 |
| FR-CAT-004 | UC-L02, UC-T02 | CatalogItemPublic không field dịch | T-CAT-004 schema |
| FR-CAT-005 | UC-T02 | staff create | T-CAT-005 |
| FR-SES-001 | UC-L03 | POST /sessions | T-SES-001 |
| FR-SES-002 | UC-L04 | POST /sessions/{id}/end | T-SES-002 |
| FR-SES-003 | UC-L03 | session không cần media | T-SES-003 |
| FR-PRG-001 | UC-L04, UC-L05 | minutes tăng khi end | T-PRG-001 |
| FR-PRG-002 | UC-L05 | current_ci_level | T-PRG-002 |
| FR-PRG-003 | UC-L05 | OpenAPI additionalProperties false | T-PRG-003 no extra scores |
| FR-PRG-004 | UC-L06 | GET /progress | T-PRG-004 |
| FR-CMS-001 | UC-T03 | upload media | T-CMS-001 |
| FR-CMS-002 | UC-T04, UC-A01 | submit-qa, publish | T-CMS-002 |
| FR-CMS-003 | UC-A01, UC-L02, UC-L10 | playback_url HMAC `exp`+`sig` | T-CMS-003 |
| FR-CMS-004 | UC-A01 | URL từ API (không CDN hardcode) | T-CMS-004 |
| FR-FLG-001 | UC-A02 | GET /flags defaults false | T-FLG-001 |
| FR-FLG-002 | UC-A02 | UI ẩn | T-FLG-002 client |
| FR-EVT-001 | UC-L03, UC-L04 | events table | T-EVT-001 |
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
| NFR-A11Y-001 | S-LOGIN, S-SESSION | keyboard pause (P5 play) / chrome AA | T-NFR-A1 |
| NFR-OBS-001 | — | request id | T-NFR-O1 echo `x-request-id` |
| FR-LRN-001 | UC-L10 | web `<video>` trong phiên, signed URL | T-NFR-A1 keyboard controls |
| FR-LRN-002…004 | UC-L11–12 | chưa | T-P5-hold |

Lỗ = hàng FR nền tảng không có UC hoặc không có thiết kế. Cổng nền tảng 2026-08-25: exception HLS player / native UC-L06 / alert 5xx còn mở.

### Trạng thái hiện thực (2026-08-25)

| Hạng | Trạng thái |
|---|---|
| FR v1 identity/catalog/session/progress/flags/events | PASS API + web |
| FR-CMS-003/004 signed URL | PASS API (HMAC query; JWT vẫn được) |
| FR-FLG-002 | PASS web `useFlags()`; kênh tắt không vẽ |
| FR-LRN-001 | PARTIAL — player web trong phiên; chưa Expo |
| UC-L06 native | PARTIAL — API+web; máy thật chưa |
| NFR-PERF-002 HLS trên client | GAP |
| NFR-A11Y-001 contrast đo | GAP |
| NFR-OBS-001 alert 5xx staging | PARTIAL — log JSON khi 5xx + request id |
