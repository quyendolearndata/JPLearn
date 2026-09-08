# JPLearn — bộ tài liệu nền tảng

Cập nhật hiện trạng: 2026-09-05. Backend hiện là FastAPI + Alembic, đã refactor
package theo ADR-006; không còn chờ scaffold Phase 0. Bắt đầu ở
[tài liệu backend hiện hành](backend/README.md): sử dụng API, phát triển và vận hành.

Lịch sử ký cổng nằm ở [gates.md](company/gates.md), không đại diện cho mọi revision
sau đó. Engineering còn review hiệu năng; R-09 Operational Acceptance vẫn **HOLD**.
Xem [ADR-006](sad/03-design/adr-006-clean-architecture.md) và
[verification refactor](qa/package-layout-refactor.md). Không cấp lại chữ ký từ việc cập nhật docs.

## Đọc theo thứ tự

1. [Tầm nhìn công ty](company/vision.md)
2. [Pedagogy bible](pedagogy/bible.md) — đầu vào nghiệp vụ, không thay SRS
3. [SAD-1 Khảo sát + SRS](sad/01-survey-srs/srs.md)
4. [SAD-2 Phân tích](sad/02-analysis/use-cases.md) — [sơ đồ](sad/02-analysis/diagrams.md)
5. [SAD-3 Thiết kế](sad/03-design/c4.md) — [sơ đồ](sad/03-design/diagrams.md) · [wireframes](sad/03-design/wireframes/README.md)
6. [Spec tổng hợp](superpowers/specs/2026-08-25-jplearn-foundation-design.md)
7. [Implementation plan — scaffold platform](superpowers/plans/2026-08-25-jplearn-platform-foundation.md)
8. [Board — task theo ghế](company/board.md) — GitHub Projects · [sync 2026-08-25](company/sync/2026-08-25-q1-planning.md)
9. [OKR/KPI theo ghế Q1](company/okr-q1-by-seat.md)
10. [Agents theo ghế](../.cursor/agents/README.md)

## Cổng

| Cổng | Ai ký | Điều kiện |
|---|---|---|
| SAD-1 | CPO, Pedagogy, CTO | SRS có mã, phạm vi in/out rõ |
| SAD-2 | BA, Pedagogy, CTO | Mọi FR nền tảng map ≥1 use case |
| SAD-3 (cổng thiết kế) | CEO, CPO, BA, Pedagogy, CTO | C4 + ERD + OpenAPI + UI shell + truy vết |
| Nền tảng (trước Phase 5) | CEO, CPO, Pedagogy, CTO | 3 client shell + CMS publish + sự kiện học |

Mẫu ký: [company/gates.md](company/gates.md)
