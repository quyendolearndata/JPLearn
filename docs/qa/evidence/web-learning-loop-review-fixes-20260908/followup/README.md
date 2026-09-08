# Follow-up evidence — 2026-09-08

Source commit `f446c88e9627dcc9687298fb6e56d7e9011763d0`, tree
`cb94a5cdf142e9418284dcf79e1dde0542a1efa0`, branch `codex/web-ui-learning-loop`.
Base `908b6bbf16a94b9c8e5c0b8bc15c714763011757`. Ghi nhận lúc 17:42 +07:00.
Code/test đã commit trước lượt cuối; khi kiểm tra có symlink media tạm tới media
nguồn, không có diff tracked source. README và evidence được sửa sau kiểm tra.
Symlink được gỡ khi hoàn tất; media nguồn và 28 status entry ở checkout gốc giữ nguyên.

| Lệnh | Cấu hình | Exit | Kết quả / log |
|---|---|---:|---|
| `pnpm --filter @jplearn/web test` | TypeScript + unit | 0 | [54/54](web-unit.log) |
| `pnpm test:guard` | pedagogy guard | 0 | [PASS](guard.log) |
| `apps/api-python/.venv/bin/pytest apps/api-python/tests/test_architecture_guard.py -q` | architecture only | 0 | [20/20](architecture.log) |
| `apps/api-python/differential/web-e2e-python.sh` | Chromium + WebKit, playback/smart-stream true | 0 | [106/106, 53 mỗi engine](full-e2e.log) |
| `PLAYBACK_TRACKING_ENABLED=false SMART_STREAM_ENABLED=false apps/api-python/differential/web-e2e-python.sh e2e/shell.spec.ts e2e/hls.spec.ts` | Chromium + WebKit | 0 | [16/16](capability-off.log) |

Full run `20260908173722_16184`; capability-off run `20260908174032_18409`.
[Production build](web-build.log) được harness chạy trước full E2E, exit 0.
Mỗi run dùng Docker PostgreSQL `/jplearn_test` riêng và cleanup thành công.
Không chạy lại toàn API suite hoặc domain vì không thay backend/schema/domain;
domain 3/3 trong thư mục cha thuộc source `18c9e02`.

Năm test trong `learning-races.spec.ts` chạy ở mỗi engine, dùng mock/barrier để ép
PUT, 409-refresh và DELETE trả sau khi A đổi B qua focus; GET cũ sau DELETE 202;
token mất trước mutation. Test real playback/accounting nằm riêng trong learning-loop.
A → B → A, body deferred và unmount/Strict Mode là unit ownership gate, không phải
browser streaming JSON. Chưa chứng nhận thiết bị vật lý, production hoặc physical deletion.

## Lượt phát triển trước commit cuối

- [Lượt race đầu thất bại](race-initial-failed.log): test kích hoạt focus GET trước
  khi bấm DELETE nên loading ẩn nút; không thể thực hiện thứ tự dự kiến.
- [Lượt sửa test PASS 10/10](race-fixed.log), run `20260908173636_18775`: gửi DELETE
  trước và giữ response, sau đó giữ GET cũ, trả 202 rồi thả GET. Hai log này thuộc
  working tree đang phát triển, không dùng làm PASS source cuối.

Log giữ nguyên kết quả, bỏ ANSI color, chuẩn hóa CR/newline và whitespace cuối dòng;
đường dẫn checkout thay bằng placeholder. Checksum gồm cả lượt failure để bảo toàn
diễn biến kiểm thử. Ảnh pending goal/409 tại thư mục cha thuộc `18c9e02`.
