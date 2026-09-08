# ADR-006 — Clean Architecture Rewrite & Internal Boundary Governance

- **Ghế chủ trì:** CTO (`jplearn-cto`)
- **Ngày:** 2026-09-05
- **Trạng thái:** Architecture decision Accepted; current engineering acceptance pending performance review. Operational Acceptance on HOLD.

> Verification correction: the Closure v4 sign-off below is historical, not acceptance of the current working tree. Timeout ownership and benchmark tooling were subsequently corrected; current results and limitations are in `docs/qa/clean-architecture-audit/cleanup-fix-verification.md`.
- **Phối hợp:** BA (`jplearn-ba`), Platform (`jplearn-platform`), QA (`jplearn-qa`), Ops (`jplearn-ops`), Web (`jplearn-web`)
- **Kế thừa & liên quan:** ADR-001, ADR-003, ADR-004, ADR-005, `docs/superpowers/plans/2026-09-05-fastapi-clean-architecture-rewrite.md`

---

## 1. Bối cảnh

Backend FastAPI hiện tại (`apps/api-python`) đã hoàn thành các milestone hardening và đạt 100% contract parity với hệ thống nguyên bản. Tuy nhiên, kiến trúc nội bộ của backend đang gặp phải các vấn đề khớp nối chặt (tight coupling):

1. **Rò rỉ framework & ORM vào tầng nghiệp vụ:** Các service functions (`auth_service`, `catalog_service`, `sessions_service`, `media_service`) nhận trực tiếp `AsyncSession` của SQLAlchemy, tự gọi `session.commit()` / `session.rollback()`, và ném trực tiếp `fastapi.HTTPException`.
2. **Thiếu ranh giới Unit of Work rõ ràng:** Nghiệp vụ giao dịch (transaction boundary) bị trộn lẫn với logic điều phối; việc kiểm thử nghiệp vụ buộc phải khởi tạo PostgreSQL engine hoặc phụ thuộc nặng vào monkeypatching session mock.
3. **Thao tác I/O đồng thời và quản lý tài nguyên:** Các thao tác filesystem và database commit cần có sự phân tách rõ rệt giữa domain entity/policy và application-owned ports/adapters.

Hệ thống cần một cấu trúc Clean Architecture chuẩn mực theo cuốn *Architecture Patterns with Python* mà **không làm thay đổi** bất kỳ public HTTP route, status code, response shape, OpenAPI schema hay DDL schema nào.

---

## 2. Các quyết định kiến trúc chính

### 2.1 Hướng phụ thuộc nghiêm ngặt (Strict Dependency Direction)

Quy tắc phụ thuộc một chiều từ ngoài vào trong:

```text
HTTP Router / CLI Entrypoint
  ↓ (Commands / Queries)
Application Handlers
  ↓ (Domain Entities & Policies)
Domain Model
  ↑ (Implements Ports)
Adapters (SQLAlchemy, Storage, Argon2, JWT, Observability)
```

- **Domain Layer (`domain/`):** Thuần Python (Pure Python). Tuyệt đối **CẤM** import FastAPI, Pydantic, SQLAlchemy, asyncpg, hoặc đọc biến môi trường (`os.environ`). Sở hữu các entities (`UserAccount`, `CatalogItem`, `LearningSession`, `LearnerProgress`, `MediaAsset`), value objects và domain exceptions.
- **Application Layer (`application/`):** Chứa command/query handlers, use case workflows, và các interface (Ports / Protocols). Tuyệt đối **CẤM** import FastAPI, Pydantic, SQLAlchemy, asyncpg, hoặc đọc biến môi trường.
- **Adapters Layer (`adapters/`):** Triển khai cụ thể các ports (SQLAlchemy persistence, filesystem/memory storage, Argon2 password hasher, JWT token service, observability alert queue).
- **Entrypoints Layer (`entrypoints/`):** FastAPI app, routers, middleware, Pydantic schemas, HTTP exception mappers, và CLI commands.
- **Bootstrap (`bootstrap.py`):** Composition Root duy nhất khởi tạo và kết nối các concrete adapters với application handlers.

### 2.2 Ranh giới Aggregate & Coordination

