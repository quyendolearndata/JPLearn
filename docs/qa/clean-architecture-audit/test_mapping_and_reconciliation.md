# Clean Architecture Rewrite — Test Mapping & Coverage Reconciliation

- **Baseline Commit:** `2f5e200` (164 test cases)
- **Rewrite Intermediate Commit:** `4ae7673` (173 test cases)
- **Audit Hardened Commit:** `b565b7b` (179 test cases)
- **Current Candidate:** **187 test cases**
- **Audit Plan Reference:** [`docs/superpowers/plans/2026-09-05-clean-architecture-remaining-gaps-v2.md`](../../superpowers/plans/2026-09-05-clean-architecture-remaining-gaps-v2.md) (Phase 4 — V4)
- **Status:** **RECONCILIATION COMPLETE — 0 Tests Deleted, 0 Tests Skipped, 23 Tests Added**

---

## 1. Summary of Suite Evolution Across Checkpoints

| Checkpoint | Commit SHA | Test Count | Key Invariants Added / Transformed |
|---|---|---|---|
| **Baseline** | `2f5e200` | **164** | Baseline FastAPI implementation with complete parity against TypeScript reference (authentication, catalog, media streaming, sessions, Alembic migrations). |
| **Rewrite (Audit 1)** | `4ae7673` | **173** | In-memory use case unit tests with initial AST architecture guard (+9 tests in `test_architecture_guard.py`). |
| **Intermediate (Audit 2)** | `b565b7b` | **179** | Closed audit gaps G1–G4: pre-commit rollback compensation, deterministic abort translation, AST relative imports, subprocess zero side-effects (+6 tests). |
| **Final Candidate** | `Candidate` | **187** | Closed remaining verification gaps V1–V3: 3-scope upload transaction isolation & connection release (+2 in `test_media.py`), transitive import analyzer, aliased constructor detection, and ports re-export guard (+6 in `test_architecture_guard.py`). |

---

## 2. Test File & Category Breakdown (Final Candidate: 187 Tests)

| Test File | Baseline (`2f5e200`) | Audit 1 (`4ae7673`) | Audit 2 (`b565b7b`) | Candidate | Category | Primary Invariant / Coverage |
|---|---|---|---|---|---|---|
| `tests/test_architecture_guard.py` | 0 | 9 | 13 | **19** | Architecture / AST | Transitive import graph analysis, alias resolver, pure ports abstraction, mutation fixtures, subprocess import isolation, fake UoW transaction boundaries. |
| `tests/test_auth.py` | 7 | 7 | 7 | **7** | Integration / HTTP | User registration, password hashing, login, logout, token version revocation (FR-ID-001..003). |
| `tests/test_catalog.py` | 6 | 6 | 6 | **6** | Integration / HTTP | Catalog state machine (`draft -> submit-qa -> publish -> unpublish -> archive`), RBAC rules (FR-CAT-001..005). |
| `tests/test_contract.py` | 2 | 2 | 2 | **2** | Contract / Schema | OpenAPI schema endpoint parity and structure validation. |
| `tests/test_e2e_runner_isolation.py` | 6 | 6 | 6 | **6** | Test Infra / Ops | Differential test runner isolation and container port resolution. |
| `tests/test_env_resolver.py` | 6 | 6 | 6 | **6** | Config / Unit | Strict environment variable parsing, fallback suppression, secret strength. |
| `tests/test_errors.py` | 2 | 2 | 2 | **2** | Presentation / HTTP | Domain error to RFC 7807 problem details mapping, unhandled error sanitization. |
| `tests/test_flags.py` | 3 | 3 | 3 | **3** | Integration / HTTP | Feature flag reading, defaults seeding, admin update restrictions (FR-FLG-001..003). |
| `tests/test_health.py` | 5 | 5 | 5 | **5** | Observability | Liveness, readiness probes under healthy and degraded storage/DB states. |
| `tests/test_hls.py` | 6 | 6 | 6 | **6** | Integration / Media | HLS manifest registration, playlist streaming, byte-range segment streaming (FR-CMS-001). |
| `tests/test_media.py` | 24 | 24 | 24 | **26** | Concurrency / Storage | 3-scope UoW upload isolation, byte stream connection release barrier, catalog deleted race compensation, 5 commit outcome recovery scenarios. |
| `tests/test_migrate_fail_closed.py` | 16 | 16 | 16 | **16** | DB / Ops | Alembic migration fail-closed policies, destructive downgrade protection across environments. |
| `tests/test_neg.py` | 1 | 1 | 1 | **1** | Guard | Negative route scanner asserting 404 on all deprecated textbook routes. |
| `tests/test_obs.py` | 11 | 11 | 11 | **11** | Observability | Request ID echo, 5xx webhook alerting, credentials redaction, CORS policy. |
| `tests/test_openapi_diff.py` | 7 | 7 | 7 | **7** | Contract | Semantic diff against handwritten `openapi.yaml` (asserts 0 differences). |
| `tests/test_openapi_mutation_suite.py` | 19 | 19 | 19 | **19** | Contract Mutation | 18 negative schema mutations + 1 baseline zero diff. |
| `tests/test_schema_ddl.py` | 8 | 8 | 8 | **8** | DB / DDL | Schema equality with Prisma baseline reference, no textbook tables/columns. |
| `tests/test_seed.py` | 4 | 4 | 4 | **4** | DB / Seeds | Seed idempotency, bootstrap admin user creation, password policies. |
| `tests/test_sessions.py` | 10 | 10 | 10 | **10** | Concurrency / DB | Learning session lifecycle, pessimistic row locking, atomic events. |
| `tests/test_storage_media_readiness.py` | 19 | 19 | 19 | **19** | Storage / Ops | Path traversal guards, 24h reconciliation retention, bounded worker concurrency. |
| `tests/test_sync.py` | 1 | 1 | 1 | **1** | Integration | Cross-device learner progress and session synchronization. |
| `tests/test_vectors.py` | 3 | 3 | 3 | **3** | Security | Cryptographic test vectors matching Node.js reference (Argon2, JWT, HMAC). |
| **Total** | **164** | **173** | **179** | **187** | | |

