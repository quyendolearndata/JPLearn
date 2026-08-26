# Sơ đồ phân tích (SAD-2)

Mở file này trên GitHub hoặc preview Markdown để xem diagram. Spec chữ: [use-cases.md](use-cases.md), [context.md](context.md), [processes.md](processes.md), [domain-model.md](domain-model.md).

Mục: **1** actor → UC; **1b** «include» / «extend»; **2** system context; **3** domain bounded context; **4** phiên học skeleton; **5** nhà máy nội dung; **6** class diagram (domain); **7** state diagram (`CatalogItem.status`, `LearningSession`).

Phase 5 (`UC-L10`…`UC-L13` phát CI / probe) **không** vẽ trên các sơ đồ v1.

## 1. Use case — nền tảng v1

```mermaid
flowchart TB
  subgraph actors [Actors]
    Learner
    Teacher
    LevelQA
    Admin
  end

  subgraph learnerUC [Học viên]
    L01[UC-L01 Đăng nhập]
    L02[UC-L02 Xem catalog published]
    L03[UC-L03 Bắt đầu phiên]
    L04[UC-L04 Kết thúc phiên]
    L05[UC-L05 Xem phút CI + cấp]
    L06[UC-L06 Đồng bộ thiết bị]
  end

  subgraph staffUC [Nhân sự]
    T01[UC-T01 Đăng nhập staff]
    T02[UC-T02 Tạo item draft]
    T03[UC-T03 Upload media]
    T04[UC-T04 Nộp Level QA]
    Q01[UC-Q01 / Q02 Rubric CI]
    A01[UC-A01 Publish]
    A02[UC-A02 Feature flags]
    A03[UC-A03 Gán role]
  end

  Learner --> L01
  Learner --> L02
  Learner --> L03
  Learner --> L04
  Learner --> L05
  Learner --> L06
  Teacher --> T01
  Teacher --> T02
  Teacher --> T03
  Teacher --> T04
  LevelQA --> Q01
  Admin --> A01
  Admin --> A02
  Admin --> A03
```

Không có use case flashcard, bài ngữ pháp, hay cặp dịch L1 trên client học viên (`FR-NEG-001`…`003`).

## 1b. Quan hệ include / extend

Quy ước mũi tên UML (**không đảo**):

- **«include»:** UC cơ sở `--«include»-->` UC bị include (nhánh luôn thực hiện).
- **«extend»:** UC mở rộng `--«extend»-->` UC cơ sở (tùy chọn / ngoại lệ). Tên extension là alt của UC hiện có — **không** cấp FR id mới.

Mô hình login v1: chặt UML thì đăng nhập là *precondition*; JPLearn v1 vẽ **«include»** vì mọi UC học viên bắt buộc đi qua `UC-L01`, mọi UC nhân sự bắt buộc đi qua `UC-T01`.

Không vẽ chuỗi nhà máy `T02 → T03 → T04 → Q01 → A01` thành include — đó là tuần tự BPMN (mục 5). `UC-A01` (item `published`) là **điều kiện tiên quyết dữ liệu** để `UC-L02` có catalog; ghi chữ, không vẽ include.

`UC-L10`…`UC-L13` (Phase 5) **không** vẽ trên sơ đồ v1.

Association actor → UC: giữ mục 1. `UC-Q02` tách node ở đây vì kịch bản Pass/Reject; mục 1 vẫn gộp nhãn Q01/Q02.

### Include

```mermaid
flowchart TB
  subgraph learnerInc [Học viên]
    L01[UC-L01 Đăng nhập]
    L02[UC-L02 Xem catalog]
    L03[UC-L03 Bắt đầu phiên]
    L04[UC-L04 Kết thúc phiên]
    L05[UC-L05 Xem tiến độ]
    L06[UC-L06 Đồng bộ thiết bị]
    L02 -->|"«include»"| L01
    L03 -->|"«include»"| L01
    L04 -->|"«include»"| L01
    L05 -->|"«include»"| L01
    L06 -->|"«include»"| L01
    L06 -->|"«include»"| L02
    L06 -->|"«include»"| L05
  end

  subgraph staffInc [Nhân sự]
    T01[UC-T01 Đăng nhập staff]
    T02[UC-T02 Tạo item draft]
    T03[UC-T03 Upload media]
    T04[UC-T04 Nộp Level QA]
    Q01[UC-Q01 Review rubric CI]
    Q02[UC-Q02 Approve hoặc reject]
    A01[UC-A01 Publish]
    A02[UC-A02 Feature flags]
    A03[UC-A03 Gán role]
    T02 -->|"«include»"| T01
    T03 -->|"«include»"| T01
    T04 -->|"«include»"| T01
    Q01 -->|"«include»"| T01
    Q02 -->|"«include»"| T01
    A01 -->|"«include»"| T01
    A02 -->|"«include»"| T01
    A03 -->|"«include»"| T01
  end
```

