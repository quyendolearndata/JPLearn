# Privacy note — staging Q1

Owner: Ops. Hiển thị trên môi trường staging (footer hoặc trang `/privacy-staging`).

## PII thu thập (NFR-PRIV-001)

- Email và id tài khoản nội bộ / tester.
- Không bán dữ liệu Q1.
- Không dùng MAU dashboard cho học viên thật (chưa mời).

## Không thu

- Vị trí GPS bắt buộc.
- Danh bạ điện thoại.
- Thanh toán (Q1 không có).

## Media

Clip thí điểm có người xuất hiện chỉ sau khi có [release form](release-form-template.md).

## Token và mật khẩu

Mật khẩu hash (argon2). Token không log (NFR-SEC-001).

## Liên hệ

Tester nội bộ: _______________ (điền email Ops).

## Xóa tài khoản

v1: không self-serve; Admin xóa tay trên staging khi được yêu cầu.
