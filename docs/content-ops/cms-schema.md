# CMS schema (editorial)

Ánh xạ 1-1 `catalog_items` + `media_assets`. Form staff:

Bắt buộc: topic, ci_level, duration_seconds, media_type, visual_support, title_internal, file.

Cố định: spoken_language=`ja`, has_l1_translation=`false` (không hiện checkbox “thêm bản dịch” v1).

Trạng thái: draft → level_qa → published | archived.

Ghi chú QA nội bộ: bảng tùy chọn `qa_notes (item_id, body, author)` **không** expose GET /catalog.

Không: vocabulary tags, grammar point, Vietnamese script trên learner.