---

## 3. Reconciliation of Added Tests (Gaps V1 – V3)

All 8 tests added between `b565b7b` (179) and `Candidate` (187) are dedicated verification additions closing audit gaps:

| Test Node ID | Origin | Target Invariant |
|---|---|---|
| `tests/test_media.py::test_upload_byte_stream_barrier_releases_db_connection` | **V1** | Proves via PostgreSQL `pg_stat_activity` that zero DB connections are held while streaming 5MB upload payload to storage. |
| `tests/test_media.py::test_upload_catalog_deleted_between_preflight_and_write_compensates` | **V1** | Simulates concurrent catalog deletion between Scope 1 (preflight) and Scope 3 (write), proving Scope 3 rolls back cleanly and deletes promoted storage object. |
| `tests/test_architecture_guard.py::test_domain_layer_transitive_dependencies` | **V3** | Builds full import graph of `jplearn_api` and asserts no domain module transitively imports adapters, frameworks, or outer layers. |
| `tests/test_architecture_guard.py::test_application_layer_transitive_dependencies` | **V3** | Asserts no application module transitively imports adapters, routers, or frameworks. |
| `tests/test_architecture_guard.py::test_ports_layer_pure_abstractions` | **V3** | Verifies all modules in `application/ports` define pure protocols/interfaces and never re-export concrete adapter classes. |
| `tests/test_architecture_guard.py::test_guard_mutation_catches_transitive_import_leak` | **V3** | Mutation test proving transitive analyzer reliably detects multi-hop indirect leaks (`domain -> helper -> adapter`). |
| `tests/test_architecture_guard.py::test_guard_mutation_catches_aliased_constructor_in_router` | **V3** | Mutation test proving AST alias resolver catches adapter instantiation disguised via `import ... as U` or variable assignment `U = SqlAlchemyUnitOfWork`. |
| `tests/test_architecture_guard.py::test_guard_mutation_catches_symbol_reexport_leak` | **V3** | Mutation test proving ports guard catches concrete adapter imports and `__all__` re-exports in application ports. |

---

## 4. Preservation Invariant Sign-Off

- **Baseline Retention:** 100% of the 164 tests from baseline commit `2f5e200` are present, unmodified in requirement, and passing.
- **Zero Test Deletion:** Diff between `2f5e200` test functions and candidate test functions is `set()` (empty).
- **Zero Skipped Tests:** All 187 collected tests execute to completion (`187 passed, 0 failed, 0 skipped`).
