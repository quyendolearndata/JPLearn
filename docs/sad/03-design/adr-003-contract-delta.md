# ADR-003 — Contract delta (BA sở hữu)

- Ghế: **BA** · Ngày: 2026-08-31 · Kèm: [ADR-003](adr-003-runtime-python.md)
- ADR-003 **Accepted** 2026-08-31. **Đã áp** SRS / UC-L01 / traceability / OpenAPI theo bảng dưới. D10 vẫn `KNOWN_DEBT_CARRIED` (comment trong `sessions.service.ts`).
- Mục đích: phân loại drift **trước** khi lấy contract baseline. Mỗi dòng một hành động, không “sửa câu chữ”.

## Phân loại (bắt buộc dùng đúng bốn nhãn)

| Nhãn | Nghĩa | Artifact phải đụng |
|---|---|---|
| `CONTRACT_FIX_TO_RUNTIME` | Contract/docs sai, runtime+test đúng → sửa OpenAPI (và docs thiết kế nếu cần) cho khớp hành vi đang chạy | OpenAPI, có khi traceability Test |
| `RUNTIME_FIX_TO_CONTRACT` | Runtime lệch contract đã ký → sửa NestJS trước khi port | code Nest + test |
| `INTENTIONAL_REQUIREMENT_CHANGE` | Đổi yêu cầu đã ghi ở SRS (và chuỗi SAD) | **SRS → use case → traceability → OpenAPI** theo thứ tự đó; phiên ký SAD-1/SAD-2 nếu FR đổi nghĩa |
| `KNOWN_DEBT_CARRIED` | Biết là sai/yếu, **cố ý không đổi semantics** trong lúc replatform | card nợ + test freeze hành vi hiện tại |

Không dùng nhãn `KEEP CURRENT`.

## Bảng delta

| # | Phát hiện | Runtime / test | Contract / SRS | Nhãn đề xuất | Hành động sau khi ký |
|---|---|---|---|---|---|
| D1 | `POST /staff/media/{id}/hls` | `hls.e2e-spec.ts` expect **201** | OpenAPI `responses: "200"` | `CONTRACT_FIX_TO_RUNTIME` | Sửa OpenAPI thành 201 |
| D2 | HLS playback chấp nhận signed query | `media-access.guard.ts` + rewrite `exp`/`sig` trên từng URI m3u8 (#40); hls.js không gửi Bearer | OpenAPI `/media/{id}/hls/{file}` chỉ `security: [{ bearerAuth: [] }]`, không khai `exp`/`sig` | `CONTRACT_FIX_TO_RUNTIME` | OpenAPI: Bearer **hoặc** cặp `exp`+`sig` (cùng pattern `/media/{id}`) |
| D3 | Logout vô hiệu hoá **mọi** token của user | `AuthService.logout` increment `tokenVersion`; JWT claim `ver`; `jwt.guard.ts` so với DB | SRS FR-ID-003 «đăng xuất trên thiết bị hiện tại»; UC-L01 hậu điều kiện cùng câu; OpenAPI `204` «Logged out this device» | `INTENTIONAL_REQUIREMENT_CHANGE` | Phê duyệt rồi: sửa FR-ID-003 + UC-L01 + OpenAPI description + T-ID-003 thành **logout toàn bộ thiết bị** (đổi schema per-device **không** nằm trong ADR-003) |
| D4 | Chỉ Admin publish | `@Roles("admin")` trên publish/unpublish; OpenAPI `403: Admin only`; UC-A01 / `processes.md` đã ghi policy v1 Admin | SRS FR-CMS-002 «giáo viên hoặc admin» | `INTENTIONAL_REQUIREMENT_CHANGE` | Phê duyệt rồi: sửa **chỉ SRS** FR-CMS-002 cho khớp UC-A01 (use case đã đúng runtime) |
| D5 | `title_internal` bắt buộc ở DB + `CreateCatalogInput` | Prisma `titleInternal String`; create không default | `CatalogItemWrite.required` **không** gồm `title_internal` | `CONTRACT_FIX_TO_RUNTIME` | Thêm `title_internal` vào `required` |
| D6 | Validation `ci_level` | Create: không range-check (Prisma `Int`); query `GET /catalog?ci_level=` parse integer, **không** min/max 0–4 | Public item / progress: `current_ci_level` 0–4; `CatalogItemWrite.ci_level` **không** min/max; query catalog có min 0 max 4 | `CONTRACT_FIX_TO_RUNTIME` (query đã ghi) + ghi rõ write: **không** range-check v1 — test freeze; **không** để Pydantic tự 422 trên create nếu Nest đang 201 | Align write schema với runtime (không thêm min/max nếu Nest không enforce); giữ min/max trên query param |
| D7 | `/health`, `x-request-id`, error body | `GET /health` → `{ok:true}`; interceptor echo `x-request-id`; Nest validation/HTTP `{statusCode,message,error}` | OpenAPI **không** có `/health`; không spec header request-id; không schema lỗi chung | `CONTRACT_FIX_TO_RUNTIME` | Thêm `/health`; header `x-request-id` (echo); schema lỗi 400/401/403/404 khớp Nest — **không** 422 FastAPI mặc định |
| D8 | `/docs`, `/redoc`, `/openapi.json` | Nest không expose Swagger UI | FastAPI mặc định mở | `CONTRACT_FIX_TO_RUNTIME` (chính sách mới, ghi vào OpenAPI/deployment) | Staging + prod: **tắt** docs UI và không public `/openapi.json` ra internet; local dev được bật. Contract test đọc file `openapi.yaml` trong repo, không phụ thuộc endpoint công khai |
| D9 | OpenAPI 3.0.3 vs FastAPI 3.1.0 | — | `openapi: 3.0.3` | (quy tắc diff, không đổi runtime) | Semantic **normalized** diff: giữ status, required/nullability, security, `operationId`, `x-jplearn-fr`, error schema. Allowlist: phiên bản 3.0↔3.1 (`nullable` vs type union), tên component sinh, `servers`, `info`. **Cấm** lệch status / required / security |
| D10 | Hai `end()` đồng thời có thể cộng phút hai lần | `sessions.service.ts`: đọc `endedAt` **ngoài** `$transaction`, rồi increment phút trong transaction | FR-PRG-001 không spec concurrency | `KNOWN_DEBT_CARRIED` | Port nguyên semantics (kể cả race). **Cấm** «sửa hộ» chỉ ở Python. Muốn hết race: card riêng, **sửa Nest trước**, rồi port — nhãn lúc đó thành `RUNTIME_FIX_TO_CONTRACT` trên hành vi tiến độ |

## Chuỗi cập nhật khi D3/D4 được phê duyệt

1. `docs/sad/01-survey-srs/srs.md` (FR-ID-003, FR-CMS-002)
2. `docs/sad/02-analysis/use-cases.md` (UC-L01; UC-A01 đã khớp D4)
3. `docs/sad/03-design/traceability.md` (cột Test T-ID-003 mô tả)
4. `docs/sad/03-design/openapi.yaml`
5. Chạy lại contract baseline trên NestJS

Pedagogy ký ADR-003 vì D3 đổi nghĩa phiên; không đụng bible/FR-NEG.

## Nợ không nằm trong delta này

- #30 UC-L06 native — exception cổng nền tảng, không phải drift OpenAPI.
- Harness Docker test API đang sửa dở — chặn Phase 1, không phải FR.
