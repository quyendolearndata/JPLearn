# Replatform API NestJS → FastAPI

> **For agentic workers:** ADR-003 **đã ký**. Phase 0–3 **xong** (toàn bộ 19 route). Tiếp: Phase 4 differential parity (hai DB clone, critical 100%), rồi Phase 5 cutover.

**Goal:** Thay runtime API (`apps/api` NestJS) bằng FastAPI, giữ DDL Prisma, contract OpenAPI viết tay, và hành vi learner không đổi — sau khi drift được phân loại và cổng được ký.

**Architecture:** Rewrite/replatform, không refactor. `apps/api-python` song song, **active-passive** (một writer). SQLAlchemy mapping-only. Cutover trên **internal staging**; production vẫn env riêng.

**Tech Stack:** Python 3.12, FastAPI, `uv`, SQLAlchemy 2.0 (no Alembic), PostgreSQL hiện tại, OpenAPI 3.0.3 file trong repo.

## Global Constraints

- Động lực: preference Python — không có FR driver; không thêm hành vi learner.
- Cổng ký ADR: **CEO, CPO, BA, Pedagogy, CTO** (`docs/company/gates.md` SAD-3). QA không thay BA. QA ký parity checklist; Platform+Ops duyệt cutover runbook.
- DDL owner song song: Prisma Node. Cấm Alembic / `create_all` / autogenerate.
- Contract: `docs/sad/03-design/openapi.yaml`; semantic normalized diff + allowlist (không YAML literal; FastAPI sinh 3.1).
- Pydantic: model **từng** response; cấm `response_model_exclude_none` global.
- Critical parity 100%: auth, authorization, session/progress, HLS, FR-NEG.
- Abort: dừng deploy, tag/archive nhánh, giữ evidence — không xoá `apps/api-python` như bước abort.
- Đánh giá tĩnh: harness test API còn dirty; **chưa** chạy lại e2e cho plan này.

---

## Artifact phải tạo (Phase 0 docs) — phiên này

Đã tạo; ADR-003 **Accepted** 2026-08-31. Checklist QA chưa ký (retire Nest):

| File | Ghế |
|---|---|
| `docs/sad/03-design/adr-003-runtime-python.md` | CTO |
| `docs/sad/03-design/adr-003-contract-delta.md` | BA |
| `docs/qa/adr-003-parity-checklist.md` | QA |

**Không** giả định các file này đã có trước phiên. **Không** trích «vector mẫu đã nằm trong checklist» — vector HMAC/argon2/JWT **tạo ở Phase 1** sau khi ký.

## Quyết định stack (chốt)

| | |
|---|---|
| Framework | FastAPI, Python 3.12. `Depends()` hữu ích; lifecycle Nest **không** 1-1 |
| ORM | SQLAlchemy 2.0 mapping-only; Prisma giữ migration `0001`…`0004` |
| Package manager | `uv` (`pyproject.toml`, `.python-version`, `uv.lock`) |
| Prisma Python | **Không** (archived) |

Chi tiết schema/time/session: ADR-003 §2.

## Phase 0 — Quyết định & baseline yêu cầu (trước code)

- [x] Ký ADR-003 đúng **năm ghế SAD-3** (CEO, CPO, **BA**, Pedagogy, CTO) — 2026-08-31, `gates.md`.
- [x] Phê duyệt delta D3/D4 là `INTENTIONAL_REQUIREMENT_CHANGE` rồi cập nhật **SRS → use case → traceability → OpenAPI** (không «sửa câu chữ»).
- [x] Áp D1, D2, D5–D9 `CONTRACT_FIX_TO_RUNTIME` trên OpenAPI (+ `/health`, error schema, HLS security Bearer **OR** `exp`+`sig`, `title_internal` required, docs UI policy).
- [x] D10 race `end()`: giữ `KNOWN_DEBT_CARRIED` (comment `sessions.service.ts` + hàng board.md). Card GitHub khi CPO tạo.
- [x] Card board: ghi bảng ADR-003 trên `board.md` (Seat CTO / Gate Platform / Surface API / NFR-XPLAT-001 + FR-NEG-004). Issue GitHub khi CPO `gh issue create`.
- [x] Feature freeze API ghi vào `board.md`; cutover runbook **dự thảo** = `deployment.md` D8 + plan Phase 5 — chưa deploy.

**Exit:** chữ ký đủ; OpenAPI/SRS/UC khớp nhãn; checklist QA **chưa** ký retire Nest.

## Phase 1 — Compatibility gates & risk spike (sau ký, trước app)

- [x] **Tạo** test vectors (JSON dùng chung Node/Python): HMAC, argon2, JWT `sub`/`email`/`ver`/`jti` — `docs/qa/vectors/` + `apps/api/test/vectors.spec.ts`.
- [x] **Risk spike sớm** — `docs/qa/adr-003-risk-spike-storage.md`; `STORAGE_ROOT` trên Nest.
- [x] Thêm Playwright project WebKit **cạnh** Desktop Chrome — không thay #30.
- [x] Merge/ổn định harness `apps/api/test/docker-*.cjs` + global setup/teardown — 2026-09-04 Jest 14+contract PASS. Evidence: `docs/qa/adr-003-harness.md`.
- [x] Contract suite trên **NestJS** xanh (baseline) — `apps/api/test/contract.e2e-spec.ts`.
- [x] Scanner `assert-no-textbook.ts` + `.py`; T-NEG-004 trên `information_schema`; negative test.

**Exit:** baseline Nest xanh; spike không blocker ẩn; vectors committed.

