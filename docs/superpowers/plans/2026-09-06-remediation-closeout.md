# Remediation Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal (historical closeout):** Đóng thật kế hoạch [2026-09-06-web-frontend-remediation.md](2026-09-06-web-frontend-remediation.md): bù các acceptance test còn thiếu (C2/C3/C4/C5), sửa một vi phạm thiết kế ở web session storage, đưa tài liệu trạng thái về đúng sự thật (C0), và tạo evidence có SHA/log (C6). Kết quả tại `fd838d2` không còn đủ để đóng C4 recovery; follow-up hiện hành đã mở lại C4 vì F-01–F-03.

**Architecture:** Backend giữ FastAPI + SQLAlchemy async + Alembic + PostgreSQL; race tests dùng `asyncio.Barrier` + `httpx.AsyncClient(ASGITransport)` + `asyncpg` để kiểm row trực tiếp (pattern đã có ở `tests/test_sessions_concurrency.py`). Web tách hai module thuần (`lib/session-storage.ts`, `lib/safe-redirect.ts`) để unit-test bằng `node --test`, và thêm `e2e/recovery.spec.ts` dùng `page.route()` với kỹ thuật **fetch-rồi-abort** để mô phỏng "server đã commit nhưng client mất response".

**Tech Stack:** Python 3.12, pytest-asyncio, httpx, asyncpg; Next.js 15, TypeScript 5.7, Playwright 1.49, axe-playwright; tsx 4.19 (node test loader).

## Global Constraints

- Không mở scope mới: không subscription, analytics theo ngày, MP3/audio upload, quiz, grammar, flashcard, bản dịch L1.
- Giữ invariant: end lần hai trả 400 và không cộng phút; phút tính theo server start→end; logout thu hồi token mọi thiết bị; teacher không publish; learner không thấy draft/`title_internal`/L1; client cũ không gửi `Idempotency-Key` vẫn hoạt động.
- Mọi test DB chạy trên Docker Compose project riêng qua `pg_harness` hoặc `/jplearn_test`; **không** reset DB dev, volume `jplearn_postgres_data` hay media dev.
- Wording bắt buộc: "axe không phát hiện vi phạm tự động trên các route/state đã quét" (không phải "đạt WCAG 2.2 AA"); "Chromium/WebKit" là browser engine, không phải thiết bị thật.
- Commit message dạng `type(scope): mô tả (FR-…, R-…)`; mỗi commit đóng một invariant có test.
- Test IDs trong traceability là mã truy vết; test thật phải mang ID đó trong docstring/tên test.
- Lệnh chạy từ repo root `/Users/quyendo/Documents/Learn/JPLearn` trừ khi ghi khác. Backend: `cd apps/api-python && uv run pytest …`.

---

## Bản đồ file

| File | Trách nhiệm | Task |
|---|---|---|
| `apps/api-python/tests/test_catalog_concurrency.py` | Thêm race PATCH×publish, PATCH×unpublish | 3 |
| `apps/api-python/tests/test_sessions_concurrency.py` | Thêm cross-user key, fault-injection, key quá dài | 4 |
| `apps/api-python/src/jplearn_api/entrypoints/http/routers/sessions.py` | Giới hạn độ dài `Idempotency-Key` | 4 |
| `docs/sad/03-design/openapi.yaml` | `maxLength` + mô tả thời gian lưu key | 4 |
| `apps/web/src/lib/session-storage.ts` (mới) | Record phiên theo user/tab, không chứa clip | 5 |
| `apps/web/src/lib/safe-redirect.ts` (mới) | `getSafeRedirect` | 5 |
| `apps/web/src/lib/*.test.ts` (mới) | Unit test node --test | 5 |
| `apps/web/src/app/session/page.tsx` | Dùng module mới, bỏ `clip` khỏi storage | 5 |
| `apps/web/src/app/login/page.tsx` | Import `getSafeRedirect` | 5 |
| `apps/web/src/lib/auth-storage.ts` | `logout()` xoá record phiên của user hiện tại | 5 |
| `apps/web/package.json` | script `test:unit`, devDep `tsx` | 5 |
| `apps/web/e2e/recovery.spec.ts` (mới) | 6 ca recovery T-SES-REC-001 | 6 |
| `apps/api-python/differential/grant_role.py` (mới) | Cấp role cho user E2E trong DB cô lập | 7 |
| `apps/api-python/differential/web-e2e-python.sh` | Tạo teacher E2E; kiểm container sót | 7, 9 |
| `apps/web/e2e/staff.spec.ts` | Teacher→admin handoff, reload, fail paths | 7 |
| `apps/web/src/app/staff/new/page.tsx`, `apps/web/src/app/staff/[id]/page.tsx` | Validation `.mp4` AND mime; option Audio disabled | 7 |
| `apps/web/e2e/auth.spec.ts` (mới) | T-AUTH-SEC-001, T-AUTH-ERR-001 | 7 |
| `apps/web/e2e/a11y.spec.ts` | Thêm state error/active/detail + keyboard | 8 |
| `docs/superpowers/plans/2026-09-06-web-frontend-remediation.md`, `walkthrough.md`, `docs/qa/remediation-evidence-2026-09-06.md`, `docs/sad/03-design/traceability.md` | Trạng thái đúng sự thật | 2, 10 |

---

### Task 1: Commit baseline đang dirty thành các commit theo invariant

**Owner:** Platform + Web. Không đổi code. Mục đích: có SHA để gắn evidence (C6) và diff review được.

**Files:** toàn bộ working tree hiện tại (53 file, base `00576eb`).

- [x] **Step 1: Xác nhận baseline xanh trước khi commit**

Run: `cd apps/api-python && uv run pytest -q -p no:cacheprovider 2>&1 | tail -2`
Expected: `212 passed, 2 warnings in ~30s`

Run: `pnpm test:guard && pnpm --filter @jplearn/web exec tsc --noEmit && echo OK`
Expected: `OK`

- [x] **Step 2: Commit migration + snapshot (R-04)**

```bash
git add apps/api-python/src/jplearn_api/migrations/versions/0002_session_idem_rev.py \
  apps/api-python/src/jplearn_api/resources/adr-004-schema-head-0002.json \
  docs/qa/adr-004-schema-head-0002.json \
  apps/api-python/src/jplearn_api/adapters/persistence/models.py \
  apps/api-python/src/jplearn_api/entrypoints/cli/migrate.py \
  apps/api-python/tests/test_schema_ddl.py \
  apps/api-python/tests/test_migrate_fail_closed.py \
  apps/api-python/tests/test_package_layout.py
git commit -m "feat(api): migration 0002 idempotency keys + catalog revision, separate head snapshot (NFR-MIG-001, R-04)"
```

- [x] **Step 3: Commit backend CAS + advisory lock (R-01, R-02)**

```bash
git add apps/api-python
git commit -m "feat(api): atomic draft CAS and advisory-locked session idempotency (FR-CAT-005, FR-SES-001, R-01, R-02)"
```

- [x] **Step 4: Commit web + SAD docs (R-03, R-05, R-06, R-07)**

```bash
git add apps/web docs/sad landing_preview.html
git commit -m "feat(web): learner shell, staff CMS, scoped session storage (FR-LRN-001, FR-CMS-002, R-03, R-05, R-06, R-07)"
```

- [x] **Step 5: Commit tài liệu kế hoạch/evidence tạm**

```bash
git add docs/superpowers docs/qa walkthrough.md
git commit -m "docs(qa): remediation plan and interim evidence (pending closeout)"
git status --short | wc -l
```
Expected: `0`

---

### Task 2: C0 — đưa tài liệu trạng thái về đúng sự thật

**Owner:** BA + QA. Không đổi runtime.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-06-web-frontend-remediation.md:3`
- Modify: `walkthrough.md`
- Modify: `docs/qa/remediation-evidence-2026-09-06.md`
- Modify: `docs/sad/03-design/traceability.md`

- [x] **Step 1: Đổi trạng thái kế hoạch remediation**

Thay dòng 3 của `2026-09-06-web-frontend-remediation.md`:

```markdown
Ngày: 2026-09-06. Trạng thái: **REMEDIATION IN PROGRESS** — code R-01…R-07 đã có (commit Task 1 của [closeout plan](2026-09-06-remediation-closeout.md)); acceptance C0/C4/C5/C6 và một phần C2/C3 chưa đủ. Chỉ đổi sang COMPLETED khi closeout plan xong Task 10.
```

Tick (`- [x]`) đúng các mục đã có bằng chứng: toàn bộ C1 (§4 — `test_stamp_adopts_a_database_built_before_alembic` kiểm đủ), 5 mục "Thiết kế" của C2 (§5), mục "Hai PATCH thật sự đồng thời", "Race PATCH với submit-QA", "Test stale tuần tự…" của C2, 4 mục "Thiết kế" đầu của C3 (§6, **không** tick mục "Giới hạn/validate độ dài Idempotency-Key"), 2 mục test đầu của C3 và mục "Request không có key giữ hành vi hiện hành". Mọi mục khác giữ `- [ ]`.

- [x] **Step 2: Sửa `walkthrough.md`**

Thay đoạn mở đầu (dòng 3):

```markdown
> **Trạng thái: REMEDIATION IN PROGRESS.** Kế hoạch [Mốc A/B](docs/superpowers/plans/2026-09-06-web-frontend-implementation.md) đã có code đầy đủ; kế hoạch [remediation](docs/superpowers/plans/2026-09-06-web-frontend-remediation.md) đang đóng theo [closeout plan](docs/superpowers/plans/2026-09-06-remediation-closeout.md). Số test dưới đây là **baseline hồi quy** tại commit Task 1, không phải nghiệm thu cuối.
```

Thay bullet "Khôi phục phiên học gián đoạn qua `localStorage`…" bằng:

```markdown
  - Khôi phục phiên học gián đoạn qua `sessionStorage` tách theo user và tab (`jplearn.session:<userId>`), state machine `starting → active → ending → outcome_unknown`, xác thực trạng thái máy chủ qua `GET /sessions/{id}`.
