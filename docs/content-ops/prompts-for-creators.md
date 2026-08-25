# Prompt thuê người / AI tạo 10 clip Q1

Owner: Production. Dùng khi **không tự quay**. Đủ 10 file MP4 + quyền (hợp đồng/AI license) là đóng [#12](https://github.com/quyendolearndata/JPLearn/issues/12).

Gửi **khối A + một clip** mỗi lần. Không gửi cả 10 nếu người kia dễ trộn thoại.

---

## A. Luật chung (dán đầu mọi tin)

Làm video dạy tiếng Nhật kiểu **comprehensible input**: người chưa biết tiếng Nhật vẫn hiểu nhờ **nhìn**.

- Độ dài mỗi clip: **70–95 giây**. MP4, ngang 16:9, 1080p nếu được.
- Camera: **cận tay và đồ vật**. Có thể không lộ mặt.
- Ánh sáng rõ, một người, một chỗ, không nhạc nền, không text trên hình.
- **Cấm:** phụ đề Việt, chữ dịch, bảng chữ “Bài 1”, giảng ngữ pháp, giọng thuyết minh tiếng Việt/Anh.
- Thoại: **chỉ tiếng Nhật**, chậm, lặp đúng script bên dưới. Nói đúng lúc tay chạm vật đó.
- Giao: 10 file `level-0-breakfast.mp4` … (tên trong bảng). Kèm giấy phép dùng trong app học (thương mại nội bộ Q1).

---

## B. Nhắn người quay (tiếng Việt — copy)

```
Mình cần 1 clip ~80 giây, điện thoại cũng được.

Quay [TÌNH HUỐNG]. Camera thấy tay và đồ. Không cần mặt.

Khi tay chạm vật, nói chậm, lặp (chỉ tiếng Nhật, không phụ đề):
[THOẠI]

Không giải thích, không tiếng Việt. File MP4 gửi lại.
```

Thay `[TÌNH HUỐNG]` / `[THOẠI]` bằng hàng trong bảng C.

---

## C. Prompt AI tạo video (English — Kling / Runway / Veo / Sora)

Dán **mỗi clip một prompt**. Sau đó thu âm Nhật riêng (điện thoại hoặc TTS) rồi ghép — nhiều tool AI **không** nói đúng tiếng Nhật chậm. Nếu tool có voice: “slow Japanese only, words: …”

**Negative (mọi clip):** subtitles, captions, Vietnamese text, English text, on-screen labels, classroom, chalkboard, grammar, flashcards, music, fast cuts, talking head lecture.

| File | Prompt hình (English) | Thoại (nói khi ghép audio) |
|---|---|---|
| `level-0-breakfast.mp4` | Close-up of adult hands at a breakfast table: pour water into a clear glass, drink, then pick up bread and take a bite. Bright kitchen, no face needed, photorealistic, one continuous shot, 80 seconds. | みず、みず。のむ、のむ。パン、パン。 |
| `level-0-kitchen.mp4` | Hands open a cupboard, take a cup, place it on a table, point at the cup. Home kitchen, photorealistic, no face, 80 seconds. | コップ、コップ。テーブル、テーブル。おく、おく。 |
| `level-0-wash-hands.mp4` | Close-up of two hands under a faucet: turn water on, soap, wash thoroughly, dry on a towel. Bathroom sink, photorealistic, 70 seconds. | て、て。あらう、あらう。きれい、きれい。 |
| `level-0-put-on-jacket.mp4` | Person puts on a jacket in front of a mirror, buttons it. Camera on hands and jacket. Photorealistic, 80 seconds. | ジャケット、ジャケット。きる、きる。ボタン、ボタン。 |
| `level-0-fold-clothes.mp4` | Hands fold a shirt on a bed, then put it in a closet. Photorealistic, 80 seconds. | シャツ、シャツ。たたむ、たたむ。しまう、しまう。 |
| `level-0-boil-water.mp4` | Electric kettle boils, steam, pour hot water into a cup. Close-up kettle and cup. Photorealistic, 80 seconds. | おゆ、おゆ。わく、わく。あつい、あつい。 |
| `level-0-bedtime.mp4` | Hands place slippers by the bed, turn off a lamp, person lies down. Dim bedroom, photorealistic, 80 seconds. | スリッパ、スリッパ。けす、けす。おやすみ、おやすみ。 |
| `level-0-tidy-books.mp4` | Hands put books onto a shelf, align the spines. Photorealistic, 80 seconds. | ほん、ほん。ならべる、ならべる。たな、たな。 |
| `level-1-open-door.mp4` | Inside a home: hand unlocks and opens the front door, person steps out, looks back. Photorealistic, 65 seconds. | ドア、ドア。あける、あける。いってきます、いってきます。 |
| `level-1-pack-bag.mp4` | Open backpack on a table: put in a book, notebook, pencil case, water bottle, zip, lift onto a shoulder. Photorealistic, 90 seconds. | かばん、かばん。ほん、ほん。いれる、いれる。いこう、いこう。 |

---

## D. Prompt Voice (nếu tách audio)

```
Read this Japanese slowly, clearly, with a pause after each word. Repeat each word twice. No English. No explanation.
[dán cột Thoại]
```

Giọng: người lớn, trung tính. Không hát.

---

## E. Checklist nhận hàng (đóng #12)

- [ ] 10 file MP4, tên đúng bảng C
- [ ] Không phụ đề Việt / chữ trên hình
- [ ] Nghe được thoại Nhật khớp cột Thoại
- [ ] Hợp đồng hoặc license AI: dùng trong app JPLearn
- [ ] Nếu lộ mặt người thật: [release form](../ops/release-form-template.md) đã ký

Nhận đủ 10 file → Production đóng issue #12. Upload CMS là việc Content (#13, đã chạy 1 clip).
