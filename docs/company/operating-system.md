# Hệ điều hành công ty

## Nhịp tuần

| Khi | Ai | Việc |
|---|---|---|
| Thứ Hai 30 phút | CEO, CPO, BA, CTO, Content, Pedagogy | Blocker nền tảng + lỗ truy vết SRS |
| Chu kỳ 2 tuần | Toàn bộ Sóng 1 | Planning theo workstream **và mã FR/NFR**; review artifact SAD hoặc shell, không demo “bài học” |
| Thứ Tư | Content, Pedagogy, Production | Standup nhà máy clip thí điểm |
| Thứ Năm | Design, CPO, BA, Mobile/Web | Critique design system; iPad ≠ phone |
| Thứ Sáu | CEO, Ops, CTO | Rủi ro pháp lý, media, tuyển |

## Nhịp tháng

Business review: ngân sách nội dung vs kỹ thuật, sóng tuyển, số clip thí điểm đi hết pipeline (không dùng MAU).

## Nhịp quý

OKR. Quý 1 chỉ OKR nền tảng — xem [okr-q1.md](okr-q1.md).

## Definition of Ready

Board và cách dịch DoR sang field: [board.md](board.md).

Một task được kéo vào sprint khi có:

1. Owner và RACI
2. Tiêu chí chấp nhận
3. Bề mặt ảnh hưởng: web / phone / iPad / CMS / API / docs
4. Mã SRS (`FR-*` hoặc `NFR-*`) nếu là việc kỹ thuật
5. Không vi phạm [pedagogy bible](../pedagogy/bible.md)

## Definition of Done (nền tảng)

1. Chạy trên staging (hoặc artifact docs đã review)
2. Có kiểm chứng: test tự động hoặc checklist QA trỏ mã FR/NFR
3. Phòng khác dùng được (README hoặc contract)
4. Nếu đụng domain học: sự kiện đã đăng ký trong data dictionary — kể cả khi UI chỉ là shell
