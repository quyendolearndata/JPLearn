# FastAPI Clean Architecture Rewrite

> **Trạng thái:** AUDIT GAP CLOSURE — các lát cắt cơ bản đã triển khai tại 4ae7673, đang mở lại và khắc phục các lỗ hổng kiến trúc G0–G6 theo kế hoạch `docs/superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md`.  
> **Baseline:** branch `codex/fastapi-backend-hardening`, commit `2f5e200`  
> **PR nền:** [#42](https://github.com/quyendolearndata/JPLearn/pull/42)  
> **Kiến trúc tham chiếu:** *Architecture Patterns with Python* (`python-architecture`)  
> **Chủ trì:** CTO (`jplearn-cto`)  
> **Phân tích:** BA (`jplearn-ba`)  
> **Thực hiện:** Platform/Backend (`jplearn-platform`)  
> **Kiểm chứng:** QA Engineering (`jplearn-qa`)  

## 1. Mục tiêu

Viết lại phần bên trong backend FastAPI theo dependency direction:

```text
HTTP / CLI
  -> command hoặc query
    -> application handler
      -> domain model / domain policy
        -> application-owned ports
          -> SQLAlchemy, PostgreSQL, filesystem, JWT, Argon2 adapters
```

Sau rewrite:

- domain và application layer không import FastAPI, Pydantic, SQLAlchemy, asyncpg
  hoặc biến môi trường;
- HTTP router chỉ parse request, gọi use case và map lỗi sang HTTP;
- write use case có transaction boundary qua async Unit of Work, explicit commit và
  rollback-by-default;
- repository trả domain aggregate hoặc application read model, không để query
  builder/ORM model rò vào handler;
- FastAPI, PostgreSQL, Alembic, OpenAPI và toàn bộ hành vi public hiện tại được giữ;
- không mở thêm grammar, flashcard hoặc learner translation surface.

Đây là rewrite kiến trúc nội bộ, **không phải** đổi framework, đổi database hoặc
viết lại API contract.

## 2. Invariant bắt buộc giữ nguyên

| Khu vực | Invariant |
|---|---|
| Identity | Email unique; Argon2; JWT secret policy; logout tăng token version trên mọi device |
| Catalog | `draft -> level_qa -> published`; admin-only publish; published phải có media; không L1 translation |
| Learning | EndSession exactly-once; không lost update; duration zombie không cộng phút; 2 event được ghi atomic |
| Media | MP4/HLS contract; path traversal bị chặn; không xóa object khi COMMIT outcome unknown |
| Flags | Default false; không sinh UI/API textbook |
| DDL | Alembic baseline giữ đúng 6 enum, 10 bảng, constraint/index/FK hiện tại |
| Contract | `docs/sad/03-design/openapi.yaml` tiếp tục là authority; semantic diff bằng 0 |
| Runtime | Staging/production fail closed về secret, HTTPS, CORS và destructive migration |

Không thay tên bảng/cột, enum, constraint, HTTP route, status code hoặc response
shape trong rewrite. Mọi thay đổi nghiệp vụ phát hiện trong lúc làm phải quay lại
BA/SRS/ADR thành một quyết định riêng.

## 3. Kiến trúc đích

```text
apps/api-python/src/jplearn_api/
├── domain/
│   ├── identity.py
│   ├── catalog.py
│   ├── learning.py
│   ├── media.py
│   ├── events.py
│   └── errors.py
├── application/
│   ├── commands.py
│   ├── queries.py
│   ├── handlers/
│   │   ├── identity.py
│   │   ├── catalog.py
│   │   ├── learning.py
│   │   └── media.py
│   ├── ports/
│   │   ├── repositories.py
│   │   ├── unit_of_work.py
│   │   ├── storage.py
│   │   ├── security.py
│   │   ├── clock.py
│   │   └── identifiers.py
│   └── read_models.py
├── adapters/
│   ├── persistence/
│   │   ├── records.py
│   │   ├── repositories.py
│   │   ├── queries.py
│   │   └── unit_of_work.py
│   ├── storage/
│   │   ├── local.py
│   │   └── memory.py
│   ├── security/
│   │   ├── argon2.py
│   │   └── jwt.py
│   └── observability/
├── entrypoints/
│   ├── http/
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   ├── error_mapping.py
│   │   ├── schemas.py
│   │   └── routers/
│   └── cli/
├── bootstrap.py
├── config.py
├── migrations/
└── resources/
```

Tên thư mục là tín hiệu dependency, không phải mục tiêu tự thân. Không tạo lớp
pass-through chỉ để đúng sơ đồ.

### 3.1 Domain model

- `UserAccount`: identity, email, token version và role-related invariants.
- `CatalogItem`: sở hữu state transition submit QA, publish, unpublish/archive.
- `LearningSession`: sở hữu trạng thái start/end và chống end lần hai.
- `LearnerProgress`: sở hữu phép cộng phút và current CI level.
- `MediaAsset`: identity và lifecycle metadata; binary object vẫn thuộc StoragePort.
- Value objects: `Email`, `DeviceClass`, `CiLevel`, `SessionDuration`,
  `StorageKey` chỉ được tạo khi chúng loại bỏ invalid state thực tế.
- Domain errors dùng ngôn ngữ nghiệp vụ, không chứa HTTP status.

`EndSession` được ghi rõ là ngoại lệ coordination cần atomic transaction giữa
`LearningSession` và `LearnerProgress`, vì contract hiện yêu cầu progress cập nhật
ngay và events atomic. Không tạo aggregate `Learner` khổng lồ chứa toàn bộ lịch sử.

### 3.2 Application layer

Write use cases dùng command có một handler:

- `RegisterUser`, `LogoutUser`;
- `CreateCatalogItem`, `SubmitCatalogForQa`, `PublishCatalogItem`,
  `UnpublishCatalogItem`;
- `StartLearningSession`, `EndLearningSession`;
- `UploadMedia`, `RegisterHlsAsset`;
- `UpdateFeatureFlags`.

Read use cases dùng query handlers/read ports:

- `AuthenticateUser`, `GetCurrentUser`, `ListPublishedCatalog`, `GetProgress`,
  `GetFlags`, `GetMediaForPlayback`.

Không dựng full CQRS infrastructure. Việc tách command/query chỉ nhằm làm rõ
transaction và tối ưu read path. Chưa thêm broker hay generic message bus.

### 3.3 Ports và adapters

- Repository port được thiết kế theo aggregate/use case, không có generic
  `filter(**kwargs)` hoặc expose SQLAlchemy expression.
- Mỗi command nhận một UoW factory/request-scoped UoW; không dùng singleton session.
- SQLAlchemy declarative records nằm hoàn toàn trong persistence adapter và được
  map tường minh sang domain object.
- Query adapter được phép dùng SQLAlchemy Core/ORM trực tiếp nhưng chỉ trả read DTO.
- `StoragePort` hiện tại được chuyển vào application ports và giữ nguyên behavior.
- Password hashing, token issuing/verifying, clock và ID generation trở thành explicit
  dependencies để test không monkeypatch global/import path.
- `bootstrap.py` là composition root duy nhất biết concrete adapters.

### 3.4 Events

- Domain có thể sinh `SessionStarted`, `SessionEnded`, `MinutesComprehensibleAdded`,
  `CatalogPublished` dưới dạng fact thuần Python.
- Các `learning_events` bắt buộc hiện tại được lưu trong cùng UoW với mutation.
- Chỉ thêm dispatcher/message bus khi có ít nhất hai reaction độc lập cần tách.
- Không publish external event sau commit nếu chưa có transactional outbox,
  idempotency và replay policy.

## 4. Chiến lược rewrite

Không tạo backend thứ hai và không dual-write. Mỗi vertical slice được chuyển theo
quy trình:

```text
characterization test
  -> domain/application API mới
  -> fake-backed handler tests
  -> PostgreSQL/storage adapter tests
  -> chuyển router sang handler mới
  -> chạy contract/E2E
  -> xóa implementation cũ của slice
```

Trong một thời điểm, mỗi HTTP route chỉ có một active implementation. Rollback của
mỗi slice là revert commit, không dùng schema downgrade và không thêm runtime flag
lâu dài chỉ để chọn kiến trúc cũ/mới.

## 5. Các phase thực hiện

### Phase 0 — Khóa baseline và quyết định kiến trúc

**Owner:** CTO + BA; **Verification:** QA

- [x] Tạo ADR-006 cho Clean Architecture rewrite, dependency rules, aggregate
  boundaries và quyết định không full CQRS/message bus.
- [x] Xác nhận không có FR/NFR hoặc OpenAPI/DDL delta; nếu có, dừng rewrite và đưa
  thay đổi đó qua quy trình BA riêng.
- [x] Sửa các tài liệu đang overclaim production acceptance; R-09 tiếp tục HOLD.
- [x] Ghi baseline từ commit sạch: 164 pytest, guard, OpenAPI diff, 10 Web E2E và
  container gate 7/7.
- [x] Lập behavior matrix cho từng route: success, authorization, validation,
  concurrency, transaction, side effect và error response.

**Exit:** ADR được review; behavior matrix bao phủ mọi operationId; baseline có SHA
và raw evidence tái tạo được.

### Phase 1 — Walking skeleton và dependency guard

**Owner:** Platform; **Verification:** QA + CTO

- [x] Tạo `domain`, `application`, `adapters`, `entrypoints`, `bootstrap` skeleton.
- [x] Tạo domain error taxonomy và HTTP error mapper tập trung.
- [x] Định nghĩa `AsyncUnitOfWork` Protocol, UoW factory và một repository port nhỏ.
- [x] Tạo `SqlAlchemyUnitOfWork` rollback-by-default; commit chỉ explicit.
- [x] Tạo Fake UoW/repository dùng cho application tests.
- [x] Thêm architecture guard bằng AST/import inspection:
  - domain không import application/adapters/entrypoints/framework;
  - application không import adapters/entrypoints/FastAPI/SQLAlchemy/Pydantic;
  - adapters không import entrypoints;
  - chỉ bootstrap/entrypoints chọn concrete adapter.
- [x] Chuyển một read-only use case (`GetFlags`) làm walking skeleton.

**Exit:** domain/application import được khi không có DB/network; unit tests chạy
không khởi động Docker; `/flags` giữ nguyên contract.

### Phase 2 — Identity và feature flags

**FR:** FR-ID-001..004, FR-FLG-001..002  
**Owner:** Platform; **Verification:** QA

- [x] Tạo identity commands/queries, `UserAccount`, domain errors và repository port.
- [x] Tách `PasswordHasher` và `TokenService` ports; Argon2/JWT là adapters.
- [x] Registration atomic: user + learner role + learner progress trong một UoW.
- [x] Duplicate email được adapter translate sang stable application error, sau đó
  HTTP mapper trả response contract hiện tại.
- [x] Logout tăng token version qua aggregate operation và explicit commit.
- [x] Chuyển flags read/update; không tạo aggregate ceremony cho read-only flags.
- [x] Chuyển auth/flags routers rồi xóa `auth_service.py`, `flags_service.py` cũ.

**Exit:** T-ID-001..004, T-FLG-001..002 và security negative tests PASS; handler
tests không cần FastAPI/PostgreSQL, mapping tests dùng PostgreSQL thật.

### Phase 3 — Catalog workflow

**FR:** FR-CAT-001..005, FR-CMS-002..004  
**Owner:** Platform; **Verification:** BA + QA

- [x] Tạo `CatalogItem` aggregate với transition methods và domain errors.
- [x] Repository chỉ load/save aggregate root; media được biểu diễn bằng reference
  cần thiết cho publish invariant.
- [x] `PublishCatalogItem` kiểm role ở security boundary, semantic precondition trong
  handler và publish invariant trong domain.
- [x] Storage existence đi qua port; xác định rõ thứ tự I/O và transaction để không
  giữ DB lock qua external I/O lâu hơn cần thiết.
- [x] List catalog dùng query adapter/read DTO, không hydrate aggregate chỉ để đọc.
- [x] Chuyển catalog routers rồi xóa `catalog_service.py` cũ.

**Exit:** state transition tests thuần domain; PostgreSQL round-trip; publish thiếu
media/missing object/forbidden role đều giữ đúng HTTP contract.

### Phase 4 — Learning sessions, progress và events

**FR:** FR-SES-001..003, FR-PRG-001..004, FR-EVT-001..003  
**Owner:** Platform; **Verification:** QA

- [x] Tạo `LearningSession`, `LearnerProgress`, duration policy và domain events.
- [x] `StartLearningSession` ghi session/device/events qua một explicit UoW.
- [x] `EndLearningSession` lock session rồi progress theo thứ tự cố định, gọi domain
  operations và ghi hai events trong cùng transaction.
- [x] Repository port có operation tường minh cho pessimistic lock; không expose
  `.with_for_update()` ra application.
- [x] Duplicate/concurrent EndSession giữ exactly-once; nhiều session cùng user không
  lost update; rollback mọi mutation/event khi một bước fail.
- [x] Chuyển session/progress routers rồi xóa `sessions_service.py` và
  `session_policy.py` cũ sau khi domain replacement hoàn tất.

**Exit:** test domain thuần; application fake tests; real PostgreSQL concurrency tests
và T-SES/T-PRG/T-EVT đều PASS.

### Phase 5 — Media lifecycle và reconciliation

**FR:** FR-CMS-001..004, NFR-PERF-002  
**Owner:** Platform; **Verification:** BA + QA + Ops

- [x] Tách transport `UploadFile` khỏi handler; router truyền async byte stream và
  metadata command đã parse.
- [x] Giữ StoragePort lifecycle: stage, promote, delete, stream, range, metadata,
  readiness; adapters tự sở hữu file handles/executors.
- [ ] `UploadMedia` thể hiện rõ state machine:
  `STAGED -> PROMOTED -> COMMITTED | ROLLBACK_CONFIRMED | OUTCOME_UNKNOWN` (Reopened: fault injection vào `media_repo.add()` sau promote).
- [x] Không rollback đồng thời với COMMIT; unknown outcome giữ object và tạo recovery
  evidence không chứa secret/PII.
- [ ] Reconciliation dùng query/repository ports và giữ 24h retention + recheck trước
  delete (Reopened: chuyển reconciliation sang application handler).
- [x] HTTP Range/HLS/signature policy tách khỏi persistence model.
- [ ] Chuyển media routers/CLI rồi xóa `media_service.py`, `media_access.py` và storage
  implementation cũ sau khi adapters mới đạt parity (Reopened: media router vẫn qua `media_service`).

**Exit:** cancellation/fault matrix PASS ở handler và real adapters; playback MP4,
Range, signed URL, HLS và reconciliation giữ nguyên contract/E2E.

### Phase 6 — Runtime boundaries và operational adapters

**NFR:** NFR-SEC-001, NFR-PRIV-001, NFR-OBS-001  
**Owner:** Platform + Ops; **Verification:** QA + CTO

- [x] Chuyển settings thành immutable bootstrap input; domain/application không đọc env.
- [x] Tách alert queue/webhook, request ID, health/readiness thành adapters/entrypoints.
- [x] Health/readiness query application-owned capabilities nhưng không giả làm domain.
- [x] Giữ migration/schema snapshot/Alembic trong operational adapter/CLI boundary.
- [x] Seed đi qua application command hoặc adapter bootstrap rõ ràng; create-only admin
  không ghi đè credential hiện hữu.
- [x] Đảm bảo import package/domain không tạo engine, storage, queue hoặc network client.

**Exit:** production config fail-closed; packaged container chạy non-root; migration,
seed, ready/health và alert tests PASS.

### Phase 7 — Xóa legacy và làm sạch test architecture

**Owner:** Platform; **Verification:** QA + CTO

- [ ] Không còn router/service nhận `AsyncSession` ngoài persistence/entrypoint adapter (Reopened: hoàn tất dependencies wiring).
- [x] Không còn application/domain import FastAPI/Pydantic/SQLAlchemy/asyncpg.
- [ ] Xóa ORM models khỏi package root; adapter records không được trả ra ngoài (Reopened: dọn `models.py` alias).
- [ ] Xóa các service module cũ chỉ sau khi route cuối cùng đã chuyển (Reopened: `media_service.py`).
- [x] Phân loại tests thành `unit/domain`, `unit/application`, `integration`, `e2e`
  mà không xóa characterization coverage.
- [x] Giảm monkeypatch framework/import path; ưu tiên fake ports và state assertions.
- [x] Kiểm N+1/query count cho catalog và auth role loading.
- [ ] Cập nhật C4 Level 3, diagrams, ADR, README và walkthrough theo code thực (Reopened: sửa ADR-006 routes).

**Exit:** architecture guard không có allowlist tạm; tìm kiếm không còn legacy import;
reviewer trace được entrypoint -> handler -> domain -> port -> adapter -> persistence.

### Phase 8 — Requalification

**Owner:** QA + Ops; **Decision:** CTO

- [x] `pnpm test:guard` PASS.
- [x] Toàn bộ 164 test case baseline vẫn tồn tại hoặc có mapping replacement; không
  dùng tổng test count làm bằng chứng duy nhất (173 tests PASS).
- [x] Domain/application unit suite chạy không Docker.
- [x] PostgreSQL repository/UoW/mapping/concurrency integration suite PASS.
- [x] Semantic OpenAPI diff và mutation suite PASS (26/26 PASS).
- [x] Web E2E Chromium + WebKit 10/10 PASS.
- [ ] Container verification 7/7 PASS từ clean checkout và immutable image digest (Reopened cho clean candidate SHA).
- [ ] So sánh latency/query count/memory với baseline; không nhận regression chưa giải thích (Reopened).
- [ ] Draft PR được review theo BA/Platform/QA/CTO đúng phạm vi (Reopened).

**Exit:** engineering rewrite được phép merge. R-09 operational acceptance vẫn là
gate riêng; local rewrite PASS không tự động mở learner traffic.

## 6. Test strategy

| Tầng | Mục tiêu | Infrastructure |
|---|---|---|
| Domain unit | Invariant, transition, duration, error vocabulary | Không |
| Application unit | Command/query workflow, commit intent, compensation | Fake ports/UoW |
| Adapter integration | Mapping, constraints, locks, rollback, filesystem | PostgreSQL/storage thật |
| Contract | OpenAPI, error/status/schema parity | FastAPI TestClient |
| E2E | Wiring API + Web + DB + media | Docker + Playwright |

Mỗi production bug được giữ ở tầng thấp nhất tái hiện trung thực nguyên nhân. Fake
không thay thế test PostgreSQL cho lock/isolation và không thay thế filesystem thật
cho cancellation/lifecycle.

## 7. Commit/PR sequence đề xuất

1. `docs(api): accept clean architecture rewrite ADR`
2. `refactor(api): add application boundaries and dependency guard`
3. `refactor(api): migrate identity and flags use cases`
4. `refactor(api): migrate catalog aggregate and queries`
5. `refactor(api): migrate learning unit of work and events`
6. `refactor(api): migrate media lifecycle adapters`
7. `refactor(api): isolate runtime and operational boundaries`
8. `refactor(api): remove legacy service and ORM coupling`
9. `test(api): requalify clean architecture rewrite`
10. `docs(api): record rewrite evidence and remaining R-09 hold`

Mỗi commit phải giữ guard, targeted tests và OpenAPI diff xanh. Phase 4/5 phải chạy
real PostgreSQL/storage tests trước khi chuyển router. Không squash mất boundary
nếu việc đó làm mất khả năng revert từng vertical slice.

## 8. Rủi ro và kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Rewrite làm đổi behavior ngoài ý muốn | Characterization matrix + OpenAPI/E2E sau từng slice |
| Domain chỉ là ORM model đổi tên | Domain import guard + unit tests không infrastructure |
| Generic repository thành ORM trá hình | Port theo aggregate/use case; cấm query builder |
| UoW dùng chung giữa async requests | UoW factory, một instance mỗi command/request |
| Fake PASS nhưng PostgreSQL fail | Contract tests cho repo + real concurrency integration |
| Media side effect và DB lệch nhau | Explicit lifecycle states, compensation, reconciliation |
| Event mất/duplicate | Persist atomic; chưa externalize nếu chưa có outbox/idempotency |
| Big-bang branch khó review | Vertical slice commits, một active implementation/route |
| Scope creep sang feature mới | Không FR/NFR delta trong rewrite; BA gate mọi thay đổi |
| Tài liệu overclaim production | Tách implemented/local/CI/staging/production evidence |

## 9. Definition of Done

- [x] Mọi HTTP operation hiện tại đi qua application command/query handler.
- [x] Domain/application độc lập FastAPI, Pydantic, SQLAlchemy, asyncpg và env.
- [x] Mọi write use case có explicit UoW boundary và rollback-by-default.
- [ ] ORM records, SQL query và transaction implementation chỉ nằm trong adapters (Reopened: dọn models.py alias).
- [x] Business transition/invariant nằm trong domain; HTTP mapping nằm ở entrypoint.
- [ ] Storage/security/time/ID là explicit ports khi use case cần thay thế hoặc lifecycle (Reopened: clock/ID injection).
- [x] Không có generic repository, singleton session/UoW hoặc broker/message bus không cần thiết.
- [x] DDL baseline, OpenAPI và toàn bộ FR/NFR hiện tại không drift.
- [x] Test pyramid có domain/application unit, adapter integration và thin E2E.
- [ ] CI từ clean checkout PASS và artifact gắn đúng SHA/digest (Reopened).
- [ ] Legacy service/root ORM modules đã xóa; architecture guard không có bypass (Reopened).
- [x] `landing_preview.html`, development DB, media và named volume không bị chạm.
- [x] R-09 chỉ được mở khi staging HTTPS/soak/canary/rollback/native có evidence riêng (STRICTLY HOLD — Milestone 2).

## 10. Điều kiện dừng

Dừng phase và không chuyển route nếu:

- OpenAPI/error semantics hoặc DDL baseline thay đổi mà chưa có BA/CTO decision;
- handler mới cần import framework/ORM để hoàn thành business rule;
- fake repository che mất unique/locking behavior nhưng chưa có integration test;
- UoW không chứng minh rollback/close trên exception và cancellation;
- media COMMIT outcome unknown có thể xóa final object;
- EndSession không còn exactly-once trên PostgreSQL thật;
- test cũ bị xóa chỉ để làm suite xanh;
- rewrite được dùng để tuyên bố production-ready khi R-09 chưa đạt.

