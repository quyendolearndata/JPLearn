# Deployment

| Môi trường | Web | API | Mobile |
|---|---|---|---|
| Local | Next.js dev | API dev + Postgres | Expo |
| Staging | Preview URL | `api.staging` HTTPS | TestFlight + internal Android track |
| Prod | Không Q1 | Không Q1 | Không Q1 |

## CI/CD (sau scaffold)

- PR: lint, typecheck, test API, OpenAPI diff không thêm field cấm.
- Web preview mỗi PR.
- Mobile: build nội bộ khi tag `staging-*`.

## Observability

- `NFR-OBS-001`: request id header, log JSON, alert 5xx staging qua webhook stub — bật bằng env `ALERT_WEBHOOK_URL` (default tắt; Ops cấp URL kênh thật).
- Không log access_token, password.

## Media

- Q1 thí điểm: object storage + MP4 URL ký (xem ADR).
- Trước cổng nền tảng / P5: HLS.
