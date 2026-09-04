# FastAPI Backend Hardening — Walkthrough (DRAFT / NOT ACCEPTED)

> **Trạng thái:** DRAFT / NOT ACCEPTED — Chờ đóng các khoảng trống theo plan 2026-09-05 và chữ ký đúng ghế.
> **Baseline:** `3180709`
> **Gap closure plan:** `docs/superpowers/plans/2026-09-05-fastapi-hardening-gap-closure.md`


---

## 1. Executive Summary

This hardening implementation executed the 7-phase production readiness plan for the FastAPI/Alembic backend (`apps/api-python`), replacing the historical NestJS backend while maintaining 100% contract fidelity, enforcing PostgreSQL concurrency guarantees, securing media uploads with bounded streaming, locking Alembic schema migrations, and delivering a production-ready container artifact.

### Key Milestones Achieved:
1. **Phase 0 (Baseline Checkpoint & Doc Sync):** Commit `889bff2` reconciled test counts and eliminated historical references.
2. **Phase 1 (Secure Seed & Settings Validation):** Commit `396dc49` decoupled reference data from admin bootstrap, made admin creation create-only with no password overwrite, enforced `JWT_SECRET >= 32` bytes, enforced HTTPS & dedicated media signing secrets for staging/prod, and sanitized exception handling.
3. **Phase 2 (`EndSession` Exactly-Once Concurrency):** Commit `d8121c2` extracted `session_policy.py`, implemented pessimistic row locking (`SELECT ... FOR UPDATE` on session and learner progress), rollback-by-default, and atomic event recording. Proved with real PostgreSQL concurrent test.
4. **Phase 3 (Media Streaming & Storage Port):** Commit `3bcb531` introduced `StoragePort` abstraction, chunked bounded streaming via temporary `.part` keys, compensation on DB failures, missing file publish rejection (`FR-CAT-002`), and orphan reconciliation.
5. **Phase 4 (Semantic OpenAPI Contract Gate):** Commit `6931ed8` hardened Pydantic boundary schemas (strict email, regex, literal enums, string formats) and upgraded `openapi_diff.py` to recursively resolve `$ref`, compare schema types/constraints, and prevent spec drift.
6. **Phase 5 (Migration & Stamp Safety):** Commit `e19d411` added baseline verification before `stamp 0001_prisma_baseline` against `adr-004-schema-baseline.json`, and blocked destructive `downgrade base` in staging/prod without explicit override.
7. **Phase 6 (Deployment & Readiness Gate):** Commit `f7e2dee` created Dockerfile with non-root user `appuser`, implemented `/ready` probe checking live PostgreSQL and storage health, offloaded Argon2 password hashing to thread pools, and updated `web-e2e-python.sh`.

---

## 2. Verification Gate Results

All four mandatory gates from section 8 of the hardening plan pass:

| Verification Gate | Command | Result | Details |
|---|---|---|---|
| **Repository Invariants** | `pnpm test:guard` | **PASS** | 0 textbook / forbidden references |
| **FastAPI Test Suite** | `uv run pytest -q` | **PASS** | **80 passed** (exceeds 55+ target) |
| **OpenAPI Contract Gate** | `PYTHONPATH=src uv run python -m jplearn_api.openapi_diff` | **PASS** | 0 discrepancies between code and SAD |
| **Differential Web E2E** | `apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit` | **PASS** | **10/10 Playwright tests passed** across Chromium and WebKit |

---

## 3. Git Commit History

```
* 3180709 docs(plan): update hardening plan checklist and DoD
* f7e2dee ops(api): add staging deployment and readiness gate
* e19d411 fix(api): guard Alembic stamp and destructive downgrade
* 6931ed8 test(api): enforce semantic OpenAPI schemas
* 3bcb531 refactor(api): introduce storage port and bounded upload
* d8121c2 fix(api): make session end exactly once
* 396dc49 fix(api): secure bootstrap seed and runtime settings
* 889bff2 docs(api): reconcile FastAPI counts and runbooks
* 972ce6d chore(api): checkpoint FastAPI replatform baseline
```

---

## 4. Key Architectural Additions

### A. Storage Port & Bounded Upload (`apps/api-python/src/jplearn_api/storage.py`)
- `StoragePort`: Abstract protocol for `save_stream`, `open_read`, `delete`, `exists`, and `list_keys`.
- `LocalFilesystemStorage`: Path-traversal proof filesystem adapter using `.resolve()` check.
- `media_service.py`: Streams directly from `UploadFile` chunks into `.part` file, checks MIME and bounded file size, promotes to `.bin` key upon completion, and issues `await storage.delete()` compensation if database insert fails.
- `reconciliation.py`: `reconcile_orphans()` detects orphaned storage files and missing database records.

### B. Exactly-Once Session Completion (`apps/api-python/src/jplearn_api/sessions_service.py`)
- Pure Python policy in `session_policy.py` for duration and minute calculations (e.g. capped at 240 mins).
- Pessimistic locking via `SELECT ... FOR UPDATE` on `learning_sessions` and `learner_progress`.
- Atomic recording of `session_ended` and `minutes_comprehensible` events.
- Concurrency test with real PostgreSQL connections proves duplicate `end` attempts reject gracefully without double-counting progress.

### C. Migration & Baseline Stamp Guard (`apps/api-python/src/jplearn_api/migrate.py`)
- `stamp("0001_prisma_baseline")` snapshots live PostgreSQL schema via `snapshot_url()` and computes structural diff against `adr-004-schema-baseline.json`. Refuses to stamp if diverged.
- `downgrade("base")` raises `RuntimeError` in `staging` or `production` unless `ALLOW_DESTRUCTIVE_DOWNGRADE=true` is explicitly provided.

### D. Production Deployment Artifact & Readiness Probe
- `apps/api-python/Dockerfile`:
  - Python 3.12 slim base with `uv` package manager.
  - Non-root user `appuser` (UID 10001).
  - Frozen dependency installation via `uv.lock`.
  - Exposes port 3002 running uvicorn.
- `apps/api-python/src/jplearn_api/routers/health.py`:
  - `/health`: Liveness probe.
  - `/ready`: Readiness probe verifying PostgreSQL `SELECT 1` and storage directory accessibility. Returns 200 `{"ok": true, "database": "up", "storage": "up"}` or 503 if unhealthy.
  - Fully documented in `docs/sad/03-design/openapi.yaml`.