```

Thay bullet "Cập nhật baseline [docs/qa/adr-004-schema-baseline.json]…" bằng:

```markdown
  - Snapshot Prisma `0001` ([docs/qa/adr-004-schema-baseline.json](docs/qa/adr-004-schema-baseline.json), 10 bảng) **bất biến**; snapshot head `0002` tách riêng ([docs/qa/adr-004-schema-head-0002.json](docs/qa/adr-004-schema-head-0002.json), 11 bảng).
```

Mục 2.A: sửa "Không chứa bất kỳ từ khoá hoặc cột chrome bị cấm (`Ngữ pháp`, `Flashcard`, `Bản dịch`)" thành "Không chứa cột/field schema cấm (`vocabulary_score`, `grammar_lesson_id`, `textbook_percent`, `translation_vi`). Text chrome cấm (`Ngữ pháp`, `Flashcard`, `Bản dịch`) do `shell.spec.ts` kiểm, không phải guard."

Mục 2.C: `208 passed` → `212 passed`, thêm dòng `tests/test_catalog_concurrency.py: 2/2`, `tests/test_sessions_concurrency.py: 2/2`.

Mục 2.D/E: `5 passed` → `8 passed`, thêm `staff.spec.ts` (2 ca) và `a11y.spec.ts` staff. Sửa mô tả a11y thành: "axe không phát hiện vi phạm tự động (contrast, document-title, ARIA) trên 5 route learner và 2 route staff ở trạng thái mặc định. Không phải audit WCAG 2.2 AA toàn diện."

Mục 3: đổi tiêu đề thành "Hướng Dẫn Thao Tác Thủ Công (không phải evidence)".

- [x] **Step 3: Sửa evidence doc**

`docs/qa/remediation-evidence-2026-09-06.md`:
- Dòng `- **Status:** **VERIFIED & CLOSED**` → `- **Status:** **IN PROGRESS** — số liệu §2 là baseline tại commit Task 1; evidence đóng nằm ở §4 (điền tại Task 10).`
- Dòng "Axe WCAG 2.2 AA contrast verified across all routes." → "axe không phát hiện vi phạm tự động trên 7 route đã quét ở trạng thái mặc định."
- Xoá 2 bullet của QA Seat; thay bằng `- Chưa ký. Điều kiện: Task 10 closeout plan.`
- Cột Traceability của R-03: `T-SES-REC-001 (chưa có test — Task 6)`; R-06: `T-AUTH-ERR-001 (chưa có test — Task 7)`; R-07: `T-AUTH-SEC-001 (chưa có test — Task 7)`.

- [x] **Step 4: Khôi phục hàng P5 hold và thêm test ID mới vào traceability**

Trong `docs/sad/03-design/traceability.md`, ngay sau hàng `FR-LRN-001`, thêm lại:

```markdown
| FR-LRN-002…004 | UC-L11–12 | chưa | T-P5-hold |
```

Sửa hàng `FR-ID-001` cột Test: `T-ID-001 register+login, T-AUTH-ERR-001 login 400 hiển thị, T-AUTH-SEC-001 redirect an toàn`.

- [x] **Step 5: Commit**

```bash
git add docs walkthrough.md
git commit -m "docs(qa): reopen remediation status, restore FR-LRN hold row, fix a11y/guard wording (C0, R-06)"
```

---

### Task 3: C2 — race PATCH × publish và PATCH × unpublish

**Owner:** Platform; QA review. FR-CAT-005, UC-T05. Test ID: T-CAT-005-CAS.

**Files:**
- Modify: `apps/api-python/tests/test_catalog_concurrency.py` (append)

**Interfaces:**
- Consumes: fixture `client_factory` (yield `_make_client`), `_create_admin_token(client, postgres_url)` đã có trong file.
- Upload media thật qua `POST /staff/catalog/{id}/media` multipart để publish hợp lệ.

- [x] **Step 1: Thêm helper và 2 test đỏ**

Append vào cuối `test_catalog_concurrency.py`:

```python
from pathlib import Path

_STOCK_MP4 = Path(__file__).resolve().parents[3] / "media" / "stock" / "mp4" / "level-0-wash-hands.mp4"


async def _create_level_qa_item_with_media(client: AsyncClient, token: str) -> tuple[str, int]:
    """Create draft -> upload mp4 -> submit-qa. Returns (item_id, revision)."""
    if not _STOCK_MP4.exists():
        pytest.skip("stock mp4 missing (media/stock/mp4 is gitignored)")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/staff/catalog",
        headers=headers,
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 30,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "race-publish-item",
        },
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    upload = await client.post(
        f"/staff/catalog/{item_id}/media",
        headers=headers,
        files={"file": ("clip.mp4", _STOCK_MP4.read_bytes(), "video/mp4")},
    )
    assert upload.status_code == 201, upload.text
    qa = await client.post(f"/staff/catalog/{item_id}/submit-qa", headers=headers)
    assert qa.status_code == 200, qa.text
    return item_id, qa.json()["revision"]


@pytest.mark.asyncio
async def test_race_patch_vs_publish_never_writes_draft_back(client_factory, postgres_url: str):
    """T-CAT-005-CAS: PATCH racing publish on a level_qa item must never succeed; publish wins, revision only moves forward."""
    make_client = client_factory
    admin = await make_client()
    token = await _create_admin_token(admin, postgres_url)
    item_id, rev_qa = await _create_level_qa_item_with_media(admin, token)
    assert rev_qa == 2

    barrier = asyncio.Barrier(2)

    async def patch_worker():
        c = await make_client()
        await barrier.wait()
        return await c.patch(
            f"/staff/catalog/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"revision": rev_qa, "title_internal": "should-never-land"},
        )

    async def publish_worker():
        c = await make_client()
        await barrier.wait()
        return await c.post(f"/staff/catalog/{item_id}/publish", headers={"Authorization": f"Bearer {token}"})

    r_patch, r_pub = await asyncio.gather(patch_worker(), publish_worker())
    assert r_pub.status_code == 200, r_pub.text
    assert r_patch.status_code in (400, 409), r_patch.text

    final = (await admin.get(f"/staff/catalog/{item_id}", headers={"Authorization": f"Bearer {token}"})).json()
    assert final["status"] == "published"
    assert final["revision"] == 3
    assert final["title_internal"] == "race-publish-item"


