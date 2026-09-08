# Runbook vận hành backend FastAPI

Owner: Ops + Platform; reviewer cần có CTO và QA. Đây là hướng dẫn vận hành theo
code hiện tại, **không phải biên bản nghiệm thu staging**. R-09 vẫn HOLD.
Tham chiếu [deployment](../sad/03-design/deployment.md),
[backup/restore](runbook-backup-restore.md), [API usage](../backend/api-usage.md).

## Cấu hình

Runtime đọc `Settings` từ process env rồi `.env` tại working directory. Đặt
`ENVIRONMENT` tường minh khi triển khai; không dựa vào default `local`.

| Biến | Hành vi và yêu cầu |
| --- | --- |
| `ENVIRONMENT` | `local`, `test`, `staging`, `production`; runtime mặc định local |
| `DATABASE_URL` | PostgreSQL; không in URL có mật khẩu vào log/evidence |
| `JWT_SECRET` | Bắt buộc ≥32 bytes; staging/production từ secret manager, không dùng mẫu local |
| `API_PUBLIC_URL` | Local `http://localhost:3002`; staging/production bắt buộc HTTPS; dùng để tạo signed URL |
| `MEDIA_SIGNING_SECRET` | Staging/production bắt buộc khác JWT secret; local/test có fallback JWT |
| `STORAGE_ROOT` | Đường dẫn tuyệt đối; mặc định `cwd/storage`; container dùng mount `/app/storage` |
| `CORS_ORIGINS` | JSON array; staging/production cần danh sách HTTPS tường minh, không `*`/`null` |
| `CORS_ORIGIN_REGEX` | Local cho loopback/Expo; staging chỉ regex hẹp đã review, tốt nhất bỏ |
| `OPENAPI_UI` | Mặc định false; Ops phải giữ false ngoài local — code không tự cấm bật ở staging |
| `ALERT_WEBHOOK_URL` | Mặc định tắt; cấp endpoint thật và kiểm thử delivery trước nghiệm thu |
| `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` | CLI seed đọc từ process env, không tự lấy từ Settings |
| `ALLOW_ADMIN_BOOTSTRAP` | Không bật trong production runbook; xem giới hạn bootstrap bên dưới |
| `ALLOW_DESTRUCTIVE_DOWNGRADE` | Chỉ cho thao tác đã được duyệt; không phải quyền mở traffic hoặc data rollback |

CLI migrate/seed dùng resolver riêng: URL explicit → process env → `.env`.
Destructive downgrade cần environment có nguồn cấu hình rõ. Các opt-in flags
và bootstrap credentials phải nằm trong process env, không chỉ ghi ở `.env`.

## Khởi động và triển khai artifact

Local source: làm theo [development](../backend/development.md). Compose hiện chỉ
có PostgreSQL `db`/`db-test`, không tự chạy backend hoặc provision staging.

Build từ repo root:

```bash
docker build -t jplearn-api-python:local apps/api-python
```

Ví dụ chạy trên **Docker Desktop local**, sau khi DB đã migrate và thư mục storage
đã tồn tại, có quyền đọc/ghi phù hợp. Bind đúng storage mà DB dev đang tham chiếu:

```bash
docker run --rm --name jplearn-api-local --stop-timeout 30 \
  -p 127.0.0.1:3002:3002 \
  --env-file apps/api-python/.env \
  -e ENVIRONMENT=local \
  -e DATABASE_URL=postgresql://jplearn:jplearn@host.docker.internal:5432/jplearn \
  -e STORAGE_ROOT=/app/storage \
  --mount "type=bind,source=$PWD/apps/api-python/storage,target=/app/storage" \
  jplearn-api-python:local
```

Linux cần endpoint/network DB riêng; không mặc định `host.docker.internal` tồn tại.
Không chạy đồng thời dev server khác chiếm :3002. Container chạy UID 10001;
pre-provision quyền mount theo owner, không dùng `chmod 777`/chown rộng trên media thật.
Không lưu media duy nhất vào writable layer của container. Giữ cặp DB + storage
khi chuyển môi trường; database trỏ `.bin`/HLS không có trong mount là lỗi dữ liệu.

Image mặc định chạy `uvicorn jplearn_api.entrypoints.http.app:app --port 3002`;
đổi env `PORT` không tự đổi CMD. Tên console `jplearn-migrate`, `jplearn-seed`,
`jplearn-openapi-diff` không đổi. Image không tự migrate/seed, không chứa ffmpeg,
không có TLS termination hoặc deployment/canary automation tích hợp.

Staging/production cần một release được phê duyệt riêng: image digest, secrets,
TLS proxy, DB/storage persistent, backup, migration job duy nhất, probe routing,
stop timeout và rollback target. Không sao chép nguyên ví dụ local sang production.

## Migration và bootstrap

