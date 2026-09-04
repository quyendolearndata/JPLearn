# ADR-004 — DDL: Alembic (Python) thay Prisma

- Trạng thái: **Accepted** 2026-09-04 — chữ ký §9
- Ngày: 2026-09-04
- Người đề xuất: ghế CTO
- Quan hệ: **Supersedes [ADR-003](adr-003-runtime-python.md) D2** (phần chủ DDL + phần «cấm Alembic»). [ADR-001](adr-001-stack.md) giữ nguyên: PostgreSQL, object storage, Next.js, Expo, `/staff`.
- Kèm: baseline schema [`docs/qa/adr-004-schema-baseline.json`](../../qa/adr-004-schema-baseline.json) · test [`apps/api-python/tests/test_schema_ddl.py`](../../../apps/api-python/tests/test_schema_ddl.py)

## 1. Bối cảnh

ADR-003 D2 giữ Prisma làm chủ DDL và **cấm Alembic** — đó là quyết định có chủ đích, không phải quán tính. Lý do: giai đoạn song song có hai runtime đọc **một** schema, nên chủ DDL phải là bên đang có lịch sử migration đã chạy thật (`0001`…`0004` + `_prisma_migrations`). Hai công cụ cùng ghi DDL trong giai đoạn đó là cách nhanh nhất để có schema không ai giải thích được.

Giai đoạn song song **đã kết thúc**: `apps/api` (NestJS + Prisma) bị xóa khỏi repo, commit cuối còn nó là `7a05e62`. Việc retire vượt cổng §7 của ADR-003 theo quyết định override của ghế CEO — bản ghi override thuộc ghế CEO + QA, không thuộc ADR này.

Hệ quả trực tiếp: sau khi Nest biến mất, không còn runtime nào dùng Prisma **ngoài chính việc chạy DDL**. Tiền đề của D2 hết, nên D2 hết hiệu lực. Điều kiện D2 đặt ra cho ADR-004 («guard FR-NEG chạy trên schema mới») là việc phải làm xong trước khi ký, không phải lý do hoãn — xem §3.

## 2. Quyết định

### D1 — Alembic trong `apps/api-python` là chủ DDL duy nhất

`apps/api-python/alembic.ini`, `script_location = src/jplearn_api/migrations`. `env.py` dùng async engine (asyncpg), cùng driver với app — không dựng đường DB thứ hai chỉ để migrate.

### D2 — Revision **viết tay**, `target_metadata = None`

`target_metadata = None` là **có chủ đích**, không phải chỗ còn thiếu. `models.py` là mapping-only và mang default phía Python; nếu trỏ metadata đó vào autogenerate, Alembic sẽ đề xuất **xóa** DDL thật (server default, CHECK, tên constraint, kiểu cột đã chốt). Autogenerate ở trạng thái này không phải tiện lợi, nó là drift do công cụ tạo ra.

**Cấm** bật autogenerate cho tới khi mapping mang đủ sự thật DDL. Đó không phải việc của Q1.

### D3 — Baseline squash + `stamp` cho DB đã có

`src/jplearn_api/migrations/versions/0001_prisma_baseline.py` là **squash chính xác** của Prisma `0001`…`0004`, raw SQL, giữ nguyên tên constraint/index: `users_pkey`, `users_email_key`, `devices_user_id_device_class_key`, `catalog_items_published_without_l1_translation`, các `*_fkey` với `ON DELETE RESTRICT ON UPDATE CASCADE`, riêng `learning_events_session_id_fkey` là `ON DELETE SET NULL`.

Tên constraint là **contract**, không phải chi tiết cài đặt: nó nằm trong error path, trong guard và trong snapshot. Đổi tên = đổi schema.

DB đã có schema do Prisma dựng thì **adopt**, không dựng lại: `jplearn-migrate stamp 0001_prisma_baseline`. Không drop, không «migrate reset cho sạch».

### D4 — CLI là bề mặt vận hành

