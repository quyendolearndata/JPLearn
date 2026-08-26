# Issue #30 — UC-L06 máy native founder: cài EAS dev build + checklist verify

- Ghế soạn: **Mobile** · Checklist gốc: **QA** (standup 2026-08-26, `docs/company/sync/2026-08-26-standup.md`) · Ngày: 2026-08-26 · Issue: [#30](https://github.com/quyendolearndata/JPLearn/issues/30)
- Use case: **UC-L06** (đồng bộ thiết bị) — Test ID: **T-ID-002** (cùng identity), **T-PRG-004** (đồng bộ progress), **T-NFR-X2 / NFR-XPLAT-002** (iPad ≠ scaled phone).
- Phạm vi: đóng phần "CHƯA chứng minh" của [#17](issue-17-uc-l06.md) — app iOS chạy trên **iPhone + iPad thật**. Logic/API và web đã PASS ở #17; issue này không test lại phần đó.
- Yêu cầu kỹ thuật nền: app dùng `expo-video` (native module) → **Expo Go không chạy được**, bắt buộc EAS development build (`developmentClient: true`).

## A. Checklist verify trên 2 máy thật (QA soạn)

Điều kiện đầu: build đã cài trên cả 2 máy (mục B), API + metro đang chạy đúng hướng dẫn (mục C).

| # | Bước | Kỳ vọng | Evidence | Kết quả |
|---|---|---|---|---|
| 1 | Mở app trên iPhone và iPad | Màn Đăng nhập/Đăng ký hiện, không crash | Ảnh màn hình 2 máy | |
| 2 | Đăng ký 1 tài khoản trên iPhone → đăng nhập **cùng tài khoản** trên iPad | Cả 2 vào được tabs Catalog / Phiên / Tiến độ | Ảnh 2 máy sau login | |
| 3 | Mở tab Catalog trên cả 2 | Danh sách item published **giống hệt nhau** | Ảnh đối chiếu 2 máy | |
| 4 | Tab Phiên → "Bắt đầu phiên" trên từng máy | Trạng thái "Phiên đang chạy", **video phát được** (expo-video, nguồn HLS/MP4 đã ký) | Quay màn hình mỗi máy | |
| 5a | iPhone học ≥ 1 phút → "Kết thúc phiên" → mở tab Tiến độ trên **iPad** | iPad thấy cùng `minutes_comprehensible` (chiều iPhone → iPad) | Ảnh Tiến độ cả 2 máy | |
| 5b | iPad học thêm ≥ 1 phút → "Kết thúc phiên" → xem Tiến độ trên **iPhone** | iPhone thấy tổng mới (chiều iPad → iPhone) | Ảnh Tiến độ cả 2 máy | |
| 6 | Soi layout iPad ≠ scaled phone (NFR-XPLAT-002) | Catalog: iPad **2 cột**, iPhone **1 cột** (`catalog.tsx`); padding `spaceIpad` vs `spacePhone`; video Phiên trên iPad giới hạn `maxWidth 1024`, căn giữa — không phải bản phone phóng to | Ảnh 2 máy đặt cạnh nhau, cùng màn | |

Ghi chú: mật khẩu mặc định gõ sẵn trên form là placeholder dev — đặt mật khẩu riêng cho tài khoản verify.

## B. Cài build lên máy thật (sau khi founder build xong — mục E)

1. Founder gửi **link trang build EAS** (internal distribution) hoặc **mã QR**.
2. Trên từng máy: mở link bằng **Safari** (hoặc quét QR bằng Camera) → bấm **Install** → xác nhận cài profile/build.
3. **Máy mới lần đầu**: iOS internal distribution yêu cầu UDID máy nằm trong provisioning profile → trang EAS sẽ đề nghị **Register device** (quét QR đăng ký thiết bị) trước khi cho cài. Founder cần bấm đồng ý để EAS ký lại build nếu được hỏi.
4. Ước lượng ~15 phút/máy (QA). Sau khi cài, mở app → dev client sẽ hỏi địa chỉ metro (mục C).

## C. Chạy API local cho máy thật (bắt buộc đọc trước buổi verify)

Máy thật **không dùng được `localhost`**. App lấy API base từ `EXPO_PUBLIC_API_URL` (`apps/mobile/src/api.ts`, default `http://localhost:3001` chỉ đúng cho simulator). Cần dùng **IP LAN** của Mac chạy API.

1. Lấy IP LAN trên Mac: `ipconfig getifaddr en0` (ví dụ `192.168.1.10`). iPhone, iPad và Mac phải **cùng Wi-Fi**; tắt "Private Wi-Fi Address" nếu mạng lạ chặn client-to-client.
2. Sửa `apps/api/.env`: `API_PUBLIC_URL=http://<IP-LAN>:3001`.
   **Bắt buộc**: URL video (`playback_url`/`hls_url`) là URL tuyệt đối ký HMAC build từ biến này (`apps/api/src/media/signed-url.ts` → `publicApiBaseUrl()`). Để `localhost` thì catalog vẫn lên nhưng **video không chạy trên máy thật**.
3. Chạy API: `pnpm dev:api` (NestJS `app.listen(PORT ?? 3001)` mặc định bind `0.0.0.0` → LAN truy cập được. App native dùng RN `fetch`, không gửi `Origin` → CORS whitelist trong `main.ts` không chặn máy thật; không cần sửa CORS).
4. Chạy metro cho dev build:

```bash
EXPO_PUBLIC_API_URL=http://<IP-LAN>:3001 pnpm dev:mobile
```

`EXPO_PUBLIC_*` được inline lúc bundle → **đổi IP phải restart metro**. Mở app trên máy → chọn đúng metro server cùng mạng (hoặc nhập URL thủ công `http://<IP-LAN>:8081`).
5. Kiểm tra nhanh trước khi verify: Safari trên iPhone mở `http://<IP-LAN>:3001/health` → phải ra 200. Không ra → sai IP / khác mạng / firewall macOS chặn node (System Settings → Network → Firewall → cho phép node nhận kết nối đến).
6. Dữ liệu: cần ít nhất 1 item **published có media** trong catalog (`pnpm db:seed` nếu DB trống). Khác mạng Wi-Fi thường xuyên → phương án dự phòng: tunnel API (vd `cloudflared`/`ngrok`) và đặt cả `API_PUBLIC_URL` lẫn `EXPO_PUBLIC_API_URL` bằng URL tunnel.

## D. Thu evidence trong buổi verify

- **Ảnh màn hình** từng bước bảng A (iPhone: nút sườn + tăng âm lượng; iPad: nút nguồn + tăng âm lượng / tổ hợp tùy model). Bước 4 nên **quay màn hình** (thêm nút Screen Recording trong Control Center).
- **Log**: giữ 2 terminal (API + metro) suốt buổi; copy đoạn log request khi từng bước chạy; nếu app crash: mở lại, lắc máy → dev menu → xem stack trace, chụp lại.
- Ghi kèm: model máy + iOS version (Settings → General → About), IP LAN đã dùng, thời điểm từng bước — dán vào comment issue #30.

## E. Trạng thái build & blocker cần founder

Trạng thái 2026-08-26: config EAS đã sẵn sàng (`apps/mobile/eas.json` profile `development`: `developmentClient: true`, `ios.simulator: false`; `app.json` có `ios.bundleIdentifier = com.jplearn.mobile`, `supportsTablet: true`; đã thêm dependency `expo-dev-client ~5.2.4`). Build **chưa chạy được** vì máy repo chưa có phiên Expo:

```
$ npx eas-cli whoami
Not logged in

$ npx eas-cli build --profile development --platform ios --non-interactive
An Expo user account is required to proceed.
Either log in with eas login or set the EXPO_TOKEN environment variable ...
```

Việc founder phải làm (Mobile không tự tạo/đăng nhập tài khoản):

1. Tạo tài khoản Expo miễn phí tại [expo.dev](https://expo.dev).
2. Trên máy repo: `npx eas-cli login` (đăng nhập tài khoản vừa tạo).
3. **Apple credentials**: build iOS internal distribution lên máy thật cần tài khoản **Apple Developer Program (trả phí, $99/năm)** — free Apple ID không đủ để EAS ký build cho device thật. Nhập Apple ID khi EAS hỏi (`eas build` sẽ dẫn từng bước: tạo project EAS cho slug `jplearn`, đăng ký bundle id `com.jplearn.mobile`, tạo provisioning, đăng ký UDID 2 máy qua QR).
4. Chạy build:

```bash
cd apps/mobile
npx eas-cli build --profile development --platform ios
```

5. Gửi link/QR trang build cho QA + hẹn buổi verify (~15' cài/máy + 30–45' chạy checklist).

**Đường dự phòng không tốn phí Apple** (nếu chưa muốn mua Developer Program): build local `npx expo run:ios --device` từ `apps/mobile` — cần Xcode trên Mac, cắm cáp từng máy, cert miễn phí **hết hạn 7 ngày** (phải build lại), và bật trust Developer Mode trên máy. Chậm và thủ công hơn EAS; chỉ nên dùng nếu muốn verify gấp trong tuần.
