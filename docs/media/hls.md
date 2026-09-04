# HLS playback (NFR-PERF-002)

Trạng thái: HLS là **opt-in theo từng media asset** trước cổng nền tảng; MP4 `playback_url` vẫn là fallback bắt buộc có (ADR-001 cho phép Q1 thí điểm MP4).

## Luồng dữ liệu

1. Staff upload MP4 như cũ: `POST /staff/catalog/:id/media` → asset có `playback_url` (`/media/<asset>`).
2. Transcode offline (không chạy trong request API):

```bash
cd apps/api-python
./scripts/transcode-hls.sh <asset-id> <staff-token>
```

Script dùng `ffmpeg` (`-codec: copy`, segment 4s) ghi bundle vào `storage/hls/<asset-id>/` (`index.m3u8` + `segment-NNN.ts`) rồi gọi `POST /staff/media/<asset-id>/hls` để set `hls_url` trên `media_assets`. Endpoint trả 400 nếu manifest chưa có trên disk — không đăng ký ảo.

3. API phục vụ (JWT như mọi media route):
   - `GET /media/<asset>/hls/index.m3u8` → `application/vnd.apple.mpegurl`
   - `GET /media/<asset>/hls/<file>` → segment `.ts` (`video/mp2t`), `.m4s` (`video/iso.segment`), init `.mp4`, phụ đề `.vtt`. Tên file ngoài whitelist ký tự/đuôi → 400; path traversal bị chặn.
4. Catalog public: item có thêm `hls_url?` (nullable — vắng mặt khi chưa transcode). Không field nào khác đổi; `playback_url` không mất.

## Client

- **Web**: Safari phát native qua `<video src={hls_url}>`; Chrome/Firefox dùng hls.js (`Hls.isSupported()` → attach `hls_url`). Luôn fallback `playback_url` khi `hls_url` vắng hoặc hls.js lỗi mạng nặng.
- **Mobile (Expo)**: `expo-av` `Video` hỗ trợ HLS native cả iOS/Android — truyền thẳng `hls_url` vào `source={{ uri }}`, fallback `playback_url` tương tự.

## Fallback MP4

- Item chưa transcode: `hls_url` absent → client phát `playback_url` (MP4 progressive), đúng chế độ Q1.
- Transcode lỗi/thiếu segment: player tự rơi về `playback_url` vì manifest là URL riêng, không ghi đè MP4.

## Không phạm vi

Không transcode trong request, không CDN/ký URL HLS (vẫn JWT như media hiện có), không adaptive bitrate ladder (single rendition đủ cho cổng nền tảng; ladder là ADR tương lai khi lên object storage).
