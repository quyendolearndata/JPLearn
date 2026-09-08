# Remote integration into main — 2026-09-08

## Remote inventory

- `origin/main`: `ccb7c44` (previous PR #42 merge).
- `origin/codex/fastapi-backend-hardening`: `d6b1d05`, clean architecture, recovery and learning workflows.
- `origin/codex/jplearn-development`: `881dd29`, CMS draft metadata and recorded QA, PR #43.
- `origin/evaluate-repo-9444422764928202759`: `faba42f`, old CI adjustments, PR #41.

All three histories are incorporated by merge commits. Existing remote branches are retained.
Uncommitted UI, local demo and benchmark files in the original checkout are excluded and preserved.

## Conflict resolutions

- Port recorded QA into the current domain/application/persistence layers; do not restore retired services.
- Keep revision-based draft CAS. Each submission advances QA round, review stores authenticated reviewer and timestamp; rejection requires notes, returns to draft and unfreezes content.
- Admin publishing requires current-round approval plus existing media/content integrity checks. Staff detail provides review history and refreshed signed media links; learner payloads exclude internal review data.
- Keep both published migration histories unchanged. `0019_merge_cms_reviews` joins `0018_hls_bundle_integrity` and `0002_cms_reviews`; exact schema snapshot contains 38 tables. Upgrade tests preserve catalog data from both lineages and existing CMS approvals without inventing reviews.
- Keep current CMS list/detail pages, add explicit approval/rejection and history. Retain upload cancellation protections and source recovery.
- Preserve manifest-selected pnpm. Remove obsolete Prisma generation for retired Node API; install ffmpeg for Python media checks in CI.
- Rename the CMS design decision to ADR-008 to avoid colliding with ADR-006 clean architecture. Historical schema resource names remain unchanged.
- Concurrency tests account for the additional review revision. Timing fixtures use the application clock to avoid Docker/host clock skew. Sync E2E compares fresh item URLs because other CMS tests publish concurrently.

## Validation

Evidence is under `evidence/remote-integration-20260908/` and applies to the integration working tree before the merge commit, not a production deployment.

- API: **420 passed**, 2 dependency deprecation warnings, no skipped tests.
- Web: TypeScript and **40 unit tests passed**.
- Mobile: **12 tests passed**; shared domain: **3 tests passed**.
- Negative-feature guard and OpenAPI compatibility/mutation checks passed (API suite).
- Container verification passed: non-root runtime, migrations, schema divergence rejection, populated database adoption and preserved data.
- E2E: **88 passed** on Chromium/WebKit in 2.6 minutes, exit 0.

Existing burst-load SLO and external operational/physical-device/Pedagogy acceptance limitations remain open as documented in the backend remediation report. This merge does not claim those gates are complete.
