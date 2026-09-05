# Backend package-layout refactor — 2026-09-05

Scope: reorganize `apps/api-python/src/jplearn_api` without changing business
rules, HTTP contracts, DDL, or transaction behavior. This records local working-tree
verification, not clean-commit qualification, human sign-off, or production acceptance.

## Changes

- Package root now contains only `__init__.py`, `bootstrap.py`, and `settings.py`.
- HTTP app, routers, schemas, middleware and dependencies live in `entrypoints/http/`.
- Migrate, seed and reconciliation commands live in `entrypoints/cli/`.
- Database connection/schema snapshot, password/JWT/HMAC helpers and sanitization
  live beside their respective adapters.
- Environment resolution lives in `config/`; contract comparison lives in `tooling/`.
- Removed the obsolete root `alert.py` re-export and `storage.py` module alias.
  Operational alert logger name remains stable.
- Updated CI, Docker, package scripts, console metadata, test imports and monkeypatch
  targets. Benchmark runner obtains the app factory from each revision's own harness
  so pre-layout baselines remain selectable; no performance benchmark was rerun here.
- Alembic script lookup uses package resources. Repository fallback search no longer
  assumes a fixed nesting depth. HTTP schema normalization no longer imports tooling.

## Regression checks

| Check | Result |
| --- | --- |
| `pnpm test:guard` | PASS |
| `cd apps/api-python && uv run pytest -q` | 206 passed; 2 existing dependency deprecation warnings |
| Architecture + package layout + OpenAPI mutation tests | 49 passed |
| `PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff` | PASS; no contract differences |
| Web differential E2E, Chromium + WebKit | 10 passed |
| Container verification | 7/7 gates PASS |
| `git diff --check` | PASS |

New checks prevent root module sprawl, require a nonempty router scan at the new
location, reject config/tooling imports from inner layers, import relocated
entrypoints without network effects, verify CLI metadata/help, and locate resources
from an unrelated working directory.

Local command logs and container manifest: `/tmp/jplearn-layout-verification.7YioM2/`.
Detailed E2E artifacts: `/tmp/jplearn-e2e-20260905224137_2160/`.
These are temporary local artifacts, not archived release evidence. Historical QA
reports/manifests and completed plans were not rewritten to pretend they tested
the new paths. See `apps/api-python/README.md` for current launch commands.

The outstanding performance review and R-09 operational HOLD are unchanged.
User-owned `walkthrough.md` and untracked `landing_preview.html` were not edited
or staged. No commit or push was performed for this refactor.
