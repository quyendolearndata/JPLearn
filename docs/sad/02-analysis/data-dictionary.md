# Từ điển dữ liệu v1

Kiểu: UUID, timestamptz UTC, text, int, boolean, enum.

## users

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| email | text | có | unique, lowercase |
| password_hash | text | có | |
| created_at | timestamptz | có | |

## user_roles

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| user_id | UUID | có | FK users |
| role | enum `learner` `teacher` `admin` | có | một user nhiều role được |

## devices

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| user_id | UUID | có | FK users |
| device_class | enum `web` `phone` `ipad` | có | |
| last_seen_at | timestamptz | có | |

## topics

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | text | có | PK, ví dụ `daily_home` |
| label_internal | text | có | tiếng Anh nội bộ, không hiện L1 trên learner UI v1 |

## catalog_items

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| topic_id | text | có | FK topics |
| ci_level | int | có | 0–4 |
| duration_seconds | int | có | > 0 |
| media_type | enum `video` `audio` | có | |
| visual_support | enum `high` `medium` `low` | có | |
| has_l1_translation | boolean | có | published v1 ⇒ false |
| spoken_language | text | có | `ja` |
| status | enum `draft` `level_qa` `published` `archived` | có | |
| title_internal | text | có | CMS only |
| created_by | UUID | có | FK users |

Cấm cột: `translation_vi`, `vocabulary_list`, `grammar_point`.

## media_assets

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| catalog_item_id | UUID | có | FK catalog_items |
| storage_key | text | có | |
| playback_url | text | không | null đến khi xử lý xong |
| mime | text | có | |

## learning_sessions

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| user_id | UUID | có | FK users |
| device_class | enum `web` `phone` `ipad` | có | |
| started_at | timestamptz | có | |
| ended_at | timestamptz | không | |
| duration_seconds | int | không | chỉ khi ended; zombie > 4 giờ không cộng phút |

## learner_progress

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| user_id | UUID | có | PK, FK users |
| minutes_comprehensible | int | có | ≥ 0 |
| current_ci_level | int | có | 0–4, mặc định 0 |
| updated_at | timestamptz | có | |

Cấm: `vocabulary_score`, `grammar_lesson_id`, `textbook_percent`.

## feature_flags

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| key | text | có | PK; `speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled` |
| value | boolean | có | mặc định false cho kênh textbook |

## learning_events

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| user_id | UUID | có | FK users |
| session_id | UUID | không | FK learning_sessions |
| type | enum | có | `session_started` `session_ended` `minutes_comprehensible` `level_exposed` |
| payload | jsonb | có | không chứa password; `minutes` int; `ci_level` int |
| created_at | timestamptz | có | |

## comprehension_probes (chừa chỗ, không UI)

| Thuộc tính | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| id | UUID | có | PK |
| catalog_item_id | UUID | có | FK catalog_items |
| prompt_media_key | text | có | |

Không tạo bảng lúc scaffold; migration `0002_probes` khi Phase 5. OpenAPI v1 không expose CRUD probe cho learner.

## Quy tắc xóa

User xóa tài khoản (deferred): ẩn PII, giữ aggregate ẩn danh nếu pháp lý cho phép. v1: không self-serve delete; Admin xóa tay trên staging.
