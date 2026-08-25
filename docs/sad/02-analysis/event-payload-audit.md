# Event payload audit — code vs dictionary

Owner: Data. Đối chiếu `apps/api` với [data-dictionary.md](data-dictionary.md). Ngày: 2026-08-25.

## Bảng

| type | Dictionary payload | Code (`sessions.service.ts`) | Khớp |
|---|---|---|---|
| `session_started` | jsonb, không password | `{}` | Có |
| `session_ended` | jsonb | `{}` | Có |
| `minutes_comprehensible` | `minutes` int | `{ minutes }` | Có |
| `level_exposed` | `ci_level` int | `{ ci_level: progress.currentCiLevel }` | Có |

## Ghi chú

- `session_id` FK set khi `record(..., session.id)`.
- Không log `access_token` / password trong payload.
- Phase 5 có thể thêm probe events — migration riêng, không v1.

## Kết luận

Payload hiện tại **khớp dictionary**. Issue #16 có thể Done sau khi QA spot-check trên staging.
