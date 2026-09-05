#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# verify-container.sh — Hardened Container Verification Gate for JPLearn API (R-08/B)
# Verifies Docker image build, non-root execution, packaged resources, CLI exit
# codes, DB adoption stamp safety, schema divergence detection, live baseline adoption
# on populated DB, single-response probe assertions, and container health & readiness isolation.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
API_DIR="$REPO_ROOT/apps/api-python"

IMAGE_TAG="${IMAGE_TAG:-jplearn-api-python:hardened}"
NETWORK_NAME="jplearn-verify-net-$$"
PG_CONTAINER="jplearn-pg-verify-$$"
API_CONTAINER="jplearn-api-verify-$$"
HOST_PORT="${HOST_PORT:-3392}"
EVIDENCE_FILE="${EVIDENCE_FILE:-$REPO_ROOT/apps/api-python/container_verification_manifest.json}"

# Invalidate existing manifest so old PASS artifact cannot be mistakenly reused on failure
rm -f "$EVIDENCE_FILE"

cleanup() {
  local exit_code=$?
  echo "==> Cleaning up verification resources..."
  docker rm -f "$API_CONTAINER" 2>/dev/null || true
  docker rm -f "$PG_CONTAINER" 2>/dev/null || true
  docker network rm "$NETWORK_NAME" 2>/dev/null || true
  if [ $exit_code -ne 0 ]; then
    echo "❌ Container verification FAILED with exit code $exit_code"
  fi
  exit $exit_code
}
trap cleanup EXIT INT TERM

fetch_http() {
  local url="$1"
  local raw
  raw="$(curl -s --max-time 10 -w "\n%{http_code}" "$url" || true)"
  HTTP_CODE="${raw##*$'\n'}"
  HTTP_BODY="${raw%$'\n'*}"
}

echo "========================================================================"
echo " JPLearn FastAPI Container Verification Gate (Hardened R-08/B)"
echo "========================================================================"
START_TIME_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
DIRTY_COUNT="$(git -C "$REPO_ROOT" status --porcelain | wc -l | tr -d '[:space:]')"
echo "Commit SHA: $HEAD_SHA (dirty files: $DIRTY_COUNT)"
echo "Started At (UTC): $START_TIME_UTC"

# Step 1: Build Docker image from current checkout
echo ""
echo "--- [1/7] Building Container Image: $IMAGE_TAG ---"
docker build -t "$IMAGE_TAG" "$API_DIR"
IMAGE_ID="$(docker inspect --format='{{.Id}}' "$IMAGE_TAG")"
echo "Image ID: $IMAGE_ID"

# Step 2: Test Non-root UID 10001
echo ""
echo "--- [2/7] Verifying Non-root Execution (UID 10001) ---"
RUN_UID="$(docker run --rm "$IMAGE_TAG" id -u)"
echo "Container user ID: $RUN_UID"
if [ "$RUN_UID" != "10001" ]; then
  echo "FAIL: Expected UID 10001, got $RUN_UID"
  exit 1
fi
echo "✓ Non-root UID 10001 verified"

# Step 3: Test Packaged Resources (No Repo Fallback)
echo ""
echo "--- [3/7] Verifying Packaged Wheel Resources ---"
docker run --rm "$IMAGE_TAG" python -c "
from jplearn_api.migrate import load_baseline_schema
schema = load_baseline_schema()
assert 'users' in schema['tables'], 'Missing users table in schema'
assert len(schema['tables']) == 10, f'Expected 10 tables, got {len(schema[\"tables\"])}'
print(f'Successfully loaded {len(schema[\"tables\"])} baseline tables without repo fallback')
"
# Test fail-closed on corrupted/missing resource path
set +e
docker run --rm -e SCHEMA_BASELINE_PATH=/nonexistent "$IMAGE_TAG" python -c "from jplearn_api.migrate import load_baseline_schema; load_baseline_schema()" 2>/dev/null
CORRUPT_EXIT=$?
set -e
if [ "$CORRUPT_EXIT" -eq 0 ]; then
  echo "FAIL: Corrupted/missing resource path did not fail closed"
  exit 1
fi
echo "✓ Packaged resource loading and fail-closed verified"

# Step 4: Test CLI Help (0) and Unknown Command (!= 0)
echo ""
echo "--- [4/7] Verifying CLI Exit Codes ---"
docker run --rm "$IMAGE_TAG" jplearn-migrate --help >/dev/null
echo "✓ jplearn-migrate --help returned 0"

set +e
docker run --rm "$IMAGE_TAG" jplearn-migrate invalid_cmd 2>/dev/null
INVALID_EXIT=$?
set -e
if [ "$INVALID_EXIT" -ne 2 ]; then
  echo "FAIL: Expected exit code 2 for invalid CLI command, got $INVALID_EXIT"
  exit 1
