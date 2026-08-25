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

## C. Prompt dán thẳng vào Veo (10 cái — mỗi lần một cái)

Veo ~8 giây / lần. Tắt phụ đề nếu có. **Không dán thoại Nhật vào Veo** (ghép audio sau). Lưu file đúng tên.

### 1 → lưu `level-0-breakfast.mp4`

```
Photorealistic close-up of adult hands at a breakfast table. The hands pour water into a clear glass, drink, then pick up bread and take a bite. Bright kitchen, 16:9, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `みず、みず。のむ、のむ。パン、パン。`

### 2 → lưu `level-0-kitchen.mp4`

```
Photorealistic close-up of adult hands in a home kitchen. Hands open a cupboard, take a cup, place it on a table, then point at the cup. 16:9, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `コップ、コップ。テーブル、テーブル。おく、おく。`

### 3 → lưu `level-0-wash-hands.mp4`

```
Photorealistic close-up of two hands at a bathroom sink. Hands turn on the faucet, use soap, wash thoroughly, then dry on a towel. 16:9, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `て、て。あらう、あらう。きれい、きれい。`

### 4 → lưu `level-0-put-on-jacket.mp4`

```
Photorealistic shot of adult hands putting on a jacket in front of a mirror and buttoning it. Camera on hands and jacket, 16:9. No face needed. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `ジャケット、ジャケット。きる、きる。ボタン、ボタン。`

### 5 → lưu `level-0-fold-clothes.mp4`

```
Photorealistic close-up of adult hands folding a shirt on a bed, then placing it into a closet. 16:9, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `シャツ、シャツ。たたむ、たたむ。しまう、しまう。`

### 6 → lưu `level-0-boil-water.mp4`

```
Photorealistic close-up of a glass electric kettle boiling with steam, then hands pouring hot water into a cup. 16:9, kitchen, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `おゆ、おゆ。わく、わく。あつい、あつい。`

### 7 → lưu `level-0-bedtime.mp4`

```
Photorealistic bedroom scene: hands place slippers beside the bed, turn off a lamp, person lies down. Dim warm light, 16:9. Face optional, no talking. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `スリッパ、スリッパ。けす、けす。おやすみ、おやすみ。`

### 8 → lưu `level-0-tidy-books.mp4`

```
Photorealistic close-up of adult hands placing books onto a shelf and aligning the spines. 16:9, natural light. No face. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `ほん、ほん。ならべる、ならべる。たな、たな。`

### 9 → lưu `level-1-open-door.mp4`

```
Photorealistic shot from inside a home: a hand unlocks and opens the front door, the person steps out and glances back. 16:9, natural light. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `ドア、ドア。あける、あける。いってきます、いってきます。`

### 10 → lưu `level-1-pack-bag.mp4`

```
Photorealistic close-up of an open backpack on a table. Hands put in a book, a notebook, a pencil case, and a water bottle, zip the bag, then lift it onto a shoulder. 16:9, natural light. No face needed. Silent, no music. No subtitles, no captions, no text on screen, no Vietnamese, no English labels, no classroom, no graphics.
```

Thoại ghép sau: `かばん、かばん。ほん、ほん。いれる、いれる。いこう、いこう。`

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
