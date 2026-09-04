# ADR-003 — Runtime lớp API: Python/FastAPI

- Trạng thái: **Accepted** (cổng SAD-3 mở lại 2026-08-31) — chữ ký §10. **Chưa scaffold `apps/api-python`:** còn Phase 0 (áp delta SRS/OpenAPI, harness, vector).
- Ngày: 2026-08-31
- Người đề xuất: ghế CTO (theo yêu cầu founder)
- Quan hệ: **Supersedes một phần [ADR-001](adr-001-stack.md)** — chỉ runtime API. Web (Next.js), Expo, PostgreSQL, object storage, CMS `/staff` **giữ nguyên**. Số **ADR-003** (ADR-002 đã dành cho CMS khi `/staff` outgrow). **D2 superseded bởi [ADR-004](adr-004-ddl-alembic.md)** (2026-09-04) — chủ DDL là Alembic.
- Kèm: [delta log BA](adr-003-contract-delta.md) · [parity checklist QA](../../qa/adr-003-parity-checklist.md) · [plan](../../superpowers/plans/2026-08-31-api-python-replatform.md)

## 1. Bối cảnh và động lực

Động lực founder: **thích/thạo Python hơn cho backend.** Không có FR/NFR đang GAP vì NestJS; không giao hành vi mới cho learner.

Đây là **rewrite/replatform**, không phải refactor. Signers — nhất là CEO về runway — ký với nhận thức đó.

Nợ cổng: **#30 (UC-L06 native)** vẫn Todo. WebKit Playwright **không** thay baseline Expo/iPad máy thật.

## 2. Quyết định

### D1 — FastAPI, Python 3.12+

`APIRouter` / `Depends()` gần Nest về mặt đọc code; lifecycle/provider **không** tương đương 1-1. Pydantic theo **từng** response model, không chính sách `exclude_none` toàn API.

### D2 — DDL: Prisma (Node). Python: SQLAlchemy 2.0 mapping-only

> **SUPERSEDED bởi [ADR-004](adr-004-ddl-alembic.md) — 2026-09-04.** Văn bản D2 dưới đây **giữ nguyên** làm lịch sử: nó đúng cho giai đoạn song song hai runtime một schema. Giai đoạn đó kết thúc khi `apps/api` bị xóa (§7), nên phần «Prisma là nguồn DDL duy nhất» và phần «cấm Alembic» hết hiệu lực từ 2026-09-04. Phần còn lại của D2 — SQLAlchemy 2.0 mapping-only, ràng buộc schema vật lý, quy ước thời gian, session/transaction — **vẫn còn hiệu lực**.

- **Loại Prisma Client Python** (repo archived 2025-04-15).
- `apps/api/prisma/schema.prisma` + migrations `0001`…`0004` + `_prisma_migrations` là nguồn DDL duy nhất trong giai đoạn song song.
- **Cấm** Alembic, `create_all`, autogenerate. ADR-004 (sau cutover) mới xét chuyển DDL; điều kiện: guard FR-NEG chạy trên schema mới.

Schema vật lý phải map đúng: `TEXT` id (UUID app/Prisma), `TIMESTAMP(3)` **without time zone**, named enums PostgreSQL, JSONB, unique `(user_id, device_class)`, CHECK `published ⇒ has_l1_translation = false` (chỉ có trong SQL migration, **không** trong `schema.prisma` — mapping Python không được làm mất CHECK).

**Thời gian:** Python dùng datetime **aware UTC**. Adapter ghi/đọc naive UTC cho cột `TIMESTAMP(3)`. JSON ra **ISO-8601 UTC với `Z`** (khớp `Date.toISOString()` hiện tại).

**Session/transaction:** mỗi request/task một `AsyncSession`; không chia sẻ giữa concurrent tasks; không implicit lazy I/O. Transition nghiệp vụ (`end` session, publish, …) phải có transaction tường minh. Race `end()` đồng thời: [D10 delta](adr-003-contract-delta.md) = `KNOWN_DEBT_CARRIED` trừ khi Nest được sửa trước.

