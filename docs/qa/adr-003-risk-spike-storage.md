# ADR-003 — Risk spike: storage, HMAC, ORB (Phase 1)

Ghế: Platform · Ngày: 2026-08-31 · Đánh giá **tĩnh** (harness Docker có thay đổi chưa merge — không tuyên bố e2e PASS).

## Kết luận

Không có blocker ẩn mới so với ADR-003. Port Media/HLS vẫn để **cuối** Phase 3; spike này chốt giao diện để hai runtime không lệch.

| Hạng | Kết luận |
|---|---|
| Shared storage | Nest đọc `STORAGE_ROOT`, mặc định `process.cwd()/storage`. Python phải cùng env + volume. |
| HMAC | Vector `docs/qa/vectors/hmac-media-url.json` — Node `verifyMediaSig` phải khớp từng case (kể cả secret non-ASCII, sig hoa → false). |
| ORB / nosniff | `media-static.controller.ts` set `X-Content-Type-Options: nosniff`, MIME `.ts` → `video/mp2t`, rewrite `exp`+`sig` trên URI relative trong m3u8. Chromium e2e bắt ORB; WebKit Playwright **không** thay #30 iPad native. |
| Dual-mode auth | `MediaAccessGuard`: Bearer **hoặc** query. Thiếu cả hai → 401. |
| Traversal | `^[A-Za-z0-9._-]+$` + chặn `..`. |

## Việc cố tình chưa làm trong spike

- Không chạy Playwright HLS trên máy này trong phiên áp delta.
- Không scaffold FastAPI.
