# Báo Cáo Thực Thi: Web Frontend & Staff CMS (Mốc A & Mốc B)

> **Dữ liệu dùng thử local — 2026-09-07:** Đã nạp 10 clip thí điểm có thoại Nhật
> vào API `localhost:3002` qua create/upload/submit-qa/publish, dựa trên Level QA
> [issue #33](docs/qa/issue-33-level-qa.md). Catalog local có 10 bài published
> (8 cấp 0, 2 cấp 1); hai seed draft được giữ nguyên. Clip dài 10–32 giây,
> dùng giọng Kyoko TTS; hình thẻ là minh họa chủ đề. Chọn “Vào học bài này” →
> “Bắt đầu phiên” → “Phát” để xem video. Đây là nội dung thí điểm local.
> [Danh sách file và ID](docs/qa/evidence/local-demo-20260907/catalog.json).
> Đã xác nhận phát MP4 qua UI **10/10 Chromium + 10/10 WebKit** (video có kích thước
> hợp lệ, thời gian phát tăng, start/end thành công): [playback evidence](docs/qa/evidence/local-demo-20260907/playback.json).
> Đã bổ sung một hàng `learner_progress` còn thiếu cho admin local, mặc định 0 phút/cấp 0,
> bằng insert có kiểm tra tồn tại; không ghi đè tiến độ cũ. Không đổi mã backend.

> **UI A+B — 2026-09-07:** Đã áp dụng mẫu `design-ab.html` vào trang chủ, Catalog,
> phiên học, tiến độ và khung điều hướng dùng chung với Staff CMS. Nền kem/xanh sage,
> sidebar desktop, điều hướng gọn trên phone; dữ liệu vẫn lấy từ API hiện có.
> Xác thực đợt UI: **88/88 E2E**, **35/35 unit**, TypeScript/build/guard PASS;
> 15 tổ hợp màn hình/trạng thái và viewport không tràn ngang.
> [Bằng chứng và phạm vi kiểm tra UI A+B](docs/qa/ui-ab-evidence-2026-09-07.md).
> Các kết quả backend bên dưới là baseline lịch sử, không phải lần chạy mới của đợt UI này.

> **Cập nhật cuối:** đã sửa retry video bị khóa và HLS restore; native WebKit được
> kiểm cả paused/playing. Bản patch từ `564275e` đạt **88/88 E2E**, **217/217 backend**,
> **35/35 unit**, guard/build PASS. [Evidence và patch](docs/qa/media-retry-fix-evidence-2026-09-06.md).
> Engineering PASS; **Design PARTIAL** (Safari/iPhone/iPad thật). Số liệu bên dưới
> giữ lịch sử nghiệm thu trước đợt sửa; chưa triển khai production.

> **Trạng thái: engineering PASS, Design PARTIAL.** Không COMPLETED toàn diện. [Recovery follow-up](docs/superpowers/plans/2026-09-06-web-frontend-recovery-followup.md) đóng C4 vì F-01–F-03 có evidence; C5 keyboard/manual: engineering tests PASS, Design PARTIAL (chưa rà focus/Safari device). Evidence mới: [recovery-followup-evidence-2026-09-06.md](docs/qa/recovery-followup-evidence-2026-09-06.md) — candidate `41a4009` (code), evidence `d1715d2`: pytest **217 passed**; Playwright **42+42** Chromium/WebKit; web unit **35**; guard **0 banned**; build **10 routes**. WebKit HLS = engine, không phải iPhone. Lịch sử `fd838d2` giữ nguyên: pytest **217 passed**; Playwright **21+21**; web unit **7**. Release gate không đổi (không production).

---

## 1. Tổng Quan Kết Quả Đạt Được

### Mốc A — Learner Web (Trải Nghiệm Người Học)
- **Landing Page ([apps/web/src/app/page.tsx](apps/web/src/app/page.tsx)):** Thiết kế A+B theo mẫu đã chọn `design-ab.html`: hero minh họa, ba bước làm quen và lời mời khám phá Catalog.
- **Hệ Thống Xác Thực ([apps/web/src/app/login/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/login/page.tsx)):** Hỗ trợ Đăng ký/Đăng nhập, điều hướng bảo vệ qua query `redirect`, hiển thị tài khoản hiện tại, và hàm `logout()` thu hồi phiên triệt để trên máy chủ (`POST /auth/logout`).
- **Danh Mục Bài Học ([apps/web/src/app/catalog/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/catalog/page.tsx)):** Lọc nhanh theo cấp độ CI (Cấp 0 – 4), hiển thị thẻ clip CI kèm metadata trực quan và điều hướng vào phiên học theo clip được chọn (`/session?item_id=...`).
- **Phiên Học Trực Tiếp ([apps/web/src/app/session/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/session/page.tsx)):**
  - Trình phát media `<CiPlayer>` linh hoạt: ưu tiên luồng thích ứng HLS (`.m3u8`), tự động fallback MP4.
  - Chống trùng lặp yêu cầu qua header `Idempotency-Key` trên `POST /sessions`.
  - Khôi phục phiên học gián đoạn qua `sessionStorage` tách theo user và tab (`jplearn.session:<userId>`), state machine `starting → active → ending → outcome_unknown`, xác thực trạng thái máy chủ qua `GET /sessions/{id}`.
  - Đồng hồ đếm thời gian thực khi học, nút Bắt đầu / Kết thúc rõ ràng, và bảng tổng kết tiến độ ngay sau phiên.
- **Tiến Độ Học Tập ([apps/web/src/app/progress/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/progress/page.tsx)):** Hiển thị số phút CI tích luỹ và cấp độ hiện tại, tự động đồng bộ khi quay lại trang.

Mốc A recovery: **engineering PASS** tại `41a4009` / `d1715d2` (F-01–F-03).
F-04 engineering PASS, Design PARTIAL (focus thủ công + Safari/iPhone/iPad thật).
Mốc B CMS giữ hồi quy lịch sử `fd838d2`, không dựng lại workflow.
Số liệu `fd838d2` (217 / 21+21 / 7) là lịch sử; không thay số follow-up.

### Mốc B — Staff CMS (Cổng Quản Trị & Biên Tập Nội Dung)
- **Danh Sách Nội Dung Staff ([apps/web/src/app/staff/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/page.tsx)):** Cổng biên tập dành cho vai trò `teacher` / `admin`, lọc theo trạng thái (`draft`, `level_qa`, `published`, `archived`) và cấp độ CI, bảng chi tiết hiển thị revision và thời lượng.
- **Tạo Mới Bản Thảo ([apps/web/src/app/staff/new/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/new/page.tsx)):** Biểu mẫu tạo mới bản thảo theo chuẩn `catalogWriteFields`, tải kèm tệp MP4 ban đầu và chuyển hướng ngay vào màn hình biên tập.
- **Biên Tập & Kiểm Duyệt ([apps/web/src/app/staff/[id]/page.tsx](file:///Users/quyendo/Documents/Learn/JPLearn/apps/web/src/app/staff/%5Bid%5D/page.tsx)):**
  - Chỉnh sửa thông tin metadata bản thảo với cơ chế khoá lạc quan (optimistic locking) qua trường `revision` (bắt lỗi xung đột 409 Conflict và hỗ trợ tải lại dữ liệu mới nhất).
  - Tải lên video MP4 thay thế (`POST /staff/catalog/{id}/media`).
  - Nộp kiểm duyệt chất lượng (`POST /staff/catalog/{id}/submit-qa`).
  - Xuất bản (`publish`) và gỡ bài (`unpublish`) dành riêng cho quyền quản trị (`admin`).

### Platform & Backend
- **Migration & Database ([apps/api-python/src/jplearn_api/migrations/versions/0002_session_idem_rev.py](file:///Users/quyendo/Documents/Learn/JPLearn/apps/api-python/src/jplearn_api/migrations/versions/0002_session_idem_rev.py)):**
  - Tạo bảng `session_idempotency_keys` lưu trữ khoá chống lặp phiên học.
  - Bổ sung cột `revision` (integer, default 1) trên bảng `catalog_items`.
  - Snapshot Prisma `0001` ([docs/qa/adr-004-schema-baseline.json](docs/qa/adr-004-schema-baseline.json), 10 bảng) **bất biến**; snapshot head `0002` tách riêng ([docs/qa/adr-004-schema-head-0002.json](docs/qa/adr-004-schema-head-0002.json), 11 bảng).
- **API & OpenAPI:**
  - Cập nhật [docs/sad/03-design/openapi.yaml](file:///Users/quyendo/Documents/Learn/JPLearn/docs/sad/03-design/openapi.yaml) đồng bộ 100% với mã nguồn.
  - Hỗ trợ `GET /sessions/{id}`, `Idempotency-Key` trên `POST /sessions`, `GET /staff/catalog`, `GET /staff/catalog/{id}`, và `PATCH /staff/catalog/{id}`.
- **Tài Liệu Phân Tích (BA & SAD):**
  - Cập nhật `use-cases.md` (UC-L10, UC-T02b, UC-T05).
  - Cập nhật `traceability.md` và `ui-shell.md`.

---

## 2. Bằng Chứng Kiểm Thử (Verification Evidence)

### A. Guard Anti-Textbook
```bash
pnpm test:guard
```
- **Kết quả:** `0 errors` — Không chứa cột/field schema cấm (`vocabulary_score`, `grammar_lesson_id`, `textbook_percent`, `translation_vi`). Text chrome cấm (`Ngữ pháp`, `Flashcard`, `Bản dịch`) do `shell.spec.ts` kiểm, không phải guard.

### B. Kiểm Thử Kiểu Dữ Liệu & Bản Dựng Web
```bash
pnpm --filter @jplearn/web exec tsc --noEmit
pnpm --filter @jplearn/web build
```
- **Kết quả:** 
  - `tsc`: 0 lỗi biên dịch TypeScript.
  - `next build`: 10 route tĩnh và động được tạo thành công tối ưu.

### C. Bộ Kiểm Thử Pytest Backend (FastAPI)
```bash
cd apps/api-python && uv run pytest
```
- **Kết quả:** `217 passed` trong 30.49s tại `fd838d2` (baseline Task 1 là 212).
  - `tests/test_openapi_diff.py`: 7/7 PASSED (0 sai lệch giữa contract OpenAPI và FastAPI router).
  - `tests/test_schema_ddl.py`: 8/8 PASSED (0 sai lệch cấu trúc bảng DDL so với baseline ADR-004).
  - `tests/test_sessions.py`: 11/11 PASSED (kiểm thử chống lặp Idempotency-Key và endpoint khôi phục).
  - `tests/test_catalog.py`: 7/7 PASSED (kiểm thử optimistic locking revision và CRUD staff).
  - `tests/test_catalog_concurrency.py`: 4/4 PASSED (CAS PATCH đồng thời, PATCH × submit-QA, PATCH × publish, PATCH × unpublish).
  - `tests/test_sessions_concurrency.py`: 5/5 PASSED (idempotency replay, payload 409, cross-user, fault rollback, key max 128).

### D. Kiểm Thử E2E Playwright Trên Trình Duyệt Thật (Chromium)
```bash
./apps/api-python/differential/web-e2e-python.sh --project=chromium
```
- **Kết quả:** `21 passed (2.3m)` tại `fd838d2`.
  - `hls.spec.ts`: Phát luồng HLS thật `.m3u8` qua `CiPlayer` thành công.
  - `shell.spec.ts (login & progress)`: Chrome không chứa text kênh tắt (`Ngữ pháp`, `Flashcard`, `Bản dịch`).
  - `shell.spec.ts (catalog)`: Hiển thị đúng nội dung đã xuất bản, ẩn bản thảo.
  - `a11y.spec.ts` (4): axe không phát hiện vi phạm tự động trên 8 route + login error / session active / summary / staff detail; keyboard Chromium full walk. Không phải audit WCAG 2.2 AA toàn diện.
  - `staff.spec.ts` (5): teacher→admin handoff, reload, publish thiếu media, upload fail, stale 409, mp4 AND mime.
  - `recovery.spec.ts` (6): mất response start/end, offline, multi-tab, đổi user, không lưu signed URL.
  - `auth.spec.ts` (2): open-redirect an toàn; 400 hiện trong `p.status-error`.
  - `sync.spec.ts`: Chạy phiên học kéo dài thật >60s giữa 2 ngữ cảnh trình duyệt riêng biệt, đồng bộ chính xác từng phút tích luỹ.

### E. Kiểm Thử E2E Playwright Trên WebKit (Safari Engine)
```bash
./apps/api-python/differential/web-e2e-python.sh --project=webkit
```
- **Kết quả:** `21 passed (2.3m)` trên WebKit engine (không phải thiết bị iPhone/iPad thật).

### F. Recovery follow-up candidate `41a4009` / evidence `d1715d2` (2026-09-06)

Không thay thế mục C–E ở trên. Raw: `docs/qa/evidence/recovery-followup-20260906-170905/`.

| Lệnh | Exit | Count |
|---|---|---|
| `pnpm test:guard` | 0 | 0 banned textbook fields |
| `pnpm --filter @jplearn/web test` | 0 | **35 passed** |
| `pnpm --filter @jplearn/web build` | 0 | 10 routes |
| `pnpm test:api` | 0 | **217 passed** |
| `web-e2e-python.sh --project=chromium` | 0 | **42 passed** |
| `web-e2e-python.sh --project=webkit` | 0 | **42 passed** (HLS = engine, không phải iPhone) |

F-01–F-03 engineering PASS. F-04 engineering PASS + Design PARTIAL.

---

## 3. Hướng Dẫn Thao Tác Thủ Công (không phải evidence)

1. **Khởi chạy ứng dụng:**
   - Terminal 1 (API): `cd apps/api-python && PYTHONPATH=src uv run uvicorn jplearn_api.entrypoints.http.app:app --port 3002`
   - Terminal 2 (Web): `cd apps/web && pnpm dev` (mở tại `http://localhost:3000`)
2. **Khám phá giao diện người học (Learner):**
   - Vào `http://localhost:3000/` để xem giao diện A+B đã tích hợp; `design-ab.html` chỉ là mẫu tham chiếu.
   - Vào `/login` để đăng ký tài khoản mới (hoặc đăng nhập).
   - Vào `/catalog` để xem các bài học CI được lọc theo cấp độ.
   - Tìm theo chủ đề hoặc chọn cấp độ, nhấn "Vào học bài này" để chuyển tới `/session`, bấm "Bắt đầu phiên", theo dõi đồng hồ chạy và bấm "Kết thúc phiên".
   - Vào `/progress` để kiểm tra số phút học vừa được hệ thống tích luỹ chính xác.
3. **Trải nghiệm cổng quản trị Staff CMS:**
   - Đăng nhập bằng tài khoản quản trị viên (được nạp sẵn qua `pnpm seed` / seed script: `admin@jplearn.local` / `password10`).
   - Vào `http://localhost:3000/staff` để xem danh sách nội dung và bộ lọc trạng thái.
   - Bấm "Tạo bản thảo mới" (`/staff/new`), nhập thông tin và tải lên tệp MP4.
   - Tại màn hình chi tiết (`/staff/[id]`), cập nhật metadata, bấm "Nộp kiểm định QA", thực hiện bước "Duyệt QA" (ghi nhận review), và bấm "Xuất bản bài học" để đưa clip ra ngoài Catalog người học.

---

## 4. Tiến Độ Đợt D (Language Tools & Search Projection)

### PR8a — Nhập tay / Duyệt Transcript và Phân Tích Ngôn Ngữ Staff
- **Migration 0010:** Bổ sung các bảng `transcript_revisions`, `approved_scene_texts`, `language_analysis_jobs`.
- **Domain & Application:**
  - Invariants: Không giải thích ngữ pháp L1, không flashcard, không sửa timeline/scenes.
  - Phân tích từ vựng/câu thoại tiếng Nhật: phân rã Unicode code point, lemma, reading katana/hiragana có provenance.
  - Endpoints staff:
    - `POST /staff/content/{catalog_item_id}/transcripts/draft`
    - `POST /staff/content/{catalog_item_id}/transcripts/approve`
    - `POST /staff/content/{catalog_item_id}/transcripts/analyze`
    - `GET /staff/content/{catalog_item_id}/transcripts`

### PR8b — Search Projection và Tìm Kiếm Câu/Phân Cảnh (`GET /catalog/search`)
- **Domain Pure Logic (`jplearn_api.domain.search`):**
  - Chuẩn hóa chuỗi tìm kiếm: Unicode NFKC, strip khoảng trắng nửa rộng & toàn rộng `\u3000`. Giới hạn 1–100 ký tự.
  - Phân loại độ khớp: Ưu tiên 1 `exact_phrase`, Ưu tiên 2 `token_match`.
  - Tính toán `highlight_spans` chính xác theo Unicode code point slices `[start_offset, end_offset]`.
  - Keyset pagination qua base64 cursor với index generation pin (`gen_...:offset`).
- **Pedagogy & Security Invariants (`FR-NEG`):**
  - Chỉ tìm trên `approved_scene_texts` có `is_active = True`, thuộc `catalog_items` `published` và `content_versions` `is_published = True`.
  - Tuyệt đối không lộ bản thảo, bản thu hồi, `title_internal`, bản dịch tiếng Việt hay giải thích ngữ pháp.
  - Lọc trần CI: Không bao giờ trả về nội dung vượt quá `learner.current_ci_level`.
  - Feature capability: `scene_search_enabled` bảo vệ bằng 403 Forbidden khi tính năng bị tắt.
- **Verification:**
  - `tests/test_search.py`: 16/16 PASSED.
  - Full backend pytest: 321/321 PASSED.
  - `openapi_diff --strict`: 0 diffs.
  - `pnpm test:guard`: 0 violations.

---

## 5. Backend remediation R0–R8 — pending verification

Bản sửa đang được kiểm tra theo [remediation plan](docs/superpowers/plans/2026-09-07-backend-remediation-plan.md). Không xác nhận đã xử lý hết P1/P2 hoặc hoàn thành R0–R8. Sự tồn tại test, tổng số pytest PASS hay OpenAPI diff PASS không chứng minh đầy đủ hợp đồng nghiệp vụ, race conditions, retention hoặc client trên thiết bị thật.

R0 đã ghi engineering contract sửa trong SRS, use cases, traceability và ADR-007. Đây không phải chữ ký BA/CTO/Pedagogy/Ops. Các thay đổi implementation phải có kết quả hồi quy tại revision hiện tại trước khi đóng gate. Kết quả UI/backend lịch sử ở phần trên giữ nguyên phạm vi lịch sử; không coi là evidence cho remediation mới.

Cần evidence riêng cho lease expiry/takeover, canonical receipts/final end, delayed packets sau deletion, pending preferences qua midnight/DST, capability matrix, immutable content/transcript và quota/job transaction. PostgreSQL integration, client integration và performance targets chưa được suy ra từ unit tests. Không mở production gate.
