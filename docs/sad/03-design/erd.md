# ERD v1

Sơ đồ container/sequence: [diagrams.md](diagrams.md).

```mermaid
erDiagram
  users ||--o{ user_roles : has
  users ||--o{ devices : uses
  users ||--o{ learning_sessions : starts
  users ||--|| learner_progress : has
  users ||--o{ learning_events : emits
  users ||--o{ catalog_items : creates
  topics ||--o{ catalog_items : groups
  catalog_items ||--o{ media_assets : has
  learning_sessions ||--o{ learning_events : records

  users {
    uuid id PK
    text email
    text password_hash
    timestamptz created_at
  }
  user_roles {
    uuid user_id FK
    text role
  }
  devices {
    uuid id PK
    uuid user_id FK
    text device_class
    timestamptz last_seen_at
  }
  topics {
    text id PK
    text label_internal
  }
  catalog_items {
    uuid id PK
    text topic_id FK
    int ci_level
    int duration_seconds
    text media_type
    text visual_support
    boolean has_l1_translation
    text spoken_language
    text status
    text title_internal
    uuid created_by FK
  }
  media_assets {
    uuid id PK
    uuid catalog_item_id FK
    text storage_key
    text playback_url
    text mime
  }
  learning_sessions {
    uuid id PK
    uuid user_id FK
    text device_class
    timestamptz started_at
    timestamptz ended_at
    int duration_seconds
  }
  learner_progress {
    uuid user_id PK
    int minutes_comprehensible
    int current_ci_level
    timestamptz updated_at
  }
  feature_flags {
    text key PK
    boolean value
  }
  learning_events {
    uuid id PK
    uuid user_id FK
    uuid session_id FK
    text type
    jsonb payload
    timestamptz created_at
  }
```

## Migration strategy

1. `0001_foundation` — toàn bộ bảng trên, **không** probes.
2. `0002_probes` — chỉ khi SAD Phase 5.
3. Cấm migration thêm `vocabulary_score` / `grammar_lesson_id` / `translation_vi` trên catalog/progress.

Seed: flags false; topics taxonomy; một admin; catalog trống.
