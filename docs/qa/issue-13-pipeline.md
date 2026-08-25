# Bằng chứng issue #13 — pipeline clip đầu tiên (FR-CMS-002)

- Ghế: **Content** · Ngày: 2026-08-25 · Issue: [#13](https://github.com/quyendolearndata/JPLearn/issues/13)
- Clip: `media/stock/mp4/level-0-wash-hands.mp4` (hình Commons + thoại TTS Kyoko, không phụ đề Việt)
- Kết luận: **PASS** trên API sống :3001. `draft` → `level_qa` → `published`; nhảy QA bị 400; learner `GET /catalog` thấy item trong **0,117s** (NFR-PERF-001).

## Bước (runbook)

1. `POST /auth/login` staff `admin@jplearn.local` → 200
2. `POST /staff/catalog` `{ topic_id: body, ci_level: 0, duration_seconds: 32, media_type: video, visual_support: high, title_internal: level-0-wash-hands }`
   - 201 · `status=draft` · `has_l1_translation=false` · `spoken_language=ja`
3. `POST /staff/catalog/:id/publish` **trước** QA → **400** (không được draft→published)
4. `POST /staff/catalog/:id/media` file MP4 → 201 · `playback_url` · `hls_url=null`
5. `POST /staff/catalog/:id/submit-qa` → 200 · `status=level_qa`
6. `POST /staff/catalog/:id/publish` (admin) → 200 · `status=published`
7. Learner `GET /catalog` → item có trong list; payload public không có field dịch

## ID

| | |
|---|---|
| catalog_item_id | `7a2b55e3-8394-4eeb-b03b-90c84fbd6e7d` |
| media_asset_id | `28ee1f3f-6f9b-4578-a957-63a606e258e8` |
| playback_url | `http://localhost:3001/media/28ee1f3f-6f9b-4578-a957-63a606e258e8` |
| GET /media (learner JWT) | 200 |

## Chưa

- HLS cho clip này (opt-in, `hls_url` null — MP4 fallback đúng Q1)
- UI native iPhone/Android
- #12 quay 10–20 clip người thật — pipeline dùng stock thí điểm
