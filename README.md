# JPLearn

Nền tảng thụ đắc tiếng Nhật tự nhiên (**Comprehensible Input — CI**) dành cho người lớn. Web, Mobile Expo (iOS/iPad/Android) và Staff CMS dùng chung một API backend duy nhất.

Backend là **FastAPI / Python 3.12** (`apps/api-python`), tuân thủ Clean Architecture ([ADR-006](docs/sad/03-design/adr-006-clean-architecture.md)) và trực tiếp sở hữu toàn bộ cấu trúc DDL qua Alembic ([ADR-004](docs/sad/03-design/adr-004-ddl-alembic.md)). NestJS (`apps/api`) đã được cho nghỉ hưu hoàn toàn từ [ADR-003](docs/sad/03-design/adr-003-runtime-python.md).

> [!IMPORTANT]
> **Triết lý Sư phạm cốt lõi & Guard Anti-Textbook:**
> JPLearn theo đuổi phương pháp thụ đắc ngôn ngữ tự nhiên thông qua ngữ cảnh và hình ảnh trực quan (Krashen CI). Guard Anti-Textbook có ba lớp: (1) `pnpm test:guard`; (2) `tests/test_schema_ddl.py`; (3) `tests/test_architecture_guard.py` và E2E `shell.spec.ts`.

---

## Cấu trúc Không gian làm việc (Monorepo)

Hệ thống quản lý theo mô hình monorepo bằng `pnpm` workspace kết hợp Python `uv`:

```text
.
├── apps/
│   ├── api-python/           # Backend chính: FastAPI, PostgreSQL 16, Alembic, Clean Architecture
│   ├── web/                  # Next.js 15 (React 19): Learner Portal (Design A+B) & Staff CMS (/staff)
│   └── mobile/               # Expo SDK 53 (React Native 0.79): iOS, iPadOS, Android App
├── packages/
│   ├── domain/               # Logic nghiệp vụ, entity & bất biến dùng chung (TypeScript)
│   ├── cms-schema/           # Schema dữ liệu phục vụ Staff CMS
│   └── design-tokens/        # Token giao diện dùng bởi mobile; web dùng CSS custom properties trong globals.css
├── docs/                     # Toàn bộ tài liệu kiến trúc (SAD), nghiệp vụ, vận hành (Ops) & QA
└── scripts/                  # Scripts CI/CD và kiểm tra chống ô nhiễm sư phạm (Guard)
```

### Các năng lực chính trên hệ thống

- **Vòng học CI liên tục (CI Learning Loop — [ADR-007](docs/sad/03-design/adr-007-ci-learning-loop-contracts.md)):**
  - **Nội dung & Phân cảnh (`scenes`):** Quản lý phiên bản bất biến (`content_versions`), mốc thời gian cảnh không chồng lấn, snapshot dữ liệu media và kiểm tra tính toàn vẹn thời lượng.
  - **Series & Bộ sưu tập cá nhân (`collections`):** Gom nhóm bài học theo chủ đề, danh sách phát cá nhân hóa và quản lý tập phim.
  - **Cảnh đã lưu (`saved_scenes`):** Đánh dấu các phân cảnh đáng chú ý để xem lại theo ngữ cảnh.
  - **Báo cáo chất lượng (`content_reports`):** Thu thập phản hồi từ người học về video, âm thanh hoặc chất lượng sư phạm.
  - **Theo dõi phát trực tuyến chuẩn xác (`/playbacks`):** Heartbeat chu kỳ 15 giây, kiểm soát lease 45 giây, số thứ tự `seq` tăng đơn điệu, cơ chế chiếm quyền phát giữa các thiết bị (`epoch` takeover), lưu biên nhận xử lý chống lặp (`Idempotency-Key` / receipts), giới hạn trôi đồng hồ (drift limit) và bảo vệ mốc cắt xóa lịch sử (`deletion_cutoff`).
  - **Thời gian tích lũy thực tế (`active_watch_seconds`):** Đo đếm thời gian xem video thực trạng thái `playing` (loại bỏ tua, tạm dừng, buffer) theo từng ngày và so khớp với mục tiêu học tập hàng ngày (`daily_goal_minutes`).
  - **Tác vụ AI bất đồng bộ (trial):** Khung job/quota/lease đã có; provider hiện tại là **synthetic trial** — chưa phải dịch vụ transcription thật. Background worker (`ai_worker.py`) chạy luồng thử nghiệm.
  - **Learner Web (`apps/web`):** Catalog, Series, Library/Collections, Session, Progress, Watch History và Content Reports dùng chung hợp đồng FastAPI; trình phát `<CiPlayer>` hỗ trợ HLS (`.m3u8`) với fallback MP4 và khôi phục phiên qua `sessionStorage` tách theo người dùng/tab.
  - **Staff CMS (`/staff`):** Cổng quản trị dành cho teacher/admin gồm catalog/media, content studio cho scenes và transcript tiếng Nhật, series workflow, hàng đợi content reports, AI content jobs và usage ledger. Các thao tác ghi dùng revision CAS và giữ bước duyệt trước khi publish.

