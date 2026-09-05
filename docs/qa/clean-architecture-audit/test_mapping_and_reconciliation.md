# Clean Architecture Rewrite — Test Mapping & Coverage Reconciliation

- **Baseline Commit:** `2f5e200` (164 test cases)
- **Rewrite Intermediate Commit:** `4ae7673` (173 test cases)
- **Current Hardened Candidate:** 179 test cases
- **Audit Plan Reference:** [`docs/superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md`](../../superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md)

---

## 1. Summary of Suite Evolution

| Phase | Test Count | Key Invariants Added / Transformed |
|---|---|---|
| **Baseline `2f5e200`** | 164 | Full FastAPI parity with TypeScript backend (routes, error formats, PostgreSQL transactions, migrations). |
| **Rewrite `4ae7673`** | 173 | In-memory use case tests with initial AST architecture guard (9 new unit tests). |
| **Candidate (Current)** | **179** | Closed audit gaps G1–G4: pre-commit rollback compensation, deterministic abort translation, AST relative import & mutation guard, subprocess I/O block import test, transactional fake UoW failure boundary tests. |

---

## 2. Test File & Category Breakdown

| Test File | Test Count | Category | Primary Invariant / Coverage |
|---|---|---|---|
| `tests/test_architecture_guard.py` | 14 | Architecture / Unit | AST import resolution (relative/absolute), no outer layers, no env access, router composition rules, mutation fixtures, subprocess zero side-effects, transactional fake UoW isolation, step-by-step failure boundaries. |
| `tests/test_auth.py` | 9 | Integration / HTTP | Registration, login, logout, token revocation, role checks (FR-ID-001, FR-ID-002). |
| `tests/test_catalog.py` | 13 | Integration / HTTP | Draft, QA, Publish, Unpublish, Archive state machine (FR-CAT-001..005, FR-CMS-001). |
| `tests/test_flags.py` | 4 | Integration / HTTP | Feature flags persistence, role-based update (FR-FLG-001..003). |
| `tests/test_media.py` | 12 | Integration / Storage | MP4 upload, magic bytes, HLS registration, streaming, pre-commit compensation, 3-state commit outcome machine (FR-CMS-001..004). |
| `tests/test_migrate_fail_closed.py` | 11 | DB / Ops | Migration environment fail-closed rules, destructive downgrade protection. |
| `tests/test_neg.py` | 1 | Guard | Negative textbook route scan (asserts 404). |
| `tests/test_obs.py` | 11 | Observability | Request ID echo, 5xx alerting, credentials redaction, CORS policy. |
| `tests/test_openapi_diff.py` | 7 | Contract | Semantic OpenAPI schema comparison against handwritten `openapi.yaml`. |
| `tests/test_openapi_mutation_suite.py` | 19 | Contract Mutation | 18 negative mutations + 1 baseline zero diff. |
| `tests/test_schema_ddl.py` | 8 | DB / DDL | Schema equality with Prisma reference, no textbook tables/columns. |
| `tests/test_seed.py` | 4 | DB / Seeds | Seed idempotency, bootstrap admin user creation. |
| `tests/test_sessions.py` | 10 | Concurrency / DB | Learning session lifecycle, pessimistic row locking, atomic events. |
| `tests/test_storage_media_readiness.py` | 19 | Storage / Ops | Storage port traversal guard, 24h reconciliation retention, readiness probes. |
| `tests/test_sync.py` | 1 | Integration | Multi-device learner data synchronization. |
| `tests/test_vectors.py` | 3 | Security | JWT, Argon2, and HMAC vectors matching Node.js reference. |
| **Total** | **179** | | |

---

## 3. Detailed Mapping of Transformed and Added Tests

### 3.1 Tests Added to Close Audit Gaps (G1 – G4)

| Test ID | Origin Gap | Invariant Verified |
|---|---|---|
| `test_media.py::test_media_upload_db_failure_cleans_up_storage` | G1 | Deterministic DB failure after storage promotion triggers rollback and cleans up final binary object. |
| `test_media.py::test_media_upload_unknown_outcome_does_not_cleanup_storage` | G1 | Unknown commit outcome (timeout / unconfirmed rollback) preserves storage object for reconciliation and logs structured alert. |
| `test_architecture_guard.py::test_domain_layer_dependencies` | G4 | Domain layer AST scan: no outer imports, no env access, pure Python. |
| `test_architecture_guard.py::test_application_layer_dependencies` | G4 | Application layer AST scan: no adapters, entrypoints, frameworks, or env access. |
| `test_architecture_guard.py::test_adapters_layer_dependencies` | G4 | Adapters layer AST scan: no entrypoints or routers dependencies. |
| `test_architecture_guard.py::test_routers_composition_rules` | G4 | Routers must not instantiate concrete adapter classes directly; all creation flows through `bootstrap.py` factories. |
| `test_architecture_guard.py::test_guard_mutation_catches_violations` | G4 | Temporary source mutation fixtures (forbidden imports, env access, dynamic imports, direct adapter construction) reliably fail the AST guard. |
| `test_architecture_guard.py::test_package_import_has_zero_side_effects` | G4 | Isolated subprocess with blocked socket/engine constructors imports domain, application, and bootstrap without side effects. |
| `test_architecture_guard.py::test_fake_uow_isolation_and_rollback` | G4 | Transactional fake UoW maintains uncommitted vs committed state; rollback discards uncommitted mutations without leaking into committed state. |
| `test_architecture_guard.py::test_failure_boundaries_across_use_cases` | G4 | Step-by-step failure boundary tests across register, catalog, end session, and media upload. |

### 3.2 Preserved Baseline Invariants (`2f5e200` → Candidate)

All 164 original tests from baseline `2f5e200` remain 100% functional and present:
- Authentication & RBAC rules (student, teacher, admin).
- Catalog state transitions and invariant rules (`draft -> level_qa -> published -> archived`).
- Media upload MP4 magic bytes (`ftyp`), range request streaming (`200` vs `206` vs `416`), HMAC signed URL verification.
- Two-event atomic learning session termination with row locking.
- Database migrations, Alembic fail-closed policies, schema identity with Prisma DDL.
- Exact OpenAPI semantic parity (`0` diffs across all 22 routes and components).
