# Phát triển backend FastAPI

## 1. Môi trường local

Yêu cầu: Python 3.12, `uv`, Docker + Compose, Node.js 22 và pnpm 9. Node phục vụ
web/mobile và guard repo, không phải runtime backend. `jq` chỉ cần cho ví dụ curl.
Chạy từ **repo root**, trừ khối ghi rõ `cd apps/api-python`.

```bash
pnpm install
uv --directory apps/api-python sync --frozen
test -e apps/api-python/.env || cp apps/api-python/.env.example apps/api-python/.env
docker compose up -d db
docker compose exec -T db pg_isready -U jplearn -d jplearn
pnpm db:migrate
```

DB local `jplearn` dùng volume Compose `postgres_data`, mặc định thường mang tên
`jplearn_postgres_data` (có thể khác khi đổi project name). Không chạy
`docker compose down -v` hoặc reset DB để sửa lỗi test. DB Prisma cũ phải qua
quy trình adopt trong [runbook](../ops/runbook-backend.md), không áp `upgrade`
lên schema đã tồn tại nhưng chưa được stamp.

Seed chỉ tạo admin khi có mật khẩu trong **process environment**. Ví dụ dưới đây
chỉ dành cho DB local dùng thử; thay credential trước khi chia sẻ môi trường:

```bash
ENVIRONMENT=local \
BOOTSTRAP_ADMIN_EMAIL=admin@jplearn.local \
BOOTSTRAP_ADMIN_PASSWORD=local-admin-password10 \
pnpm db:seed
pnpm dev:api
```

Seed tạo topics/flags và catalog mẫu ở `draft` khi có creator; không tự publish.
Nếu email đã tồn tại, seed không đổi mật khẩu và không nâng quyền user cũ.
Không dùng seed như công cụ reset password. CLI seed đọc URL/environment từ `.env`,
nhưng các biến `BOOTSTRAP_ADMIN_*` và `ALLOW_ADMIN_BOOTSTRAP` phải export cho process.

API chạy tại `http://localhost:3002`; `.env` được đọc theo working directory.
`pnpm dev:api` đã `cd` đúng chỗ. Với lệnh trực tiếp:

```bash
cd apps/api-python
PYTHONPATH=src uv run uvicorn jplearn_api.entrypoints.http.app:app --reload --port 3002
```