---

## Yêu cầu môi trường (Prerequisites)

- **Python:** 3.12 trở lên và công cụ [`uv`](https://docs.astral.sh/uv/)
- **Node.js:** 22.x LTS trở lên và **pnpm 9** (kích hoạt bằng `corepack enable`)
- **Docker:** Docker Desktop hoặc Docker Engine hỗ trợ Docker Compose v2
- **FFmpeg & ffprobe:** Bắt buộc có trên hệ thống để trích xuất thông số media (`ffprobe`) trong quy trình kiểm định tải lên tệp media CMS, tạo luồng HLS, và kiểm thử E2E Playwright (luồng media thật).

---

## Cài đặt & Chuẩn bị (Setup)

### 1. Khởi động cơ sở dữ liệu PostgreSQL

```bash
docker compose up -d db
```

Cổng PostgreSQL mặc định là `localhost:5432` với tài khoản/mật khẩu `jplearn:jplearn` và database `jplearn`.

### 2. Cài đặt thư viện & Cấu hình môi trường

```bash
# Thiết lập biến môi trường API từ mẫu chuẩn
test -e apps/api-python/.env || cp apps/api-python/.env.example apps/api-python/.env

# Cài đặt toàn bộ dependencies của Monorepo (Node & Python)
pnpm install
uv --directory apps/api-python sync --frozen
```

### 3. Thực thi Database Migration & Seed dữ liệu ban đầu

```bash
pnpm db:migrate
pnpm db:seed
```

### 4. Khởi tạo tài khoản Quản trị viên (Bootstrap Admin Local)

Mặc định, lệnh `pnpm db:seed` không tạo sẵn mật khẩu admin để tránh rủi ro an ninh. Để tạo tài khoản admin dùng thử cục bộ:

```bash
ENVIRONMENT=local BOOTSTRAP_ADMIN_EMAIL=admin@jplearn.local \
BOOTSTRAP_ADMIN_PASSWORD=local-admin-password10 pnpm db:seed
```

*Lưu ý:* Nếu email đã tồn tại trong DB, lệnh seed sẽ bỏ qua và không ghi đè mật khẩu hoặc nâng quyền. Chi tiết xem [Hướng dẫn phát triển Backend](docs/backend/development.md).

> [!TIP]
> **Adoption cơ sở dữ liệu cũ (Prisma $\to$ Alembic):**
> Nếu môi trường của bạn đã có schema từ thời điểm trước ADR-004, hãy dùng lệnh `stamp` để Alembic nhận diện baseline thay vì chạy đè migration:
> ```bash
> cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate stamp 0001_prisma_baseline
> ```

---

## Khởi chạy Cục bộ (Running Locally)

Mở các cửa sổ terminal riêng biệt hoặc dùng process manager để chạy các dịch vụ:

```bash
# 1. API Backend (FastAPI tại http://localhost:3002)
pnpm dev:api

# 2. Web Portal & Staff CMS (Next.js tại http://localhost:3000)
pnpm dev:web

# 3. Mobile App (Expo Metro bundler)
pnpm dev:mobile
```

Dev server ghi artifact vào `apps/web/.next-dev`; production build ghi vào
`apps/web/.next`. Hai lệnh có thể chạy đồng thời mà không ghi đè chunk của nhau.
Nếu đặt `NEXT_DIST_DIR`, mỗi process phải dùng một thư mục riêng.

### Các dịch vụ nền & CLI bổ trợ

- **AI Background Worker (synthetic trial — khung job/quota/lease):**
  ```bash
  cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.ai_worker
  ```
- **CLI Bảo trì & Điều hòa phiên học (Maintenance & Reconciliation):**
  ```bash
  cd apps/api-python && PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.maintenance --help
  ```

Web và ứng dụng di động Mobile kết nối tới API qua biến `NEXT_PUBLIC_API_URL` / `EXPO_PUBLIC_API_URL` trỏ vào `http://localhost:3002`. Dữ liệu danh mục bài học, tiến độ học viên và phiên học được đồng bộ đồng nhất giữa các nền tảng.

### Dữ liệu thử nghiệm cục bộ (Local Pilot Catalog)

Lệnh `pnpm db:seed` tạo topics, feature flags và hai catalog item ở trạng thái `draft` khi có tài khoản admin làm người tạo. Seed không kèm media và không tự publish. Để học viên thấy nội dung, cần upload media rồi thực hiện submit QA → review approve → publish qua CMS. Bộ 10 clip Kyoko TTS trong evidence demo cũ là dữ liệu chuẩn bị riêng, không phải kết quả của lệnh seed; TTS là giọng tổng hợp và evidence đó không chứng nhận quyền sử dụng media.
- Đăng nhập tài khoản bất kỳ trên Web (`http://localhost:3000`) để trải nghiệm Catalog và phiên học trực tiếp.
- Người dùng có quyền `teacher` hoặc `admin` có thể truy cập `http://localhost:3000/staff` để quản lý danh mục bài học và quy trình kiểm duyệt chất lượng.

---

## Kiểm thử & Xác thực Chất lượng (Testing & QA)

### 1. Guard Chống Ô Nhiễm Sư Phạm (Bắt buộc chạy đầu tiên)

```bash
pnpm test:guard
```
Kiểm tra toàn diện cấu trúc cơ sở dữ liệu, contract và mã nguồn để bảo đảm không xuất hiện các từ khóa/thuộc tính cấm liên quan đến giáo trình truyền thống.

### 2. Bộ Kiểm Thử Đơn Vị & Tích Hợp Backend (FastAPI + Pytest)

```bash
pnpm test:api
```
*Cơ chế tự động:* Pytest tự động khởi tạo một PostgreSQL 16 container cô lập (`db-test`), áp dụng toàn bộ Alembic migrations, thực thi hơn 370 tests kiểm thử (bao gồm concurrency locking, CAS, idempotency receipts, media probe) và tự hủy container sau khi hoàn tất. Cơ sở dữ liệu dev `jplearn` hoàn toàn không bị ảnh hưởng.

### 3. Kiểm Thử Giao Diện Web & Kiểu Dữ Liệu TypeScript

```bash
pnpm --filter @jplearn/web test        # TypeScript compile check (tsc) + unit tests
pnpm --filter @jplearn/domain test      # Kiểm thử domain invariant packages
pnpm --filter @jplearn/mobile test      # Jest unit tests cho mobile app
```

### 4. Kiểm Thử Đầu-Cuối Web E2E (Playwright)

Bộ kiểm thử E2E khởi chạy độc lập trên môi trường DB test riêng biệt, kết hợp API thật, Web frontend thật và luồng media HLS/MP4 thật:

```bash
# Chạy toàn bộ trên cả Chromium và WebKit (giả lập Safari)
apps/api-python/differential/web-e2e-python.sh

# Chạy riêng với trình duyệt Chromium
apps/api-python/differential/web-e2e-python.sh --project=chromium
```

---

## Tổ chức Đội ngũ & Tương tác Agent (Org & Roles)

Dự án áp dụng mô hình phân quyền rõ ràng theo ghế công ty, phản ánh qua thư mục cấu hình Cursor Agents:

- **Bảng danh sách ghế:** [`.cursor/agents/README.md`](.cursor/agents/README.md)
- **Ma trận trách nhiệm:** [docs/company/raci.md](docs/company/raci.md)

> [!IMPORTANT]
> **Quy tắc làm việc:** Không sử dụng một AI agent chung chung để kiêm nhiệm toàn bộ vai trò. Mỗi quyết định kỹ thuật hay thay đổi nghiệp vụ cần đối chiếu đúng ghế chịu trách nhiệm: **BA** (kiểm soát yêu cầu, UC, SRS, hợp đồng contract), **Pedagogy** (chuẩn CI), **Platform / Backend** (FastAPI, DDL, Clean Architecture), **Web / Mobile** (client UX, playback resilience), và **QA** (xác thực bằng chứng).

---

## Bản đồ Tài liệu (Documentation Index)

| Nhóm tài liệu | Đường dẫn tham chiếu |
| --- | --- |
| **Nền tảng & Tầm nhìn** | [Mục lục nền tảng](docs/README.md) · [Tầm nhìn công ty](docs/company/vision.md) · [Pedagogy Bible](docs/pedagogy/bible.md) |
| **Yêu cầu & Nghiệp vụ** | [SAD-1 Khảo sát & SRS](docs/sad/01-survey-srs/srs.md) · [SAD-2 Phân tích & Use Cases](docs/sad/02-analysis/use-cases.md) · [Ma trận truy vết (Traceability)](docs/sad/03-design/traceability.md) |
| **Thiết kế Kiến trúc (SAD)** | [Kiến trúc C4](docs/sad/03-design/c4.md) · [Hợp đồng OpenAPI 3.0.3](docs/sad/03-design/openapi.yaml) · [Hướng dẫn tích hợp Client](docs/sad/03-design/client-integration-guide.md) · [Thiết kế UI Shell](docs/sad/03-design/ui-shell.md) |
| **Quyết định Kỹ thuật (ADR)** | [ADR-003 Runtime Python](docs/sad/03-design/adr-003-runtime-python.md) · [ADR-004 Alembic DDL](docs/sad/03-design/adr-004-ddl-alembic.md) · [ADR-006 Clean Architecture](docs/sad/03-design/adr-006-clean-architecture.md) · [ADR-007 CI Learning Loop](docs/sad/03-design/adr-007-ci-learning-loop-contracts.md) |
| **Backend & Phát triển** | [Mục lục Backend](docs/backend/README.md) · [Hướng dẫn sử dụng API](docs/backend/api-usage.md) · [Hướng dẫn phát triển](docs/backend/development.md) · [README `api-python`](apps/api-python/README.md) |
| **Vận hành (Ops Runbooks)** | [Vận hành Backend](docs/ops/runbook-backend.md) · [Backup & Khôi phục](docs/ops/runbook-backup-restore.md) · [Learning Loop Runbook](docs/ops/learning-loop-runbook.md) · [Quy trình Xuất bản & HLS](docs/sad/03-design/runbook-publish.md) |
| **Báo cáo Nghiệm thu (QA)** | [Báo cáo Tổng thể & Walkthrough](walkthrough.md) · [Bằng chứng UI A+B](docs/qa/ui-ab-evidence-2026-09-07.md) |

---

> [!WARNING]
> **Trạng thái Mở Traffic Production:**
> Cổng nghiệm thu vận hành **R-09 Operational Acceptance vẫn đang ở trạng thái HOLD**. Việc kiểm thử cục bộ hoặc qua container Docker xanh là điều kiện cần nhưng không đồng nghĩa hệ thống đã được cấp phép mở traffic production khi chưa hoàn tất diễn tập staging HTTPS, soak test và quy trình canary rollback.
