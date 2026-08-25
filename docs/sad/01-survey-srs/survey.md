# SAD-1 — Khảo sát hiện trạng

Owner: BA  
Đầu vào: [vision](../../company/vision.md), [bible](../../pedagogy/bible.md)

## As-is — người lớn Việt học tiếng Nhật hôm nay

| Kênh | Việc làm | Hệ quả |
|---|---|---|
| Lớp / gia sư | Ngữ pháp + dịch + giáo trình | Nghe thực tế yếu; im lặng bị phạt |
| App JLPT / Anki | Thẻ, quiz, streak | Biết chữ không nghe được tình huống |
| YouTube CI (Comprehensible Japanese, v.v.) | Xem video dễ hiểu | Đúng phương pháp nhưng không có cấp, tiến độ giờ, đồng bộ thiết bị, nhà máy nội dung riêng |
| Drama / anime raw | Input không comprehensible | Bỏ cuộc hoặc bật Việt ngữ |

Lỗ hổng: **không có sản phẩm** gắn CI + silent period + tiến độ theo giờ + ba bề mặt + nhà máy nội dung có Level QA.

## To-be (nền tảng, chưa vòng học đầy đủ)

Hệ thống nội bộ và client shell: danh tính một lần, catalog theo `ci_level`, phiên đếm thời lượng, CMS publish ra 3 client, cờ tắt mọi thứ textbook. Học viên thật chưa được mời.

To-be Phase 5 (deferred): xem/nghe CI, probe chọn hình, mở output có kiểm soát.

## Phạm vi

**In — gói này**

- Tổ chức, SAD, schema, API, shell 3 client, CMS, media hello-world, 10–20 clip thí điểm pipeline

**Out**

- Thư viện công khai, thanh toán, cộng đồng, JLPT, flashcard, phụ đề L1, micro speaking, tăng trưởng MAU

## Giả định

- Người học đọc được UI Việt ở onboarding/cài đặt.
- Nội dung thí điểm do team tự quay hoặc có quyền rõ (xem feasibility).
- iPad dùng cùng binary iOS (Expo), layout riêng.
