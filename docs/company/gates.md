# Mẫu ký cổng

Sao chép khối dưới vào cuối artifact khi review. Không ký bằng miệng.

## Cổng SAD-1 — SRS

- Tài liệu: `docs/sad/01-survey-srs/srs.md`
- **Artifact:** có — SRS + in/out scope
- **Chữ ký:** đã ký 2026-08-25 — CPO, Pedagogy, CTO (issue #2)
- CPO: tên / ngày / đồng ý phạm vi in-out
- Pedagogy: tên / ngày / đồng ý ràng buộc cấm textbook
- CTO: tên / ngày / đồng ý NFR khả thi

## Cổng SAD-2 — Phân tích

- Tài liệu: `docs/sad/02-analysis/` + [diagrams.md](../sad/02-analysis/diagrams.md)
- **Artifact:** có — use case, diagrams, [event audit](../sad/02-analysis/event-payload-audit.md)
- **Chữ ký:** đã ký 2026-08-25 — BA, Pedagogy, CTO (issue #3)
- BA: mọi FR nền tảng map ≥1 use case
- Pedagogy: domain không chứa điểm ngữ pháp/từ vựng như tiến độ
- CTO: domain hiện thực được bằng Hướng A

## Cổng SAD-3 — Thiết kế (được phép scaffold)

- Tài liệu: `docs/sad/03-design/` + spec tổng hợp + [diagrams](../sad/03-design/diagrams.md) + [15 khung](../sad/03-design/wireframes/README.md)
- **Artifact:** có — scaffold + wireframes merged
- **Chữ ký:** đã ký 2026-08-25 — CEO, CPO, BA, Pedagogy, CTO (issue #4)
- **Mở lại 2026-08-31** — [ADR-003](../sad/03-design/adr-003-runtime-python.md) supersede một phần ADR-001 (runtime API). Năm ghế ký lại; khối 2026-08-25 **giữ**. `apps/api-python` (FastAPI) là **backend duy nhất** từ 2026-09-04 và **sở hữu DDL** qua Alembic theo [ADR-004](../sad/03-design/adr-004-ddl-alembic.md) (CTO ký 2026-09-04; supersede ADR-003 D2 «Prisma giữ DDL»). Phase 0–4 đủ: health + OpenAPI semantic diff + auth + flags/catalog + sessions/progress/events + media/HLS. pytest 54/54 PASS; web e2e 10/10 Chromium+WebKit (`docs/qa/adr-003-web-e2e-python.md`); differential Nest↔FastAPI 40/40 (`docs/qa/differential/2026-09-04T071945Z-parity.json`) — ảnh chụp đóng băng, `apps/api` đã xoá nên **không tái tạo được**. Guard FR-NEG §4 đã port sang pytest. Còn: #30 native, cutover Phase 5 (staging soak / canary / rollback drill).
- CEO, CPO, BA, Pedagogy, CTO: năm chữ ký
- Điều kiện: truy vết FR/NFR → use case → API/bảng → test ID

## Cổng nền tảng — được phép SAD vòng học (Phase 5)

- Tài liệu: spec §8 + [traceability](../sad/03-design/traceability.md) + board #12–#17
- **Phiên ký:** CEO mở 2026-08-25 (rút HOLD). Không ký miệng.
- **Người ký:** CEO, CPO, Pedagogy, CTO (`docs/README.md`)
- **Điều kiện (spec):** bible; truy vết FR v1; 3 client cùng catalog; publish ≤ NFR-PERF-001; event phút; quyền media; tokens 3 bề mặt
- **Cấm sau khi ký:** flashcard, dịch L1-as-meaning, grammar drill như “thử nghiệm nhỏ” (FR-NEG). Flags `speaking_enabled` / `l1_subtitles_enabled` / `grammar_enabled` / `flashcards_enabled` **giữ false** đến khi Pedagogy bật có chủ đích.

### Checklist phiên này

| Điều kiện | Hiện trạng |
|---|---|
| Shell 3 bề mặt + CMS publish + sự kiện phút | **Đạt** — web + API; #13 pipeline; #14 e2e; #16 events |
| 10 clip thí điểm + quyền | **Đạt thí điểm** — #12 Veo/Commons + Kyoko; không phải 70–95s người thật |
| HLS trên web và iPad (NFR-PERF-002) | **Đã đóng phía web 2026-08-25/26** — CiPlayer hls.js + fallback MP4 (#31); #40 vá nosniff + ký segment trong manifest → e2e PASS cả Chromium lẫn WebKit (Chromium phát HLS thật, không rớt MP4); iPad native player có code (expo-video) chờ verify máy thật (#30) |
| Playback URL đã ký (FR-CMS-003/004) | **Đã đóng 2026-08-25** — HMAC `exp`+`sig` trên playback/hls URL (#24, T-CMS-003 PASS); #35 thêm guard publish thiếu media + unpublish; #39 seed không còn tái tạo item ma |
| UC-L06 native iPhone/iPad/Android | **Exception** — PASS API + web; native PARTIAL (#17), theo dõi #30 (config EAS dev build + checklist đã sẵn sàng 2026-08-26, chờ Expo login + Apple Developer của founder) |
| NFR-OBS 5xx alert; NFR-A11Y đo | **Đã đóng 2026-08-26** — request id + log 5xx JSON (#25); webhook stub `ALERT_WEBHOOK_URL` (#38, default tắt, Ops bật trên staging); contrast AA PASS (#34); document-title PASS (#36) |

Nợ exception = việc Platform/Mobile/QA **sau cổng**, không chặn SAD vòng học. Không dùng exception để mở FR-NEG.

**Chữ ký:** đủ bốn ghế 2026-08-25 (khối dưới).

## Cổng retire NestJS (ADR-003 §7) — CEO override 2026-09-04

- Tài liệu: [ADR-003 parity checklist](../qa/adr-003-parity-checklist.md) §7 + [ADR-004](../sad/03-design/adr-004-ddl-alembic.md)
- **Quyết định:** retire `apps/api` (NestJS + Prisma) **ngay**, xoá khỏi repo. Commit cuối còn nó: `7a05e62`. Backend duy nhất là `apps/api-python` (FastAPI), sở hữu DDL qua Alembic (ADR-004, CTO ký 2026-09-04); ADR-003 D2 bị supersede.
- **Người ký:** CEO (một ghế). **QA không ký mục 7** và đã ghi lại đây là quyết định **vượt cổng** — không phải cổng đã đạt.
- Phương án chọn: đóng nốt mục 6 trước khi xoá, chỉ override #30 và staging soak.

### Trạng thái 7 mục §7 lúc ký

| Mục §7 | Hiện trạng |
|---|---|
| 1. Critical §1 = 100% `PASS cả hai` + log | **Đạt** — differential Nest↔FastAPI 40/40 (`docs/qa/differential/2026-09-04T071945Z-parity.json`) |
| 2. Contract semantic diff trong allowlist | **Đạt** |
| 3. Gate §3 có test CI | **Đạt** — byte-level argon2 / JWT / HMAC |
| 4. Guard FR-NEG §4 (kể cả negative) | **Đạt** — FR-NEG-004 guard đã port sang pytest |
| 5. Web E2E Python xanh; native theo #30 | **Override một phần** — web 10/10 Chromium+WebKit **đạt**; native **chưa**, #30 vẫn mở |
| 6. T-NFR-P1 / T-NFR-PR1 / T-NFR-S1 HTTPS | **Override một phần** — T-NFR-O1/O2 (alert 5xx, 4xx không alert) và T-NFR-PR1 (không lộ credential) đã có test thật; **T-NFR-P1 (NFR-PERF-001) và T-NFR-S1 phần HTTPS: chưa test, chưa exception ký** |
| 7. Stabilization internal staging + runbook Platform+Ops duyệt + rollback drill | **Override toàn bộ** — chưa soak, chưa runbook duyệt, chưa drill. FastAPI **chưa nhận một request thật nào từ người dùng** |

pytest 54/54 PASS.

### Rủi ro CEO nhận

- **Không còn đường rollback** sang Nest ngoài git history (`7a05e62`).
- **Không còn baseline** để chạy lại differential; evidence 40/40 là ảnh chụp đóng băng, không tái tạo được trong worktree hiện tại.
- **Chưa có bằng chứng vận hành**: chưa soak, chưa canary, chưa rollback drill, chưa native #30.
- Mất DX `prisma migrate dev`. Node vẫn cần cho web/mobile và guard FR-NEG — «hết Node» chỉ đúng ở tầng backend.

### Nợ phải trả — vẫn treo, không được coi là đã xong

- Mục 7: staging soak + canary + runbook Platform+Ops duyệt + rollback drill — Phase 5, **trước** khi có learner thật.
- Mục 6: T-NFR-P1 và T-NFR-S1 phần HTTPS — test mới hoặc exception ký như cổng nền tảng.
- #30 (UC-L06 Expo iPhone/iPad máy thật) — mở. Không tuyên bố parity native.
- Override này **không** mở FR-NEG, **không** đổi trạng thái cổng nền tảng, **không** rút điều kiện Phase 5.

---

## Chữ ký (2026-08-25)

### Cổng SAD-1
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi in/out SRS
- Pedagogy — Quyen Do — 2026-08-25 — Đồng ý ràng buộc cấm textbook
- CTO — Quyen Do — 2026-08-25 — Đồng ý NFR khả thi

### Cổng SAD-2
- BA — Quyen Do — 2026-08-25 — Mọi FR nền tảng map ≥1 use case
- Pedagogy — Quyen Do — 2026-08-25 — Domain không có điểm ngữ pháp/từ vựng như tiến độ
- CTO — Quyen Do — 2026-08-25 — Domain hiện thực được bằng Hướng A

### Cổng SAD-3
- CEO — Quyen Do — 2026-08-25 — Đồng ý scaffold theo thiết kế
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi scaffold
- BA — Quyen Do — 2026-08-25 — Truy vết FR/NFR → UC → API/bảng → test
- Pedagogy — Quyen Do — 2026-08-25 — Shell không vi phạm bible
- CTO — Quyen Do — 2026-08-25 — ADR-001 + OpenAPI + schema đúng

### Cổng SAD-3 (mở lại 2026-08-31 — ADR-003)
- CEO — Quyen Do — 2026-08-31 — Mở lại cổng SAD-3; đồng ý rewrite API sang FastAPI là quyết định runway/tiền, không có FR driver
- CPO — Quyen Do — 2026-08-31 — Đồng ý phạm vi ADR-003; card `FR-LRN-*` không đợi runtime Python; không mở FR-NEG
- BA — Quyen Do — 2026-08-31 — Đồng ý delta log; D3/D4 là `INTENTIONAL_REQUIREMENT_CHANGE`; sẽ cập nhật SRS → use case → traceability → OpenAPI trước Phase 1
- Pedagogy — Quyen Do — 2026-08-31 — Đồng ý FR-NEG vẫn đóng; D3 logout toàn thiết bị không mở textbook; bốn flag giữ `false`
- CTO — Quyen Do — 2026-08-31 — Đồng ý D1 FastAPI 3.12, D2 Prisma giữ DDL + SQLAlchemy mapping-only, D3 `uv`, D4 OpenAPI viết tay + semantic diff; không Alembic trong giai đoạn song song

### Cổng nền tảng
- CEO — Quyen Do — 2026-08-25 — Mở phiên ký; rút HOLD; chấp nhận exception HLS/URL ký/UC-L06 native; cấm FR-NEG; được phép SAD vòng học (Phase 5), không tự bật flag
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi nền tảng; card `FR-LRN-*` được vào board sau cổng này; không flashcard/JLPT
- Pedagogy — Quyen Do — 2026-08-25 — Shell không textbook; clip Veo 10s không thay bible 70–95s; silent period đến khi bật `speaking_enabled`
- CTO — Quyen Do — 2026-08-25 — Schema không cột cấm; HLS/object storage/URL ký ghi nợ exception, không tuyên bố NFR-PERF-002 đã đủ hardware production

### Cổng retire NestJS (override 2026-09-04 — ADR-003 §7)
- CEO — Quyen Do — 2026-09-04 — Override §7: mục 5 phần native, mục 6 phần T-NFR-P1 + T-NFR-S1 HTTPS, mục 7 toàn bộ. Retire `apps/api` ngay; `apps/api-python` là backend duy nhất, sở hữu DDL theo ADR-004. Nhận rủi ro không rollback ngoài `7a05e62`, không tái tạo được differential, không bằng chứng vận hành. QA **không ký** mục 7. Nợ soak/canary/rollback drill/#30/T-NFR-P1/HTTPS giữ mở; không mở FR-NEG
