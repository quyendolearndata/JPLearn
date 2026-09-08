# Remediation Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa repo về một nguồn sự thật trên `main`, sửa 6 lỗi có bằng chứng (port mobile, nav cấm, brute-force login, thiếu lint, E2E ngoài CI, tài liệu sai thang cấp), và mọi thay đổi đều có test chạy trong CI.

**Architecture:** Không thêm dependency runtime mới ở backend (rate limiter in-process ở tầng entrypoints, đúng Clean Architecture ADR-006). Web/mobile chỉ sửa điểm, không tái cấu trúc. CI thêm job, không đổi job cũ.

**Tech Stack:** FastAPI/Python 3.12/uv, Next.js 15, Expo 53, pnpm 9, Playwright, GitHub Actions.

**Branch note (Task 0):** `codex/web-ui-learning-loop` đã merge vào `main` (PR #44, `fd85ea4`). Candidate hiện tại là `codex/remediation-phase-1` branched from `main`. Backup dirty tree cũ: `/tmp/jplearn-backup-20260908-b`.

## Global Constraints

- Mọi commit có FR/NFR id trong message (quy ước repo). Message không chứa từ “cursor”.
- Không đụng `docs/sad/03-design/openapi.yaml` mà không chạy `openapi_diff` (CI sẽ fail).
- Không tạo route/bảng/field có tên `grammar`, `flashcard`, `translation`, `vocabulary` (FR-NEG-001..004).
- Backend: domain/application không import `fastapi`/`sqlalchemy` (test_architecture_guard sẽ fail).
- Mọi test DB dùng Docker `db-test` / `jplearn_test`, không đụng DB dev.
- Không push/merge vào `main` khi chưa có người dùng duyệt PR.

---

### Task 0: Hợp nhất trạng thái nhánh (ghế CTO)

**Files:** không sửa mã; chỉ thao tác git.

- [x] **Bước 1–4:** Sao lưu `/tmp/jplearn-backup-20260908-b`, gỡ worktree `codex-web-ui-learning-loop` và `jplearn-integrate-main`, discard dirty tree, tạo `codex/remediation-phase-1` từ `main@fd85ea4`.
- [ ] **Bước 5: Commit PRODUCT.md**
- [ ] **Bước 6: `git gc --prune=now`**

---

### Task 1: Mobile — sửa port API mặc định và dùng `pickClipSource` (ghế Mobile)

Root `package.json` chạy API ở **3002**; `apps/mobile/src/api.ts` mặc định **3001**. `pickClipSource.ts` có test nhưng `session.tsx` nhân bản logic inline.

**Files:**
- Modify: `apps/mobile/src/api.ts`
- Modify: `apps/mobile/app/(tabs)/session.tsx`
- Test: `apps/mobile/src/__tests__/api.test.ts` (tạo mới)

**Interfaces:**
- Produces: `export const apiBaseUrl = () => string` — default `"http://localhost:3002"`; honours `EXPO_PUBLIC_API_URL`.
- Consumes: `pickClipSource(items: CatalogItemPublic[]): string | null` from `apps/mobile/src/pickClipSource.ts`.

- [ ] **Step 1: Write the failing test**

Create `apps/mobile/src/__tests__/api.test.ts`:

```ts
import { apiBaseUrl } from "../api";

describe("apiBaseUrl", () => {
  const original = process.env.EXPO_PUBLIC_API_URL;
  afterEach(() => {
    if (original === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = original;
  });

  test("defaults to the FastAPI dev port 3002 (matches root dev:api)", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(apiBaseUrl()).toBe("http://localhost:3002");
  });

  test("honours EXPO_PUBLIC_API_URL", () => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.test";
    expect(apiBaseUrl()).toBe("https://api.example.test");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @jplearn/mobile test -- api.test`
Expected: FAIL — `apiBaseUrl is not a function` / not exported.

- [ ] **Step 3: Write minimal implementation**

Replace `apps/mobile/src/api.ts` with:

```ts
export const apiBaseUrl = () =>
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:3002";

export async function api(
  path: string,
  opts: RequestInit & { token?: string } = {},
) {
  const headers = new Headers(opts.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (opts.token) headers.set("Authorization", `Bearer ${opts.token}`);
  const { token: _token, ...rest } = opts;
  return fetch(`${apiBaseUrl()}${path}`, { ...rest, headers });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter @jplearn/mobile test`
Expected: all previous tests plus 2 new ones pass.

- [ ] **Step 5: Use `pickClipSource` in `session.tsx`**

Read `apps/mobile/app/(tabs)/session.tsx` around the catalog item / clip source lines. Import `pickClipSource` from `../../src/pickClipSource`. Replace inline `hls_url || playback_url` find and `hls_url ?? playback_url` assignment with `pickClipSource`. Keep existing session/playback behavior otherwise.

- [ ] **Step 6: Typecheck + test**

Run: `pnpm --filter @jplearn/mobile exec tsc --noEmit && pnpm --filter @jplearn/mobile test`

- [ ] **Step 7: Commit**

```bash
git add apps/mobile/src/api.ts apps/mobile/src/__tests__/api.test.ts "apps/mobile/app/(tabs)/session.tsx"
git commit -m "fix(mobile): default API port 3002 and reuse pickClipSource (FR-LRN-001, NFR-PERF-002, NFR-XPLAT-002)"
```

---

### Task 2: Web — gỡ liên kết tới tính năng bị cấm khỏi chrome (ghế Web)

`apps/web/src/components/chrome.tsx` render `/grammar`, `/flashcards`, "Bản dịch", `/speak` khi flag bật. Flag kill-switch phía server (FR-FLG-001/002) **giữ nguyên** trong `@jplearn/domain` + API; chỉ UI không được có đường dẫn tới thứ không tồn tại và bị cấm.

**Files:**
- Modify: `apps/web/src/components/chrome.tsx`
- Modify: `apps/web/e2e/shell.spec.ts`

- [ ] **Step 1: Add E2E that fails while banned chrome exists when flags are on**

Append to `apps/web/e2e/shell.spec.ts` a test named `banned chrome stays absent even when server flags are on T-FLG-002 T-NEG-002` that: logs in as `admin@jplearn.local` / `password10` via API, PATCHes `/staff/flags` all four flags true, registers a learner, visits `/catalog`, asserts `BANNED_CHROME` plus link "Nói" are absent, then restores flags to all false in `finally`. Discover the Playwright API base env from `apps/api-python/differential/web-e2e-python.sh` / `web_e2e_runner.py` (do not invent a name).

- [ ] **Step 2: Run E2E to verify it fails**

Run: `apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/shell.spec.ts`
Expected: new test FAIL because "Ngữ pháp" is visible.

- [ ] **Step 3: Remove the four flag-gated nav items from `chrome.tsx`**

Delete the grammar/flashcards/L1/speak nav lines. If `useFlags` is then unused, remove that import and call. Keep `FlagsProvider` in `layout.tsx`.

- [ ] **Step 4: Re-run typecheck + shell E2E**

Run: `pnpm --filter @jplearn/web test && apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/shell.spec.ts`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/chrome.tsx apps/web/e2e/shell.spec.ts
git commit -m "fix(web): remove nav paths to forbidden features; flags stay server kill-switch (FR-NEG-002, FR-FLG-002, T-FLG-002)"
```

---

### Task 3: API — giới hạn tốc độ `/auth/login` (ghế Platform; BA cấp NFR id trước)

Thêm limiter in-process ở tầng `entrypoints/http` (không đụng domain/application), 10 lần / 60 giây theo `(client IP, email lower)`, trả `429` với body `HttpError` chuẩn ADR-005.

**Files:**
- Modify: `docs/sad/01-survey-srs/srs.md` — add `NFR-SEC-001`
- Modify: `docs/sad/03-design/traceability.md` — add row `NFR-SEC-001 | UC-L01 | login rate limit | T-SEC-001`
- Create: `apps/api-python/src/jplearn_api/entrypoints/http/rate_limit.py`
- Modify: `apps/api-python/src/jplearn_api/settings.py`
- Modify: `apps/api-python/src/jplearn_api/entrypoints/http/routers/auth.py`
- Modify: `apps/api-python/src/jplearn_api/entrypoints/http/app.py`
- Modify: `docs/sad/03-design/openapi.yaml` — add `429` for `/auth/login` and `NFR-SEC-001` in `x-jplearn-fr`
- Test: `apps/api-python/tests/test_auth_rate_limit.py`

**Interfaces:**
- Produces: `class LoginRateLimiter` with `check(key: str, now: float | None = None) -> bool` (True = allow) and `reset()`; dependency `enforce_login_rate_limit(body: LoginBody, request: Request) -> None` raises `HTTPException(429)`.
- Settings: `login_rate_limit_attempts: int = 10`, `login_rate_limit_window_seconds: int = 60`.
- App state: `app.state.login_rate_limiter`.

- [ ] **Step 0 (BA): Add NFR-SEC-001 to SRS and traceability, commit**

```bash
git add docs/sad/01-survey-srs/srs.md docs/sad/03-design/traceability.md
git commit -m "docs(ba): add NFR-SEC-001 login throttling"
```

- [ ] **Step 1: Write the failing tests**

Create `apps/api-python/tests/test_auth_rate_limit.py`:

```python
from fastapi.testclient import TestClient


def _attempt(client: TestClient, email: str) -> int:
    return client.post("/auth/login", json={"email": email, "password": "wrong-wrong"}).status_code


def test_login_is_throttled_after_limit(live_client: TestClient) -> None:
    email = "throttle-me@jplearn.local"
    codes = [_attempt(live_client, email) for _ in range(10)]
    assert set(codes) <= {400, 401}, codes
    assert _attempt(live_client, email) == 429


def test_throttle_is_scoped_per_email(live_client: TestClient) -> None:
    for _ in range(10):
        _attempt(live_client, "a@jplearn.local")
    assert _attempt(live_client, "a@jplearn.local") == 429
    assert _attempt(live_client, "b@jplearn.local") in (400, 401)


def test_throttle_window_expires(live_client: TestClient) -> None:
    limiter = live_client.app.state.login_rate_limiter
    for _ in range(10):
        _attempt(live_client, "c@jplearn.local")
    assert _attempt(live_client, "c@jplearn.local") == 429
    limiter.reset()
    assert _attempt(live_client, "c@jplearn.local") in (400, 401)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api-python && uv run pytest tests/test_auth_rate_limit.py -v`
Expected: FAIL — 401 instead of 429 / missing `login_rate_limiter`.

- [ ] **Step 3: Settings fields** as specified above.

- [ ] **Step 4: Implement `rate_limit.py`** with `LoginRateLimiter` (threading.Lock, deque sliding window, monotonic time) and `enforce_login_rate_limit`. Message: `"Too many login attempts; try again later"`.

- [ ] **Step 5: Wire into `create_app` and login route** with `dependencies=[Depends(enforce_login_rate_limit)]` and `responses` 429. Import `LoginRateLimiter` at top of `app.py`. Confirm `http_exception_handler` already maps 429 to `HttpError`.

- [ ] **Step 6: Update OpenAPI** `/auth/login` with `NFR-SEC-001` and 429 schema `$ref: '#/components/schemas/HttpError'`.

- [ ] **Step 7: Run tests + openapi diff**

```bash
cd apps/api-python && uv run pytest tests/test_auth_rate_limit.py tests/test_auth.py tests/test_architecture_guard.py tests/test_openapi_diff.py -v
PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff
```

Expected: all PASS; openapi_diff exit 0.

- [ ] **Step 8: Commit**

```bash
git add apps/api-python/src/jplearn_api/entrypoints/http/rate_limit.py apps/api-python/src/jplearn_api/entrypoints/http/routers/auth.py apps/api-python/src/jplearn_api/entrypoints/http/app.py apps/api-python/src/jplearn_api/settings.py apps/api-python/tests/test_auth_rate_limit.py docs/sad/03-design/openapi.yaml
git commit -m "feat(api): throttle /auth/login per ip+email with 429 (NFR-SEC-001, T-SEC-001)"
```

---

### Task 4: Lint/typecheck — ruff cho API, ESLint cho web (ghế Platform + Web)

**Files:**
- Modify: `apps/api-python/pyproject.toml`
- Create: `apps/web/eslint.config.mjs`
- Modify: `apps/web/package.json`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add ruff** to `[dependency-groups] dev` as `"ruff>=0.6"` and:

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

Run `cd apps/api-python && uv sync && uv run ruff check . --statistics`, then `uv run ruff check . --fix`. If `B008` (Depends() in defaults) is too noisy, `ignore = ["B008"]` with a one-line comment. Re-run ruff until clean; `uv run pytest -q` still green. If autofix touches many files, commit separately: `style(api): apply ruff autofixes`.

- [ ] **Step 2: Add ESLint to web**

```bash
pnpm --filter @jplearn/web add -D eslint@^9 eslint-config-next@^15
```

`apps/web/eslint.config.mjs`:

```js
import next from "eslint-config-next";

export default [
  ...next,
  { ignores: [".next/**", "test-results/**", "public/**"] },
];
```

Add script `"lint": "eslint src e2e"` and change `"test"` to `"tsc --noEmit && pnpm lint && pnpm test:unit"`. Fix lint errors to 0; warnings may remain if recorded in the report.

- [ ] **Step 3: CI** — in job `api-python`, before `uv run pytest`:

```yaml
      - run: uv run ruff check .
        working-directory: apps/api-python
```

- [ ] **Step 4: Commit**

```bash
git add apps/api-python/pyproject.toml apps/api-python/uv.lock apps/web/eslint.config.mjs apps/web/package.json pnpm-lock.yaml .github/workflows/ci.yml
git commit -m "chore(ci): add ruff for api and eslint for web to CI (NFR-MIG-001)"
```

---

### Task 5: CI — chạy Playwright E2E (ghế QA)

`web-e2e-python.sh` reads `media/stock/mp4/level-0-wash-hands.mp4` which is **not tracked**. Allow override via `JPLEARN_E2E_SOURCE_MP4`; CI generates a synthetic MP4 with ffmpeg. Chromium only in CI.

**Files:**
- Modify: `apps/api-python/differential/web-e2e-python.sh`
- Modify: `apps/api-python/differential/web_e2e_runner.py` if it filters env
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Override source MP4** so `SOURCE_MP4="${JPLEARN_E2E_SOURCE_MP4:-$REPO/media/stock/mp4/level-0-wash-hands.mp4}"` and exit 2 if missing. Pass `JPLEARN_E2E_SOURCE_MP4` through the Python supervisor if it filters env.

- [ ] **Step 2: Local smoke with synthetic MP4** (optional if ffmpeg present): generate `/tmp/e2e-synthetic.mp4` (20s testsrc+sine) and run shell.spec chromium.

- [ ] **Step 3: Add `web-e2e` job** to `.github/workflows/ci.yml`: ubuntu-latest, timeout 30, env `JWT_SECRET` (same as api-python job) and `JPLEARN_E2E_SOURCE_MP4: /tmp/e2e-synthetic.mp4`. Install pnpm/node 22, uv, ffmpeg, `pnpm install`, `uv sync --frozen` in api-python, `playwright install --with-deps chromium`, generate synthetic MP4, run `apps/api-python/differential/web-e2e-python.sh --project=chromium`, upload `apps/web/test-results` on failure.

- [ ] **Step 4: Commit**

```bash
git add apps/api-python/differential/web-e2e-python.sh apps/api-python/differential/web_e2e_runner.py .github/workflows/ci.yml
git commit -m "ci(qa): run Playwright chromium E2E with synthetic MP4 source (T-SES-REC-001, T-CMS-E2E-001, T-NFR-A1)"
```

Do not `git push` in this task (Task 8).

---

### Task 6: Guard chống textbook — quét đúng, đủ, ghi đúng (ghế CTO)

**Files:**
- Modify: `scripts/assert-no-textbook.ts`
- Modify: `README.md`
- Test: `scripts/__tests__/assert-no-textbook.test.ts`

- [ ] **Step 1: Export `BANNED_IDENTIFIERS`, `walk`, `findHits`, `run`.** Banned list: `vocabulary_score`, `grammar_lesson_id`, `textbook_percent`, `translation_vi`, `translation_en`, `flashcard_deck`, `srs_interval`. Scan roots: `apps`, `packages`, `scripts`, `docs/sad/03-design/openapi.yaml`. Skip dirs: `node_modules`, `.next`, `test`, `tests`, `__tests__`, `.venv`, `__pycache__`, `ios`, `android`. Extensions: `.ts|.tsx|.js|.mjs|.py|.pyi|.sql|.yaml|.yml|.json`. Case-insensitive via `text.toLowerCase()`. Skip the guard file itself when scanning `scripts/`. Keep CLI `process.exit(1)` when hits exist.

- [ ] **Step 2: Tests** in `scripts/__tests__/assert-no-textbook.test.ts` using `node:test`. Cover case-insensitive hit and clean file. Run `node --import tsx --test scripts/__tests__/assert-no-textbook.test.ts` then `pnpm test:guard`. If new hits appear, resolve with Pedagogy QA — rename or narrow the token; no file allowlist.

- [ ] **Step 3: README** — replace the “bảo vệ nghiêm ngặt bằng script tự động” sentence with three layers: (1) `pnpm test:guard`, (2) `tests/test_schema_ddl.py`, (3) `tests/test_architecture_guard.py` + E2E `shell.spec.ts`.

- [ ] **Step 4: Commit**

```bash
git add scripts/assert-no-textbook.ts scripts/__tests__/assert-no-textbook.test.ts README.md
git commit -m "fix(guard): case-insensitive scan incl. scripts/openapi, documented as one of three layers (FR-NEG-001, FR-NEG-002, FR-NEG-003, FR-NEG-004, T-NEG-004)"
```

---

### Task 7: Sửa tài liệu sai thực tế (ghế BA + CPO)

Backend ép `ci_level` 0–4 (`schemas.py`); taxonomy 0–4; `PRODUCT.md` says 0–5. README overclaims AI worker and design-tokens.

**Files:** `PRODUCT.md`, `README.md`

- [ ] **Step 1:** In `PRODUCT.md`, change CI range 0–5 to 0–4 (all occurrences). Level 4 description: "Cấp 4 (Extended — nhiều cảnh, đoạn ngắn; thư viện deferred)".
- [ ] **Step 2:** README AI worker: khung job/quota/lease đã có; provider hiện là **synthetic trial**. design-tokens: used by mobile; web uses CSS custom properties in `globals.css`. FFmpeg: **bắt buộc** cho upload CMS (ffprobe) và E2E.
- [ ] **Step 3:** `rg -n '0 ?– ?5|Cấp 5' PRODUCT.md README.md` → no matches.
- [ ] **Step 4: Commit** `docs(ba): align CI level range 0–4 and README claims with code (FR-CAT-001, FR-PRG-002)`

---

### Task 8: Mở PR ứng viên vào `main` (ghế CTO)

- [ ] Run: `pnpm test:guard && pnpm --filter @jplearn/domain test && pnpm --filter @jplearn/web test && pnpm --filter @jplearn/mobile test && pnpm test:api`. Record counts + SHA.
- [ ] `git push -u origin HEAD` then `gh pr create --base main --head codex/remediation-phase-1` listing FR ids, test results, and explicitly: **does not** change R-09 HOLD / Design PARTIAL / device PARTIAL.
- [ ] Do **not** merge.

---

## Self-review Plan 1

Coverage: port mobile (T1), nav cấm (T2), brute-force (T3), lint (T4), E2E CI (T5), guard+README (T6), thang 0–5 (T7), repo (T0, T8). Deferred: token localStorage, large files, dual StoragePort, playback capability flags, security scan, ADR-002, traceability Status column, staging, mobile parity, real content.
