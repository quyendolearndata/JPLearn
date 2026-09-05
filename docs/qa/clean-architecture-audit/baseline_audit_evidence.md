# Clean Architecture Rewrite — Baseline Audit Evidence

- **Commit Baseline:** `4ae7673` (`docs(api): record rewrite evidence and remaining R-09 hold`)
- **Branch:** `codex/fastapi-backend-hardening`
- **Audit Plan:** [`docs/superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md`](../../superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md)
- **Status:** In Progress (Gap Closure G0–G6)

## 1. Initial State & Dirty Working Tree Inspection

- **Tracked Dirty Files:**
  - `walkthrough.md`: Updated with rewrite records.
  - `docs/superpowers/plans/2026-09-05-fastapi-clean-architecture-rewrite.md`: Reopened checkboxes for audit gaps.
  - `docs/sad/03-design/adr-006-clean-architecture.md`: Corrected all 21 operation routes and behavior matrix.
- **Untracked Boundary:**
  - `landing_preview.html`: Untracked static asset, must NEVER be modified or committed.
  - `docs/superpowers/plans/2026-09-05-clean-architecture-audit-gap-closure.md`: Audit plan.

## 2. Baseline Verification Commands & Results

| Check | Command | Baseline Result |
|---|---|---|
| Root Guard | `pnpm test:guard` | **PASS** (0 violations) |
| Architecture Guard | `cd apps/api-python && uv run pytest tests/test_architecture_guard.py` | **PASS** (9 passed) |
| Pytest Suite | `cd apps/api-python && uv run pytest -q` | **PASS** (173 passed, 2 warnings, ~23s) |
| OpenAPI Diff | `uv run pytest tests/test_openapi_diff.py tests/test_openapi_mutation_suite.py` | **PASS** (26 passed) |
| Web E2E | `apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit` | **PASS** (10 passed) |
| Container Gate | `apps/api-python/scripts/verify-container.sh` | **PASS** (7/7 gates) |

## 3. Audit Gap Mapping (G0 – G6)

| Gap ID | Focus | Severity | File Targets |
|---|---|---|---|
| **G0** | Scope lock & status correction | P2 | `docs/superpowers/plans/*`, `ADR-006` |
| **G1** | Upload transaction & pre-commit rollback compensation | P1 | `application/handlers/media.py`, `adapters/persistence/media_repository.py`, `tests/test_media.py` |
| **G2** | Complete ports/adapters wiring, remove root `models.py` & legacy services | P2 | `bootstrap.py`, `deps.py`, `models.py`, `routers/media.py`, `reconciliation.py` |
| **G3** | Explicit clock/ID/security injection & adapter error translation | P2 | `application/ports/*`, `application/handlers/*`, `adapters/security/*` |
| **G4** | AST architecture guard mutation tests & transactional test fakes | P2 | `tests/test_architecture_guard.py`, `fakes.py` |
| **G5** | Reconcile test mapping, C4 documentation, and evidence | P2 | `docs/*`, `walkthrough.md` |
| **G6** | Clean candidate requalification & performance benchmark | P2 | Entire test suite, clean checkout worktree |
