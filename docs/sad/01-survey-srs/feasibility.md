# Feasibility

## Kỹ thuật — khả thi (Hướng A)

Một API + PostgreSQL + Next.js + Expo phủ web, iOS, iPad, Android. Rủi ro: layout iPad bị bỏ quên nếu chỉ test phone — mitigations: breakpoint bắt buộc trong DoD, device lab iPad.

Media HLS: khả thi qua object storage + transcode managed (hoặc pipeline tối thiểu cho thí điểm: MP4 progressive, HLS trước khi học viên thật). Thí điểm Q1 được phép MP4 nếu ADR ghi rõ; HLS là NFR trước cổng nền tảng.

## Nội dung — khả thi có điều kiện

10–20 clip level 0–1 là đủ stress-test pipeline. Phụ thuộc giáo viên bản ngữ part-time + quyền quay. Không khả thi nếu kỳ vọng thư viện 500 clip trong Q1 — **không nằm phạm vi**.

## Pháp lý

Mọi clip thí điểm: giấy phép người xuất hiện, nhạc, địa điểm. Cấm nhặt YouTube của người khác đưa vào CMS. PII tài khoản thử: mật khẩu hashed, không log token.

## Vận hành

Sóng 1 đủ để **viết SAD và vận hành pipeline tay**. Không đủ để support 10k user — không cần Q1.

## Kết luận

Go cho nền tảng. No-go cho “app học đầy đủ” trong cùng quý. Rủi ro chính: trượt sang flashcard vì cảm thấy “trống”. Cổng pedagogy + schema cấm là biện pháp.
