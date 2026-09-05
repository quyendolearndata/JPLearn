# Sử dụng API backend

Ví dụ dành cho **local/test**, không chạy tạo dữ liệu thử trên staging/production.
Base URL local: `http://localhost:3002`. Contract chuẩn:
[openapi.yaml](../sad/03-design/openapi.yaml). Cần `curl`, `jq` cho các ví dụ.

## 1. Kiểm tra API

```bash
API_URL=http://localhost:3002
curl -fsS "$API_URL/health"
curl -fsS "$API_URL/ready"
```

`/health` trả `{"ok":true}` khi ứng dụng đáp ứng; `/ready` trả
`{"ok":true,"database":"up","storage":"up"}` khi DB/storage sẵn sàng.
Readiness lỗi trả 503 kèm trạng thái từng dependency. Không cần JWT cho hai endpoint.

## 2. Tạo tài khoản learner và đăng nhập

Chỉ chạy register một lần với email mới; email đã tồn tại trả 409. Mật khẩu
register tối thiểu 10 ký tự. Credential dưới đây chỉ là dữ liệu demo local.

```bash
curl -fsS -X POST "$API_URL/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"learner-demo@example.test","password":"local-learner-password10"}' \
  | jq '{user}'

TOKEN=$(curl -fsS -X POST "$API_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"learner-demo@example.test","password":"local-learner-password10"}' \
  | jq -er '.access_token')

curl -fsS "$API_URL/me" -H "Authorization: Bearer $TOKEN"
curl -fsS "$API_URL/flags" -H "Authorization: Bearer $TOKEN"
```

Register trả 201; login trả 200; response có `access_token` và `user`.
Register tạo learner, không tạo teacher/admin. Bootstrap admin là thao tác local
riêng trong [hướng dẫn phát triển](development.md). Không echo JWT, không bật shell
tracing (`set -x`), không đưa token vào issue/log/screenshot. Ví dụ curl truyền token
qua argv chỉ dùng trên máy local tin cậy; môi trường dùng chung cần client quản lý
credential an toàn, không đặt mật khẩu thật trong shell history.

## 3. Catalog và phát media

```bash
curl -fsS "$API_URL/catalog?ci_level=0" -H "Authorization: Bearer $TOKEN" | jq .
```

Response là `{"items":[...]}`, chỉ chứa item `published`; cần Bearer JWT.
`ci_level` query cho phép 0–4. Không có dữ liệu sau seed là bình thường: seed giữ draft.
Item public có `playback_url` và có thể có `hls_url`; không có tiêu đề/dịch nội bộ.

Client dùng URL do API trả về, không tự ghép storage key. Media chấp nhận Bearer
hoặc query `exp` + `sig`; URL ký mặc định có TTL 1 giờ. Khi URL hết hạn, đọc lại
catalog để lấy URL mới. GET media hỗ trợ Range, có thể trả 206 hoặc 416.
URL đã ký là credential: không log toàn query, không chia sẻ công khai. Logout
thu hồi JWT cũ nhưng không lập tức thu hồi mọi signed URL còn hạn.

## 4. Phiên học và progress

```bash
SESSION_ID=$(curl -fsS -X POST "$API_URL/sessions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"device_class":"web"}' | jq -er '.id')

# Thực hiện phiên học; gọi end khi người dùng kết thúc.
curl -fsS -X POST "$API_URL/sessions/$SESSION_ID/end" \
  -H "Authorization: Bearer $TOKEN"
curl -fsS "$API_URL/progress" -H "Authorization: Bearer $TOKEN"
```

`device_class` là `web`, `phone` hoặc `ipad`; không cần truyền media ID khi start.
Thời gian tính phía server: dưới 60 giây được 0 phút; còn lại lấy phần nguyên
giây/60, phiên quá 4 giờ không cộng phút. End trả progress, không phải session DTO.
Gọi end lần hai trả 400 và không cộng thêm phút; exactly-once ở đây không có nghĩa
retry luôn trả 200. Nếu response end bị mất, đọc progress để đối chiếu trước khi retry.

```bash
curl -fsS -X POST "$API_URL/auth/logout" -H "Authorization: Bearer $TOKEN"
unset TOKEN
```

Logout tăng `token_version`, vô hiệu hóa các JWT cũ của cùng user trên mọi thiết bị.

## 5. Bề mặt HTTP hiện có — 20 operations

| Method | Path | Quyền / mục đích |
| --- | --- | --- |
| GET | `/health` | Public; liveness |
| GET | `/ready` | Public; DB/storage readiness |
| POST | `/auth/register` | Public; đăng ký learner |
| POST | `/auth/login` | Public; nhận JWT |
| POST | `/auth/logout` | Bearer; thu hồi JWT cũ |
| GET | `/me` | Bearer; user hiện tại |
| GET | `/flags` | Bearer; cấu hình tính năng |
| PATCH | `/staff/flags` | Admin; gửi đầy đủ bốn boolean trong contract |
| GET | `/catalog` | Bearer; catalog published |
| POST | `/staff/catalog` | Teacher hoặc admin; tạo draft |
| POST | `/staff/catalog/{id}/submit-qa` | Teacher hoặc admin |
| POST | `/staff/catalog/{id}/publish` | Admin |
| POST | `/staff/catalog/{id}/unpublish` | Admin; về draft |
| POST | `/staff/catalog/{id}/media` | Teacher hoặc admin; multipart MP4 |
| POST | `/staff/media/{id}/hls` | Teacher hoặc admin; đăng ký manifest có sẵn |
| GET | `/media/{id}` | Bearer hoặc URL ký |
| GET | `/media/{id}/hls/{file}` | Bearer hoặc URL ký |
| POST | `/sessions` | Bearer; start |
| POST | `/sessions/{id}/end` | Bearer; chủ phiên |
| GET | `/progress` | Bearer; tiến độ của user |

Không có `GET /staff/catalog`, `DELETE /staff/catalog/{id}`, `/auth/me` hoặc
`PUT /flags` trong runtime hiện tại. Hàm domain archive không đồng nghĩa đã có
HTTP endpoint archive. Các route docs UI tùy cấu hình không tính vào 20 operations.

Theo phạm vi sản phẩm, không bật các kênh textbook chỉ vì endpoint flags cho phép
gửi boolean. [Runbook publish](../sad/03-design/runbook-publish.md) mô tả workflow CMS.

## 6. Lỗi và tích hợp client

Validation trả 400 theo contract, không phải payload 422 mặc định của FastAPI.
401 dùng `{statusCode,message}`; các lỗi chuẩn khác thường có thêm `error`.
403 là thiếu quyền; 404 là tài nguyên/route không tồn tại; 409 có thể là trùng email.
Đọc status và schema contract, không parse chuỗi lỗi để quyết định nghiệp vụ.
Gửi/ghi nhận `x-request-id` khi báo lỗi, loại token/password/PII khỏi nội dung báo cáo.

Web dùng `NEXT_PUBLIC_API_URL`, Expo dùng `EXPO_PUBLIC_API_URL` trỏ tới API.
Trên điện thoại thật, `localhost` là điện thoại, không phải laptop: dùng địa chỉ LAN
phù hợp cho local hoặc endpoint HTTPS đã được Ops cấp. Staging không dùng CORS wildcard.