fi
echo "✓ jplearn-migrate invalid_cmd returned 2"

# Step 5: Database Adoption Stamp Safety & Migrations
echo ""
echo "--- [5/7] Verifying Database Adoption Stamp Safety & Migrations ---"
docker network create "$NETWORK_NAME" >/dev/null

docker run -d \
  --name "$PG_CONTAINER" \
  --network "$NETWORK_NAME" \
  -e POSTGRES_USER=jplearn \
  -e POSTGRES_PASSWORD=jplearn \
  -e POSTGRES_DB=jplearn_test \
  postgres:16 >/dev/null

echo "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
  if docker exec "$PG_CONTAINER" pg_isready -U jplearn -d jplearn_test >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

INTERNAL_DB_URL="postgresql://jplearn:jplearn@$PG_CONTAINER:5432/jplearn_test"

# 5a: Stamp on empty database must fail closed (exit 1), assert reason, leave alembic_version untouched
echo "Testing stamp on empty database..."
set +e
STAMP_EMPTY_OUT="$(docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate stamp 0001_prisma_baseline 2>&1)"
STAMP_EMPTY_EXIT=$?
set -e
if [ "$STAMP_EMPTY_EXIT" -eq 0 ]; then
  echo "FAIL: Stamp succeeded on empty database!"
  exit 1
fi
if [[ "$STAMP_EMPTY_OUT" != *"empty database"* ]]; then
  echo "FAIL: Expected 'empty database' reason in stamp failure output: $STAMP_EMPTY_OUT"
  exit 1
fi

ALEMBIC_TABLE_EXISTS="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT to_regclass('public.alembic_version');" | tr -d '[:space:]')"
if [ -n "$ALEMBIC_TABLE_EXISTS" ] && [ "$ALEMBIC_TABLE_EXISTS" != "" ]; then
  echo "FAIL: alembic_version table exists after failed stamp on empty database!"
  exit 1
fi
echo "✓ Stamp on empty database failed closed with verified reason"

# 5b: Migration upgrade head
echo "Running migration upgrade head..."
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate upgrade head >/dev/null
echo "✓ Upgrade head succeeded"

# 5c: Migration current
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate current >/dev/null
echo "✓ Current revision checked"

# 5d: Seed with admin bootstrap password
echo "Running idempotent seed..."
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  -e ENVIRONMENT=test \
  -e BOOTSTRAP_ADMIN_EMAIL="admin@jplearn.local" \
  -e BOOTSTRAP_ADMIN_PASSWORD="StrongPassword123!" \
  "$IMAGE_TAG" jplearn-seed >/dev/null
echo "✓ Seed completed successfully"

# Step 6: Schema Divergence & Live Database Adoption Gate
echo ""
echo "--- [6/7] Verifying Schema Divergence Detection & Live Adoption ---"

# 6a: Test schema divergence fails closed on stamp
docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -c "CREATE INDEX idx_divergence_test ON users (password_hash);" >/dev/null
docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -c "DROP TABLE alembic_version;" >/dev/null

set +e
DIVERGENCE_OUT="$(docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate stamp 0001_prisma_baseline 2>&1)"
DIVERGENCE_EXIT=$?
set -e

if [ "$DIVERGENCE_EXIT" -eq 0 ]; then
  echo "FAIL: Stamp succeeded despite schema divergence!"
  exit 1
fi
if [[ "$DIVERGENCE_OUT" != *"live schema diverges from baseline"* ]]; then
  echo "FAIL: Expected 'live schema diverges from baseline' in error output: $DIVERGENCE_OUT"
  exit 1
fi
echo "✓ Schema divergence detection verified: stamp failed closed"

# Clean up divergence index
docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -c "DROP INDEX IF EXISTS idx_divergence_test;" >/dev/null

# 6b: Adopt populated DB baseline without bookkeeping, verify data counts and upgrade no-op
USER_COUNT_BEFORE="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT count(*) FROM users;" | tr -d '[:space:]')"
CATALOG_COUNT_BEFORE="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT count(*) FROM catalog_items;" | tr -d '[:space:]')"
echo "Populated DB counts before adoption: users=$USER_COUNT_BEFORE, catalog_items=$CATALOG_COUNT_BEFORE"

if [ "$USER_COUNT_BEFORE" -le 0 ] || [ "$CATALOG_COUNT_BEFORE" -le 0 ]; then
  echo "FAIL: Expected seeded data in populated DB before adoption test!"
  exit 1
fi

docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate stamp 0001_prisma_baseline >/dev/null
echo "✓ Adoption stamp on populated baseline succeeded"

