# Runbook: upload, QA, publish và HLS

Owner: Content/Platform; BA đối chiếu FR-CAT/FR-CMS; Level QA và admin duyệt nội
dung. Ví dụ dành cho local; staging cần release/rights theo
[SOP](../../content-ops/sop-pipeline.md) và [runbook backend](../../ops/runbook-backend.md).

Mục tiêu xuất hiện trong catalog ≤5 phút (thí điểm ≤15 phút) là tiêu chí
NFR-PERF-001 cần đo, không phải cam kết đã được nghiệm thu từ việc publish trả 200.

## 1. Chuẩn bị

- API và DB đã migrate; topics đã seed, admin được tạo có chủ đích theo
  [development](../../backend/development.md).
- MP4 thực có quyền sử dụng, MIME video/mp4, đuôi .mp4 và header ftyp.
  Upload hiện không nhận file bất kỳ/audio; giới hạn 500 × 1024 × 1024 bytes.
- Có curl/jq; đăng nhập bằng admin local đã bootstrap. Credential ví dụ chỉ dùng
  cho local, không phải tài khoản/mật khẩu mặc định của backend.

~~~bash
API_URL=http://localhost:3002
STAFF_TOKEN=$(curl -fsS -X POST "$API_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@jplearn.local","password":"local-admin-password10"}' \
  | jq -er '.access_token')

ITEM_ID=$(curl -fsS -X POST "$API_URL/staff/catalog" \
  -H "Authorization: Bearer $STAFF_TOKEN" -H 'Content-Type: application/json' \
  -d '{"topic_id":"daily_home","ci_level":0,"duration_seconds":30,"media_type":"video","visual_support":"high","title_internal":"local-publish-demo"}' \
  | jq -er '.id')

# Thay bằng file MP4 thật của bạn; không chạy với path placeholder.
MP4_PATH=/absolute/path/to/approved-clip.mp4
ASSET_ID=$(curl -fsS -X POST "$API_URL/staff/catalog/$ITEM_ID/media" \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -F "file=@$MP4_PATH;type=video/mp4" | jq -er '.id')
~~~

Không log token/URL ký, không bật set -x. Các ví dụ argv chỉ dùng trên local tin cậy.
Create/upload trả 201. Item mới ở draft, has_l1_translation=false do backend đặt;
body create không có field has_l1_translation.

## 2. QA rồi publish

~~~bash
curl -fsS -X POST "$API_URL/staff/catalog/$ITEM_ID/submit-qa" \
  -H "Authorization: Bearer $STAFF_TOKEN"
# Dừng để người phụ trách Level QA review rubric và quyền media.
# Chỉ gọi bước sau khi được duyệt:
curl -fsS -X POST "$API_URL/staff/catalog/$ITEM_ID/publish" \
  -H "Authorization: Bearer $STAFF_TOKEN"
~~~

Teacher hoặc admin được create/upload/submit QA; chỉ admin publish/unpublish.
API chặn draft → published trực tiếp, thiếu metadata/file media, hoặc L1 translation.
Trạng thái level_qa không tự chứng minh người QA đã ký rubric: đó là bước vận hành.

Dùng learner JWT kiểm tra GET /catalog: thấy cùng ITEM_ID trên các client;
draft không lộ. Lưu thời điểm publish và lần đầu learner nhìn thấy để đo NFR-PERF-001.
Seed idempotent không thay thế workflow QA/publish.

## 3. HLS có hỗ trợ, nhưng không tự sinh khi upload

Sau upload có MP4 playback_url. Muốn HLS phải tạo manifest/segments offline,
rồi POST /staff/media/{id}/hls. Script hiện có dùng ffmpeg codec copy, không tự tạo
adaptive-bitrate ladder hoặc bảo đảm nguồn codec nào cũng tương thích client.

Từ apps/api-python, trên máy có ffmpeg và access đúng storage của API:

~~~bash
cd apps/api-python
# STORAGE_ROOT phải cùng thư mục API đang dùng, không chỉ là đường dẫn trong container.
export STORAGE_ROOT="$PWD/storage"
./scripts/transcode-hls.sh "$ASSET_ID" "$STAFF_TOKEN" "$API_URL"
~~~

Script đọc ASSET_ID.bin, ghi hls/ASSET_ID/index.m3u8 và segment-*.ts, rồi đăng ký
HLS qua API. API chỉ đăng ký khi manifest tồn tại, không nhận một URL HLS tùy ý.
Docker image API không đóng gói ffmpeg. Script dùng overwrite; không chạy lại trên
asset đang phục vụ nếu chưa backup/phê duyệt. Token là argument có thể thấy trong
process list; dùng local tin cậy, không coi script là pipeline production bảo mật.

Đọc lại catalog để nhận hls_url ký mới. Kiểm tra manifest/segment, Safari/WebKit
và Chromium; vẫn giữ MP4 fallback. API có HLS không đồng nghĩa hạ tầng staging
hoặc player native đã được nghiệm thu.

## 4. Gỡ publish và sự cố

~~~bash
curl -fsS -X POST "$API_URL/staff/catalog/$ITEM_ID/unpublish" \
  -H "Authorization: Bearer $STAFF_TOKEN"
unset STAFF_TOKEN
~~~

Unpublish về draft, không xóa storage. Không có HTTP archive/delete hay staff
catalog-list endpoint hiện tại. Với yêu cầu thu hồi quyền media, Ops/BA/Platform
cần quyết định xử lý và kiểm tra cả URL đã cấp; không giả định ẩn catalog thu hồi
ngay mọi URL ký còn hạn.

Nếu lỗi upload/COMMIT chưa rõ: giữ file, điều tra DB và warning trước khi retry/dọn
orphan. Xem [reconciliation](../../ops/runbook-backend.md#reconciliation-media).
