# UI A+B — 2026-09-07

Candidate: working tree trên `4ead713`, chưa commit. Mẫu được người dùng chọn:
`apps/web/public/design-ab.html`. Bản tích hợp: các route Next.js đang dùng API FastAPI.

## Phạm vi

- Trang chủ, Catalog, Phiên, Tiến độ và khung điều hướng chung: nền kem, xanh sage,
  chữ serif cho tiêu đề, sidebar desktop, điều hướng trên cùng trên phone.
- Catalog: tìm tên chủ đề trên danh sách hiện tại; lọc cấp CI qua API; card dùng đúng
  ID, cấp, thời lượng và hỗ trợ trực quan. SVG có nhãn “Minh họa chủ đề”, không giả thumbnail.
- Phiên: giữ cơ chế start/end/recovery, HLS/MP4, cố định tỷ lệ player để giữ vị trí nút khi tải media.
- Tiến độ: chỉ hiển thị phút/cấp thực từ API; không đưa số mẫu hay streak vào sản phẩm.
- Staff giữ workflow và phân quyền; dùng màu sắc, form, bảng chung mới.
- BA scope: UC-L01–L05/L06/L10, UC-T02–T05 và UC-A01 giữ nguyên; không thay contract/backend/schema.

## Xác thực

**Engineering PASS** trên candidate trên. Raw evidence: [ui-ab-20260907](evidence/ui-ab-20260907/).

| Kiểm tra | Kết quả | Evidence |
|---|---|---|
| `pnpm --filter @jplearn/web test` | 35/35 unit, TypeScript PASS | [unit.log](evidence/ui-ab-20260907/unit.log) |
| `pnpm test:guard` | exit 0 | [guard.log](evidence/ui-ab-20260907/guard.log) |
| Next.js production build trong harness | PASS, 10 trang được prerender | [build.log](evidence/ui-ab-20260907/build.log) |
| `web-e2e-python.sh --project=chromium --project=webkit` | **88/88 PASS**, 44 mỗi engine, 2.4 phút, exit 0 | [e2e.log](evidence/ui-ab-20260907/e2e.log) |
| axe + keyboard trong E2E | PASS; axe không phát hiện vi phạm ở các trang/trạng thái được quét | Cùng log E2E |
| 4 route × 3 viewport | 12/12 không tràn ngang | [visual-check.json](evidence/ui-ab-20260907/visual-check.json) |
| Phiên có video × 3 viewport | 3/3 không tràn ngang | [visual-active-check.json](evidence/ui-ab-20260907/visual-active-check.json) |

Viewport: desktop 1440×1050, iPad 820×1180, phone 390×844 (Chromium giả lập kích thước).
Ảnh tiêu biểu: [desktop Catalog](evidence/ui-ab-20260907/desktop-catalog.png),
[phone Catalog](evidence/ui-ab-20260907/phone-catalog.png),
[phone phiên đang chạy](evidence/ui-ab-20260907/phone-session-active.png),
[iPad tiến độ](evidence/ui-ab-20260907/ipad-progress.png).

Harness `20260907000830_24719` dùng DB test Docker riêng, FastAPI và bản web build riêng.
Catalog trong ảnh là dữ liệu fixture thật từ DB test; số thẻ có thể khác nhau giữa ảnh
vì CMS E2E đang publish/unpublish nội dung song song. Hai kiểm tra sync đọc lại ID ở cả
hai client trước khi so sánh và vẫn xác nhận tiến độ 0 → 1 → 2 phút bằng phiên thực.
Không chạy lại pytest backend trong đợt UI này.

Lần đầu dừng để sửa locator cũ bị trùng bởi ảnh/CTA và nhãn tiến độ. Lần tiếp theo
đã nạp test trước khi sửa role tìm kiếm từ textbox sang searchbox; một kiểm tra
WebKit kết thúc phiên cũng hụt click, lặp riêng 5 lần PASS. Khung video sau đó được
ấn định 16:9 để giảm dịch chuyển khi metadata tải. Giữ nguyên kiểm tra recovery.

## Trải nghiệm

Mở `http://localhost:3000/`, đăng nhập/đăng ký tại `/login`, vào `/catalog`.
Nếu môi trường local chưa có clip published, màn hình trống là trạng thái dữ liệu thật;
staff cần upload, submit QA và publish nội dung để học. Mẫu tham chiếu vẫn chứa dữ liệu minh họa.

Engineering và kiểm tra hình ảnh tự động không thay thế Safari/iPhone/iPad thật.
Nghiệm thu trên thiết bị thật vẫn PARTIAL; chưa triển khai production.
