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

## 9 clip Veo (2026-08-25, cùng pipeline)

Learner `GET /catalog` = **11** item published (seed 30s không media + rửa tay + 9 Veo). Payload public không có field dịch. `GET /media/:id` learner JWT = 200, byte khớp file local.

| title_internal | catalog_item_id | media_asset_id |
|---|---|---|
| level-0-breakfast | `152a903b-8f50-44e9-8e94-e6d272416013` | `e8457108-29e4-4832-85b7-8b72bf704921` |
| level-0-kitchen | `ce83008d-fded-458b-85ff-23bd9e4faace` | `82c6abc1-f645-4504-a562-eb7d5461c64b` |
| level-0-put-on-jacket | `ccb6cfca-f81c-436a-b27f-5890593bcc1c` | `2d97e4aa-af36-4ecd-a5ae-e10c088ce757` |
| level-0-fold-clothes | `ca4dba75-11db-44f1-a864-96acec87024f` | `3e88fc84-21e5-4a23-a765-39d07b935150` |
| level-0-boil-water | `78fdcf39-d3b6-4ae8-85e8-6048c5c43cf7` | `b2084743-6ba8-458f-bf02-3ea23aa36de2` |
| level-0-bedtime | `71ec9d7d-4b21-4282-8289-e7dffbaa902c` | `f1a4b3d1-b016-4709-8a01-0925fc48d026` |
| level-0-tidy-books | `dee90c78-0205-4745-bf3e-a58e7ae409c4` | `cc8c36f7-c8a5-4144-b468-86a5bc851c93` |
| level-1-open-door | `9f173160-d40d-4637-bbfe-e592ca18ff1f` | `c2015843-9c62-4135-885d-375c68fdca25` |
| level-1-pack-bag | `dd1cfdc6-8a4a-49d8-811c-473dc73ba81f` | `7dbd386e-d2a6-493e-bb02-aa600e1f8203` |

## Chưa

- HLS cho các clip này (opt-in, `hls_url` null — MP4 fallback đúng Q1)
- UI native iPhone/Android
