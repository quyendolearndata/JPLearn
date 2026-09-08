# Chuẩn hóa log

Log trong thư mục này giữ nguyên kết quả và số đếm của lệnh. Quá trình chuẩn hóa chỉ:

- chuyển carriage return thành newline để diff ổn định;
- bỏ whitespace cuối dòng;
- thay đường dẫn tuyệt đối của checkout/worktree bằng `<repository>` và
  `<candidate-worktree>`.

Không có access token, Authorization header, mật khẩu hay email tài khoản test trong
các log đã lưu. Không sửa status, số test hoặc biến failure thành PASS.
