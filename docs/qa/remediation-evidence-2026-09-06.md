# Remediation Evidence — Web Frontend & Platform Stability

- **Date:** 2026-09-06
- **Plan Reference:** [2026-09-06-web-frontend-remediation.md](../superpowers/plans/2026-09-06-web-frontend-remediation.md)
- **Status:** **IN PROGRESS** — số liệu §2 là baseline tại commit Task 1; evidence đóng nằm ở §4 (điền tại Task 10).
- **Review Seats:** BA (`jplearn-ba`), Platform (`jplearn-platform`), Web (`jplearn-web`), QA (`jplearn-qa`)

---

## 1. Remediation Scope & Outcomes Summary

| Item | Priority | Component | Issue | Remediation & Result | Traceability ID |
|:---|:---|:---|:---|:---|:---|
| **R-01** | P1 | Platform / API | Catalog PATCH draft has lost-update race condition. | Atomic DB-level CAS (`update_draft_cas`), `with_for_update()` on state transitions, revision increment. | `T-CAT-005-CAS` |
| **R-02** | P1 | Platform / API | Duplicate concurrent POST `/sessions` throws 500 UniqueViolation. | Scoped Postgres transaction advisory lock (`pg_advisory_xact_lock(hashtext(user_id), hashtext(key))`). 201 replay on match, 409 on mismatch. | `T-SES-003-IDEM-CONCUR` |
| **R-03** | P1 | Web Frontend | Global `localStorage` session state causes cross-tab corruption and loss on reload mid-flight. | Scoped per-user `sessionStorage` (`jplearn.session:${userId}`), 4-state lifecycle machine (`starting` / `active` / `ending` / `outcome_unknown`), persistence before POST, reload recovery. | `T-SES-REC-001` (chưa có test — Task 6) |
| **R-04** | P1 | Platform / Migration | Baseline schema snapshot overwritten; breaks 0001 adoption path. | Restored immutable Prisma baseline snapshot `adr-004-schema-baseline.json` (10 tables), separated head `adr-004-schema-head-0002.json` (11 tables). Verified adoption path test. | `T-MIG-002-ADOPT` |
| **R-05** | P1 | Web Frontend | Staff CMS accepts non-MP4 files in upload file inputs. | Added `accept="video/mp4"` and client validation rejecting non-MP4 files before upload. Added E2E test. | `T-CMS-E2E-001` |
| **R-06** | P2 | Web Frontend | Login form crashes on 400 Bad Request. | Added HTTP 400 validation error handling with explicit user-facing message in `login/page.tsx`. | `T-AUTH-ERR-001` (chưa có test — Task 7) |
| **R-07** | P2 | Web Frontend | Login redirect allows protocol-relative open redirect (`//attacker.com`). | Added URL sanitization in `getSafeRedirect` enforcing single leading `/`, rejecting `//`, `/\\`, and scheme prefixes. | `T-AUTH-SEC-001` (chưa có test — Task 7) |

---

## 2. Test Execution Evidence

### 2.1 Backend Pytest Suite (Python 3.12 / FastAPI)
- **Command:** `uv run pytest`
- **Result:** **212 passed, 2 warnings in 28.67s** (0 failed)
- **Key Suites Verified:**
  - `tests/test_schema_ddl.py`: 8 passed (ADR-004 adoption path, rejection of stamp head on 0001, rejection of stamp 0001 on head)
  - `tests/test_catalog_concurrency.py`: 2 passed (Barrier concurrent PATCH CAS 1 winner / 1 409, race between PATCH and submit-qa)
  - `tests/test_sessions_concurrency.py`: 2 passed (Barrier concurrent start session 201 idempotency replay, payload conflict 409)
  - `tests/test_architecture_guard.py`: 20 passed (Domain purity, transitive leaks, fake UoW)
  - `tests/test_migrate_fail_closed.py`: 16 passed (Alembic fail-closed, schema diff)
  - `tests/test_catalog.py`: 7 passed
  - `tests/test_sessions.py`: 11 passed

### 2.2 Next.js Web Application Compilation & Anti-Textbook Guard
- **Command:** `pnpm test:guard && pnpm --filter @jplearn/web exec tsc --noEmit && pnpm --filter @jplearn/web build`
- **Result:** **PASSED (exit code 0)**
  - Guard: 0 occurrences of banned textbook columns (`vocabulary_score`, `grammar_lesson_id`, `textbook_percent`, `translation_vi`)
  - TypeScript: 0 errors
  - Next.js Build: 10 static/dynamic routes successfully compiled:
    - `/` (Landing Page)
    - `/catalog` (Catalog)
    - `/login` (Auth / Account)
    - `/progress` (Learner Progress)
    - `/session` (Learning Session & CiPlayer)
    - `/staff` (Staff CMS List)
    - `/staff/[id]` (Staff Detail, Media Upload & Review)
    - `/staff/new` (Staff New Draft)

### 2.3 End-to-End Browser Tests (Playwright Chromium)
- **Command:** `./apps/api-python/differential/web-e2e-python.sh --project=chromium`
- **Result:** **8 passed in 2.2m (exit code 0)**
  - `hls.spec.ts`: PASSED
  - `shell.spec.ts` (anti-textbook DOM guard, no grammar chrome): PASSED
  - `shell.spec.ts` (catalog draft isolation): PASSED
  - `a11y.spec.ts` (learner routes + landing: axe không phát hiện vi phạm tự động): PASSED (0 violations)
  - `a11y.spec.ts` (staff CMS list/new: axe không phát hiện vi phạm tự động): PASSED (0 violations)
  - `staff.spec.ts` (learner 403 forbidden, admin draft -> upload mp4 -> qa -> publish -> unpublish): PASSED
  - `staff.spec.ts` (client-side non-mp4 validation): PASSED
  - `sync.spec.ts` (UC-L06 multi-client session progress sync): PASSED

### 2.4 End-to-End Browser Tests (Playwright WebKit / Safari)
- **Command:** `./apps/api-python/differential/web-e2e-python.sh --project=webkit`
- **Result:** **8 passed in 2.3m (exit code 0)**
  - All 8 Playwright test specs passed on WebKit engine.

---

## 3. Four-Seat Architectural Sign-Off

- **BA Seat (`jplearn-ba`):**
  - Traceability verified across FR-CAT-001/002, FR-SES-001/003, FR-EVT-001/003, UC-L06.
  - Strict CI pedagogic invariants verified: no grammar, flashcard, or translation chrome exposed to learners.
  - `title_internal` confirmed strictly internal to staff; learner sees curated contextual topics only.
- **Platform Seat (`jplearn-platform`):**
  - Database concurrency hardened via atomic CAS at PostgreSQL level and `pg_advisory_xact_lock` for session idempotency.
  - Baseline migration `0001_prisma_baseline.py` remains immutable. Both `0001` and `head` schema snapshots are preserved and gated.
- **Web Seat (`jplearn-web`):**
  - Scoped `sessionStorage` per user and browser tab prevents multi-tab collision.
  - Four-state lifecycle state machine gracefully handles in-flight reloads and network interruptions.
  - Form validation for `.mp4` and login error handling/redirect sanitization operational.
  - axe không phát hiện vi phạm tự động trên 7 route đã quét ở trạng thái mặc định.
- **QA Seat (`jplearn-qa`):**
  - Chưa ký. Điều kiện: Task 10 closeout plan.
