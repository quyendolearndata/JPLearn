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

## 3. Evidence Artifacts

- `run_baseline.log` (captured during initial audit)
- Subsequent phase logs appended per task.
