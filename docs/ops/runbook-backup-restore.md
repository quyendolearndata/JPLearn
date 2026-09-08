# Runbook: backup, restore và rollback backend

Owner: Ops; reviewer cần có CTO/QA. Quy trình này chưa phải bằng chứng restore
drill đã chạy trên staging. Xem [runbook backend](runbook-backend.md) và
[deployment](../sad/03-design/deployment.md).

## 1. Phân biệt ba thao tác

- Application rollback: chạy lại image đã biết tốt nếu schema vẫn tương thích.
- Snapshot restore: phục hồi DB và storage từ bản backup đã kiểm chứng, có thể mất
  thay đổi sau thời điểm backup.
- Schema downgrade: có thể DROP dữ liệu; không phải data rollback.
  Guard CLI không phân tích an toàn của mọi named revision.

Repo chưa cấu hình continuous WAL archive/PITR. Một file pg_dump không cung cấp
khả năng phục hồi tới một thời điểm tùy ý. Không ghi "PITR đã sẵn sàng" từ dump đơn.

## 2. Trước backup

1. Ops xác nhận đúng host/DB/storage, thời gian bảo trì, owner và người phê duyệt.
2. Dừng các writer/upload/transcode và chờ transaction/cleanup đang chạy kết thúc.
   Nếu COMMIT chưa rõ kết quả, đối chiếu trước; không chỉ dừng HTTP ingress.
3. Bảo toàn cùng cặp PostgreSQL + storage (MP4 .bin, HLS và metadata liên quan).
   Không snapshot DB rồi tiếp tục thay đổi file trong khi sao chép storage.
4. Dùng PostgreSQL client 16 phù hợp với server. Cấp credential qua cơ chế riêng
   như .pgpass quyền 0600 hoặc secret injection; không ghi mật khẩu vào lệnh/evidence.

## 3. Backup snapshot

Các biến PGHOST, PGPORT, PGUSER, PGDATABASE phải được người vận hành xác nhận.
Ví dụ chạy trong shell Bash riêng; không chạy lệnh này tự động trên production:

~~~bash
set -euo pipefail
umask 077
: "$PGHOST" "$PGPORT" "$PGUSER" "$PGDATABASE"
JPLEARN_BACKUP_DIR=$(mktemp -d /var/backups/jplearn-release.XXXXXX)

pg_dump --format=custom --verbose \
  --file="$JPLEARN_BACKUP_DIR/database.dump"
pg_restore --list "$JPLEARN_BACKUP_DIR/database.dump" \
  > "$JPLEARN_BACKUP_DIR/archive-list.txt"

psql -X -v ON_ERROR_STOP=1 -At -c "
  SELECT 'catalog_items', count(*) FROM catalog_items
  UNION ALL SELECT 'devices', count(*) FROM devices
  UNION ALL SELECT 'feature_flags', count(*) FROM feature_flags
  UNION ALL SELECT 'learner_progress', count(*) FROM learner_progress
  UNION ALL SELECT 'learning_events', count(*) FROM learning_events
  UNION ALL SELECT 'learning_sessions', count(*) FROM learning_sessions
  UNION ALL SELECT 'media_assets', count(*) FROM media_assets
  UNION ALL SELECT 'topics', count(*) FROM topics
  UNION ALL SELECT 'user_roles', count(*) FROM user_roles
  UNION ALL SELECT 'users', count(*) FROM users
  ORDER BY 1;
" > "$JPLEARN_BACKUP_DIR/row-counts.txt"
~~~

Thư mục cha /var/backups phải được Ops provision. pg_dump/psql dùng PG* env đã
xác nhận. Writers phải còn dừng khi lấy row counts nếu muốn so đếm cùng snapshot.

Lưu cùng backup: snapshot/copy storage nhất quán, inventory + checksum file,
schema snapshot, Alembic revision, source SHA/image digest, thời điểm UTC, tool
versions, retention và người sở hữu. Secrets không nằm trong manifest; bảo đảm
secret recovery qua hệ thống được quản lý riêng.

pg_dump chỉ backup một database; roles/global objects cần provision/review riêng.
pg_restore --list chỉ kiểm tra archive đọc được, chưa chứng minh restore thành công.

## 4. Restore drill vào DB mới, không xóa DB nguồn

Chọn server cô lập và tên đích mới chưa tồn tại. Chuẩn bị storage restore riêng;
không mount storage đang phục vụ vào môi trường drill. Các biến RESTORE_* dưới
đây phải được xác nhận, không dùng URL môi trường đang phục vụ.

~~~bash
set -euo pipefail
: "$JPLEARN_RESTORE_HOST" "$JPLEARN_RESTORE_PORT" "$JPLEARN_RESTORE_USER"
: "$JPLEARN_BACKUP_DIR"

createdb --host="$JPLEARN_RESTORE_HOST" --port="$JPLEARN_RESTORE_PORT" \
  --username="$JPLEARN_RESTORE_USER" jplearn_restore_drill

pg_restore --host="$JPLEARN_RESTORE_HOST" --port="$JPLEARN_RESTORE_PORT" \
  --username="$JPLEARN_RESTORE_USER" --dbname=jplearn_restore_drill \
  --no-owner --no-privileges --exit-on-error --verbose \
  "$JPLEARN_BACKUP_DIR/database.dump"
~~~

createdb phải fail nếu DB đích đã tồn tại; dừng để kiểm tra, không thêm dropdb hay
--clean cho tiện. --no-owner/--no-privileges dành cho drill: ACL/roles triển khai
thật cần provision và kiểm chứng riêng trước cutover.

Kiểm chứng ít nhất:

- Lấy lại cùng truy vấn row counts ở DB restore và so với bản backup.
- So schema/enums/constraints/indexes và Alembic revision; không stamp để che lệch.
- Kiểm tra dữ liệu liên kết, không chỉ số lượng: không có media tham chiếu catalog
  mất, progress/session liên kết đúng user, các foreign key đã được tạo/validate.
- Restore storage vào vị trí riêng; so inventory/checksum, đối chiếu mọi
  media_assets.storage_key với file. Reconciliation dry-run là đầu vào, không
  thay thế xác minh HLS (reconciliation bỏ qua hls/).
- Khởi động app với DB/storage restore, secret test riêng; kiểm tra /health,
  /ready, đăng nhập bằng account thử được duyệt, catalog, Range/HLS, phiên học.
- Ghi recovery time, thời điểm dữ liệu backup, dữ liệu sau backup bị mất dự kiến,
  log/exit code và reviewer. Không suy ra RTO/RPO đạt nếu chưa đo và chưa có budget.

Không chạy full pytest vào DB restore có dữ liệu cần giữ; suite chỉ dành cho
jplearn_test cô lập. Không tự dọn DB drill, backup hoặc volume sau khi kiểm tra;
Ops xác nhận retention và exact target trước khi xóa.

## 5. Rollback release và cutover

Ưu tiên rollback image khi migration compatible. Nếu phải restore, duy trì
maintenance, phục hồi sang đích mới, xác minh DB/storage, rồi Ops/CTO duyệt chuyển
connection/routing. Giữ nguồn lỗi và evidence để điều tra; không drop nguồn trong
runbook mặc định. Không rollback runtime NestJS bằng git checkout trên máy đang
phục vụ: đó không phải artifact/DB rollback được kiểm chứng.

R-09 chỉ được xem xét đóng khi có drill thực tế, staging và quyết định release
riêng. Cập nhật tài liệu này không tạo chữ ký nghiệm thu.
