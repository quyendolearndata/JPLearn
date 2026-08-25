# Họp kiến trúc — 2026-08-25

Tham dự (ghế): CEO, CPO, BA, CTO, Platform, Pedagogy, Design (handoff Web/Mobile/QA).  
Artifact cạnh chat: canvas họp (mở trong Cursor).

## Quyết định

1. **Kiến trúc so với SAD-3 / ADR-001: chuẩn** — modular monolith Nest, Next `/staff`, Expo, Postgres, không module cấm, client mỏng, flags mặc định `false`.
2. **Kiến trúc so với cổng nền tảng: chưa chuẩn** — disk local, playback JWT localhost (chưa URL ký), HLS opt-in chưa phát trên client, UC-L06 native PARTIAL, NFR-OBS/A11Y chưa đủ.
3. **CEO: đã mở phiên ký cổng nền tảng** — HOLD rút 2026-08-25; bốn ghế đã ký trên [gates.md](../gates.md) kèm exception (HLS, URL ký, native). FR-NEG vẫn cấm.
4. **FR-NEG vẫn cấm.** Phase 5 (SAD vòng học) **được phép thiết kế** sau cổng; không tự bật flag / flashcard.

## Pattern đang áp dụng

| Áp dụng | Không áp dụng (và Q1 không đòi) |
|---|---|
| Modular monolith; module theo bounded context (packing Events/Progress lệch C4 L3) | Repository interface |
| Layered controller → service → Prisma | CQRS |
| DI NestJS + `@Inject` (tsx) | Event sourcing (`LearningEvent` = audit) |
| Guard/RBAC; mapper `to-public` | Hexagonal / ports |
| Feature flags (API); thin client; CMS-in-app | Object storage + URL ký — **nợ ADR** |
| Catalog state machine `draft → level_qa → published` | |

Chi tiết file: `apps/api/src/app.module.ts`, `catalog/to-public.ts`, `media/local-storage.ts`, `auth/jwt.guard.ts`.

## Brief 19 ghế (một việc / không làm)

| Ghế | Tuần này | Không làm |
|---|---|---|
| CEO | Đã ký cổng nền tảng | Không tuyển 3 team native; không flashcard demo |
| CPO | Checklist cổng thật; cấm card `FR-LRN-*` | Exception native lên board |
| BA | Cột PASS/PARTIAL/GAP/Deferred-P5 trên ma trận | Thêm FR Phase 5 vào SRS |
| Pedagogy | Rubric 2 clip (rửa tay + 1 Veo) | Nới 70–95s; probe/nói |
| Pedagogy QA | Duyệt chrome không L1/grammar | Publish catalog |
| Design | iPad S-SESSION = `spaceIpad` | Màn ngữ pháp / player CI |
| Content | Ghi nguồn Commons; freeze 11 item | Nhảy QA |
| Teacher | Khớp 10 MP4 ↔ 10 script | Brief mới / field L1 |
| Production | Freeze shoot | Quay người thật tuần này |
| CI Level QA | Pass/fail tay 10 clip (hình gánh nghĩa) | Tự published |
| CTO | HLS + URL ký đúng NFR-PERF-002 | Tuyên bố HLS local = cổng |
| Platform | `StoragePort` + signed URL; packing EventsModule; log 5xx | Route P5 |
| Web | `useFlags()` trên chrome (FR-FLG-002) | Player CI |
| Mobile | Một lần Expo Go = cùng catalog/phút với web | iPad = phone phóng to |
| Data | Giữ dictionary | Dashboard MAU |
| QA | Gói #17 PARTIAL native, không che Done | Claim 3 native UI pass |
| Growth | Positioning im | Campaign |
| CS | FAQ tester 5 dòng | Khuyên Anki/ngữ pháp |
| Ops | CC BY-SA 2.0 rửa tay; Veo thí điểm | Clip người thật thiếu form |

## P0 trước cổng (có FR)

- **FR-CMS-003/004** — signed URL, không JWT-only localhost.
- **NFR-OBS-001** — request id + alert 5xx.
- **FR-FLG-002** — web `useFlags()`.
- **NFR-XPLAT-002** — iPad session/progress.
- **FR-ID-002, FR-PRG-004** — UC-L06 máy thật.

Người ký cổng tiếp: BA recommend khi checklist trên xong, rồi CEO mở phiên ký trên [gates.md](../gates.md).