## Phase 2 — Scaffold `apps/api-python`

- [x] FastAPI lifespan; `AsyncSession` per request; transaction tường minh; aware UTC ↔ naive UTC adapter; JSON `Z`. (scaffold: health + models mapping-only + datetime_adapt; chưa port business)
- [x] Exception handler → 400 Nest shape; CORS như `main.ts`; `/health`; `x-request-id`; alert 5xx / 4xx im.
- [x] Tắt `/docs` `/redoc` `/openapi.json` public trên staging (`OPENAPI_UI` default false).
- [x] Model map đúng TEXT / TIMESTAMP(3) / enums / JSONB / unique / CHECK L1.
- [x] Semantic OpenAPI diff job (allowlist 3.0↔3.1) — `jplearn_api/openapi_diff.py` + `tests/test_openapi_diff.py`.

**Exit:** health + error mapping + empty router; CI job Python không phá job pnpm.

## Phase 3 — Port vertical slice

Thứ tự: auth → flags/catalog → sessions/progress/events → **media/HLS cuối**.

- [x] Auth — `POST /auth/register|login|logout`, `GET /me`; argon2id m=65536,p=4,t=3; JWT `sub`/`email`/`ver`/`jti`; logout tăng `token_version` mọi device; pytest + vectors.
- [x] Flags/catalog — `GET /flags`, `PATCH /staff/flags` (admin); `GET /catalog` published only; staff create/submit-qa/publish/unpublish; teacher≠publish; HMAC vectors; chưa port upload/HLS stream.
- [x] Sessions/progress/events — `POST /sessions`, `POST /sessions/{id}/end`, `GET /progress`; events `session_started`/`level_exposed`/`session_ended`/`minutes_comprehensible`; zombie >4h = 0; `ended_at`/`duration_seconds` null lúc start; D10 race giữ nguyên (comment `KNOWN_DEBT_CARRIED`).
- [x] Media/HLS — upload `POST /staff/catalog/{id}/media`; `GET /media/{id}` dual-mode Bearer hoặc `exp`+`sig`; `GET /media/{id}/hls/{file}` rewrite m3u8, MIME, `nosniff`, chặn `..`; `POST /staff/media/{id}/hls` 201 khi manifest có trên disk.

Mỗi slice Done khi pytest + contract subset + byte gate của slice. Sessions: key-set null; **không** «fix» race D10. Media: dual-mode, rewrite m3u8, MIME, traversal.

## Phase 4 — Differential parity

- [x] Hai DB clone, cùng corpus, không dual-write — `apps/api-python/differential/run_parity.py`: Nest :3101 (DB clone A) vs FastAPI :3102 (DB clone B), 40 bước, so status/key-set/nullability/error shape/headers + `learning_events` trực tiếp trên 2 DB.
- [x] Ma trận QA: critical 100% — 40/40 PASS, evidence `docs/qa/differential/2026-09-04T071945Z-parity.json`; differential đã bắt và sửa 4 lệch thật: 401 không có `error`, 403 `Forbidden resource`, 404 `Cannot GET /…`, `nosniff` trên 400/404 HLS.
- [x] Web E2E → API Python — `differential/web-e2e-python.sh`: **10/10 (Chromium + WebKit) trên cả Python lẫn Nest baseline**; evidence `docs/qa/adr-003-web-e2e-python.md`; vá flake WebKit bằng prod build. Expo máy thật lặp #30 còn mở (manual) — WebKit ≠ iPad native.

## Phase 5 — Cutover

CEO override 2026-09-04: retire Nest **trước** stabilization, đảo thứ tự plan gốc.
Bản ghi: `docs/company/gates.md`; QA không ký mục 7 (`docs/qa/adr-003-parity-checklist.md`).

- [x] Writer duy nhất — FastAPI là backend duy nhất; `apps/api` đã xóa (commit cuối còn nó: `7a05e62`).
- [x] ADR-004 DDL — Alembic sở hữu DDL (`adr-004-ddl-alembic.md`), baseline chống drift `docs/qa/adr-004-schema-baseline.json` + `tests/test_schema_ddl.py`. Plan gốc xếp việc này *sau* stabilization; đã kéo lên vì xóa Nest là xóa luôn Prisma.
- [x] Vá lỗ hổng coverage trước khi xóa: `test_sync.py` (T-ID-002/T-PRG-004/T-NFR-X1 — trước chỉ có bên Nest), `test_obs.py` (T-NFR-O1/O2), `test_contract.py`, T-NFR-PR1. pytest 54/54.
- [ ] Shadow GET-only — **không còn khả thi**, không còn runtime thứ hai để so.
- [ ] Target **internal staging**; canary, soak, reconciliation (`deployment.md`).
- [ ] Rollback drill — rollback về Nest giờ chỉ còn `git checkout 7a05e62`, không phải thao tác vận hành.
- [ ] Exception ký cho T-NFR-P1 (NFR-PERF-001) + T-NFR-S1 phần HTTPS.
- [ ] #30 Expo máy thật (UC-L06 native) — override không đóng nợ này.

## Abort

Critical chưa 100%; HMAC/argon2/ORB/FR-NEG không đóng; guard `.py` chưa vá. → dừng deploy, tag/archive, giữ evidence. Nest vẫn writer.

## Việc cố tình không làm trong plan này

- Sửa SRS/OpenAPI trước chữ ký.
- Implement FastAPI.
- Ký giả cổng.
- Chạy e2e trên harness dirty và tuyên bố PASS.
