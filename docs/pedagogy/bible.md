# Pedagogy bible — thụ đắc như trẻ

Owner: Head of Pedagogy  
Vai trò: **đầu vào nghiệp vụ** cho BA. Không thay [SRS](../sad/01-survey-srs/srs.md).

## 1. Cơ chế

Trẻ không học “bài 12: thì quá khứ”. Trẻ nghe ngôn ngữ gắn với thế giới nhìn thấy được, im lặng rất lâu, rồi nói khi sẵn sàng. JPLearn sao chép cơ chế đó cho người lớn:

1. **Input dễ hiểu (CI)** trước output.
2. **Silent period** được bảo vệ: không ép nói, không ép viết.
3. **Nghĩa từ ngữ cảnh** (hình, cử chỉ, tình huống), không từ bản dịch.
4. **Recast** khi sau này có output: nhắc lại đúng, không giảng quy tắc.
5. **Lặp nghĩa**, không nhồi paradigm chia động từ.

## 2. Tiến bộ là gì

| Là | Không là |
|---|---|
| Giờ / phút input ở đúng cấp (`minutes_comprehensible`) | Số thẻ Anki, điểm quiz |
| Cấp CI đang tiếp xúc (`level_exposed`) | “Hoàn thành bài 7” |
| (Phase 5) trả lời đúng bằng **hành động không lời** — chọn hình | Điểm ngữ pháp, điền hạt |

## 3. Silent period

- Mặc định: học viên mới ở chế độ **chỉ nhận**. Không micro, không prompt “nói theo”.
- Mở output (shadowing / nói) là quyết định Pedagogy + feature flag, sau cổng Phase 5 và SRS bổ sung.
- UI nền tảng không được có nút “Luyện nói” nếu flag tắt.

## 4. Cấm (ghi thành yêu cầu phủ định trên SRS)

- Flashcard / SRS từ vựng làm **kênh chính**
- Bài ngữ pháp, chia động từ, giải thích “vì sao dùng は”
- Phụ đề tiếng Việt (hoặc tiếng Anh) làm cách hiểu mặc định
- Tiến độ = % hoàn thành giáo trình tuyến tính kiểu sách giáo khoa

Được phép: phụ đề **tiếng Nhật** (nếu có) là lớp hỗ trợ sau này, không phải v1 bắt buộc. Onboarding / cài đặt được dùng tiếng Việt.

## 5. Recast

Khi (sau này) học viên nói sai, hệ thống hoặc giáo viên **nói lại câu đúng** trong ngữ cảnh, không mở bảng quy tắc. Không implement trong nền tảng v1; nguyên tắc chặn thiết kế UI “chấm lỗi đỏ + giải thích”.

## 6. Vai trò người lớn

Người lớn có metacognition. Dùng nó cho **kỷ luật phiên** (ngồi xem, không pause để tra từ), không dùng để nhồi grammar. Onboarding được giải thích *tại sao không dịch* — một lần, bằng tiếng Việt.

## 7. Ba bề mặt

- **iPad:** kênh CI video chính (ngả lưng, màn hình đủ ngữ cảnh hình).
- **Phone:** nối phiên, audio-forward khi đi đường (hình vẫn phải có khi dừng).
- **Web:** phiên dài; không biến thành “trang bài tập”.

Chi tiết cấp độ và nhãn nội dung: [taxonomy.md](taxonomy.md).
