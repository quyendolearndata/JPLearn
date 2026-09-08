# Web API surfaces — implementation evidence 2026-09-08

## Phạm vi

Ghế BA đối chiếu route với API hiện hành và cập nhật UI shell/traceability. Ghế
Web triển khai các bề mặt learner và staff còn thiếu, giữ guard không đưa grammar,
flashcard hoặc L1 translation vào chrome.

| Bề mặt | Route web | API chính |
|---|---|---|
| Series learner | `/series`, `/series/[id]` | `GET /series`, `GET /series/{id}` |
| Library | `/library`, `/library/collections/[id]` | saved scenes và personal collections |
| Watch history | `/history` | cursor history và asynchronous deletion status |
| Content reports learner | `/reports` | `GET /me/content-reports` |
| Series staff | `/staff/series`, `/staff/series/[id]` | metadata/items CAS và workflow QA/publish |
| Content studio | `/staff/[id]/studio` | scenes, transcript revision, language analysis và AI draft job |
| Vận hành staff | `/staff/reports`, `/staff/jobs`, `/staff/ai-usage` | moderation, content-job lifecycle và usage ledger |

Content-report API hiện tái sử dụng các FR/UC đã có nghĩa khác trong SRS. Màn
hình bám đúng HTTP contract hiện hành; traceability ghi rõ gap và chưa coi đó là
requirement coverage cho tới khi BA cấp ID riêng.

## Lỗi runtime và phòng tái diễn

Một production build chạy cùng lúc với `next dev` từng ghi đè `.next`, làm dev
server trả HTTP 500 vì thiếu webpack chunk. `next.config.ts` nay dùng `.next-dev`
cho development server và `.next` cho production build; `.gitignore` bỏ qua cả
hai thư mục.

## Xác minh

- `pnpm --filter @jplearn/web test`: PASS — TypeScript, ESLint không có error,
  54 unit tests. Ba warning hooks đã tồn tại ở Catalog/Progress/Session.
- `pnpm --filter @jplearn/web build`: PASS — 18 page generations, gồm toàn bộ
  route mới.
- Smoke khi production build chạy song song dev server: 14 route trả HTTP 200;
  60 JS/CSS/static assets được tải, không có failure.
- `pnpm test:guard`: PASS.
- `git diff --check`: PASS.

Đây là evidence local engineering. Chưa thay thế Playwright trên Chromium/WebKit,
thiết bị thật hoặc operational acceptance.
