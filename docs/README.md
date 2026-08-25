# JPLearn — bộ tài liệu nền tảng

Ngày: 2026-08-25  
Trạng thái: **bản thiết kế nền tảng, chưa được ký cổng**. Không scaffold mã nguồn platform trước khi cổng SAD-3 đóng.

## Đọc theo thứ tự

1. [Tầm nhìn công ty](company/vision.md)
2. [Pedagogy bible](pedagogy/bible.md) — đầu vào nghiệp vụ, không thay SRS
3. [SAD-1 Khảo sát + SRS](sad/01-survey-srs/srs.md)
4. [SAD-2 Phân tích](sad/02-analysis/use-cases.md)
5. [SAD-3 Thiết kế](sad/03-design/c4.md)
6. [Spec tổng hợp](superpowers/specs/2026-08-25-jplearn-foundation-design.md)
7. [Implementation plan — scaffold platform](superpowers/plans/2026-08-25-jplearn-platform-foundation.md)

## Cổng

| Cổng | Ai ký | Điều kiện |
|---|---|---|
| SAD-1 | CPO, Pedagogy, CTO | SRS có mã, phạm vi in/out rõ |
| SAD-2 | BA, Pedagogy, CTO | Mọi FR nền tảng map ≥1 use case |
| SAD-3 (cổng thiết kế) | CEO, CPO, BA, Pedagogy, CTO | C4 + ERD + OpenAPI + UI shell + truy vết |
| Nền tảng (trước Phase 5) | CEO, CPO, Pedagogy, CTO | 3 client shell + CMS publish + sự kiện học |

Mẫu ký: [company/gates.md](company/gates.md)