`PYTHONPATH=src` là đường chạy editable thống nhất của repo, tránh lỗi `.pth`
hidden trên macOS. Sau thay đổi `pyproject.toml`, chạy lại `uv sync` để cập nhật
console metadata. `PORT` trong Settings không thay thế tham số `--port` của Uvicorn.
Xem [cấu hình](../ops/runbook-backend.md#cấu-hình) cho secrets, storage và CORS.

## 2. Đọc code theo một use case

Ví dụ kết thúc phiên học:

```text
entrypoints/http/routers/sessions.py   nhận HTTP, xác thực và chuyển DTO
  → application/handlers/learning.py  điều phối use case, transaction
  → domain/learning.py                quy tắc phút học, phiên đã kết thúc
  → application/ports/                hợp đồng UoW/repository
  → adapters/persistence/             SQLAlchemy, row locks, PostgreSQL
```

`bootstrap.py` cung cấp factory/adapters. `entrypoints/http/app.py` sở hữu lifecycle
ASGI; `entrypoints/cli/` sở hữu các lệnh vận hành. Các boundary HTTP như xác thực
hiện vẫn có truy vấn ORM; không suy ra rằng mọi truy cập DB đã đi qua handler.
Xem cây thư mục trong [README backend](../../apps/api-python/README.md#package-layout).

## 3. Quy trình thay đổi

1. BA xác nhận FR/UC trong [SRS](../sad/01-survey-srs/srs.md) và
   [traceability](../sad/03-design/traceability.md). Không tự thêm chức năng ngoài phạm vi.
2. Đặt quy tắc nghiệp vụ thuần Python ở `domain/`; workflow ở `application/handlers/`.
   Domain/application không import FastAPI, ORM, config, CLI hoặc tooling.
3. Thêm port khi cần một ranh giới I/O có ý nghĩa; triển khai adapter ở ngoài.
   Wire bằng bootstrap/DI; không tạo adapter trực tiếp trong router.
4. Write use case dùng UoW, explicit commit, rollback-by-default. Không giữ DB
   connection trong lúc stream upload. Không sửa cleanup/cancellation như refactor
   hình thức: cần fault tests cả rollback confirmed và commit outcome unknown.
5. HTTP schemas và error mapping ở `entrypoints/http/`; không trả ORM object ra API.
   Nếu đổi contract, BA/CTO review YAML cùng tests; không nới diff để test xanh.
6. DDL dùng revision Alembic viết tay. Không `create_all`, không autogenerate.
   Baseline Prisma và packaged copy dùng cho adoption của `0001`; không ghi đè
   baseline lịch sử để hợp thức hóa schema mới. Thay schema cần thiết kế lại test
   expected-head/adoption tương ứng, review migration và backup trước rollout.
7. Cập nhật hướng dẫn liên quan, chạy các gate, ghi source revision/dirty status,
   lệnh và exit code. Không ghi chữ ký người chưa review hoặc tuyên bố production-ready.

## 4. Kiểm thử

Từ repo root:

```bash
pnpm test:guard
cd apps/api-python
uv run pytest tests/test_architecture_guard.py tests/test_package_layout.py -q
uv run pytest -q
PYTHONPATH=src uv run python -m jplearn_api.tooling.openapi_diff
uv run pytest tests/test_openapi_diff.py tests/test_openapi_mutation_suite.py -q
```

Pytest tự dựng DB `jplearn_test` cô lập. Nếu truyền `JPLEARN_TEST_DATABASE_URL`,
pathname **phải** là `/jplearn_test` và DB phải dành riêng cho test; tên đúng không
đảm bảo dữ liệu an toàn nếu bạn trỏ nhầm instance. Không truyền URL DB dev/staging.

Từ repo root, test tích hợp toàn stack:

```bash
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
VERIFY_DIR=$(mktemp -d /tmp/jplearn-container-check.XXXXXX)
OUTPUT_DIR="$VERIFY_DIR" IMAGE_TAG=jplearn-api-python:verification \
  apps/api-python/scripts/verify-container.sh
```

E2E supervisor tạo DB/API/web riêng, serialize qua file lock, lưu artifact ngoài
repo. Container gate kiểm tra build, UID 10001, tài nguyên packaged, CLI fail-closed,
schema adoption và probe isolation. Test DB dùng tmpfs; không dùng DB persistent.
Các nhóm test hiện cùng nằm trong `tests/`, không giả định có thư mục `tests/unit/`.

`scripts/benchmark_workloads.py --help` và `scripts/compare_benchmarks.py --help`
là điểm bắt đầu đo hiệu năng; cần cùng harness/dataset/môi trường cho baseline
và candidate, lưu raw samples. Không lấy số trong report cũ làm kết quả lần chạy mới.

## 5. Lỗi local thường gặp

| Hiện tượng | Kiểm tra |
| --- | --- |
| `ModuleNotFoundError` với đường root cũ | Đổi sang `entrypoints.http.app`, `entrypoints.cli.*`, `tooling.openapi_diff`; chạy lại `uv sync` |
| JWT secret quá ngắn | Secret phải ≥32 bytes; shell env ghi đè `.env` |
| Catalog rỗng sau seed | Seed là draft; cần upload, submit QA và admin publish |
| Login admin lỗi | Seed không có mật khẩu mặc định và không reset user đã có |
| `/docs` trả 404 | Chỉ local: bật `OPENAPI_UI=true`, restart API |
| `/ready` 503 nhưng `/health` 200 | Kiểm tra DB và quyền ghi `STORAGE_ROOT`, không kết luận app chết |
| Test không lên DB | Kiểm tra Docker/Compose, URL test và port; không xóa volume dev |

Không commit `.env`, media thật, token, file cá nhân hay sửa evidence lịch sử.
