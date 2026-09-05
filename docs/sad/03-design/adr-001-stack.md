# ADR-001 — Stack nền tảng (Hướng A)

- Trạng thái: Accepted (ký cổng SAD-3 2026-08-25). **Superseded một phần** bởi [ADR-003](adr-003-runtime-python.md) (2026-08-31): runtime API được phép FastAPI; web/Expo/Postgres/storage/`/staff` giữ nguyên.
- Ngày: 2026-08-25

## Quyết định

Monorepo TypeScript: Next.js (web + CMS route), Expo (iOS, iPad, Android), NestJS API, PostgreSQL, object storage cho media.

Từ chối Hướng B (Swift+Kotlin tách) vì chi phí team. Từ chối Hướng C (PWA-only) vì iPad/phone media và layout.

## Hệ quả

- Một ngôn ngữ, một OpenAPI, ba client mỏng.
- Phải discipline iPad layout (NFR-XPLAT-002).
- Native module đặc biệt (sau này mic) qua Expo — không cần Q1.

## Media Q1 vs cổng nền tảng

- Q1 thí điểm: MP4 trên storage, URL ký, đủ FR-CMS-003.
- Trước cổng nền tảng / Phase 5: HLS (`NFR-PERF-002`).

## CMS

v1: `/staff` trên web, role-gated. Không Notion làm nguồn sự thật. Không bắt buộc Sanity/Strapi ở Q1; ADR-002 chỉ khi editorial outgrow `/staff`.

## Cấm

Package hay bảng `flashcards`, `grammar_lessons`, `translations` kênh learner.
