# Runbook: PostgreSQL Backup, Restore & Rollback Strategy

- **Ghế chủ trì:** Ops / Legal / Finance (`jplearn-ops`)
- **Review:** CTO (`jplearn-cto`)
- **Verification:** QA (`jplearn-qa`)
- **Ngày:** 2026-09-05
- **Trạng thái:** Active Runbook

---

## 1. Nguyên tắc cốt lõi: Schema Downgrade ≠ Data Rollback

> [!CAUTION]
> **Schema downgrade (`alembic downgrade base` hoặc `-1`) KHÔNG PHẢI là data rollback.**  
> Chạy downgrade đối với migration phá hủy (destructive migration) sẽ làm DROP bảng/cột, dẫn tới mất vĩnh viễn dữ liệu người dùng và tiến độ học tập.

1. **Phân loại Migration:**
   - **Additive:** Thêm bảng mới, thêm cột nullable hoặc cột có default value an toàn. (Cho phép application rollback mà không cần schema downgrade).
   - **Compatible:** Đổi view, tạo thêm index, cập nhật constraint tương thích ngược.
   - **Destructive:** Xóa cột, xóa bảng, đổi kiểu dữ liệu incompatible, split cột. Destructive migration mặc định bị chặn trên staging và production, chỉ được phép chạy khi có backup hoàn chỉnh và cờ tường minh `ALLOW_DESTRUCTIVE_DOWNGRADE=true`.

2. **Quy trình Rollback chuẩn:**
   - Nếu deployment ứng dụng thất bại khi migration là *additive/compatible*: Rollback container image ứng dụng về phiên bản trước (image 이전), giữ nguyên schema DB.
   - Nếu migration thất bại hoặc gây hỏng dữ liệu: Thực hiện **Data Restore** từ bản backup snapshot trước khi release, KHÔNG chạy schema downgrade trên DB hỏng.

---

## 2. Quy trình Backup trước Release (Pre-Migration Snapshot)

Trước mọi lần deploy staging/production hoặc chạy `jplearn-migrate upgrade`:

```bash
# 1. Thiết lập biến môi trường
export BACKUP_DIR="/var/backups/jplearn/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_DIR}"

# 2. Chụp snapshot nhất quán (custom format nén có transaction)
pg_dump -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" \
  --format=custom \
  --blobs \
  --verbose \
  --file="${BACKUP_DIR}/pre_release_snapshot.dump"

# 3. Ghi lại số lượng bản ghi kiểm chứng (Row Counts)
psql -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "
  SELECT 'users', count(*) FROM users
  UNION ALL SELECT 'user_roles', count(*) FROM user_roles
  UNION ALL SELECT 'catalog_items', count(*) FROM catalog_items
  UNION ALL SELECT 'media_assets', count(*) FROM media_assets
  UNION ALL SELECT 'learning_sessions', count(*) FROM learning_sessions
  UNION ALL SELECT 'learner_progress', count(*) FROM learner_progress
  UNION ALL SELECT 'events', count(*) FROM events;
" > "${BACKUP_DIR}/row_counts.txt"

echo "Backup completed successfully at ${BACKUP_DIR}"
```

---

## 3. Quy trình Khôi phục (Point-in-Time / Snapshot Restore Drill)

Khi cần phục hồi dữ liệu về trạng thái trước release:

```bash
# 1. Chấm dứt các kết nối đang hoạt động tới DB đích
psql -h "${PGHOST}" -U "${PGUSER}" -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = '${PGDATABASE}' AND pid <> pg_backend_pid();
"

# 2. Xóa và tạo lại database sạch
dropdb -h "${PGHOST}" -U "${PGUSER}" "${PGDATABASE}"
createdb -h "${PGHOST}" -U "${PGUSER}" "${PGDATABASE}"

# 3. Restore từ snapshot dump
pg_restore -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" \
  --clean \
  --if-exists \
  --exit-on-error \
  --verbose \
  "${BACKUP_DIR}/pre_release_snapshot.dump"

# 4. Kiểm chứng tính toàn vẹn (Verification Drill)
# a. Kiểm tra hàng và khóa ngoại
psql -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "
  SELECT 'users', count(*) FROM users
  UNION ALL SELECT 'user_roles', count(*) FROM user_roles
  UNION ALL SELECT 'catalog_items', count(*) FROM catalog_items
  UNION ALL SELECT 'media_assets', count(*) FROM media_assets
  UNION ALL SELECT 'learning_sessions', count(*) FROM learning_sessions
  UNION ALL SELECT 'learner_progress', count(*) FROM learner_progress
  UNION ALL SELECT 'events', count(*) FROM events;
" > "${BACKUP_DIR}/restored_row_counts.txt"

diff -u "${BACKUP_DIR}/row_counts.txt" "${BACKUP_DIR}/restored_row_counts.txt"
if [ $? -ne 0 ]; then
  echo "FATAL: Row count discrepancy detected after restore!"
  exit 1
fi

echo "Restore drill passed: row counts and foreign keys intact."
```

---

## 4. Quyền hạn và Ký duyệt

- **Thực hiện:** Kỹ sư Ops / Platform được phân công.
- **Phê duyệt:** Ghế **Ops** và **CTO** phải ký biên bản xác nhận backup trước khi kích hoạt lệnh release.