### D3 — `uv`

`pyproject.toml`, `.python-version`, `uv.lock`.

### D4 — Contract authority

File `docs/sad/03-design/openapi.yaml` (3.0.3) **viết tay** là contract. FastAPI mặc định OpenAPI 3.1.0 — so sánh bằng **semantic normalized diff + allowlist**, không diff YAML/JSON literal. Giữ: HTTP status, required/nullability, security, `operationId`, `x-jplearn-fr`, error schema. Không lấy `/openapi.json` public làm nguồn sự thật.

## 3. Phạm vi

| Đổi | Giữ |
|---|---|
| Runtime API → FastAPI (`apps/api-python` sau khi ký) | Web, mobile, Postgres, storage, `/staff` UI |
| Job CI Python riêng | Prisma DDL; OpenAPI viết tay |

**Active-passive:** một runtime nhận write. Shadow chỉ GET/read-safe. Cutover target hiện tại = **internal staging**. **Production vẫn là environment riêng** (`deployment.md`: Prod không Q1). Không đồng nhất «production = staging».

## 4. Hệ quả

**Được:** founder code API bằng Python; hạ tầng sẵn nếu sau này có FR ML/ASR.

**Mất:** nguyên tắc ADR-001 «một ngôn ngữ». `@jplearn/domain` hết làm link kiểu API↔client (`DEFAULT_FLAGS`, `minutesFromDuration` / `ZOMBIE_SESSION_SECONDS` 4h, `CatalogItemPublic`) — drift không còn compile error. Hai host, hai job CI. Feature freeze lớp API khi song song.

## 5. Rủi ro chặn (không đủ liệt kê trong e2e «xanh»)

| Rủi ro | Sự thật | Chặn |
|---|---|---|
| Guard FR-NEG chết | Guard cũ đọc file `.prisma`; `scripts/assert-no-textbook.ts` chỉ `ts/tsx/prisma/sql` | Scanner `.py` + assert `information_schema` + negative test, nay ở [`apps/api-python/tests/test_schema_ddl.py`](../../../apps/api-python/tests/test_schema_ddl.py) (`schema.guard.spec.ts` đã xóa cùng `apps/api`) |
| HMAC / ORB / storage | `signed-url.ts`; `nosniff` + MIME + rewrite segment; `process.cwd()/storage` | **Risk spike Phase 1** (trước khi port Media xong): `STORAGE_ROOT` chung, vector HMAC, streaming, Chromium ORB |
| JWT `ver` / argon2 | `tokenVersion`; `argon2.hash` default node-argon2 | Vector chéo Node↔Python; token Nest verify được ở Python và ngược lại |
| Response null vs omit | `/sessions` `ended_at: null` **khác** field thiếu; `/progress` đúng hai key | Model Pydantic **từng** operation; test key-set + nullability. **Cấm** `response_model_exclude_none` mặc định toàn app |
| FastAPI 422 | Nest 400 `{statusCode,message,error}` | Exception handler map về shape Nest |
| Dual-mode media | JWT **hoặc** signed query | Cả hai nhánh + thiếu cả hai → 401 |

## 6. Tiền điều kiện — trước dòng Python ứng dụng (sau khi ký)

1. Delta D1–D9 áp dụng theo nhãn; contract suite xanh trên **NestJS** (baseline).
2. Scanner FR-NEG đọc `.py`; guard cột trên DB thật; negative test đỏ đúng lúc.
3. Vector HMAC + argon2 + JWT `sub`/`email`/`ver`/`jti`.
4. Harness Docker test API **đã merge ổn định** (working tree hiện chưa xong — đánh giá này không chạy lại e2e).
5. Risk spike storage/HMAC/ORB có kết luận ghi nhận.
6. #30 đóng **trước khi tuyên bố parity cross-surface**; không chặn viết ADR nhưng chặn «implementation-ready cho cutover native».