VERSION_NUM="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT version_num FROM alembic_version;" | tr -d '[:space:]')"
if [ "$VERSION_NUM" != "0001_prisma_baseline" ]; then
  echo "FAIL: Expected alembic_version '0001_prisma_baseline', got '$VERSION_NUM'"
  exit 1
fi

# Upgrade head must be clean no-op
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate upgrade head >/dev/null

USER_COUNT_AFTER="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT count(*) FROM users;" | tr -d '[:space:]')"
CATALOG_COUNT_AFTER="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT count(*) FROM catalog_items;" | tr -d '[:space:]')"
if [ "$USER_COUNT_BEFORE" != "$USER_COUNT_AFTER" ] || [ "$CATALOG_COUNT_BEFORE" != "$CATALOG_COUNT_AFTER" ]; then
  echo "FAIL: Business data modified during adoption stamp / upgrade no-op!"
  exit 1
fi
echo "✓ Baseline adoption verified: version=$VERSION_NUM, data counts unchanged (users=$USER_COUNT_AFTER, items=$CATALOG_COUNT_AFTER)"

# Step 7: Container Readiness & Liveness Probes
echo ""
echo "--- [7/7] Verifying Container Readiness & Liveness Probe Isolation ---"
docker run -d \
  --name "$API_CONTAINER" \
  --network "$NETWORK_NAME" \
  -p "$HOST_PORT:3002" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  -e JWT_SECRET="ci-secret-at-least-32-bytes-long-for-pyjwt-security" \
  -e ENVIRONMENT=test \
  "$IMAGE_TAG" >/dev/null

echo "Waiting for container API to start..."
READY=0
for i in $(seq 1 30); do
  fetch_http "http://127.0.0.1:$HOST_PORT/health"
  if [ "$HTTP_CODE" = "200" ]; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "FAIL: Container failed to start within 30s. Container logs:"
  docker logs "$API_CONTAINER"
  exit 1
fi

# 7a: Positive Readiness (single curl call per endpoint)
fetch_http "http://127.0.0.1:$HOST_PORT/health"
HEALTH_CODE="$HTTP_CODE"
HEALTH_BODY="$HTTP_BODY"

fetch_http "http://127.0.0.1:$HOST_PORT/ready"
READY_CODE="$HTTP_CODE"
READY_BODY="$HTTP_BODY"

if [ "$HEALTH_CODE" != "200" ] || [ "$READY_CODE" != "200" ]; then
  echo "FAIL: Expected 200 for health and readiness, got health=$HEALTH_CODE ready=$READY_CODE"
  exit 1
fi

# Assert exact JSON body structure for healthy state
python3 -c "
import json, sys
data = json.loads(sys.argv[1])
assert data.get('ok') is True, f'Expected ok=True, got {data.get(\"ok\")}'
assert data.get('database') == 'up', f'Expected database=up, got {data.get(\"database\")}'
assert data.get('storage') == 'up', f'Expected storage=up, got {data.get(\"storage\")}'
" "$READY_BODY"
echo "✓ Initial probes healthy: health=$HEALTH_CODE, ready=$READY_CODE, body=$READY_BODY"

# 7b: Storage degraded (make storage read-only)
echo "Testing degraded storage probe..."
docker exec -u 0 "$API_CONTAINER" chmod -R 555 /app/storage
fetch_http "http://127.0.0.1:$HOST_PORT/ready"
STORAGE_DOWN_CODE="$HTTP_CODE"
STORAGE_DOWN_BODY="$HTTP_BODY"

fetch_http "http://127.0.0.1:$HOST_PORT/health"
LIVENESS_CODE_STORAGE_DOWN="$HTTP_CODE"
LIVENESS_BODY_STORAGE_DOWN="$HTTP_BODY"

# Restore permissions immediately
docker exec -u 0 "$API_CONTAINER" chmod -R 777 /app/storage

if [ "$STORAGE_DOWN_CODE" != "503" ]; then
  echo "FAIL: Expected 503 for readiness when storage is degraded, got $STORAGE_DOWN_CODE"
  exit 1
fi
if [ "$LIVENESS_CODE_STORAGE_DOWN" != "200" ]; then
  echo "FAIL: Liveness probe must stay 200 during readiness degradation, got $LIVENESS_CODE_STORAGE_DOWN"
  exit 1
fi

python3 -c "
import json, sys
data = json.loads(sys.argv[1])
assert data.get('ok') is False, f'Expected ok=False, got {data.get(\"ok\")}'
assert data.get('database') == 'up', f'Expected database=up, got {data.get(\"database\")}'
assert data.get('storage') == 'down', f'Expected storage=down, got {data.get(\"storage\")}'
" "$STORAGE_DOWN_BODY"
echo "✓ Storage probe degradation verified: ready=503 (storage:down, db:up), liveness=200"

