# FastAPI Hardening Evidence Run Manifest

- **Run ID:** `20260904T184657Z`
- **Baseline Commit SHA:** `31807095a2dbe629573ff3e6ec8c9ed66c1513c4`
- **Branch:** `codex/fastapi-backend-hardening`
- **OS:** macOS Darwin 25.3.0 arm64
- **Environment:** Local / Isolation Test Runner

---

## 1. Initial Baseline Verification Results

| Target Gate | Command | Exit Code | Duration | Status | Notes |
|---|---|---|---|---|---|
| Repository Invariants | `pnpm test:guard` | 0 | 0.4s | PASS | 0 forbidden textbook / grammar references |
| Backend Pytest Suite | `uv run pytest -q` | 0 | 15.1s | PASS | 80 passed, 2 warnings (FastAPI starlette deprecation) |
| OpenAPI Diff (Initial) | `PYTHONPATH=src uv run python -m jplearn_api.openapi_diff` | 0 | 1.1s | PASS | Initial shallow check clean |

---

## 2. Gaps & Discrepancies Under Closure

Evidence run tracking the resolution of:
- G-01: `parents[4]` in `jplearn_api.migrate` causing Docker crash.
- G-02: DB empty skipping baseline diff and being stamped.
- G-03: Baseline JSON missing from container image / fail closed.
- G-04: OpenAPI diff missing min/max, nullable, extra fields, error bodies, security alternatives.
- G-05: `/ready` probe ignoring storage errors and write verification.
- G-06: Storage path traversal prefix matching allowing sibling directories.
- G-07: Media upload MIME/extension/magic bytes validation missing.
- G-08: StoragePort leaking `Path` dependency to application layer.
- G-09: 5xx webhook alerting on critical synchronous request path.
- G-10: E2E runner port/DB/storage isolation.
- G-11: Container build, migration CLI execution, soak, restore drills.
- G-12: Sign-offs and seat attribution.
- G-13: Plan status consistency.

---

## 3. Phase 1 Evidence — Migration & Release Artifact Fail Closed

- **Status:** **PASS** (G-01, G-02, G-03 closed)
- **Packaged Resource:** `jplearn_api.resources.adr-004-schema-baseline.json` bundled in wheel and Docker image.
- **Docker Build & CLI:** Pinned `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea` and `uv@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff`. Non-root UID 10001 confirmed. Verified `python -m jplearn_api.migrate --help` and baseline loading (10 tables) inside container.
- **Fail-Closed Stamp:** Empty database stamp rejected with `RuntimeError` before creating `alembic_version`. Diverged schema rejected before creating `alembic_version`.
- **Environment Resolver:** Missing or unknown environment blocks destructive downgrade without `ALLOW_DESTRUCTIVE_DOWNGRADE=true`.
- **Runbook:** `docs/ops/runbook-backup-restore.md` authored by Ops seat.
- **Pytest Gate:** 94 passed (14 new tests in `test_migrate_fail_closed.py`).

---

## 4. Phase 2 Evidence — Semantic OpenAPI Gate & Mutation Suite

- **Status:** **PASS** (G-04 closed)
- **OpenAPI Comparator Hardening:**
  - Added `/ready` to `REQUIRED_OPERATIONS`.
  - Bi-directional operation, parameter, property, and required fields comparison.
  - Strict min, max, minLength, maxLength, pattern, format, enum, and nullable validation.
  - Full security alternatives comparison (no reduction to boolean).
  - Strip auto-generated 422 at custom OpenAPI boundary in `main.py` per ADR-005; comparator checks all declared responses.
- **OpenAPI Mutation Suite:** 10/10 PASS (`test_openapi_mutation_suite.py`):
  1. `ci_level: integer -> string`: caught type mismatch.
  2. Drop minimum or maximum: caught missing min/max.
  3. Add nullable: caught nullable mismatch.
  4. Drop required field: caught missing required field.
  5. Expand `device_class` enum: caught enum mismatch.
  6. Inject 422 / `{detail}`: caught extra responses 422 not in contract.
  7. Drop security alternative: caught security mismatch.
  8. Add forbidden response field: caught extra property not in contract.
  9. Delete `/ready` operation: caught missing required operation.
  10. CLI gate fail-closed: exit code 1 verified.
- **Pytest Gate:** 104 passed (10 new tests in `test_openapi_mutation_suite.py`).

---

## 5. Phase 3 Evidence — Storage Boundary, Media Validation, Readiness & Retention

- **Status:** **PASS** (G-06, G-07, G-08, G-09 closed)
- **Storage Port Hardening (G-06):**
  - Removed `get_path() -> Path` from `StoragePort` to decouple application layer from local filesystem paths.
  - Added `open_read() -> AsyncIterator[bytes]` and `get_metadata() -> StorageMetadata`.
  - Replaced `FileResponse` with `StreamingResponse` in `routers/media.py`.
  - Hardened `LocalFilesystemStorage._resolve(key)` with absolute path detection, parent escape rejection, and `is_relative_to(self.root)` guard against sibling-directory prefix collisions.
  - Created `InMemoryStorage` fake object storage adapter passing parity contract tests.
- **Media Upload Validation & Atomicity (G-07):**
  - Enforced `.mp4` file extension and `video/mp4` MIME type per ADR-005 BA decision.
  - Enforced inspection of first chunk for MP4 box type `ftyp` at bytes 4..8. Corrupted headers, non-MP4 files, and payloads < 8 bytes return 400 Bad Request.
  - Enforced temporary staging to `<asset_id>.part` with atomic promotion to `<asset_id>.bin`.
  - Wrapped DB commit with compensation deletion to ensure no orphaned files on DB failure and no DB rows on storage failure.
- **Active Readiness Probe (G-08):**
  - Upgraded `/ready` probe to perform an active write + fsync + read + delete cycle (`__probe__/probe.tmp`) with `asyncio.wait_for(..., timeout=2.0)`.
  - Negative tests verify 503 Service Unavailable with `storage="down"` upon simulated storage failure or unwritable filesystem.
- **Media Orphan Retention Policy (G-09):**
  - Enforced 24-hour grace window in `reconcile_orphans`: unreferenced storage objects newer than 24 hours are marked protected and never deleted.
  - Default CLI and library execution is report-only (`--dry-run`). Destructive deletion requires explicit `--confirm-retention-exceeded` (or `confirm_retention_exceeded=True`).
- **Phase 3 Tests:** 6 new unit/integration tests in `test_storage_media_readiness.py` covering traversal, adapter parity, MIME/magic bytes validation, active readiness probe, and 24h grace window retention.
- **Pytest Gate:** 110 passed.


