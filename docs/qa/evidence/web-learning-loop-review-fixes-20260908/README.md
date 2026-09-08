# Evidence — Web learning-loop review fixes — 2026-09-08

Nguồn được kiểm chứng: `18c9e02d1b984fa3786bd400a872302b37cdd872`, tree
`9cecad93cd066fed958bc06212a188048fccdc9a`. Base `origin/main` đã fetch lại là
`908b6bbf16a94b9c8e5c0b8bc15c714763011757` và là tổ tiên của candidate.

## Kết quả

| Hạng mục | Kết quả | Log |
|---|---:|---|
| Domain | 3/3 PASS | [domain](jplearn-review-fixes-20260908-domain.log) |
| Web typecheck + unit | 50/50 PASS | [web test](jplearn-review-fixes-20260908-web-test.log) |
| Next.js production build | PASS, 10 route | [web build](jplearn-review-fixes-20260908-web-build.log) |
| Architecture guard | 20/20 PASS | [architecture](jplearn-review-fixes-20260908-architecture.log) |
| Anti-textbook guard | PASS | [guard](jplearn-review-fixes-20260908-guard.log) |
| Toàn bộ E2E, Chromium + WebKit | 96/96 PASS, 48 mỗi engine | [full E2E](jplearn-review-fixes-20260908-e2e-full.log) |
| Capability off, Chromium + WebKit | 16/16 PASS, 8 mỗi engine | [capability-off E2E](jplearn-review-fixes-20260908-e2e-flags-off.log) |

Lượt E2E đầy đủ dùng Docker PostgreSQL test riêng, fixture MP4/HLS thật, và workflow
`upload → HLS → submit QA → review approve → publish`. `learning-loop.spec.ts` phát
video qua UI, chờ `currentTime` tăng, kiểm tra checkpoint có active time dương, kết
thúc phiên legacy thật đủ hơn 60 giây, rồi so sánh số progress/activity trước và sau
DELETE 202. History được kiểm tra ở projection API; evidence này không khẳng định job
đã xóa vật lý record.

Ảnh current candidate:

- [Pending goal](pending-goal.png)
- [Goal conflict 409](goal-conflict.png)

Chi tiết lệnh, exit code và flags ở [commands.tsv](commands.tsv); SHA/tree, phiên bản
runtime và trạng thái source ở [source.txt](source.txt). Log đã bỏ CR, whitespace cuối
dòng và thay đường dẫn máy cục bộ bằng placeholder; xem [redaction note](redaction-note.md).
