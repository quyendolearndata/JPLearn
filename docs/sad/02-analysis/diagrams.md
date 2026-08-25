# Sơ đồ phân tích (SAD-2)

Mở file này trên GitHub hoặc preview Markdown để xem diagram. Spec chữ: [use-cases.md](use-cases.md), [context.md](context.md), [processes.md](processes.md), [domain-model.md](domain-model.md).

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