`jplearn-migrate upgrade|downgrade|stamp|current` (`src/jplearn_api/migrate.py`) và `jplearn-seed` (`src/jplearn_api/seed.py`, port của `prisma/seed.ts`, idempotent, **không đè `status`** — FR-CAT-002/#39: seed không được publish hộ và không được kéo item đang QA về `draft`).

Runbook và CI gọi CLI này. Gọi `alembic` trần bỏ qua cấu hình async engine của repo.

## 3. Gate chống drift (điều kiện D2 của ADR-003 đã trả)

- `src/jplearn_api/schema_snapshot.py` chụp cấu trúc **thật** từ `information_schema` / `pg_catalog`: enums, columns, constraints, indexes. So schema sống, không so file.
- Baseline [`docs/qa/adr-004-schema-baseline.json`](../../qa/adr-004-schema-baseline.json) chụp từ DB do **Prisma** dựng, **trước khi xóa**: 6 enum, 10 bảng, 20 constraint, 12 index. Đây là bằng chứng còn lại duy nhất của schema thời Prisma.
- [`apps/api-python/tests/test_schema_ddl.py`](../../../apps/api-python/tests/test_schema_ddl.py) — **5 test, PASS**:
  1. DB do Alembic dựng == baseline.
  2. `downgrade base` → `upgrade head` trở lại **đúng** baseline (migration hai chiều, không one-way).
  3. Seed idempotent và giữ `draft`.
  4. FR-NEG-004: schema sống không có cột textbook.
  5. Scanner `scripts/assert-no-textbook.ts` vẫn **đỏ** khi cột cấm nằm trong file `.py`.

**Quy tắc:** đổi schema có chủ đích thì revision mới **và** regenerate baseline JSON **trong cùng một commit**, kèm FR id. Baseline lệch mà commit chỉ sửa test → reject.

**Cấm** nới lỏng test cho xanh (skip, xfail, so sánh lỏng field). Test đỏ nghĩa là schema đã lệch, không phải test sai.

## 4. Hệ quả

**Được:**

- Một ngôn ngữ ở tầng backend; DDL và app cùng vòng đời: `uv sync` → `jplearn-migrate upgrade` → pytest.
- Migration là SQL đọc được, review được, không qua generator.
- Guard FR-NEG chạy trên **schema sống** thay vì đọc file `.prisma`.

**Mất:**

- DX `prisma migrate dev`: không còn diff schema tự động, không còn shadow DB. Viết SQL tay đổi kỷ luật review thành thứ chặn duy nhất.
- Khả năng **chạy lại** differential Nest↔FastAPI. Evidence 40/40 đóng băng tại `docs/qa/differential/2026-09-04T071945Z-parity.json`; đó là lịch sử, không phải suite hồi quy.
- `_prisma_migrations` hết ý nghĩa; lịch sử migration bắt đầu lại ở `alembic_version`.

**«Hết Node» chỉ đúng ở tầng backend.** Node vẫn cần cho web (Next.js), mobile (Expo) và cho `scripts/assert-no-textbook.ts` — guard repo-level quét cả `.ts/.tsx/.py`. Ai đề xuất bỏ Node khỏi CI phải trả lời đủ ba chỗ đó trước.

## 5. Rủi ro còn lại

| Rủi ro | Sự thật | Chặn |
|---|---|---|
| Revision tay sai hoặc thiếu | Không có autogenerate đối chiếu | Round-trip `downgrade base` → `upgrade head` so baseline; job CI `api-python` chạy `jplearn-migrate upgrade` trên DB trống |
| Regenerate baseline «cho xanh» | JSON là chỗ dễ ăn gian nhất trong gate | Review coi sửa baseline **là** sửa schema: phải có revision + FR id đi kèm trong cùng commit |
| Không còn runtime thứ hai để đối chiếu | Sai **hành vi** (không phải sai schema) không còn bên nào so | Baseline mới = pytest 54/54 + web E2E Playwright 10/10 (chromium + webkit). Hồi quy phải thành test mới, không so với Nest |
| `stamp` sai trên staging | `stamp` ghi version mà không kiểm shape | Chạy `schema_snapshot` so baseline **trước** khi stamp; nằm trong runbook Platform + Ops |
| Có người «điền vào» `target_metadata` | `None` dễ bị đọc là thiếu sót | Ghi lý do tại `env.py` và tại D2 ở trên; PR bật autogenerate khi mapping chưa mang DDL truth → reject |

## 6. Phương án loại

- **Giữ Prisma làm package Node DDL-only.** Rủi ro thấp nhất, giữ được `migrate dev`. **CEO bác** — mục tiêu là sạch Node ở backend.
- **Prisma Client Python.** Repo archived 2025-04-15. Đã loại từ ADR-003 D2, không xét lại.
- **SQLAlchemy `create_all`.** **Cấm.** Không có lịch sử migration, không downgrade, không adopt được DB đang có dữ liệu.

## 7. Cấm (giữ ADR-001 / ADR-003)

Không revision nào tạo bảng, model hay cột `flashcards`, `grammar_lessons`, `translations` kênh learner. Không cột textbook (FR-NEG-004). Bốn flag giữ `false`.

Alembic không phải cửa sau để «thêm cột cho demo». Revision viết tay nghĩa là dễ thêm hơn, không phải dễ duyệt hơn.

## 8. Cập nhật kéo theo

Trong cùng commit này: [`adr-003-runtime-python.md`](adr-003-runtime-python.md) (D2 superseded, §7 đã retire, dòng guard trỏ sang `test_schema_ddl.py`), [`diagrams.md`](diagrams.md) (node persistence → SQLAlchemy / PostgreSQL).

Còn nợ, ngoài phạm vi ADR này: nhãn «NestJS» còn sót trong [`c4.md`](c4.md), [`deployment.md`](deployment.md), `README.md` và các sơ đồ container/sequence của `diagrams.md`.

## 9. Chữ ký

ADR này **không** mở lại cổng SAD-3: không đổi FR, không đổi contract `openapi.yaml`, không đổi hành vi learner. Đổi công cụ DDL trong biên `apps/api-python` là quyết định ghế CTO.

Việc retire `apps/api` (vượt cổng §7 parity) là bản ghi **riêng** của ghế CEO + QA — xem [parity checklist](../../qa/adr-003-parity-checklist.md) §7 và [gates.md](../../company/gates.md). ADR-004 không ký hộ quyết định đó và không hợp lý hoá nó về sau.

**Không ký miệng.**

- CTO — Quyen Do — 2026-09-04 — Alembic là chủ DDL duy nhất; revision viết tay và `target_metadata = None` có chủ đích; baseline squash `0001_prisma_baseline` + `stamp` để adopt DB cũ; gate chống drift `schema_snapshot` + `adr-004-schema-baseline.json` + `test_schema_ddl.py`; cấm autogenerate và cấm nới lỏng test
