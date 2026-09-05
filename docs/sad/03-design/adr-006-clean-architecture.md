# ADR-006 — Clean Architecture Rewrite & Internal Boundary Governance

- **Ghế chủ trì:** CTO (`jplearn-cto`)
- **Ngày:** 2026-09-05
- **Trạng thái:** Accepted
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

| Method | Path | Auth / Role | Invariant & Validation | Concurrency & Transaction | Error Response Codes |
|---|---|---|---|---|---|
| `POST` | `/auth/register` | Public | Email valid, min password 10 chars | Atomic UoW (user + role + progress) | `400` (Validation), `409` (Duplicate email) |
| `POST` | `/auth/login` | Public | Valid credentials | Read query + Argon2 verify | `401` (Unauthorized) |
| `POST` | `/auth/logout` | Authenticated | User exists, token valid | UoW: `token_version += 1`, commit | `401` (Unauthorized) |
| `GET` | `/auth/me` | Authenticated | Token version match | Read query by user_id | `401` (Unauthorized) |
| `GET` | `/flags` | Public | Default false | Query flags with ensure_defaults | `200` |
| `PUT` | `/flags` | Staff/Admin | Boolean flags only | UoW upsert all flags, commit | `401`, `403` |
| `GET` | `/catalog` | Public | Filter `status=published`, optional `ci_level` | Read query with media relation | `200` |
| `POST` | `/catalog` | Staff/Admin | Topic exists, duration > 0, L1 false | UoW create draft catalog item | `400`, `401`, `403` |
| `POST` | `/catalog/{id}/submit-qa` | Staff/Admin | Only `draft` -> `level_qa` | UoW status transition, commit | `400`, `401`, `403`, `404` |
| `POST` | `/catalog/{id}/publish` | Admin only | Only `level_qa` -> `published`, media exists on storage | UoW status transition, storage existence verify | `400`, `401`, `403`, `404` |
| `POST` | `/catalog/{id}/unpublish` | Staff/Admin | Only `published` -> `draft` | UoW status transition, commit | `400`, `401`, `403`, `404` |
| `DELETE` | `/catalog/{id}` | Admin only | Mark `archived` | UoW status transition, commit | `401`, `403`, `404` |
| `POST` | `/sessions/start` | Learner | Valid device_class | UoW: session + device upsert + 2 events | `400`, `401` |
| `POST` | `/sessions/{id}/end` | Learner (owner) | Must not already ended, exactly-once | UoW: Row lock session + progress, 2 events | `400` (Already ended), `401`, `403`, `404` |
| `GET` | `/progress` | Learner | Progress exists | Read query for user | `401`, `404` |
| `POST` | `/media/upload` | Staff/Admin | MIME `video/mp4`, magic bytes `ftyp` | Storage stage -> promote -> DB UoW | `400`, `401`, `403`, `404` |
| `POST` | `/media/{id}/hls` | Staff/Admin | HLS master manifest exists | UoW update asset hls_url | `400`, `401`, `403`, `404` |
| `GET` | `/media/{id}` | Authenticated | Asset exists | Read query asset | `401`, `404` |
| `GET` | `/media/{id}/stream` | Signed query / Auth | Valid signature or token | Stream with Range header support | `400`, `401`, `403`, `404`, `416` |
| `GET` | `/health` | Public | Basic process check | No DB query required | `200` |
| `GET` | `/ready` | Public | Probes DB & storage | Storage probe + DB connection probe | `200`, `503` |

---

## 4. Trạng thái kiểm chứng & Ranh giới vận hành

- **Milestone 1 (Clean Architecture Rewrite):** Toàn bộ các module được tái cấu trúc bảo đảm passing 100% các suite kiểm thử: guard, pytest (164+ tests), OpenAPI parity (zero diff), Web E2E (10/10), container verification (7/7 gates).
- **Milestone 2 (Operational Acceptance / R-09):** Tiếp tục duy trì trạng thái **STRICTLY HOLD / BLOCKED** cho đến khi có đủ hạ tầng staging và quyết định mở traffic từ ghế Ops & CTO.
