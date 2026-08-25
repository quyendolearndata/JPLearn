# OKR Quý 1 — chỉ nền tảng

Mục tiêu: **đóng cổng thiết kế và chứng minh xương sống**, không có học viên trả tiền, không có thư viện công khai.

## O1 — Công ty vận hành được như một hệ thống

- KR1: Org, RACI, nhịp họp, DoR/DoD đã dùng trong ≥4 tuần liên tiếp (không chỉ nằm trong repo).
- KR2: 100% task kỹ thuật trên board có mã FR/NFR.
- KR3: Cổng SAD-1 và SAD-2 đã ký.

## O2 — Domain học không bị textbook hóa

- KR1: Pedagogy bible đã ký; rubric CI dùng cho ≥10 clip thí điểm.
- KR2: Schema v1 **không** có `vocabulary_score`, `grammar_lesson_id`, `translation_pair` kênh chính (kiểm bằng review ERD + OpenAPI).
- KR3: Ma trận truy vết không lỗ cho mọi FR nền tảng.

## O3 — Ba bề mặt nói cùng một API

- KR1: Cổng SAD-3 đã ký (C4, ERD, OpenAPI, UI shell).
- KR2: Sau khi được phép scaffold: một user đăng nhập web, iOS/iPad, Android thấy cùng catalog thí điểm.
- KR3: Publish CMS → xuất hiện trên 3 client trong thời gian thỏa `NFR-PERF-001`.

KR2–KR3 của O3 **không** là điều kiện để viết tài liệu này; chúng là mục tiêu sau cổng thiết kế.
