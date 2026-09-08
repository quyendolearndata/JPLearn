# Media retry/HLS correction — 2026-09-06

Ghế Web + QA; BA đối chiếu acceptance FR-LRN-001, FR-CMS-003/004,
T-LRN-001 và T-SES-REC-001. Scope S-SESSION / F-03.

Status: **engineering PASS** — full E2E 88/88; Design vẫn **PARTIAL**.

## Candidate và thay đổi

Base `564275e`; candidate là working tree chưa commit, không phải nội dung nguyên
bản của SHA đó. [Patch đã kiểm](evidence/media-retry-fix-20260906/tested-code.patch)
và [SHA-256 từng file](evidence/media-retry-fix-20260906/code-sha256.txt) xác định
chính xác bốn file runtime/test. Không đổi backend, database schema hoặc endpoint.

- Manual retry giữ lock theo danh tính request, không theo generation của item.
  Chọn default từ target null không còn khiến nút retry bị khóa ở lỗi tiếp theo.
- CiPlayer chụp vị trí/ý định phát trước khi đổi nguồn; không cho reset/pause của
  nguồn cũ ghi đè snapshot. Chỉ restore khi có metadata, hủy listener restore cũ
  khi lỗi; không hoàn tất restore chỉ vì hls.js đã parse manifest.
- HLS E2E đo riêng forced hls.js và đường engine: native HLS ở WebKit, hls.js ở
  Chromium. Kiểm vị trí và paused/playing, có assertion nguồn thực tế. Không skip,
  không tăng timeout. Test retry kiểm tiếp một chu kỳ lỗi sau khi chọn default.

## Bằng chứng tái hiện và kiểm thử

Raw logs: [media-retry-fix-20260906](evidence/media-retry-fix-20260906/).

| Kiểm tra | Kết quả | Log |
| --- | --- | --- |
| Retry regression trên logic lock cũ | 2/2 FAIL đúng assertion retry phải enabled | `retry-red.log` |
| Media focused trên bản cuối, repeat-each=3 | 42/42 PASS, 22.0s, 0 skip | `focused-repeat.log` |
| Guard | exit 0 | `guard.log` |
| TypeScript + web unit | 35/35 PASS, exit 0 | `web-unit.log` |
| Production build | PASS, exit 0 | `build.log` |
| Backend pytest | 217/217 PASS, 30.33s, 2 deprecation warnings | `api.log` |
| Full E2E đầu | 86 PASS, 2 FAIL WebKit ở recovery test setup/click synchronization | `full-e2e-first.log` |
| Recovery 401/offline sau sửa synchronization, repeat-each=3 | 12/12 PASS, 4.5s | `recovery-repeat.log` |
| Full E2E Chromium/WebKit cuối | 88/88 PASS (44+44), 2.5m, exit 0, 0 skip | `full-e2e.log` |

Các lệnh thực thi từ repo root:

```sh
# Red: test mới + logic retry cũ; trước khi áp dụng fix lock.
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit --grep 'manual retry remains usable'
# Bản cuối: lặp nhóm từng không ổn định trước khi chạy hồi quy đầy đủ.
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit --grep 'HLS|manual retry remains usable' --repeat-each=3
pnpm test:guard
pnpm --filter @jplearn/web test
pnpm --filter @jplearn/web build
pnpm test:api
apps/api-python/differential/web-e2e-python.sh --project=chromium --project=webkit
```

Red run chỉ xác nhận lỗi lock trước fix; không gọi nó là regression của toàn bộ
baseline. URL trong fixture retry được giữ cố định cho auto-refetch để TTL không
làm thay đổi điều kiện lỗi. Fault injection gọi error và reset nguồn cũ có kiểm
soát; URL mới tải media thật từ API/DB/media test cô lập. Không tuyên bố đã kiểm
mọi lỗi mạng thực tế hoặc hết hạn trên thiết bị thật.

Full run đầu phát hiện 401 test ghi record trước khi empty-storage bootstrap hoàn
tất và offline test click khi player/recovery còn thay đổi UI. Test cuối chờ Start
enabled trước khi cài record cho reload; chờ video metadata + End enabled và xác
nhận response POST end. Không thay đổi auth/end runtime hoặc kéo dài timeout.
Giữ raw log failure; 12 lượt focused PASS không thay thế full-run gate cuối.

## Phạm vi nghiệm thu

F-01/F-02 giữ coverage recovery hiện hành; F-03 đã đạt full regression và được
đóng lại trong phạm vi engineering. BA rà diff không thấy lỗi chặn mới; QA xác nhận
88/88 PASS trên patch cuối. F-04 keyboard/axe là evidence tự động. Rà focus thủ công và Safari trên
iPhone/iPad thật vẫn **Design PARTIAL**. Không tự mở production/release gate.

Harness dùng Compose project riêng và `/jplearn_test`; không reset DB/media dev.
Không lưu token hoặc mật khẩu vào evidence. Harness đã cleanup, exit 0;
`containers-after.txt` rỗng, không còn container E2E. SHA-256 bốn file khớp sau test.