## 7. Điều kiện retire `apps/api`

> **Đã retire 2026-09-04.** `apps/api` (NestJS + Prisma) bị xóa khỏi repo; commit cuối còn nó: `7a05e62`. Việc này **vượt** cổng mô tả bên dưới, theo quyết định override của ghế CEO — bản ghi override thuộc ghế CEO + QA ([parity checklist](../../qa/adr-003-parity-checklist.md) §7, [gates.md](../../company/gates.md)), không phải mục này. Văn bản điều kiện giữ nguyên bên dưới làm lịch sử: nó là thứ **đã bị vượt**, không phải thứ đã được thoả. DDL sau retire: [ADR-004](adr-004-ddl-alembic.md).

QA sở hữu [parity checklist](../../qa/adr-003-parity-checklist.md). Vùng **critical 100%**: auth, authorization, session/progress, HLS, FR-NEG. Không dùng ngưỡng «≥90%» cho các vùng đó.

Không xoá Nest khi pytest vừa xanh. Stabilization window trên **internal staging**. Rollback drill trước cutover. Platform + Ops duyệt runbook cutover (không thay chữ ký SAD-3).

**Abort:** dừng deploy Python, tag/archive nhánh, **giữ evidence** (log, vector, diff). **Không** xoá `apps/api-python` như điều kiện abort.

## 8. Phương án loại

- Giữ ADR-001 — rẻ nhất; loại vì không thoả động lực founder.
- Python sidecar sau OpenAPI — không mở lại cổng; loại vì founder muốn lớp API chính.
- Rewrite tại chỗ — không rollback.

## 9. Cấm (giữ ADR-001)

Không model/package/bảng `flashcards`, `grammar_lessons`, `translations` kênh learner. Bốn flag giữ `false`.

## 10. Chữ ký — cổng SAD-3 (không thay BA bằng QA)

Mẫu [gates.md](../../company/gates.md) cổng SAD-3. **Không ký miệng.**

ADR stack đã ký kèm SAD-3 (ADR-001). Supersede một phần = **mở lại năm ghế SAD-3**. Cùng khối ghi trong [gates.md](../../company/gates.md).

- CEO — Quyen Do — 2026-08-31 — Mở lại cổng SAD-3; đồng ý rewrite API sang FastAPI là quyết định runway/tiền, không có FR driver
- CPO — Quyen Do — 2026-08-31 — Đồng ý phạm vi ADR-003; card `FR-LRN-*` không đợi runtime Python; không mở FR-NEG
- BA — Quyen Do — 2026-08-31 — Đồng ý delta log; D3/D4 là `INTENTIONAL_REQUIREMENT_CHANGE`; sẽ cập nhật SRS → use case → traceability → OpenAPI trước Phase 1
- Pedagogy — Quyen Do — 2026-08-31 — Đồng ý FR-NEG vẫn đóng; D3 logout toàn thiết bị không mở textbook; bốn flag giữ `false`
- CTO — Quyen Do — 2026-08-31 — Đồng ý D1 FastAPI 3.12, D2 Prisma giữ DDL + SQLAlchemy mapping-only, D3 `uv`, D4 OpenAPI viết tay + semantic diff; không Alembic trong giai đoạn song song

**Không** nằm khối SAD-3:

- QA: ký [parity checklist](../../qa/adr-003-parity-checklist.md) khi đủ điều kiện retire Nest (sau implementation)
- Platform + Ops: duyệt cutover runbook (staging vs prod tách)

## 11. Cập nhật kéo theo nếu được ký

`c4.md`, `deployment.md`, `README.md`, `.cursor/agents/jplearn-platform.md`, `okr-q1-by-seat.md` (KR ADR-001), `.github/workflows/ci.yml`.
