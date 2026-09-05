# Bằng chứng issue #35 — gỡ item `published` không có media (c1) khỏi catalog learner

> Tài liệu lịch sử: lần kiểm chứng này từng dùng embedded PostgreSQL. Workflow
> hiện tại chỉ dùng Docker PostgreSQL qua Compose `db-test`.

- Ghế: **Ops / Legal / Finance** · Ngày: 2026-08-26 · Issue: [#35](https://github.com/quyendolearndata/JPLearn/issues/35)
- Code kiểm chứng: `main` @ `43f7358` (endpoint `POST /staff/catalog/:id/unpublish`, admin only, published→draft + guard chặn publish thiếu media, FR-CAT-002)
- Kết luận: **PASS**. c1 `published`→`draft`; learner `GET /catalog` không còn thấy c1; toàn catalog còn **0** item `published` thiếu media.

## Môi trường chạy (lệch mặc định, đã cô lập)

- Docker daemon không khởi động được trên máy → dùng **embedded-postgres** (cùng cơ chế `apps/api/test/dev-db.cjs`).
- Cổng mặc định **:3001** (API) và **:55444** (DB) đang bị một phiên song song chiếm (worktree `.worktrees/web-react-fix` đang chạy API :3001 + e2e ghi liên tục vào DB 55444). Để không phá phiên đó và không nhiễm bằng chứng, stack verify của card này chạy trên cổng riêng:
  - DB: embedded Postgres `127.0.0.1:55446`, db `jplearn_ops35`, data dir `/tmp/jplearn-ops35-pg` (xóa sau khi xong).
  - API: main repo, `PORT=3011`, `DATABASE_URL=...55446/jplearn_ops35`, `JWT_SECRET`/`MEDIA_SIGNING_SECRET`=`test-secret`, `API_PUBLIC_URL=http://localhost:3011`.
- Migrate `deploy` 4 migration OK + `prisma/seed.ts` OK. State sau seed đúng giả định card: `c1 published, media_count=0`; `d1 draft`; 1 user admin.

## Lệnh + output

### 0. Route tồn tại trên code main (chưa auth → 401, không phải 404)

```bash
curl -X POST http://localhost:3011/staff/catalog/00000000-0000-4000-8000-0000000000c1/unpublish
```

```
HTTP 401  {"message":"Unauthorized","statusCode":401}
```

### 1. Auth

```bash
curl -X POST http://localhost:3011/auth/login    -d '{"email":"admin@jplearn.local","password":"password10"}'   # HTTP 200 → access_token (admin)
curl -X POST http://localhost:3011/auth/register -d '{"email":"learner.ops35@jplearn.local","password":"learnerpass10"}'  # HTTP 201 → access_token (learner)
```

### 2. TRƯỚC — learner thấy c1 dù không có media

```bash
curl http://localhost:3011/catalog -H "Authorization: Bearer $LEARNER_TOKEN"
```

```
HTTP 200
{"items":[{"id":"00000000-0000-4000-8000-0000000000c1","ci_level":0,"duration_seconds":30,"media_type":"video","topic_id":"daily_home","visual_support":"high"}]}
```

Payload public **không có `playback_url`** (vì `media_count=0`) — đúng mô tả bug: item published nhưng không có nguồn phát.

DB trước thao tác (query trực tiếp qua Prisma):

```
c1 status=published media_count=0
```

### 3. Thao tác unpublish (admin)

```bash
curl -X POST http://localhost:3011/staff/catalog/00000000-0000-4000-8000-0000000000c1/unpublish -H "Authorization: Bearer $ADMIN_TOKEN"
```

```
HTTP 200
{"id":"00000000-0000-4000-8000-0000000000c1",...,"status":"draft","title_internal":"seed-ci0-daily-home","media":[]}
```

### 4. SAU — verify 2 chiều

(a) Phía staff: API chưa có `GET /staff/catalog` list (controller chỉ có POST) → verify tương đương bằng query DB trực tiếp:

```
AFTER DB: c1 status=draft media_count=0
```

(b) Phía learner: `GET /catalog` không còn c1:

```
HTTP 200
{"items":[]}
```

(c) Gọi lại unpublish lần 2 → guard state machine chặn đúng:

```
HTTP 400  {"message":"Only published items can be unpublished","error":"Bad Request","statusCode":400}
```

### 5. Re-check toàn catalog (published thiếu media)

```
00000000-0000-4000-8000-0000000000c1 status=draft media_count=0
00000000-0000-4000-8000-0000000000d1 status=draft media_count=0
published thiếu media còn lại: 0
```

## Cảnh báo hiệu lực (đã ghi nhận từ Platform, KHÔNG sửa trong card này)

- `apps/api/prisma/seed.ts` dòng ~67: `update: { status: "published" }` cho c1 → **mỗi lần reseed, c1 lại thành `published`**. Thao tác unpublish này có hiệu lực tới lần seed kế tiếp. Sẽ mở card riêng để sửa seed (không để seed re-publish item thiếu media).
- Guard mới ở `publish` (FR-CAT-002) chặn publish thiếu media về sau, nhưng không chặn đường seed ghi thẳng DB.

## Ghi chú vận hành

- Không đóng issue — QA đối chiếu xong mới đóng (theo điều phối).
- Stack verify (API :3011, DB :55446) đã tắt + dọn data dir sau khi chụp bằng chứng. Stack :3001/:55444 của phiên song song **không động vào**.
- Trong lúc dựng stack đã `kill` một process postgres cũ (PID 17350, cổng 55444, data dir đã hỏng/không còn nguyên) trước khi phát hiện phiên song song — phiên đó hiện ghi vào cluster 55444 mới. Cần agent điều phối thông báo cho phiên worktree nếu họ còn dùng DB đó.