`UC-L06` include `UC-L02` và `UC-L05`: cùng catalog `published` và cùng progress trên thiết bị khác — khớp spec hiện tại.

### Extend

Chỉ alt/exception đã có trong spec / `processes.md` / sequence SAD-3. Không bịa hành vi mới.

```mermaid
flowchart TB
  L01[UC-L01 Đăng nhập]
  L02[UC-L02 Xem catalog]
  L04[UC-L04 Kết thúc phiên]
  Q01[UC-Q01 Review rubric CI]
  Q02[UC-Q02 Approve hoặc reject]

  E_pwd[Sai mật khẩu] -->|"«extend»"| L01
  E_tok[Hết hạn token] -->|"«extend»"| L01
  E_empty[Catalog trống] -->|"«extend»"| L02
  E_retry[Retry mất mạng] -->|"«extend»"| L04
  E_zom[Phiên zombie hơn 4h cộng 0 phút] -->|"«extend»"| L04
  E_rej[Rubric reject về draft] -->|"«extend»"| Q01
  E_rej -->|"«extend»"| Q02
```

## 2. System context

```mermaid
flowchart TB
  Learner[Learner - tài khoản thử]
  Teacher[Teacher / Level QA]
  Web[Web Next.js]
  Phone[Expo phone]
  iPad[Expo iPad]
  API[JPLearn Platform - API + DB]
  CMS[CMS /staff]
  Store[Object storage / local MP4]
  Events[Learning events]

  Learner -->|HTTPS| Web
  Learner -->|HTTPS| Phone
  Learner -->|HTTPS| iPad
  Teacher --> CMS
  Web --> API
  Phone --> API
  iPad --> API
  CMS --> API
  API --> Store
  API --> Events
```

Ba client **không** đọc Postgres trực tiếp, **không** mở thư mục storage (chỉ URL playback do API cấp).

## 3. Domain — bounded context

```mermaid
flowchart LR
  subgraph identity [Identity]
    User
    Device
    Role
  end
  subgraph catalog [Catalog]
    Topic
    CatalogItem
    MediaAsset
  end
  subgraph session [Session]
    LearningSession
  end
  subgraph progress [Progress]
    LearnerProgress
  end
  subgraph flags [FeatureFlag]
    Flag
  end
  subgraph events [LearningEvent]
    EventRecord
  end

  User --> Device
  User --> Role
  User --> LearningSession
  User --> LearnerProgress
  User --> EventRecord
  Topic --> CatalogItem
  CatalogItem --> MediaAsset
  LearningSession --> EventRecord
```

`LearnerProgress` chỉ có `minutes_comprehensible` và `current_ci_level`. `ComprehensionProbe` để chỗ schema, không UI v1.

## 4. Quy trình phiên học skeleton

```mermaid
flowchart TD
  Start([Bắt đầu]) --> Login[UC-L01 Login]
  Login -->|sai mật khẩu| Login
  Login --> Browse[UC-L02 Catalog published]
  Browse --> StartSes[UC-L03 Start session + device_class]
  StartSes --> Shell[Ở shell - không bắt play video]
  Shell --> EndSes[UC-L04 End session]
  EndSes -->|mất mạng| Retry[Client retry - không bịa duration]
  Retry --> EndSes
  EndSes -->|duration hợp lệ ≤ 4h| Minutes[Cộng minutes_comprehensible]
  EndSes -->|zombie > 4h| Zero[Cộng 0 phút]
  Minutes --> View[UC-L05 Xem tiến độ]
  Zero --> View
  View --> Stop([Kết thúc])
```

## 5. Quy trình nhà máy nội dung

```mermaid
flowchart TD
  Brief[Script brief topic + ci_level] --> Shoot[Quay / thu]
  Shoot --> Draft[UC-T02 Draft + UC-T03 Upload]
  Draft --> QA[UC-T04 status = level_qa]
  QA --> Rubric{UC-Q01 Rubric CI}
  Rubric -->|Fail| Draft
  Rubric -->|Pass| Pub[UC-A01 Admin publish]
  Pub --> API[GET /catalog có item]
  API --> Clients[Web + phone + iPad thấy ≤ NFR-PERF-001]
```

Cấm nhảy `draft` → `published` bỏ Level QA.

## 6. Class diagram — domain

Class **domain**, không vẽ Controller/Service NestJS. Thuộc tính bám [ERD](../03-design/erd.md) (PK/FK). Phương thức chỉ mức nghiệp vụ: `publish()` / `unpublish()` khớp guard FR-CAT-002 (publish cần media, xem `catalog.service.ts`); `end()` khớp UC-L04.