1. **`UserAccount` Aggregate:** Quản lý thông tin định danh, email đã chuẩn hóa, password hash, và vòng đời token version (`increment_token_version` khi logout).
2. **`CatalogItem` Aggregate:** Quản lý state machine: `draft -> level_qa -> published -> archived`. Invariant: Không thể publish nếu thiếu media hợp lệ trên storage; cấm gắn cờ `has_l1_translation=True` khi đã publish.
3. **`LearningSession` & `LearnerProgress` Coordination:** `EndSession` được thực thi dưới dạng transaction phối hợp nguyên tử (atomic transaction) giữa hai aggregate thông qua pessimistic row locking (`with_for_update`) trên PostgreSQL để đảm bảo exactly-once và ngăn ngừa triệt để lost updates. Không gộp thành một God-Aggregate `Learner`.
4. **`MediaAsset` & Storage Port:** Phân tách rõ giữa metadata của asset trong database và nhị phân file trong Storage. Media upload tuân thủ 3 trạng thái giao dịch: `COMMITTED`, `ROLLBACK_CONFIRMED`, `OUTCOME_UNKNOWN`.

### 2.3 Async Unit of Work (UoW) với Rollback-by-Default

Mọi write use case đều bắt buộc phải chạy trong phạm vi của một `AsyncUnitOfWork`:
- Mặc định tự động rollback khi thoát context block mà chưa gọi `await uow.commit()`.
- Mỗi request / use case invocation nhận một UoW instance độc lập từ UoW factory; cấm sử dụng singleton session.
- Repository ports chỉ nhận aggregate hoặc application read models, không để SQLAlchemy expressions hoặc ORM models rò rỉ ra application handlers.

### 2.4 Quyết định KHÔNG áp dụng Full CQRS và Message Bus trong Sóng 1

- **Không dựng Full CQRS:** Chỉ tách biệt command handlers (ghi qua UoW) và query handlers (đọc tối ưu qua query adapters trả DTO), không xây dựng hai database riêng biệt hay event sourcing.
- **Không dựng external Message Broker hay Message Bus phức tạp:** Các domain events (`SessionStarted`, `SessionEnded`, `MinutesComprehensibleAdded`, `LevelExposed`) được persist trực tiếp và đồng thời vào bảng `learning_events` trong cùng một UoW transaction để bảo toàn tính toàn vẹn dữ liệu. Không emit async message ra ngoài khi chưa có transactional outbox.

---

## 3. Ma trận hành vi các Route (Behavior Matrix)

Đối chiếu code + OpenAPI ngày 2026-09-05: **20 operations**. Ma trận này mô tả
runtime hiện có; domain handler chưa có route không được tính là HTTP operation.
Hướng dẫn gọi API: [api-usage.md](../../backend/api-usage.md).

