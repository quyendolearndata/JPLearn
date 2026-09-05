# Deployment — backend hiện hành và hạ tầng còn chờ

Đối chiếu 2026-09-05. Xem [runbook backend](../../ops/runbook-backend.md) để chạy
artifact/configure probes và [backup/restore](../../ops/runbook-backup-restore.md).

| Môi trường | Web | API | Mobile |
|---|---|---|---|
| Local | Next.js :3000 | FastAPI :3002 + PostgreSQL 16 Docker | Expo |
| Staging (yêu cầu, chưa nghiệm thu) | Preview URL được cấp | HTTPS proxy + image Python + DB/storage độc lập | TestFlight/internal Android theo kế hoạch |
| Prod | Không mở traffic từ tài liệu này | R-09 HOLD | Không Q1 |

## CI đã có và CD chưa được chứng minh

- `.github/workflows/ci.yml`: job monorepo tests/guard, Python pytest trên PostgreSQL,
  Alembic upgrade + OpenAPI diff, container verification + artifact upload.
- Full differential Web E2E có lệnh riêng trong README; không coi nó đã nằm trong
  CI này chỉ vì chạy local xanh. Không khẳng định có lint/typecheck job khi YAML chưa có.
- Chưa có bằng chứng trong workflow này cho tự động provision staging HTTPS,
  web preview, mobile release theo tag, canary hoặc rollback. Đây là yêu cầu vận hành,
  không phải chức năng CD đã triển khai.
- Dockerfile chạy non-root UID 10001, CLI/API dùng chung image; không tự chạy migration.
  Runtime filesystem là `LocalFilesystemStorage`, cần mount persistent.

## Observability

- `NFR-OBS-001`: request id header, log JSON cho 5xx, alert qua `ALERT_WEBHOOK_URL`
  (default tắt; Ops cấp URL và kiểm chứng delivery).
- Không log access_token, password.
- Liveness `/health`; readiness `/ready` kiểm tra PostgreSQL + quyền ghi storage.
  Readiness không kiểm tra schema/media đầy đủ hoặc quarantine UoW.

## OpenAPI / docs UI (ADR-003 D8)

- Contract: `docs/sad/03-design/openapi.yaml` trong git ([openapi-diff.md](openapi-diff.md)).
- Staging và prod: **tắt** `/docs`, `/redoc`, `/openapi.json` public.
- Local: được bật.
- Đây là policy triển khai: `OPENAPI_UI=false` phải được đặt/kiểm tra bởi Ops;
  runtime không tự từ chối giá trị true trong staging.

## Media

- MP4 + signed URL và HLS local đã có đường chạy/test; HLS được tạo offline bằng
  `apps/api-python/scripts/transcode-hls.sh`, không phải background transcoding service.
- Object storage ngoài filesystem/CDN là hướng triển khai, chưa phải adapter đang chạy.
- R-09 vẫn cần staging độc lập, soak/budget review, backup/restore drill,
  canary/rollback và chữ ký Ops/CTO. Không biến PASS kỹ thuật thành quyền mở traffic.
