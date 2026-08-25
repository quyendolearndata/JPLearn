# Mẫu ký cổng

Sao chép khối dưới vào cuối artifact khi review. Không ký bằng miệng.

## Cổng SAD-1 — SRS

- Tài liệu: `docs/sad/01-survey-srs/srs.md`
- **Artifact:** có — SRS + in/out scope
- **Chữ ký:** chờ CPO, Pedagogy, CTO (issue #2)
- CPO: tên / ngày / đồng ý phạm vi in-out
- Pedagogy: tên / ngày / đồng ý ràng buộc cấm textbook
- CTO: tên / ngày / đồng ý NFR khả thi

## Cổng SAD-2 — Phân tích

- Tài liệu: `docs/sad/02-analysis/` + [diagrams.md](../sad/02-analysis/diagrams.md)
- **Artifact:** có — use case, diagrams, [event audit](../sad/02-analysis/event-payload-audit.md)
- **Chữ ký:** chờ BA, Pedagogy, CTO (issue #3)
- BA: mọi FR nền tảng map ≥1 use case
- Pedagogy: domain không chứa điểm ngữ pháp/từ vựng như tiến độ
- CTO: domain hiện thực được bằng Hướng A

## Cổng SAD-3 — Thiết kế (được phép scaffold)

- Tài liệu: `docs/sad/03-design/` + spec tổng hợp + [diagrams](../sad/03-design/diagrams.md) + [15 khung](../sad/03-design/wireframes/README.md)
- **Artifact:** có — scaffold + wireframes merged
- **Chữ ký:** chờ CEO, CPO, BA, Pedagogy, CTO (issue #4)
- CEO, CPO, BA, Pedagogy, CTO: năm chữ ký
- Điều kiện: truy vết FR/NFR → use case → API/bảng → test ID

## Cổng nền tảng — được phép SAD vòng học (Phase 5)

Checklist trong spec tổng hợp. Không mở flashcard, dịch, grammar như “thử nghiệm nhỏ”.
