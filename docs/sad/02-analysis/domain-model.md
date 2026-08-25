# Domain model

Bounded contexts v1. Mỗi context một trách nhiệm; giao tiếp qua API/platform, không soi bảng của nhau từ client.

```
Identity          Catalog           Session
─────────         ───────           ───────
User              Topic             LearningSession
Device            CatalogItem
Role              MediaAsset

Progress          FeatureFlag       LearningEvent
────────          ───────────       ─────────────
LearnerProgress   Flag              EventRecord

ComprehensionProbe (schema only, no UI)
──────────────────
Probe  ProbeChoice   (deferred P5)
```

## Quan hệ chính

- User 1—* Device (class: web/phone/ipad)
- User *—* Role
- Topic 1—* CatalogItem
- CatalogItem 1—* MediaAsset
- User 1—* LearningSession
- User 1—1 LearnerProgress
- LearningSession *—* EventRecord (hoặc event độc lập với `session_id`)
- CatalogItem (future) 1—* Probe

## Invariants

1. `LearnerProgress` không có field điểm từ/ngữ pháp.
2. `CatalogItem.has_l1_translation` = false trên mọi item `published` v1.
3. Flag textbook mặc định false.
4. `minutes_comprehensible` chỉ tăng khi session `ended` hợp lệ (`ended_at > started_at`, duration ≤ 4 giờ — cắt session zombie).

Owner context: xem bảng trong spec tổng hợp.

Sơ đồ: [diagrams.md](diagrams.md).