@pytest.mark.asyncio
async def test_race_patch_vs_unpublish_revision_never_regresses(client_factory, postgres_url: str):
    """T-CAT-005-CAS: PATCH with the pre-unpublish revision must fail whether it runs before (wrong status) or after (stale) unpublish."""
    make_client = client_factory
    admin = await make_client()
    token = await _create_admin_token(admin, postgres_url)
    headers = {"Authorization": f"Bearer {token}"}
    item_id, _ = await _create_level_qa_item_with_media(admin, token)
    published = await admin.post(f"/staff/catalog/{item_id}/publish", headers=headers)
    assert published.status_code == 200
    rev_published = published.json()["revision"]
    assert rev_published == 3

    barrier = asyncio.Barrier(2)

    async def patch_worker():
        c = await make_client()
        await barrier.wait()
        return await c.patch(
            f"/staff/catalog/{item_id}",
            headers=headers,
            json={"revision": rev_published, "title_internal": "stale-after-unpublish"},
        )

    async def unpublish_worker():
        c = await make_client()
        await barrier.wait()
        return await c.post(f"/staff/catalog/{item_id}/unpublish", headers=headers)

    r_patch, r_unpub = await asyncio.gather(patch_worker(), unpublish_worker())
    assert r_unpub.status_code == 200, r_unpub.text
    assert r_patch.status_code in (400, 409), r_patch.text

    final = (await admin.get(f"/staff/catalog/{item_id}", headers=headers)).json()
    assert final["status"] == "draft"
    assert final["revision"] == 4
    assert final["title_internal"] == "race-publish-item"

    # A PATCH carrying the fresh revision must now succeed and bump to 5.
    ok = await admin.patch(
        f"/staff/catalog/{item_id}",
        headers=headers,
        json={"revision": 4, "title_internal": "edited-after-unpublish"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["revision"] == 5
```

- [x] **Step 2: Chạy, xác nhận trạng thái**

Run: `cd apps/api-python && uv run pytest tests/test_catalog_concurrency.py -v -p no:cacheprovider`
Expected: 4 passed. Nếu test mới FAIL, đó là lỗi thật của CAS/lock — sửa ở `catalog_repository.py`/`handlers/catalog.py`, không nới assertion. (Hai test này là **acceptance** còn thiếu, không phải red-green cho code mới; kỳ vọng xanh ngay vì `update_draft_cas` đã đúng.)

- [x] **Step 3: Commit**

```bash
git add apps/api-python/tests/test_catalog_concurrency.py
git commit -m "test(api): race PATCH vs publish/unpublish keeps state machine and revision monotonic (FR-CAT-005, T-CAT-005-CAS)"
```

---

### Task 4: C3 — cross-user key, fault injection, giới hạn độ dài Idempotency-Key

**Owner:** Platform; QA review. FR-SES-001/003, FR-EVT-001/003. Test ID: T-SES-003-IDEM-CONCUR.

**Files:**
- Modify: `apps/api-python/tests/test_sessions_concurrency.py` (append)
- Modify: `apps/api-python/src/jplearn_api/entrypoints/http/routers/sessions.py:42-56`
- Modify: `docs/sad/03-design/openapi.yaml:491-494`

**Interfaces:**
- Consumes: `SqlAlchemyLearningRepository.save_idempotency(self, user_id, key, session_id, request_hash)` tại `adapters/persistence/learning_repository.py:97`; fixture `client_factory`, `_create_learner_token(client) -> (user_id, token)`.
- Produces: hằng `IDEMPOTENCY_KEY_MAX_LENGTH = 128` trong `routers/sessions.py`.

- [x] **Step 1: Test cross-user và fault-injection (kỳ vọng xanh) + test độ dài key (kỳ vọng đỏ)**

Trước hết sửa fixture `client_factory` trong `test_sessions_concurrency.py` để cho phép tắt raise:

```python
            async def _make_client(*, raise_app_exceptions: bool = True):
                transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
                return AsyncClient(transport=transport, base_url="http://test")
```

Rồi append vào cuối file:

```python
async def _count_rows(postgres_url: str, user_id: str) -> tuple[int, int, int]:
    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        sessions = await conn.fetchval("SELECT COUNT(*) FROM learning_sessions WHERE user_id = $1", user_id)
        keys = await conn.fetchval("SELECT COUNT(*) FROM session_idempotency_keys WHERE user_id = $1", user_id)
        events = await conn.fetchval("SELECT COUNT(*) FROM learning_events WHERE user_id = $1", user_id)
        return sessions, keys, events
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_same_key_two_users_creates_two_isolated_sessions(client_factory, postgres_url: str):
    """T-SES-003-IDEM-CONCUR: idempotency scope is (user_id, key); the same key across users must not leak sessions."""
    make_client = client_factory
    c = await make_client()
    user_a, token_a = await _create_learner_token(c)
    user_b, token_b = await _create_learner_token(c)
    key = f"shared-{uuid4()}"
    barrier = asyncio.Barrier(2)

    async def worker(token: str):
        cc = await make_client()
        await barrier.wait()
        return await cc.post(
            "/sessions",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
            json={"device_class": "web"},
        )

    ra, rb = await asyncio.gather(worker(token_a), worker(token_b))
    assert ra.status_code == 201 and rb.status_code == 201
    assert ra.json()["id"] != rb.json()["id"]

    # Owner check: A must not read B's session and vice versa.
    cross = await c.get(f"/sessions/{rb.json()['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert cross.status_code == 403

    assert await _count_rows(postgres_url, user_a) == (1, 1, 2)
    assert await _count_rows(postgres_url, user_b) == (1, 1, 2)


@pytest.mark.asyncio
async def test_failure_before_commit_leaves_no_orphan_key_and_retry_creates_one_session(
    client_factory, postgres_url: str, monkeypatch: pytest.MonkeyPatch
):
    """T-SES-003-IDEM-CONCUR: if the transaction fails after session/events were staged, nothing persists; retry with the same key creates exactly one session."""
    from jplearn_api.adapters.persistence.learning_repository import SqlAlchemyLearningRepository

    make_client = client_factory
    c = await make_client()
    user_id, token = await _create_learner_token(c)
    key = f"fault-{uuid4()}"

    original = SqlAlchemyLearningRepository.save_idempotency
    calls = {"n": 0}

    async def failing_once(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected failure before commit")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SqlAlchemyLearningRepository, "save_idempotency", failing_once)

    # raise_app_exceptions=False so the injected error surfaces as HTTP 500 instead of propagating into the test.
    faulty = await make_client(raise_app_exceptions=False)

    first = await faulty.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json={"device_class": "web"},
    )
    assert first.status_code == 500
    assert await _count_rows(postgres_url, user_id) == (0, 0, 0), "rollback must leave no session/key/event"

    retry = await c.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        json={"device_class": "web"},
    )
    assert retry.status_code == 201, retry.text
    assert await _count_rows(postgres_url, user_id) == (1, 1, 2)


@pytest.mark.asyncio
async def test_idempotency_key_longer_than_128_is_400(client_factory):
    """T-SES-003-IDEM-CONCUR: header length is bounded so the (user_id,key) PK stays cheap to hash and index."""
    make_client = client_factory
    c = await make_client()
    _, token = await _create_learner_token(c)
    res = await c.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k" * 129},
        json={"device_class": "web"},
    )
    assert res.status_code == 400
    assert "Idempotency-Key" in res.json()["detail"]

    ok = await c.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k" * 128},
        json={"device_class": "web"},
    )
    assert ok.status_code == 201
```

- [x] **Step 2: Chạy, xác nhận 2 xanh 1 đỏ**

Run: `cd apps/api-python && uv run pytest tests/test_sessions_concurrency.py -v -p no:cacheprovider`
Expected: `test_same_key_two_users…` PASS, `test_failure_before_commit…` PASS, `test_idempotency_key_longer_than_128_is_400` FAIL (`assert 201 == 400`).

Nếu `test_failure_before_commit…` FAIL với rows ≠ (0,0,0): UoW không rollback khi handler ném lỗi — kiểm `SqlAlchemyUnitOfWork.__aexit__` tại `adapters/persistence/unit_of_work.py:36`; đây là bug thật, sửa ở đó.

- [x] **Step 3: Thêm giới hạn độ dài trong router**

Trong `routers/sessions.py`, sau `DEVICE_CLASSES = (...)` thêm:

```python
IDEMPOTENCY_KEY_MAX_LENGTH = 128
```

Trong `start_session`, ngay sau kiểm `device_class`:

```python
    if idempotency_key is not None and len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Idempotency-Key must be at most {IDEMPOTENCY_KEY_MAX_LENGTH} characters",
        )
```

- [x] **Step 4: Cập nhật OpenAPI**

Trong `docs/sad/03-design/openapi.yaml` thay block header param:

```yaml
        - in: header
          name: Idempotency-Key
          required: false
          description: >-
            Optional. Max 128 chars. Scoped per (user, key). Same key + same body replays the stored
            session (201); same key + different body returns 409. Keys are retained for the lifetime of
            the session row (ON DELETE CASCADE); no TTL sweep in Q1.
          schema: { type: string, nullable: true, maxLength: 128 }
```

- [x] **Step 5: Chạy lại focused + contract**

Run: `cd apps/api-python && uv run pytest tests/test_sessions_concurrency.py tests/test_sessions.py tests/test_openapi_diff.py tests/test_openapi_mutation_suite.py tests/test_contract.py -q -p no:cacheprovider`
Expected: all passed. Nếu `test_openapi_diff` báo lệch vì `maxLength`/`description` không có trong schema FastAPI sinh ra: thêm `max_length=128` và `description=` vào `Header(...)` trong router để hai phía khớp, rồi chạy lại.

- [x] **Step 6: Commit**

```bash
git add apps/api-python/tests/test_sessions_concurrency.py apps/api-python/src/jplearn_api/entrypoints/http/routers/sessions.py docs/sad/03-design/openapi.yaml
git commit -m "test(api)+feat(api): idempotency cross-user isolation, pre-commit fault rollback, key max length 128 (FR-SES-001, T-SES-003-IDEM-CONCUR)"
```

---

### Task 5: C4 — tách session-storage / safe-redirect thành module thuần có unit test; bỏ clip khỏi storage

**Owner:** Web. FR-LRN-001, S-SESSION. Test ID: T-SES-REC-001 (unit phần), T-AUTH-SEC-001 (unit phần).

**Files:**
- Create: `apps/web/src/lib/session-storage.ts`
- Create: `apps/web/src/lib/session-storage.test.ts`
- Create: `apps/web/src/lib/safe-redirect.ts`
- Create: `apps/web/src/lib/safe-redirect.test.ts`
- Modify: `apps/web/package.json` (scripts + devDep)
- Modify: `apps/web/src/app/session/page.tsx`
- Modify: `apps/web/src/app/login/page.tsx:8-19`
- Modify: `apps/web/src/lib/auth-storage.ts:55-91`

**Interfaces (Produces):**

```ts
// lib/session-storage.ts
export type SessionLifecycleState = "starting" | "active" | "ending" | "outcome_unknown";
export interface StoredSession {
  v: 1;
  state: SessionLifecycleState;
  idempotencyKey: string;
  deviceClass: "web";
  startedAt: string;        // ISO
  itemId?: string;
  sessionId?: string;
}
export function sessionStorageKey(userId: string): string;             // `jplearn.session:${userId}`
export function readSessionRecord(userId: string): StoredSession | null;
export function writeSessionRecord(userId: string, rec: StoredSession): void;
export function clearSessionRecord(userId: string): void;
export function newIdempotencyKey(): string;
// lib/safe-redirect.ts
export function getSafeRedirect(target: string | null | undefined): string;
```

- [x] **Step 1: Thêm test runner unit cho web**

`apps/web/package.json`:

```json
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "test": "tsc --noEmit && pnpm test:unit",
    "test:unit": "node --import tsx --test \"src/lib/**/*.test.ts\"",
    "test:e2e": "playwright test"
  },
