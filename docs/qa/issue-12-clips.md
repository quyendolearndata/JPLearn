# Bằng chứng issue #12 — 10 clip Q1 (Veo + TTS Kyoko)

- Ghế: **Production** · Ngày: 2026-08-25 · Issue: [#12](https://github.com/quyendolearndata/JPLearn/issues/12)
- Tiêu đề issue: quay/thu 10–20 clip thí điểm level 0–1 — Q1 MP4, visual support cao, quyền hình, không HLS.
- Kết luận: **PASS theo phạm vi đã chấp nhận** (10 MP4 khớp 10 brief, thoại Nhật đúng script, không phụ đề Việt). **Không** phải 10–20 clip người thật 70–95 giây.

Binary **gitignore** (`media/stock/mp4/`, `media/stock/audio/`). Không commit lên GitHub.

## Bộ 10 file (local)

Thư mục: `media/stock/mp4/`

| File | dur | Hình | Thoại (Kyoko, khớp brief) |
|---|---|---|---|
| `level-0-breakfast.mp4` | 10s | Google Veo | みず、みず。のむ、のむ。パン、パン。 |
| `level-0-kitchen.mp4` | 10s | Google Veo | コップ、コップ。テーブル、テーブル。おく、おく。 |
| `level-0-wash-hands.mp4` | 32s | Commons CC BY-SA 2.0 ([Hand Washing video](https://commons.wikimedia.org/wiki/File:Hand_Washing_video.webm)) | て、て。あらう、あらう。きれい、きれい。 |
| `level-0-put-on-jacket.mp4` | 10s | Google Veo | ジャケット、ジャケット。きる、きる。ボタン、ボタン。 |
| `level-0-fold-clothes.mp4` | 10s | Google Veo | シャツ、シャツ。たたむ、たたむ。しまう、しまう。 |
| `level-0-boil-water.mp4` | 10s | Google Veo | おゆ、おゆ。わく、わく。あつい、あつい。 |
| `level-0-bedtime.mp4` | 10s | Google Veo | スリッパ、スリッパ。けす、けす。おやすみ、おやすみ。 |
| `level-0-tidy-books.mp4` | 10s | Google Veo | ほん、ほん。ならべる、ならべる。たな、たな。 |
| `level-1-open-door.mp4` | 10s | Google Veo | ドア、ドア。あける、あける。いってきます、いってきます。 |
| `level-1-pack-bag.mp4` | 10s | Google Veo | かばん、かばん。ほん、ほん。いれる、いれる。いこう、いこう。 |

Veo gốc (im lặng / nhạc AI) giữ tại `media/stock/mp4/veo-original/` — file `level-*.mp4` ở thư mục cha là bản **đã thay audio** bằng TTS.

## Cách ghép thoại

`say -v Kyoko -r 100` → WAV 44.1 kHz mono → concat + silence 0,8s → `apad` đúng độ dài video → `ffmpeg -c:v copy -map 0:v:0 -map 1:a:0 -c:a aac` (thay audio Veo, không mix nhạc nền).

Đo loudness (mean volume ~−30 dB, không phải track im): 9 file Veo sau mux và clip rửa tay.

## Quyền

| Nguồn | Dùng Q1 trong app |
|---|---|
| Google Veo (9 clip) | Video tạo bởi founder; dùng nội bộ thí điểm. Không phát tán file gốc như stock công cộng. |
| Wikimedia Commons Hand Washing video | CC BY-SA 2.0 — ghi nguồn khi publish. |
| macOS voice **Kyoko** | TTS hệ thống; không lấy giọng YouTube/Forvo. |

Không lộ người thật → không cần [release form](../ops/release-form-template.md) cho bộ này. Clip người thật + form ký vẫn là bước sau (ngoài #12 thí điểm).

## Checklist nhận hàng ([prompts-for-creators.md](../content-ops/prompts-for-creators.md) mục E)

- [x] 10 file MP4, tên đúng 10 brief
- [x] Không phụ đề Việt / chữ dạy trên hình (prompt Veo cấm caption)
- [x] Nghe được thoại Nhật khớp script
- [x] Ghi license: Veo + Commons + Kyoko
- [x] Không HLS ở bước Production (đúng body issue)

## Không nằm trong #12

- Upload 9 clip còn lại lên CMS (Content; #13 đã chạy 1 clip rửa tay).
- Quay người thật 70–95 giây.
- HLS (`NFR-PERF-002` là #15, Platform).
