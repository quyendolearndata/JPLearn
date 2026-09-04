# Sơ đồ thiết kế (SAD-3)

Mở file này trên GitHub hoặc preview Markdown. Spec chữ: [c4.md](c4.md), [erd.md](erd.md), [ui-shell.md](ui-shell.md), [openapi.yaml](openapi.yaml). Khung màn: [wireframes/README.md](wireframes/README.md).

Không có `GrammarModule`, `FlashcardModule`, `TranslationModule`.

## 1. C4 Level 1 — Context

```mermaid
flowchart TB
  PersonLearner[Người học - tài khoản thử]
  PersonStaff[Giáo viên / CMS]
  System[JPLearn Platform]
  Storage[Object storage]
  Transcode[Transcode - tuỳ chọn Q1]

  PersonLearner --> System
  PersonStaff --> System
  System --> Storage
  System -.-> Transcode
```

## 2. C4 Level 2 — Container

```mermaid
flowchart LR
  Web[Web Next.js - learner + /staff]
  Expo[Expo iOS / iPad / Android]
  API[API FastAPI]
  DB[(PostgreSQL)]
  Files[Local / object storage]

  Web -->|HTTPS JSON| API
  Expo -->|HTTPS JSON| API
  API --> DB
  API --> Files
```

Client không nói chuyện thẳng với DB. Playback: API trả URL đã ký; Q1 là MP4, HLS trước cổng nền tảng / P5 (`NFR-PERF-002`).

## 3. C4 Level 3 — Component API

```mermaid
flowchart TB
  HTTP[HTTP + request id]
  HTTP --> Auth[AuthModule FR-ID]
  HTTP --> Catalog[CatalogModule FR-CAT / FR-CMS]
  HTTP --> Session[SessionModule FR-SES]
  HTTP --> Progress[ProgressModule FR-PRG]
  HTTP --> Flags[FlagsModule FR-FLG]
  HTTP --> Events[EventsModule FR-EVT]
  HTTP --> Media[MediaModule upload + playback]
  Auth --> SQLA[SQLAlchemy / PostgreSQL]
  Catalog --> SQLA
  Session --> SQLA
  Progress --> SQLA
  Flags --> SQLA
  Events --> SQLA
  Media --> SQLA
  Media --> Disk[storage files]
```

## 4. Sequence — đăng nhập và catalog (UC-L01, UC-L02)

```mermaid
sequenceDiagram
  actor U as Learner
  participant C as Web hoặc Expo
  participant A as API FastAPI
  participant D as PostgreSQL

  U->>C: Email + mật khẩu
  C->>A: POST /auth/login
  A->>D: Tìm user, so argon2
  alt Sai mật khẩu
    A-->>C: 401
    C-->>U: Không vào shell
  else Đúng
    A-->>C: access_token + user
    C->>A: GET /catalog Bearer
    A->>D: catalog_items status = published
    A-->>C: CatalogItemPublic không field dịch L1
    C-->>U: S-HOME theo ci_level
  end
```

## 5. Sequence — kết thúc phiên và phút CI (UC-L03, UC-L04, UC-L05)

```mermaid
sequenceDiagram
  actor U as Learner
  participant C as Client
  participant A as API
  participant D as PostgreSQL

  U->>C: Bắt đầu phiên
  C->>A: POST /sessions device_class
  A->>D: Insert session + event session_started
  A-->>C: session id
  U->>C: Kết thúc phiên
  C->>A: POST /sessions/id/end
  alt Mất mạng
    C->>C: Retry, không bịa duration
  else duration > 4 giờ
    A->>D: Cộng 0 phút
  else duration hợp lệ
    A->>D: Cộng floor phút + events
  end
  C->>A: GET /progress
  A-->>C: minutes_comprehensible + current_ci_level
```

## 6. Sequence — CMS publish (UC-T02 … UC-A01)

```mermaid
sequenceDiagram
  actor T as Teacher
  actor Q as LevelQA
  actor Ad as Admin
  participant CMS as Web /staff
  participant A as API
  participant D as PostgreSQL

  T->>CMS: Tạo draft
  CMS->>A: POST /staff/catalog
  T->>CMS: Upload media
  CMS->>A: POST media  staff only
  T->>CMS: Nộp QA
  CMS->>A: status = level_qa
  Q->>CMS: Rubric
  alt Reject
    A->>D: về draft
  else Pass
    Ad->>CMS: Publish
    CMS->>A: status = published AND has_l1_translation = false
    A->>D: Update
  end
  Note over A: Learner GET /catalog thấy item. Cấm draft→published bỏ QA.
```

## 7. Sequence — learner bị cấm CMS (NFR-SEC-002)

```mermaid
sequenceDiagram
  actor L as Learner
  participant C as Client
  participant A as API

  L->>C: POST /staff/catalog hoặc upload media
  C->>A: Bearer learner
  A-->>C: 403
```

## 8. Deploy Q1

```mermaid
flowchart LR
  Dev[Laptop] --> Compose[docker compose Postgres]
  Dev --> API[API :3001]
  Dev --> Web[Web :3000]
  Dev --> Expo[Expo]
  API --> Compose
  Staging[Staging] --> HTTPS[HTTPS API]
  Staging --> Preview[Web preview]
  Staging --> TF[TestFlight / internal Android]
```

Prod không nằm trong Q1.