```

Thêm vào `devDependencies`: `"tsx": "^4.19.2"`, `"@types/node": "^22.10.0"` (cần cho `node:test`/`node:assert` khi `tsc --noEmit` quét `src/lib/*.test.ts`). Run: `pnpm install --filter @jplearn/web` → Expected: lockfile cập nhật, không lỗi.

- [x] **Step 2: Viết test đỏ cho safe-redirect**

`apps/web/src/lib/safe-redirect.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { getSafeRedirect } from "./safe-redirect";

test("T-AUTH-SEC-001: accepts only internal paths with exactly one leading slash", () => {
  assert.equal(getSafeRedirect("/progress"), "/progress");
  assert.equal(getSafeRedirect("/session?item_id=abc"), "/session?item_id=abc");
  assert.equal(getSafeRedirect("/staff/123"), "/staff/123");
});

test("T-AUTH-SEC-001: rejects protocol-relative, backslash, scheme and empty targets", () => {
  for (const bad of [null, undefined, "", "//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)", "progress", "/%2F%2Fevil"]) {
    assert.equal(getSafeRedirect(bad), "/", `expected "/" for ${String(bad)}`);
  }
});
```

Run: `pnpm --filter @jplearn/web test:unit`
Expected: FAIL — `Cannot find module './safe-redirect'`.

- [x] **Step 3: Implement safe-redirect**

`apps/web/src/lib/safe-redirect.ts`:

```ts
/** R-07 / T-AUTH-SEC-001: only same-origin absolute paths are allowed as post-login targets. */
export function getSafeRedirect(target: string | null | undefined): string {
  if (!target) return "/";
  if (!target.startsWith("/")) return "/";
  if (target.startsWith("//") || target.startsWith("/\\")) return "/";
  if (target.includes("://") || target.includes("\\")) return "/";
  let decoded: string;
  try {
    decoded = decodeURIComponent(target);
  } catch {
    return "/";
  }
  if (decoded.startsWith("//") || decoded.startsWith("/\\") || decoded.includes("://")) return "/";
  return target;
}
```

Run: `pnpm --filter @jplearn/web test:unit` → Expected: 2 passed.

- [x] **Step 4: Viết test đỏ cho session-storage**

`apps/web/src/lib/session-storage.test.ts`:

```ts
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
// Static import is safe: session-storage.ts only touches window/sessionStorage lazily inside store().
import {
  sessionStorageKey,
  readSessionRecord,
  writeSessionRecord,
  clearSessionRecord,
  newIdempotencyKey,
  type StoredSession,
} from "./session-storage";

// Minimal Storage shim for node --test (sessionStorage is per-tab in browsers).
class MemoryStorage {
  private m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
}
(globalThis as unknown as { window: unknown }).window = globalThis;
(globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage = new MemoryStorage();

beforeEach(() => (globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage.clear());

const rec = (over: Partial<StoredSession> = {}): StoredSession => ({
  v: 1, state: "starting", idempotencyKey: "k1", deviceClass: "web", startedAt: "2026-09-06T00:00:00.000Z", ...over,
});

test("T-SES-REC-001: key is scoped per user", () => {
  assert.equal(sessionStorageKey("u1"), "jplearn.session:u1");
  writeSessionRecord("u1", rec());
  assert.equal(readSessionRecord("u2"), null);
  assert.deepEqual(readSessionRecord("u1"), rec());
});

test("T-SES-REC-001: clear only touches the given user", () => {
  writeSessionRecord("u1", rec({ idempotencyKey: "a" }));
  writeSessionRecord("u2", rec({ idempotencyKey: "b" }));
  clearSessionRecord("u1");
  assert.equal(readSessionRecord("u1"), null);
  assert.equal(readSessionRecord("u2")?.idempotencyKey, "b");
});

test("T-SES-REC-001: corrupt or foreign-shaped records are dropped, never returned", () => {
  sessionStorage.setItem("jplearn.session:u1", "{not json");
  assert.equal(readSessionRecord("u1"), null);
  assert.equal(sessionStorage.getItem("jplearn.session:u1"), null);
  sessionStorage.setItem("jplearn.session:u1", JSON.stringify({ state: "active", clip: { hls_url: "x" } }));
  assert.equal(readSessionRecord("u1"), null, "records without v:1 or with clip payload are rejected");
});

test("T-SES-REC-001: writer refuses payloads carrying catalog/media URLs", () => {
  assert.throws(() => writeSessionRecord("u1", { ...rec(), clip: { hls_url: "signed" } } as unknown as StoredSession));
});

test("newIdempotencyKey returns distinct, header-safe values ≤128 chars", () => {
  const a = newIdempotencyKey(); const b = newIdempotencyKey();
  assert.notEqual(a, b);
  assert.match(a, /^[A-Za-z0-9-]{8,128}$/);
});
```

Run: `pnpm --filter @jplearn/web test:unit` → Expected: FAIL `Cannot find module './session-storage'`.

- [x] **Step 5: Implement session-storage**

`apps/web/src/lib/session-storage.ts`:

```ts
/**
 * Per-user, per-tab learning-session record (R-03 / T-SES-REC-001).
 * Stored in sessionStorage so tabs never overwrite each other. Never stores catalog objects
 * or signed playback/HLS URLs — recovery always refetches the catalog.
 */
export type SessionLifecycleState = "starting" | "active" | "ending" | "outcome_unknown";

export interface StoredSession {
  v: 1;
  state: SessionLifecycleState;
  idempotencyKey: string;
  deviceClass: "web";
  startedAt: string;
  itemId?: string;
  sessionId?: string;
}

const PREFIX = "jplearn.session:";
const STATES: readonly SessionLifecycleState[] = ["starting", "active", "ending", "outcome_unknown"];
const ALLOWED_KEYS = new Set(["v", "state", "idempotencyKey", "deviceClass", "startedAt", "itemId", "sessionId"]);

export function sessionStorageKey(userId: string): string {
  return `${PREFIX}${userId}`;
}

function store(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function isValid(x: unknown): x is StoredSession {
  if (!x || typeof x !== "object") return false;
  const r = x as Record<string, unknown>;
  if (r.v !== 1) return false;
  if (!STATES.includes(r.state as SessionLifecycleState)) return false;
  if (typeof r.idempotencyKey !== "string" || typeof r.startedAt !== "string") return false;
  if (r.deviceClass !== "web") return false;
  for (const k of Object.keys(r)) if (!ALLOWED_KEYS.has(k)) return false;
  return true;
}

export function readSessionRecord(userId: string): StoredSession | null {
  const s = store();
  if (!s) return null;
  const key = sessionStorageKey(userId);
  const raw = s.getItem(key);
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isValid(parsed)) return parsed;
  } catch {
    /* fallthrough */
  }
  s.removeItem(key);
  return null;
}

export function writeSessionRecord(userId: string, rec: StoredSession): void {
  if (!isValid(rec)) throw new Error("StoredSession must not carry catalog/media payload");
  store()?.setItem(sessionStorageKey(userId), JSON.stringify(rec));
}

export function clearSessionRecord(userId: string): void {
  store()?.removeItem(sessionStorageKey(userId));
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
```

Run: `pnpm --filter @jplearn/web test:unit` → Expected: 7 passed (2 + 5).

- [x] **Step 6: Nối `login/page.tsx` với module mới**

Xoá hàm `getSafeRedirect` cục bộ (dòng 8–19) và thêm import:

```ts
import { getSafeRedirect } from "../../lib/safe-redirect";
```

- [x] **Step 7: `logout()` xoá record phiên của user hiện tại**

Trong `auth-storage.ts`, thêm import đầu file:

```ts
import { clearSessionRecord } from "./session-storage";
```

Trong `logout()`, ngay trước `clearSession();` thêm:

```ts
  const current = getUser();
  if (current?.id) clearSessionRecord(current.id);
```

(Policy: logout là hành động chủ đích của user → record phiên UI của user đó bị bỏ; server vẫn giữ session active và owner-check là nguồn quyền. Ghi policy này vào `docs/sad/03-design/ui-shell.md` hàng S-SESSION: "logout xoá record phiên UI của user hiện tại; không end session trên server".)

- [x] **Step 8: Viết lại phần storage trong `session/page.tsx`**

Thay các định nghĩa `SessionLifecycleState`, `StoredSession`, `getStorageKey` (dòng 11–43) bằng:

```ts
import {
  clearSessionRecord,
  newIdempotencyKey,
  readSessionRecord,
  writeSessionRecord,
  type StoredSession,
} from "../../lib/session-storage";

function currentUserId(): string | null {
  return getUser()?.id ?? null;
}
```

Thay toàn bộ `loadClip` bằng bản không ghi storage:

```ts
  const loadClip = useCallback(async (targetItemId?: string | null) => {
    const token = getToken();
    if (!token) return;
    let playable: CatalogItemPublic | null = null;
    try {
      const catRes = await api("/catalog", { token });
      if (catRes.ok) {
        const catalog = await parseApiResponse<{ items: CatalogItemPublic[] }>(catRes);
        const items = catalog?.items || [];
        if (targetItemId) playable = items.find((i) => i.id === targetItemId) || null;
        if (!playable && items.length > 0) playable = items.find((i) => i.hls_url ?? i.playback_url) || items[0];
      }
    } catch {
      /* catalog failure must not block end-session */
    }
    setClip(playable);
    setStatus(playable ? "Phiên đang chạy." : "Phiên đang chạy. Chưa có clip published.");
  }, []);
```

Thay toàn bộ `checkActiveSession` bằng:

```ts
  const checkActiveSession = useCallback(async () => {
    const token = getToken();
    const userId = currentUserId();
    if (!token || !userId) return;
    try { localStorage.removeItem("jplearn_active_session"); } catch {}

    const stored = readSessionRecord(userId);
    if (!stored) return;

    // 1. Mid-flight start: replay POST with the same key.
    if (stored.state === "starting") {
      setStatus("Đang khôi phục phiên...");
      setLoading(true);
      try {
        const res = await api("/sessions", {
          method: "POST",
          token,
          headers: { "Idempotency-Key": stored.idempotencyKey },
          body: JSON.stringify({ device_class: stored.deviceClass }),
        });
        if (res.ok) {
          const body = await parseApiResponse<{ id: string; started_at?: string }>(res);
          if (body?.id) {
            const active: StoredSession = { ...stored, state: "active", sessionId: body.id, startedAt: body.started_at || stored.startedAt };
            writeSessionRecord(userId, active);
            setSessionId(body.id);
            setStartedAt(new Date(active.startedAt));
            await loadClip(stored.itemId);
            setStatus("Phiên đang chạy (đã khôi phục).");
            return;
          }
        }
        clearSessionRecord(userId);
        setStatus("Không thể khôi phục phiên.");
      } catch {
        setStatus("Lỗi kết nối khi khôi phục phiên. Tải lại trang để thử lại.");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!stored.sessionId) { clearSessionRecord(userId); return; }

    // 2. active / ending / outcome_unknown: ask the server what really happened.
    try {
      const res = await api(`/sessions/${stored.sessionId}`, { token });
      if (res.status === 404 || res.status === 403) { clearSessionRecord(userId); return; }
      if (!res.ok) throw new Error("status check failed");
      const data = await parseApiResponse<{ started_at?: string; ended_at?: string | null; duration_seconds?: number }>(res);

      if (data?.ended_at) {
        clearSessionRecord(userId);
        if (stored.state === "ending" || stored.state === "outcome_unknown") {
          const progressRes = await api("/progress", { token });
          const progress = progressRes.ok
            ? await parseApiResponse<{ minutes_comprehensible: number; current_ci_level: number }>(progressRes)
            : null;
          setCompletedSummary({
            minutesComprehensible: progress?.minutes_comprehensible ?? 0,
            currentCiLevel: progress?.current_ci_level ?? 0,
            durationSeconds: data.duration_seconds ?? 0,
          });
          setStatus("Phiên đã kết thúc.");
        }
        return;
      }

      // Still active on the server.
      const start = new Date(data?.started_at || stored.startedAt);
      setSessionId(stored.sessionId);
      setStartedAt(start);
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000)));
      writeSessionRecord(userId, { ...stored, state: "active" });
      setStatus(stored.state === "active" ? "Phiên đang chạy." : "Phiên vẫn đang chạy trên máy chủ — hãy kết thúc lại.");
      await loadClip(stored.itemId);
    } catch {
      if (stored.state !== "active") {
        writeSessionRecord(userId, { ...stored, state: "outcome_unknown" });
        setStatus("Chưa xác nhận được trạng thái phiên với máy chủ. Tải lại trang khi có mạng.");
      } else {
        setStatus("Không kiểm tra được phiên với máy chủ.");
      }
    }
  }, [loadClip]);
