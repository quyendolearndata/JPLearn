# Stock footage thí điểm — nguồn hợp pháp

Owner: Production / Ops. Ngày: 2026-08-25.

## Không lấy từ đâu

Clip CI tiếng Nhật trên YouTube / kênh Comprehensible Japanese **không được tải về repo**. Đó là bản quyền của người tạo. Pedagogy cũng không dùng clip có phụ đề Việt làm kênh hiểu nghĩa.

## Đã lưu trên máy (public domain / CC)

Thư mục local (không commit binary): `media/stock/mp4/`

| File | Brief gần nhất | Giấy phép | Ghi chú |
|---|---|---|---|
| `clean-hands-short.mp4` (23s) | [level-0-wash-hands](briefs/level-0-wash-hands.md) | Public domain — [Commons](https://commons.wikimedia.org/wiki/File:Clean_hands_short.webm) | Cận cảnh rửa tay |
| `hand-washing-video.mp4` (32s) | cùng brief | CC BY-SA 2.0 — [Commons](https://commons.wikimedia.org/wiki/File:Hand_Washing_video.webm) | Ghi nguồn khi publish |
| `sensor-faucet.mp4` (8s) | gần [level-0-kitchen](briefs/level-0-kitchen.md) / rửa tay | CC BY-SA 4.0 — [Commons](https://commons.wikimedia.org/wiki/File:Sensor_faucet_in_a_hotel_room.webm) | Vòi nước; **không** phải lấy cốc |

Hai file `.ogg` “washing hands” trên Commons thực ra **chỉ có tiếng**, không có hình — đã bỏ.

**Thiếu thoại tiếng Nhật.** Stock gốc im lặng. Q1 dùng TTS **Kyoko** (macOS, tiếng Nhật) ghép vào — không lấy giọng YouTube/Forvo (bản quyền).

## Clip đã ghép thoại (local)

| File | Thoại | Nguồn hình |
|---|---|---|
| `media/stock/mp4/level-0-wash-hands.mp4` (32s) | て、て / あらう、あらう / きれい、きれい (lặp) | Commons CC BY-SA 2.0 Hand Washing video |
| `media/stock/mp4/level-0-wash-hands-alt.mp4` (23s) | cùng thoại, bản ngắn | Commons PD Clean hands short |
| `media/stock/mp4/level-0-kitchen-water.mp4` (8s) | みず、みず | Commons CC BY-SA 4.0 sensor faucet |

Không phụ đề Việt. Pedagogy QA: TTS rõ nhưng chưa phải giọng người thật — đủ để chạy pipeline #13; clip “đời thực + giọng native” làm sau.

Mở file chính: `open media/stock/mp4/level-0-wash-hands.mp4`


## Pexels — khớp brief hơn, tải tay (1 nút Download)

Pexels License: dùng trong app được; không bán lại file gốc. Máy agent bị Cloudflare chặn nên **không tải hộ được**. Bạn mở từng link → Download HD:

| Brief | Clip | Link |
|---|---|---|
| Rửa tay | Hands + soap | https://www.pexels.com/video/washing-hands-thoroughly-with-soap-and-water-4002685/ |
| Bữa sáng / nước | Rót nước vào ly | https://www.pexels.com/video/a-person-pouring-water-into-a-glass-on-a-table-27935830/ |
| Đun nước | Ấm điện sôi | https://www.pexels.com/video/boiling-water-in-a-glass-electric-kettle-10974750/ |
| Gấp quần áo | Folding laundry | https://www.pexels.com/video/woman-folding-clothes-7279093/ |
| Cặp / いこう | Sách vào balo | https://www.pexels.com/video/boy-putting-his-books-in-his-backpack-5182805/ |
| Mở cửa | Mở cửa vào nhà | https://www.pexels.com/video/people-hand-legs-door-4010080/ |
| Bánh mì (gần breakfast) | Cho bánh vào túi | https://www.pexels.com/video/a-woman-putting-bread-inside-a-paper-bag-8430965/ |

Lưu file tải về `media/stock/mp4/` đặt tên theo brief, ví dụ `level-0-wash-hands.mp4`.

Pixabay tương tự (cũng Cloudflare với máy): [rửa tay #34050](https://pixabay.com/videos/wash-hands-hand-washing-hygiene-34050/).

## Dùng cho pipeline (#13)

1. Chọn **một** MP4 (ưu tiên `hand-washing-video.mp4` hoặc Pexels rửa tay).
2. Lồng thoại JP ngắn (ghi âm điện thoại) **hoặc** nộp Level QA với ghi chú “visual-only, audio TBD”.
3. Upload CMS → `level_qa` → publish. Không nhúng file Pexels nguyên bản lên GitHub public (điều khoản: không phát tán như stock).

Thuê người / AI tạo 10 clip: [prompts-for-creators.md](prompts-for-creators.md).