Từ `apps/api-python`, xác nhận đúng DB và có backup trước mọi ghi DDL:

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate current
# Chỉ DB mới trống, hoặc DB đã được Alembic quản lý:
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate upgrade head
```

Với DB Prisma cũ chưa có Alembic version, chạy adoption **sau backup**:

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.migrate stamp 0001_prisma_baseline
```

CLI so schema live với baseline packaged, từ chối DB trống/mismatch trước stamp.
Không bypass verification, không dùng `alembic stamp` trần, không sửa baseline để
che mismatch. Stamp chỉ ghi version, không tạo bảng và không sửa schema lệch.

Guard downgrade hiện nhận diện `base` và revision tương đối âm (`-1`, `-all`, …),
không phân tích nội dung SQL của mọi named revision. Vì vậy **mọi downgrade đều
cần review**, không coi việc CLI cho chạy là bằng chứng an toàn. Environment thiếu
hoặc sai chặn các dạng destructive này kể cả có opt-in; local/test tường minh có
thể chạy, staging/production cần thêm flag. Runbook thông thường không dùng downgrade
để rollback release; xem [backup/restore](runbook-backup-restore.md).

Seed không tự tạo admin nếu thiếu password, không đổi password/status có sẵn,
không nâng role cho email đã tồn tại. Runtime Settings cấm admin bootstrap ở
production, nhưng CLI seed có validation riêng và có thể cho phép với opt-in.
Không dựa vào runtime validator để bảo vệ CLI; runbook này **không cho bootstrap
production**. Provision/reset quản trị cần quy trình Ops riêng đã duyệt.

## Probes, log và sự cố

```bash
curl -fsS http://localhost:3002/health
curl -sS -i http://localhost:3002/ready
```

| Dấu hiệu | Hành động kiểm tra |
| --- | --- |
| `/health` không đáp ứng | Process, port, proxy, startup validation |
| `/ready` 503, `database:down` | Connectivity, credentials, pool và DB health |
| `/ready` 503, `storage:down` | Mount đúng path, UID 10001, disk/inode/quota, quyền tạo/xóa probe |
| Readiness 200 nhưng ghi lỗi | Probe chỉ `SELECT 1` + storage I/O; không xác minh schema, media đầy đủ hoặc UoW admission |
| 5xx | Tìm theo `x-request-id`, error class, log JSON middleware; không paste token/password |
| `storage_cleanup_failed` | Giữ object, kiểm tra filesystem và tác vụ cleanup, không xóa hàng loạt |
| `media_upload_commit_outcome_unknown` | Đối chiếu DB/storage; không xóa file khi kết quả COMMIT chưa rõ |
| UoW cleanup quarantined / `uow_shutdown_cleanup_pending` | Ngừng traffic mới, giữ evidence; đợi settlement, dùng process supervisor nếu I/O không kết thúc |

Middleware có log JSON cho 5xx, không phải full access-log JSON cho mọi request.
Alert webhook default tắt; cấu hình URL không chứng minh đã delivery thành công.
Proxy/access logs cũng phải loại query `sig`, Authorization và PII.
Quarantine có thể chặn transaction mới trên cùng event loop; shutdown đợi tối đa
5 giây rồi báo lỗi nếu còn cleanup để tránh dispose đồng thời. `/ready` hiện
không kiểm tra quarantine. Không giả định restart/kill đã giải quyết COMMIT không rõ.

## Reconciliation media

Từ `apps/api-python`, với DB/storage cùng môi trường đã xác minh:

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.reconciliation --dry-run
```

Mặc định chỉ báo cáo. Object chưa đủ 24 giờ, metadata không rõ hoặc mtime tương lai
được bảo vệ. `.part`, HLS và probe keys bị loại khỏi pool dọn orphan; lệnh này
không dọn toàn bộ loại file và không tự phục hồi missing media.
CLI in thống kê; nếu cần từng key, Platform dùng kết quả handler/read-only inspection,
không kết luận từ số lượng rằng file nào có thể xóa.

Chỉ sau review danh sách/backup và kiểm tra không còn upload/COMMIT chưa xác định:

```bash
PYTHONPATH=src uv run python -m jplearn_api.entrypoints.cli.reconciliation \
  --execute --confirm-retention-exceeded --retention-hours 24
```

Đây là lệnh xóa thật, không có trash/undo; tuổi file không thay thế xác nhận vận hành.
Lệnh có recheck tham chiếu DB nhưng không phải khóa toàn cục với mọi writer.
Không lên lịch tự động xóa khi chưa có retention policy và bằng chứng an toàn.

## Điều kiện mở traffic

Giữ HOLD cho tới khi Ops/CTO có staging HTTPS độc lập, backup/restore drill,
soak và budget hiệu năng, canary/rollback có bằng chứng, monitoring/alert delivery,
secrets/CORS/storage review. Local container/E2E PASS chỉ là đầu vào kỹ thuật,
không ký thay cho các điều kiện đó.