```

Trong `startSession`: thay `const storageKey = getStorageKey();` bằng `const userId = currentUserId(); if (!userId) { setStatus("Hãy đăng nhập."); return; }`; thay sinh key bằng `const idempotencyKey = pendingIdempotencyKeyRef.current || newIdempotencyKey();`; thay mọi `sessionStorage.setItem(storageKey, JSON.stringify(x))` bằng `writeSessionRecord(userId, x)` với `x` có thêm `v: 1` và `deviceClass: "web"` (bỏ field `clip`); thay mọi `sessionStorage.removeItem(storageKey)` bằng `clearSessionRecord(userId)`; gọi `await loadClip(requestedItemId);` (bỏ tham số record).

Trong `endSession`: tương tự — đọc `const rec = readSessionRecord(userId)`; `if (rec) writeSessionRecord(userId, { ...rec, state: "ending" })`; ở nhánh lỗi `writeSessionRecord(userId, { ...rec, state: "outcome_unknown" })`; khi xác nhận ended `clearSessionRecord(userId)`.

- [x] **Step 9: Kiểm compile + lint kiểu**

Run: `pnpm --filter @jplearn/web test` → Expected: `tsc` 0 lỗi, unit 7 passed.
Run: `rg -n "sessionStorage\.|clip\?:|activeRecord\.clip" apps/web/src/app/session/page.tsx` → Expected: không có kết quả.

- [x] **Step 10: Cập nhật ui-shell policy + commit**

Trong `docs/sad/03-design/ui-shell.md` hàng `S-SESSION`, cột Ghi chú thêm: "record `sessionStorage` theo user/tab, không lưu clip/signed URL; logout xoá record UI của user hiện tại, không end server session."

```bash
git add apps/web/package.json pnpm-lock.yaml apps/web/src/lib apps/web/src/app/session/page.tsx apps/web/src/app/login/page.tsx docs/sad/03-design/ui-shell.md
git commit -m "refactor(web): pure session-storage/safe-redirect modules with unit tests; never persist clip URLs (FR-LRN-001, R-03, R-07, T-SES-REC-001, T-AUTH-SEC-001)"
```

---

### Task 6: C4 — Playwright `recovery.spec.ts` (6 ca T-SES-REC-001)

**Owner:** QA + Web. Chạy qua `./apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/recovery.spec.ts`.

**Files:**
- Create: `apps/web/e2e/recovery.spec.ts`

**Interfaces (Consumes):** token trong `localStorage["jplearn.access_token"]`, user trong `localStorage["jplearn.user"]` (`{id,email,roles}`); record ở `sessionStorage["jplearn.session:<id>"]`; API base = `NEXT_PUBLIC_API_URL` lúc build (đọc từ request URL bị intercept). Seed item published trong E2E: `00000000-0000-4000-8000-0000000000c1`.

Kỹ thuật cốt lõi — "server commit, client mất response":

```ts
await page.route(/\/sessions$/, async (route) => {
  if (route.request().method() !== "POST") return route.continue();
  const resp = await route.fetch();          // server thực sự xử lý & commit
  committedIds.push((await resp.json()).id);
  await route.abort("failed");               // client không nhận được
});
```

- [x] **Step 1: Viết spec**

`apps/web/e2e/recovery.spec.ts`:

```ts
import { test, expect, type Page, type BrowserContext } from "@playwright/test";

const SEED_PUBLISHED_ITEM = "00000000-0000-4000-8000-0000000000c1";

