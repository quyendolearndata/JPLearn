# Backend Python — tài liệu hiện hành

Đối chiếu code ngày 2026-09-05. Backend duy nhất là FastAPI/Python 3.12,
PostgreSQL 16 và Alembic; package được tổ chức theo domain/application/adapters/entrypoints.

| Bạn cần làm gì? | Đọc tài liệu |
| --- | --- |
| Cài và chạy nhanh | [README backend](../../apps/api-python/README.md) |
| Sửa code, viết test, thêm use case | [Hướng dẫn phát triển](development.md) |
| Gọi API, đăng nhập, đọc catalog, ghi phiên học | [Hướng dẫn sử dụng API](api-usage.md) |
| Upload, QA, publish và HLS | [Runbook publish](../sad/03-design/runbook-publish.md) |
| Cấu hình, triển khai, theo dõi lỗi, reconciliation | [Runbook vận hành backend](../ops/runbook-backend.md) |
| Backup dữ liệu và phục hồi | [Runbook backup/restore](../ops/runbook-backup-restore.md) |
| Ranh giới triển khai và điều kiện mở traffic | [Deployment](../sad/03-design/deployment.md) |
| Contract và kiểm tra thay đổi API | [OpenAPI](../sad/03-design/openapi.yaml), [semantic diff](../sad/03-design/openapi-diff.md) |
| Kiến trúc và yêu cầu | [C4](../sad/03-design/c4.md), [ADR-006](../sad/03-design/adr-006-clean-architecture.md), [traceability](../sad/03-design/traceability.md) |

## Cách đọc trạng thái

- Code, OpenAPI và các hướng dẫn trên mô tả đường chạy hiện tại.
- [Package-layout verification](../qa/package-layout-refactor.md) ghi lần kiểm tra
  refactor gần nhất: 206 pytest, 10 E2E, 7 container gates; không phải số lượng test
  được bảo đảm cho mọi revision tương lai.
- [Cleanup/performance verification](../qa/clean-architecture-audit/cleanup-fix-verification.md)
  ghi các giới hạn và review hiệu năng còn mở.
- R-09 Operational Acceptance vẫn **HOLD**. Có Dockerfile và test local xanh không
  đồng nghĩa staging HTTPS, soak, canary hoặc rollback drill đã được nghiệm thu.
- `docs/qa/`, các plan đã hoàn thành và phần chữ ký ADR là bằng chứng theo revision.
  Không chạy máy móc lệnh cũ trong đó; dùng hướng dẫn hiện hành. Tài liệu này không
  cấp chữ ký thay CTO/BA/QA/Ops.

Quyền sở hữu: Platform duy trì hướng dẫn code/API; BA đối chiếu FR/UC và contract;
Ops duy trì runbook; CTO quyết định kiến trúc và release; QA lưu bằng chứng thực thi.

## Kiểm tra bản cập nhật tài liệu

Ngày 2026-09-05: bảng API usage và ADR-006 khớp 20 operations sinh từ runtime;
liên kết file local trong tài liệu cập nhật không bị gãy; `.env.example` vượt
Settings validation; guard và OpenAPI diff PASS. Nhóm regression auth/catalog/
session/HLS/health/seed/migrate/contract/package-layout: **59 passed, 2 warnings**.
Các ví dụ shell được kiểm tra cú pháp, không chạy các lệnh deploy/backup/restore/
reconciliation-delete. Đây không phải restore drill hoặc nghiệm thu vận hành.