| Method | Path | Operation ID | Auth / Role | Invariant & Validation | Concurrency & Transaction | Error Codes |
|---|---|---|---|---|---|---|
| `POST` | `/auth/register` | `register` | Public | Email valid, min password 10 chars | Atomic UoW (user + role + progress) | `400`, `409` |
| `POST` | `/auth/login` | `login` | Public | Valid credentials | Read query + Argon2 verify | `401` |
| `POST` | `/auth/logout` | `logout` | Authenticated | User exists, token valid | UoW: `token_version += 1`, commit | `401` |
| `GET` | `/me` | `getMe` | Authenticated | Token version match | Read query by user_id | `401` |
| `GET` | `/flags` | `getFlags` | Authenticated | Default false | Query flags with ensure_defaults | `200`, `401` |
| `PATCH` | `/staff/flags` | `patchFlags` | Admin only | Four booleans per contract | UoW upsert all flags, commit | `401`, `403` |
| `GET` | `/catalog` | `listCatalog` | Authenticated | Filter published; query ci_level 0–4 | Read query with media relation | `200`, `400`, `401` |
| `POST` | `/staff/catalog` | `createCatalogItem` | Teacher/Admin | Topic exists; write integers follow v1 contract; L1 false | UoW create draft catalog item | `400`, `401`, `403` |
| `POST` | `/staff/catalog/{id}/submit-qa` | `submitLevelQa` | Staff/Admin | Only `draft` -> `level_qa` | UoW status transition, commit | `400`, `401`, `403`, `404` |
| `POST` | `/staff/catalog/{id}/publish` | `publishCatalogItem` | Admin only | Only `level_qa` -> `published`, media exists | UoW status transition, storage verify | `400`, `401`, `403`, `404` |
| `POST` | `/staff/catalog/{id}/unpublish` | `unpublishCatalogItem` | Admin only | Only `published` -> `draft` | UoW status transition, commit | `400`, `401`, `403`, `404` |
| `POST` | `/staff/catalog/{id}/media` | `uploadMedia` | Staff/Admin | MIME `video/mp4`, magic bytes `ftyp` | Storage stage -> promote -> DB UoW | `400`, `401`, `403`, `404` |
| `POST` | `/staff/media/{id}/hls` | `registerHls` | Staff/Admin | HLS master manifest exists | UoW update asset hls_url | `400`, `401`, `403`, `404` |
| `GET` | `/media/{id}` | `streamMedia` | Signed query / Auth | Valid signature or token | Stream with Range header support | `400`, `401`, `403`, `404`, `416` |
| `GET` | `/media/{id}/hls/{file}` | `streamHls` | Signed query / Auth | Valid signature or token, safe path | Stream manifest or segment | `400`, `401`, `403`, `404`, `416` |
| `POST` | `/sessions` | `startSession` | Learner | Valid device_class | UoW: session + device upsert + 2 events | `400`, `401` |
| `POST` | `/sessions/{id}/end` | `endSession` | Learner (owner) | Must not already ended, exactly-once | UoW: Row lock session + progress, 2 events | `400`, `401`, `403`, `404` |
| `GET` | `/progress` | `getProgress` | Learner | Progress exists | Read query for user | `401`, `404` |
| `GET` | `/health` | `health` | Public | Basic process check | No DB query required | `200` |
| `GET` | `/ready` | `ready` | Public | Probes DB & storage | Storage probe + DB connection probe | `200`, `503` |

---

## 4. Trạng thái kiểm chứng & Ranh giới vận hành

### Hiện hành

Package layout, đường ASGI/CLI và test imports đã cập nhật; xem
[backend docs](../../backend/README.md) và [package-layout verification](../../qa/package-layout-refactor.md).
Root chỉ còn bootstrap/settings/package marker; HTTP/CLI ở entrypoints, hạ tầng
ở adapters, config/tooling nằm ngoài inner layers. Việc gom thư mục không chứng
minh mọi boundary HTTP đã loại ORM; auth dependency và một số query vẫn nằm ở ngoài.
Review hiệu năng hiện còn mở theo [cleanup verification](../../qa/clean-architecture-audit/cleanup-fix-verification.md).
R-09 vẫn HOLD. Bản cập nhật tài liệu không cấp lại chữ ký nghiệm thu.

### Bản ghi Closure v4 lịch sử — không áp dụng cho candidate hiện hành

- **Milestone 1 (Clean Architecture Rewrite):** Đã hoàn thành nghiệm thu kỹ thuật (Engineering Closure Complete) theo Closure v4 ([`2026-09-05-clean-architecture-closure-v4.md`](../../superpowers/plans/2026-09-05-clean-architecture-closure-v4.md)). Cả 5 ghế kỹ thuật (CTO, BA, Platform, QA, Ops) đã ký duyệt sau khi giải quyết trọn vẹn 4 lỗ hổng cốt lõi:
  1. `UploadTransactionCoordinator` bảo đảm single-owner cleanup khi bị repeated cancellation mà không orphan task hay gây double-rollback context exit.
  2. Machine-readable baseline mapping 164/164 test cases và assertion diff review đầy đủ (196 candidate tests).
  3. In-tree benchmark runner, raw sample measurement, và quyết định chấp thuận đánh đổi +12% (+2.71 ms) upload p95 latency từ CTO để đổi lấy tính an toàn tuyệt đối khi hủy tác vụ và giải phóng kết nối DB trong lúc stream file.
  4. Clean detached worktree qualification với 0 dirty files pre/post và toàn bộ 6 verification gates PASS 100%.
- **Milestone 2 (Operational Acceptance / R-09):** Tiếp tục duy trì trạng thái **STRICTLY HOLD / BLOCKED** cho đến khi có đủ hạ tầng staging thực tế và quyết định mở traffic từ ghế Ops & CTO.
