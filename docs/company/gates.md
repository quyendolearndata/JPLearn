# Mẫu ký cổng

Sao chép khối dưới vào cuối artifact khi review. Không ký bằng miệng.

## Cổng SAD-1 — SRS

- Tài liệu: `docs/sad/01-survey-srs/srs.md`
- **Artifact:** có — SRS + in/out scope
- **Chữ ký:** đã ký 2026-08-25 — CPO, Pedagogy, CTO (issue #2)
- CPO: tên / ngày / đồng ý phạm vi in-out
- Pedagogy: tên / ngày / đồng ý ràng buộc cấm textbook
- CTO: tên / ngày / đồng ý NFR khả thi

## Cổng SAD-2 — Phân tích

- Tài liệu: `docs/sad/02-analysis/` + [diagrams.md](../sad/02-analysis/diagrams.md)
- **Artifact:** có — use case, diagrams, [event audit](../sad/02-analysis/event-payload-audit.md)
- **Chữ ký:** đã ký 2026-08-25 — BA, Pedagogy, CTO (issue #3)
- BA: mọi FR nền tảng map ≥1 use case
- Pedagogy: domain không chứa điểm ngữ pháp/từ vựng như tiến độ
- CTO: domain hiện thực được bằng Hướng A

## Cổng SAD-3 — Thiết kế (được phép scaffold)

- Tài liệu: `docs/sad/03-design/` + spec tổng hợp + [diagrams](../sad/03-design/diagrams.md) + [15 khung](../sad/03-design/wireframes/README.md)
- **Artifact:** có — scaffold + wireframes merged
- **Chữ ký:** đã ký 2026-08-25 — CEO, CPO, BA, Pedagogy, CTO (issue #4)
- CEO, CPO, BA, Pedagogy, CTO: năm chữ ký
- Điều kiện: truy vết FR/NFR → use case → API/bảng → test ID

## Cổng nền tảng — được phép SAD vòng học (Phase 5)

Checklist trong spec tổng hợp. Không mở flashcard, dịch, grammar như “thử nghiệm nhỏ”.

**Chữ ký:** chưa — chờ #14–#17 (e2e, HLS, UC-L06) và pipeline clip đầu tiên.

---

## Chữ ký (2026-08-25)

### Cổng SAD-1
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi in/out SRS
- Pedagogy — Quyen Do — 2026-08-25 — Đồng ý ràng buộc cấm textbook
- CTO — Quyen Do — 2026-08-25 — Đồng ý NFR khả thi

### Cổng SAD-2
- BA — Quyen Do — 2026-08-25 — Mọi FR nền tảng map ≥1 use case
- Pedagogy — Quyen Do — 2026-08-25 — Domain không có điểm ngữ pháp/từ vựng như tiến độ
- CTO — Quyen Do — 2026-08-25 — Domain hiện thực được bằng Hướng A

### Cổng SAD-3
- CEO — Quyen Do — 2026-08-25 — Đồng ý scaffold theo thiết kế
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi scaffold
- BA — Quyen Do — 2026-08-25 — Truy vết FR/NFR → UC → API/bảng → test
- Pedagogy — Quyen Do — 2026-08-25 — Shell không vi phạm bible
- CTO — Quyen Do — 2026-08-25 — ADR-001 + OpenAPI + schema đúng