async function register(page: Page): Promise<{ email: string; userId: string; token: string }> {
  await page.goto("/login");
  const email = `rec${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
  const { userId, token } = await page.evaluate(() => ({
    userId: JSON.parse(localStorage.getItem("jplearn.user") || "{}").id as string,
    token: localStorage.getItem("jplearn.access_token") as string,
  }));
  return { email, userId, token };
}

async function readRecord(page: Page, userId: string) {
  return page.evaluate((k) => {
    const raw = sessionStorage.getItem(k);
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  }, `jplearn.session:${userId}`);
}

test.describe("Session recovery T-SES-REC-001", () => {
  test("start response lost after commit → reload replays same key → one session", async ({ page }) => {
    const { userId } = await register(page);
    const committed: string[] = [];
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      const resp = await route.fetch();
      committed.push((await resp.json()).id);
      await route.abort("failed");
    });
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Lỗi kết nối máy chủ khi bắt đầu phiên.")).toBeVisible();
    const starting = await readRecord(page, userId);
    expect(starting?.state).toBe("starting");
    expect(committed).toHaveLength(1);

    await page.unroute(/\/sessions$/);
    await page.reload();
    await expect(page.getByText("Phiên đang chạy (đã khôi phục).")).toBeVisible();
    const active = await readRecord(page, userId);
    expect(active?.state).toBe("active");
    expect(active?.sessionId).toBe(committed[0]);
    expect(active?.idempotencyKey).toBe(starting?.idempotencyKey);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
  });

  test("started → reload → route away and back → session still active, end works once", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const before = await readRecord(page, userId);

    await page.reload();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    await page.goto("/progress");
    await page.goto("/session");
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
    const after = await readRecord(page, userId);
    expect(after?.sessionId).toBe(before?.sessionId);

    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
    expect(await readRecord(page, userId)).toBeNull();
  });

  test("end response lost after commit → GET confirms ended → summary shown, no second end", async ({ page, request }) => {
    const { userId, token } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const rec = await readRecord(page, userId);
    const sessionId = rec?.sessionId as string;

    let endUrl = "";
    await page.route(/\/sessions\/[^/]+\/end$/, async (route) => {
      endUrl = route.request().url();
      await route.fetch();           // server ends the session
      await route.abort("failed");   // client never sees it
    });
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Đã kết thúc phiên.")).toBeVisible();
    expect(await readRecord(page, userId)).toBeNull();

    // Server: a second end is a 400 and progress is unchanged.
    const again = await request.post(endUrl, { headers: { Authorization: `Bearer ${token}` } });
    expect(again.status()).toBe(400);
    const got = await request.get(endUrl.replace(/\/end$/, ""), { headers: { Authorization: `Bearer ${token}` } });
    expect((await got.json()).id).toBe(sessionId);
    expect((await got.json()).ended_at).not.toBeNull();
  });

  test("end and status check both offline → not reported ended, record kept for retry", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();

    await page.route(/\/sessions\/[^/]+(\/end)?$/, (route) => route.abort("failed"));
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Lỗi kết nối khi kết thúc phiên.")).toBeVisible();
    await expect(page.getByText("Tổng kết phiên học")).toHaveCount(0);
    const rec = await readRecord(page, userId);
    expect(rec?.state).toBe("outcome_unknown");
    expect(rec?.sessionId).toBeTruthy();

    await page.unroute(/\/sessions\/[^/]+(\/end)?$/);
    await page.reload();
    // Server never received the end (we aborted before send) → still active → user can end again.
    await expect(page.getByText(/đang chạy/)).toBeVisible();
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
  });

  test("two tabs same user keep independent records; switching user hides previous record", async ({ browser }) => {
    const ctx: BrowserContext = await browser.newContext();
    const tabA = await ctx.newPage();
    const { userId: u1 } = await register(tabA);
    await tabA.goto("/session");
    await tabA.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(tabA.getByText(/Phiên đang chạy/)).toBeVisible();
    const recA = await readRecord(tabA, u1);

    const tabB = await ctx.newPage();
    await tabB.goto("/session");
    expect(await readRecord(tabB, u1)).toBeNull(); // sessionStorage is per tab
    await expect(tabB.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
    await tabB.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(tabB.getByText(/Phiên đang chạy/)).toBeVisible();
    const recB = await readRecord(tabB, u1);
    expect(recB?.sessionId).not.toBe(recA?.sessionId);
    expect((await readRecord(tabA, u1))?.sessionId).toBe(recA?.sessionId);

    // Switch user in tab A: logout clears u1's UI record; u2 starts clean.
    await tabA.goto("/login");
    await tabA.getByRole("button", { name: "Đăng xuất" }).click();
    expect(await readRecord(tabA, u1)).toBeNull();
    const { userId: u2 } = await register(tabA);
    await tabA.goto("/session");
    expect(await readRecord(tabA, u2)).toBeNull();
    await expect(tabA.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
    await expect(tabA.getByText(/đã khôi phục/)).toHaveCount(0);
    await ctx.close();
  });

  test("recovery refetches catalog; record never contains media URLs", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.locator("video")).toBeVisible();
    const raw = await page.evaluate((k) => sessionStorage.getItem(k), `jplearn.session:${userId}`);
    expect(raw).not.toContain("hls_url");
    expect(raw).not.toContain("playback_url");
    expect(raw).not.toContain("sig=");

    const catalogRefetch = page.waitForRequest((r) => r.url().endsWith("/catalog") && r.method() === "GET");
    await page.reload();
    await catalogRefetch;
    await expect(page.locator("video")).toBeVisible();
  });
});
```

- [x] **Step 2: Chạy chromium chỉ spec này**

Run: `./apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/recovery.spec.ts`
Expected: `6 passed`. Nếu ca 1 fail vì `route.fetch()` không được gọi do preflight CORS (OPTIONS): Playwright route chỉ intercept request chính; nếu thấy request `OPTIONS` bị abort, thêm `if (route.request().method() === "OPTIONS") return route.continue();` đầu handler.

- [x] **Step 3: Chạy webkit**

Run: `./apps/api-python/differential/web-e2e-python.sh --project=webkit e2e/recovery.spec.ts`
Expected: `6 passed`.

- [x] **Step 4: Commit**

```bash
git add apps/web/e2e/recovery.spec.ts
git commit -m "test(web): session recovery E2E — lost start/end responses, offline, multi-tab, user switch, no stored URLs (FR-LRN-001, T-SES-REC-001)"
```

---

### Task 7: C5 — CMS teacher→admin handoff, fail paths, validation, auth E2E

**Owner:** Web + QA; BA xác nhận quyết định Audio.

**Files:**
- Create: `apps/api-python/differential/grant_role.py`
- Modify: `apps/api-python/differential/web-e2e-python.sh:104-127`
- Modify: `apps/web/src/app/staff/new/page.tsx:104,253-258,287-291`
- Modify: `apps/web/src/app/staff/[id]/page.tsx:181,568-573,629-633`
- Modify: `apps/web/e2e/staff.spec.ts` (viết lại)
- Create: `apps/web/e2e/auth.spec.ts`

**Interfaces (Produces):** tài khoản E2E `teacher@e2e.local` / `password10` (role `teacher` only) chỉ tồn tại trong DB Compose `jplearn-web-e2e-<run>`.

- [x] **Step 1: Script cấp role trong DB cô lập**

`apps/api-python/differential/grant_role.py`:

```python
"""Grant a role to an E2E user inside the isolated Compose database only.

    .venv/bin/python differential/grant_role.py <database_url> <email> <role>
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tests"))
from pg_harness import assert_test_database_url  # noqa: E402


async def main(url: str, email: str, role: str) -> int:
    assert_test_database_url(url)  # refuses anything that is not a test database
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
        if user_id is None:
            print(f"no user {email}", file=sys.stderr)
            return 1
        await conn.execute(
            'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
            user_id,
            role,
        )
    finally:
        await conn.close()
    print(f"granted {role} to {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(*sys.argv[1:4])))
```

- [x] **Step 2: Harness tạo teacher sau bước seed**

Trong `web-e2e-python.sh`, sau dòng `echo "   published item $ITEM_ID, asset $ASSET_ID (+hls)"` thêm:

```bash
echo "== 3b/5 teacher E2E account (isolated DB only) =="
curl -fsS -X POST "http://localhost:$PY_PORT/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"teacher@e2e.local","password":"password10"}' >/dev/null
"$VENV_PY" "$REPO/apps/api-python/differential/grant_role.py" "$DATABASE_URL" teacher@e2e.local teacher
```

- [x] **Step 3: Client validation `.mp4` AND mime; option Audio disabled**

Ở cả hai file staff (`new/page.tsx` dòng 104 & 290; `[id]/page.tsx` dòng 181 & 632), thay điều kiện thành:

```ts
const isMp4 = (f: File) => f.name.toLowerCase().endsWith(".mp4") && (f.type === "" || f.type === "video/mp4");
```

(khai báo một lần ở top-level mỗi file) và dùng `if (!isMp4(file))` / `if (!isMp4(uploadFile))`.

Option Audio ở cả hai select:

```tsx
<option value="audio" disabled>Audio (Q1 chưa hỗ trợ tải tệp audio)</option>
```

Ghi vào `docs/sad/02-analysis/use-cases.md` UC-T02 phần "Ngoại lệ": "Q1: `media_type=audio` giữ trong schema, UI vô hiệu hoá lựa chọn vì upload chỉ nhận MP4 (FR-CMS-001). BA quyết định 2026-09-06."

- [x] **Step 4: Viết lại `staff.spec.ts`**

```ts
import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

function stockMp4(): string {
  const candidates = [
    path.resolve(__dirname, "../../../media/stock/mp4/level-0-wash-hands.mp4"),
    path.resolve(process.cwd(), "../../media/stock/mp4/level-0-wash-hands.mp4"),
  ];
  const hit = candidates.find((c) => fs.existsSync(c));
  if (!hit) throw new Error("stock mp4 missing");
  return hit;
}

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL("/");
}
async function register(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`l${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}
async function createDraft(page: Page, title: string): Promise<string> {
  await page.goto("/staff/new");
  await page.getByLabel(/Tiêu đề nội bộ/i).fill(title);
  await page.getByLabel(/Thời lượng/i).fill("30");
  await page.getByRole("button", { name: "Tạo bản nháp bài học" }).click();
  await expect(page).toHaveURL(/\/staff\/[0-9a-f-]+/);
  return page.url().split("/staff/")[1].split("?")[0];
}

test.describe("Staff CMS T-CMS-E2E-001", () => {
  test("teacher drafts+uploads+submits (no publish button); admin publishes; learner sees; admin unpublishes — each step survives reload", async ({ browser }) => {
    test.setTimeout(180_000);
    const title = `E2E handoff ${Date.now()}`;

    const learnerCtx = await browser.newContext();
    const learner = await learnerCtx.newPage();
    await register(learner);
    await learner.goto("/staff");
    await expect(learner.getByRole("heading", { name: "Không có quyền truy cập" })).toBeVisible();

    const teacherCtx = await browser.newContext();
    const teacher = await teacherCtx.newPage();
    await login(teacher, "teacher@e2e.local");
    const itemId = await createDraft(teacher, title);
    await teacher.reload();
    await expect(teacher.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
    await expect(teacher.getByLabel(/Tiêu đề nội bộ/i)).toHaveValue(title);

    await teacher.locator("input#upload").setInputFiles(stockMp4());
    await teacher.getByRole("button", { name: "Tải lên tệp MP4", exact: true }).click();
    await expect(teacher.getByText("Tải tệp media lên thành công!")).toBeVisible();
    await teacher.reload();
    await teacher.getByRole("button", { name: "Nộp kiểm định QA" }).click();
    await expect(teacher.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await teacher.reload();
    await expect(teacher.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await expect(teacher.getByRole("button", { name: "Xuất bản bài học" })).toHaveCount(0);
    await teacherCtx.close();

    await learner.goto("/catalog");
    await expect(learner.locator(`a[href*="${itemId}"]`)).toHaveCount(0);

    const adminCtx = await browser.newContext();
    const admin = await adminCtx.newPage();
    await login(admin, "admin@jplearn.local");
    await admin.goto("/staff");
    await expect(admin.getByRole("heading", { name: "Quản trị nội dung CI" })).toBeVisible();
    await admin.goto(`/staff/${itemId}`);
    await admin.getByRole("button", { name: "Xuất bản bài học" }).click();
    await expect(admin.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();
    await admin.reload();
    await expect(admin.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();

    await learner.goto("/catalog");
    await expect(learner.locator(`a[href*="${itemId}"]`)).toBeVisible();
    await expect(learner.getByText(title)).toHaveCount(0); // title_internal never leaks

    await admin.getByRole("button", { name: "Gỡ xuất bản (Về nháp)" }).click();
    await expect(admin.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
    await learner.goto("/catalog");
    await expect(learner.locator(`a[href*="${itemId}"]`)).toHaveCount(0);

    await adminCtx.close();
    await learnerCtx.close();
  });

  test("publish without media is refused and status stays level_qa", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await createDraft(page, `no-media ${Date.now()}`);
    await page.getByRole("button", { name: "Nộp kiểm định QA" }).click();
    await expect(page.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Xuất bản bài học" }).click();
    await expect(page.getByText(/Cannot publish without media/)).toBeVisible();
    await expect(page.getByText("Đã xuất bản (published)", { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
  });

  test("upload failure keeps the draft and shows an error", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await createDraft(page, `upload-fail ${Date.now()}`);
    await page.route(/\/staff\/catalog\/[^/]+\/media$/, (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "storage unavailable" }) }),
    );
    await page.locator("input#upload").setInputFiles(stockMp4());
    await page.getByRole("button", { name: "Tải lên tệp MP4", exact: true }).click();
    await expect(page.getByText("storage unavailable")).toBeVisible();
    await expect(page.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
  });

  test("stale revision → 409 → reload button loads the winner", async ({ browser }) => {
    const ctx = await browser.newContext();
    const p1 = await ctx.newPage();
    await login(p1, "admin@jplearn.local");
    const itemId = await createDraft(p1, `stale ${Date.now()}`);
    const p2 = await ctx.newPage();
    await p2.goto(`/staff/${itemId}`);
    await p2.getByLabel(/Tiêu đề nội bộ/i).fill("winner title");
    await p2.getByRole("button", { name: /Lưu thay đổi/ }).click();
    await expect(p2.getByText(/Đã lưu thay đổi thành công \(Phiên bản v2\)/)).toBeVisible();

    await p1.getByLabel(/Tiêu đề nội bộ/i).fill("loser title");
    await p1.getByRole("button", { name: /Lưu thay đổi/ }).click();
    await expect(p1.getByText(/Xung đột phiên bản/)).toBeVisible();
    await p1.getByRole("button", { name: "Tải lại dữ liệu" }).click();
    await expect(p1.getByLabel(/Tiêu đề nội bộ/i)).toHaveValue("winner title");
    await ctx.close();
  });

  test("client-side validation rejects non-mp4 in both staff forms", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await page.goto("/staff/new");
    await page.locator("input#mediaFile").setInputFiles({ name: "x.txt", mimeType: "text/plain", buffer: Buffer.from("t") });
    await expect(page.getByText("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).")).toBeVisible();
    await expect(page.locator("input#mediaFile")).toHaveAttribute("accept", "video/mp4");
    await expect(page.locator('select option[value="audio"]')).toBeDisabled();
  });
});
```

Nếu nút lưu có nhãn khác `/Lưu thay đổi/`, đọc `apps/web/src/app/staff/[id]/page.tsx` (form `onSubmit={handleSaveChanges}`) và dùng đúng nhãn — không đổi nhãn UI để chiều test.

- [x] **Step 5: `auth.spec.ts` (T-AUTH-SEC-001, T-AUTH-ERR-001)**

```ts
import { test, expect } from "@playwright/test";

test("T-AUTH-SEC-001: open-redirect targets fall back to /, internal path is honoured", async ({ page }) => {
  await page.goto("/login?redirect=//evil.example/phish");
  await page.getByLabel("Email").fill(`r${Date.now()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");

  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await page.goto("/login?redirect=%2Fprogress");
  await page.getByLabel("Email").fill(`r${Date.now()}b@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/progress");
});

test("T-AUTH-ERR-001: a 400 validation error from the API is shown verbatim in the alert", async ({ page }) => {
  await page.route(/\/auth\/login$/, (route) =>
    route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "email must be lowercase" }) }),
  );
  await page.goto("/login");
  await page.getByLabel("Email").fill("Mixed@Example.com");
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByRole("alert")).toHaveText("email must be lowercase");
});
```

- [x] **Step 6: Chạy hai spec trên chromium + webkit**

Run: `./apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/staff.spec.ts e2e/auth.spec.ts`
Expected: `7 passed`.
Run: `./apps/api-python/differential/web-e2e-python.sh --project=webkit e2e/staff.spec.ts e2e/auth.spec.ts`
Expected: `7 passed`.

- [x] **Step 7: Commit**

```bash
git add apps/api-python/differential/grant_role.py apps/api-python/differential/web-e2e-python.sh apps/web/src/app/staff apps/web/e2e/staff.spec.ts apps/web/e2e/auth.spec.ts docs/sad/02-analysis/use-cases.md
git commit -m "test(web): teacher→admin CMS handoff with reload/fail/conflict paths; auth redirect+400 E2E; mp4 validation aligned with API (FR-CMS-001, FR-CMS-002, T-CMS-E2E-001, T-AUTH-SEC-001, T-AUTH-ERR-001)"
```

---

### Task 8: C5 — mở rộng phạm vi axe và kiểm keyboard

**Owner:** Design + QA. NFR-A11Y-001, T-NFR-A1.

**Files:**
- Modify: `apps/web/e2e/a11y.spec.ts`

- [x] **Step 1: Thêm state và route detail**

Append vào `a11y.spec.ts`:

```ts
test("axe: error state on login, active session state, staff detail route T-NFR-A1", async ({ page }) => {
  // Login error state (role=alert visible)
  await page.goto("/login");
  await page.getByLabel("Email").fill("bad");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  // Active session with player
  await register(page);
  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(page.locator("video")).toBeVisible();
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
  await page.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  // Staff detail (published seed item)
  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await loginAdmin(page);
  await page.goto("/staff/00000000-0000-4000-8000-0000000000c1");
  await expect(page.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
});

test("keyboard: login form tab order and Enter-to-submit; player controls reachable T-NFR-A1", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Mật khẩu")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Đăng ký" })).toBeFocused();
  await page.getByLabel("Email").fill(`k${Date.now()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/");

  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).focus();
  await page.keyboard.press("Enter");
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect(video).toHaveAttribute("controls", "");
  await video.focus();
  await expect(video).toBeFocused();
});
```

Nếu `<video>` trong `CiPlayer` không có `controls`, đó là lỗi NFR-A11Y-001 thật: thêm `controls` vào `apps/web/src/components/ci-player.tsx`, không bỏ assertion.

- [x] **Step 2: Chạy**

Run: `./apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/a11y.spec.ts` → Expected: `4 passed`.
Run: `./apps/api-python/differential/web-e2e-python.sh --project=webkit e2e/a11y.spec.ts` → Expected: `4 passed`.

- [x] **Step 3: Commit**

```bash
git add apps/web/e2e/a11y.spec.ts apps/web/src/components/ci-player.tsx
git commit -m "test(web): axe on error/active/summary/staff-detail states + keyboard order (NFR-A11Y-001, T-NFR-A1)"
```

---

### Task 9: C6 — kiểm container sót trước E2E và bổ sung fresh-run guard

**Owner:** QA/Ops.

**Files:**
- Modify: `apps/api-python/differential/web-e2e-python.sh:84` (trước bước 1/5)

- [x] **Step 1: Thêm guard container sót**

Ngay trước `echo "== 1/5 docker db-test …"` thêm:

```bash
STALE="$(docker ps --filter "name=jplearn-web-e2e-" --format '{{.Names}}' | grep -v "$E2E_PROJECT" || true)"
if [[ -n "$STALE" ]]; then
  echo "== stale E2E containers detected (previous run did not clean up): ==" >&2
  echo "$STALE" >&2
  if [[ "${JPLEARN_E2E_PRUNE_STALE:-}" == "true" ]]; then
    while read -r name; do
      proj="${name%-db-test-1}"
      "$VENV_PY" "$REPO/apps/api-python/differential/db.py" --project "$proj" down >/dev/null 2>&1 || true
    done <<<"$STALE"
  else
    echo "   set JPLEARN_E2E_PRUNE_STALE=true to remove them, or run: docker compose -p <name-without--db-test-1> down -v" >&2
    exit 2
  fi
fi
```

- [x] **Step 2: Dọn container sót hiện có và xác nhận guard**

Run: `docker ps --filter name=jplearn-web-e2e- --format '{{.Names}}'`
Expected hiện tại: `jplearn-web-e2e-20260906115846_30869-db-test-1`.
Run: `JPLEARN_E2E_PRUNE_STALE=true ./apps/api-python/differential/web-e2e-python.sh --project=chromium e2e/hls.spec.ts`
Expected: log "stale E2E containers detected", rồi `1 passed`; sau đó `docker ps --filter name=jplearn-web-e2e- -q | wc -l` → `0`.

- [x] **Step 3: Commit**

```bash
git add apps/api-python/differential/web-e2e-python.sh
git commit -m "chore(e2e): fail closed on stale E2E containers, opt-in prune (C6 step 7)"
```

---

### Task 10: C6 — full regression, evidence có SHA/log, đóng trạng thái

**Owner:** QA chạy; BA review coverage; Platform/Web sửa nếu đỏ.

**Files:**
- Modify: `docs/qa/remediation-evidence-2026-09-06.md` (thêm §4)
- Modify: `docs/superpowers/plans/2026-09-06-web-frontend-remediation.md:3` + checkbox
- Modify: `docs/superpowers/plans/2026-09-06-web-frontend-implementation.md` (trạng thái Mốc A/B)
- Modify: `walkthrough.md` (trạng thái + số test)
- Modify: `docs/sad/03-design/traceability.md` (bỏ hậu tố "chưa có test")

- [x] **Step 1: Tree sạch + ghi SHA**

```bash
git status --short | wc -l           # Expected: 0
SHA=$(git rev-parse HEAD); TS=$(date +%Y%m%d-%H%M%S); EV=/tmp/jplearn-evidence-$TS; mkdir -p $EV
echo "$SHA" > $EV/sha.txt; git status --short > $EV/dirty-before.txt
docker ps --filter name=jplearn -q | wc -l > $EV/containers-before.txt   # Expected: 0 (dev DB jplearn-db-1 is Exited, not counted)
```

- [x] **Step 2: Chạy toàn bộ, lưu log + exit code**

```bash
(pnpm test:guard; echo "exit=$?") > $EV/guard.log 2>&1
(cd apps/api-python && uv run pytest -q -p no:cacheprovider; echo "exit=$?") > $EV/pytest.log 2>&1
(pnpm --filter @jplearn/web test; echo "exit=$?") > $EV/web-unit.log 2>&1
(pnpm --filter @jplearn/web build; echo "exit=$?") > $EV/web-build.log 2>&1
(./apps/api-python/differential/web-e2e-python.sh --project=chromium; echo "exit=$?") > $EV/e2e-chromium.log 2>&1
(./apps/api-python/differential/web-e2e-python.sh --project=webkit; echo "exit=$?") > $EV/e2e-webkit.log 2>&1
grep -h "exit=" $EV/*.log
```
Expected: mọi dòng `exit=0`. Đếm: `tail -3 $EV/pytest.log` → `217 passed` (212 + 2 Task 3 + 3 Task 4); `grep -c "✓" $EV/e2e-chromium.log` → `21` (8 cũ − 2 staff cũ + 5 staff mới + 6 recovery + 2 auth + 2 a11y); webkit cùng số.

- [x] **Step 3: Kiểm sót và DB dev**

```bash
docker ps --filter name=jplearn-web-e2e- -q | wc -l > $EV/containers-after.txt   # Expected: 0
pgrep -fl "uvicorn jplearn_api|next start" > $EV/procs-after.txt || true          # Expected: empty
git status --short > $EV/dirty-after.txt                                          # Expected: empty
cp -r $EV docs/qa/evidence/remediation-closeout-$TS
```

- [x] **Step 4: Viết §4 vào evidence doc**

Append vào `docs/qa/remediation-evidence-2026-09-06.md`:

```markdown
## 4. Closeout Evidence (C6)

- **Candidate SHA:** `<sha.txt>`
- **Dirty state before/after:** 0 / 0 (`dirty-before.txt`, `dirty-after.txt`)
- **Environment:** macOS darwin 25.6, Docker Compose project per run, Python 3.12 (`uv`), Node 25.8, pnpm 9.15, Playwright 1.49 (Chromium + WebKit engines — không phải thiết bị thật)
- **Config sanitized:** `JWT_SECRET=test-secret-…`, `ENVIRONMENT=test`, `STORAGE_ROOT=/tmp/jplearn-e2e-<run>/storage`, `DATABASE_URL=postgresql://jplearn_test:…@127.0.0.1:<port>/jplearn_test`
- **Raw logs:** `docs/qa/evidence/remediation-closeout-<TS>/`

| Command | Exit | Count | Duration | Log |
|---|---|---|---|---|
| `pnpm test:guard` | 0 | 0 banned fields | — | `guard.log` |
| `uv run pytest` | 0 | 217 passed | <s> | `pytest.log` |
| `pnpm --filter @jplearn/web test` | 0 | tsc 0 errors; 7 unit passed | — | `web-unit.log` |
| `pnpm --filter @jplearn/web build` | 0 | 10 routes | — | `web-build.log` |
| `web-e2e-python.sh --project=chromium` | 0 | 21 passed | <m> | `e2e-chromium.log` |
| `web-e2e-python.sh --project=webkit` | 0 | 21 passed | <m> | `e2e-webkit.log` |

Containers/processes sau run: 0 / 0. DB dev không được chạm (mọi test dùng Compose project riêng).

### Test ID → test thật
| ID | File::test |
|---|---|
| T-CAT-005-CAS | `test_catalog_concurrency.py` (4 tests) |
| T-SES-003-IDEM-CONCUR | `test_sessions_concurrency.py` (5 tests) |
| T-MIG-002-ADOPT | `test_schema_ddl.py::test_stamp_adopts_a_database_built_before_alembic` |
| T-SES-REC-001 | `src/lib/session-storage.test.ts` (4), `e2e/recovery.spec.ts` (6) |
| T-CMS-E2E-001 | `e2e/staff.spec.ts` (5) |
| T-AUTH-SEC-001 | `src/lib/safe-redirect.test.ts` (2), `e2e/auth.spec.ts` (1) |
| T-AUTH-ERR-001 | `e2e/auth.spec.ts` (1) |
| T-NFR-A1 | `e2e/a11y.spec.ts` (4) — axe tự động trên 8 route + 3 state; không phải audit WCAG 2.2 AA toàn diện |

### Chữ ký
- QA (`jplearn-qa`): PASS theo bảng trên tại SHA ở trên.
- BA (`jplearn-ba`): traceability đủ hàng cho mọi Test ID mới; hàng FR-LRN-002…004 hold giữ nguyên.
- Platform / Web: như §3.
- **Ghi chú release:** PASS local/test không mở R-09; staging/production vẫn cần HTTPS/CORS/media, smoke/rollback và authorization CTO/Ops.
```

Điền giá trị thật từ log; không để `<…>` sót lại.

- [x] **Step 5: Đổi trạng thái tài liệu**

- `2026-09-06-web-frontend-remediation.md:3` → `Trạng thái: **COMPLETED** tại <SHA> — evidence: docs/qa/remediation-evidence-2026-09-06.md §4.` và tick mọi checkbox đã có bằng chứng (sau Task 3–9 là toàn bộ, trừ mục "Design: rà focus… thủ công" nếu chưa ai rà — ghi `PARTIAL` với owner Design).
- `2026-09-06-web-frontend-implementation.md`: Mốc A/B → `COMPLETED` cùng SHA.
- `walkthrough.md` đoạn mở đầu → `**Trạng thái: COMPLETED tại <SHA>.**`, số test → 217 / 21+21 / 7 unit.
- `docs/qa/remediation-evidence-2026-09-06.md` Status → `VERIFIED & CLOSED at <SHA>`; xoá các hậu tố "(chưa có test — Task N)".
- `traceability.md`: thêm `T-CMS-E2E-001`, `T-SES-REC-001`, `T-AUTH-*` đã có từ Task 2; không đổi FR id.

- [x] **Step 6: Commit cuối**

```bash
git add docs walkthrough.md
git commit -m "docs(qa): closeout evidence with SHA/logs; remediation and Mốc A/B COMPLETED (C6)"
```

---

## Self-review

**Spec coverage** (đối chiếu báo cáo đánh giá 2026-09-06 13:14):
- C0 (plan status, walkthrough, a11y wording, guard vs chrome, T-IDs vào traceability, manual = hướng dẫn) → Task 2.
- C1 → đã đạt; không task.
- C2 thiếu PATCH×publish/unpublish → Task 3.
- C3 thiếu cross-user, fault injection, key length → Task 4.
- C4: `clip` trong storage, 6 ca Playwright, logout policy, `outcome_unknown` hiển thị summary → Task 5, 6.
- C5: teacher→admin, reload, upload fail, publish thiếu media, stale 409, T-AUTH-*, mp4 AND mime, Audio quyết định BA, axe state/keyboard → Task 7, 8.
- C6: SHA/log/exit code, container sót, DB dev, commit theo invariant, đổi trạng thái → Task 1, 9, 10.
- BA: khôi phục hàng FR-LRN-002…004 → Task 2.

**Type consistency:** `StoredSession` (Task 5) có `v: 1`, `deviceClass: "web"`, không `clip`; Task 6 đọc `state`, `sessionId`, `idempotencyKey` — khớp. `IDEMPOTENCY_KEY_MAX_LENGTH = 128` khớp test `"k" * 129` → 400, `"k" * 128` → 201 và OpenAPI `maxLength: 128`. `grant_role.py` dùng `assert_test_database_url` có sẵn tại `pg_harness.py:39`.

**Rủi ro đã ghi trong bước:** CORS preflight với `page.route` (Task 6 Step 2), nhãn nút Lưu (Task 7 Step 4), `controls` trên `<video>` (Task 8 Step 1), `openapi_diff` với `maxLength` (Task 4 Step 5), UoW rollback (Task 4 Step 2).
