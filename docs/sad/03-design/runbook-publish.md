# Runbook: publish clip thí điểm (NFR-PERF-001)

Mục tiêu: item `published` xuất hiện trên GET `/catalog` của learner trong ≤ 5 phút (thí điểm ≤ 15 phút).

Q1 media: MP4 (hoặc file bất kỳ) trên disk local + `playback_url` từ API. **Không HLS.**

1. `pnpm db:seed` (seed topics, flags và demo catalog; bootstrap admin qua biến môi trường `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD`).
2. Đăng nhập staff với credential admin đã cấu hình (ví dụ `BOOTSTRAP_ADMIN_EMAIL` / mật khẩu quản trị an toàn).
3. POST `/staff/catalog` (draft, `has_l1_translation` false).
4. POST `/staff/catalog/:id/media` field `file`.
5. POST `/staff/catalog/:id/submit-qa`.
6. POST `/staff/catalog/:id/publish` (admin).
7. Learner GET `/catalog` trên web, iOS/iPad, Android — cùng `id`.

```bash
TOKEN=... # learner JWT
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:3002/catalog
```