```mermaid
classDiagram
  class User {
    +uuid id PK
    +text email
    +text password_hash
    +timestamptz created_at
  }
  class Device {
    +uuid id PK
    +uuid user_id FK
    +text device_class
    +timestamptz last_seen_at
  }
  class Role {
    +uuid user_id FK
    +text role
  }
  class Topic {
    +text id PK
    +text label_internal
  }
  class CatalogItem {
    +uuid id PK
    +text topic_id FK
    +int ci_level
    +int duration_seconds
    +text media_type
    +text visual_support
    +boolean has_l1_translation
    +text spoken_language
    +text status
    +text title_internal
    +uuid created_by FK
    +submitQa()
    +publish()
    +unpublish()
  }
  class MediaAsset {
    +uuid id PK
    +uuid catalog_item_id FK
    +text storage_key
    +text playback_url
    +text hls_url
    +text mime
  }
  class LearningSession {
    +uuid id PK
    +uuid user_id FK
    +text device_class
    +timestamptz started_at
    +timestamptz ended_at
    +int duration_seconds
    +end()
  }
  class LearnerProgress {
    +uuid user_id PK
    +int minutes_comprehensible
    +int current_ci_level
    +timestamptz updated_at
  }
  class FeatureFlag {
    +text key PK
    +boolean value
  }
  class LearningEvent {
    +uuid id PK
    +uuid user_id FK
    +uuid session_id FK
    +text type
    +jsonb payload
    +timestamptz created_at
  }
  class ComprehensionProbe {
    <<deferred P5>>
  }
  class ProbeChoice {
    <<deferred P5>>
  }

  User "1" *-- "*" Device : has
  User "1" *-- "*" Role : user_roles
  User "1" *-- "*" LearningSession : starts
  User "1" *-- "1" LearnerProgress : has
  User "1" *-- "*" LearningEvent : emits
  User "1" *-- "*" CatalogItem : creates
  Topic "1" *-- "*" CatalogItem : groups
  CatalogItem "1" *-- "*" MediaAsset : has
  LearningSession "1" *-- "*" LearningEvent : records
  ComprehensionProbe "1" *-- "*" ProbeChoice : choices
  CatalogItem "1" ..> "*" ComprehensionProbe : future deferred P5
```

Invariants ([domain-model.md](domain-model.md)):

1. `LearnerProgress` không có field điểm từ/ngữ pháp.
2. `CatalogItem.has_l1_translation` = false trên mọi item `published` v1.
3. Flag textbook (`speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled`) mặc định false.
4. `minutes_comprehensible` chỉ tăng khi session `ended` hợp lệ (`ended_at > started_at`, duration ≤ 4 giờ — cắt session zombie).

`Role` là bảng `user_roles` (user nhiều role: `learner` / `teacher` / `admin`), không phải enum trên `User` — khớp ERD. `ComprehensionProbe` / `ProbeChoice` chừa chỗ schema, **không** UI v1, **không** migration tới Phase 5.

## 7. State diagram

### 7a. `CatalogItem.status`

```mermaid
stateDiagram-v2
  [*] --> draft : UC-T02 tạo item
  draft --> level_qa : UC-T04 nộp Level QA
  level_qa --> draft : UC-Q02 reject — lý do nội bộ
  level_qa --> published : UC-A01 publish (Admin) — guard: có media (FR-CAT-002) và has_l1_translation=false
  published --> draft : UC-A01 unpublish (Admin)
  note right of published
    Schema enum còn archived: v1 chưa có UC hay endpoint chuyển vào archived.
    Chưa có delete-media: nếu item published mất media thì vi phạm guard FR-CAT-002 — rủi ro Platform #35.
  end note
```

Cấm `draft` → `published` không qua `level_qa` (processes.md, sequence SAD-3 mục 6). Reject từ `level_qa` luôn về `draft`, không giữ trạng thái riêng.

### 7b. `LearningSession`

```mermaid
stateDiagram-v2
  [*] --> started : UC-L03 bắt đầu phiên — ghi device_class
  started --> ended : UC-L04 — guard: duration ≤ 4h / action: cộng floor phút vào minutes_comprehensible
  started --> ended : UC-L04 zombie — guard: duration > 4h / action: cộng 0 phút
  ended --> [*]
  note right of started
    Mất mạng khi end: client retry, extend UC-L04 — không tách state, không bịa duration_seconds.
    Retry vẫn fail: phiên giữ started, không cộng phút, không silent-drop.
  end note
```

Zombie không phải state riêng — là guard trên transition `started → ended` (UC-L04 alt 4a, sequence SAD-3 mục 5).