# 7c: Database degraded (pause database)
echo "Testing degraded database probe..."
docker pause "$PG_CONTAINER" >/dev/null
fetch_http "http://127.0.0.1:$HOST_PORT/ready"
DB_DOWN_CODE="$HTTP_CODE"
DB_DOWN_BODY="$HTTP_BODY"

fetch_http "http://127.0.0.1:$HOST_PORT/health"
LIVENESS_CODE_DB_DOWN="$HTTP_CODE"
LIVENESS_BODY_DB_DOWN="$HTTP_BODY"

docker unpause "$PG_CONTAINER" >/dev/null

if [ "$DB_DOWN_CODE" != "503" ]; then
  echo "FAIL: Expected 503 for readiness when database is paused, got $DB_DOWN_CODE"
  exit 1
fi
if [ "$LIVENESS_CODE_DB_DOWN" != "200" ]; then
  echo "FAIL: Liveness probe must stay 200 during DB degradation, got $LIVENESS_CODE_DB_DOWN"
  exit 1
fi

python3 -c "
import json, sys
data = json.loads(sys.argv[1])
assert data.get('ok') is False, f'Expected ok=False, got {data.get(\"ok\")}'
assert data.get('database') == 'down', f'Expected database=down, got {data.get(\"database\")}'
assert data.get('storage') == 'up', f'Expected storage=up, got {data.get(\"storage\")}'
" "$DB_DOWN_BODY"
echo "✓ Database probe degradation verified: ready=503 (db:down, storage:up), liveness=200"

END_TIME_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Write Manifest with measured evidence using Python json.dump for strict validity
python3 -c "
import json, sys

manifest = {
    'status': 'PASS',
    'commit_sha': sys.argv[1],
    'git_dirty_files': int(sys.argv[2]),
    'image_tag': sys.argv[3],
    'image_id': sys.argv[4],
    'start_time_utc': sys.argv[5],
    'end_time_utc': sys.argv[6],
    'tests': {
        'non_root_uid': {'uid': int(sys.argv[7]), 'result': 'PASS'},
        'packaged_resources': {'tables_loaded': 10, 'corrupt_exit': int(sys.argv[8]), 'result': 'PASS'},
        'cli_exit_codes': {'help': 0, 'invalid_cmd': int(sys.argv[9]), 'result': 'PASS'},
        'empty_db_stamp_safety': {'exit_code': int(sys.argv[10]), 'alembic_table_untouched': True, 'result': 'PASS'},
        'schema_divergence_safety': {'exit_code': int(sys.argv[11]), 'reason_matched': True, 'result': 'PASS'},
        'populated_db_baseline_adoption': {
            'version': sys.argv[12],
            'user_count_before': int(sys.argv[13]),
            'user_count_after': int(sys.argv[14]),
            'catalog_count_before': int(sys.argv[15]),
            'catalog_count_after': int(sys.argv[16]),
            'result': 'PASS'
        },
        'migration_and_seed': {'upgrade': 'PASS', 'current': 'PASS', 'seed': 'PASS'},
        'readiness_probe_isolation': {
            'healthy': {'code': int(sys.argv[17]), 'body': json.loads(sys.argv[18]), 'result': 'PASS'},
            'storage_degraded': {'code': int(sys.argv[19]), 'body': json.loads(sys.argv[20]), 'liveness_code': int(sys.argv[21]), 'result': 'PASS'},
            'database_degraded': {'code': int(sys.argv[22]), 'body': json.loads(sys.argv[23]), 'liveness_code': int(sys.argv[24]), 'result': 'PASS'}
        }
    }
}
with open(sys.argv[25], 'w') as f:
    json.dump(manifest, f, indent=2)
" "$HEAD_SHA" "$DIRTY_COUNT" "$IMAGE_TAG" "$IMAGE_ID" "$START_TIME_UTC" "$END_TIME_UTC" \
  "$RUN_UID" "$CORRUPT_EXIT" "$INVALID_EXIT" "$STAMP_EMPTY_EXIT" "$DIVERGENCE_EXIT" \
  "$VERSION_NUM" "$USER_COUNT_BEFORE" "$USER_COUNT_AFTER" "$CATALOG_COUNT_BEFORE" "$CATALOG_COUNT_AFTER" \
  "$READY_CODE" "$READY_BODY" "$STORAGE_DOWN_CODE" "$STORAGE_DOWN_BODY" "$LIVENESS_CODE_STORAGE_DOWN" \
  "$DB_DOWN_CODE" "$DB_DOWN_BODY" "$LIVENESS_CODE_DB_DOWN" "$EVIDENCE_FILE"

echo ""
echo "========================================================================"
echo "✓ ALL CONTAINER VERIFICATION GATES PASSED!"
echo "Manifest written to: $EVIDENCE_FILE"
echo "========================================================================"
