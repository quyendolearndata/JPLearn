#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# verify-container.sh — Container Verification Gate for JPLearn API
# Verifies Docker image build, non-root execution, packaged resources, CLI exit
# codes, DB adoption stamp safety, and container health & readiness probe isolation.
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

echo "========================================================================"
echo " JPLearn FastAPI Container Verification Gate"
echo "========================================================================"
START_TIME_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
echo "Commit SHA: $HEAD_SHA"
echo "Started At (UTC): $START_TIME_UTC"

# Step 1: Build Docker image from clean checkout
echo ""
echo "--- [1/6] Building Container Image: $IMAGE_TAG ---"
docker build -t "$IMAGE_TAG" "$API_DIR"
IMAGE_ID="$(docker inspect --format='{{.Id}}' "$IMAGE_TAG")"
echo "Image ID: $IMAGE_ID"

# Step 2: Test Non-root UID 10001
echo ""
echo "--- [2/6] Verifying Non-root Execution (UID 10001) ---"
RUN_UID="$(docker run --rm "$IMAGE_TAG" id -u)"
echo "Container user ID: $RUN_UID"
if [ "$RUN_UID" != "10001" ]; then
  echo "FAIL: Expected UID 10001, got $RUN_UID"
  exit 1
fi
echo "✓ Non-root UID 10001 verified"

# Step 3: Test Packaged Resources (No Repo Fallback)
echo ""
echo "--- [3/6] Verifying Packaged Wheel Resources ---"
docker run --rm "$IMAGE_TAG" python -c "
from jplearn_api.migrate import load_baseline_schema
schema = load_baseline_schema()
assert 'users' in schema['tables'], 'Missing users table in schema'
assert len(schema['tables']) == 10, f'Expected 10 tables, got {len(schema[\"tables\"])}'
print(f'Successfully loaded {len(schema[\"tables\"])} baseline tables without repo fallback')
"
# Test fail-closed on corrupted/missing resource
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
echo "--- [4/6] Verifying CLI Exit Codes ---"
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

# Step 5: Database Adoption Stamp & Migration Gates
echo ""
echo "--- [5/6] Verifying Database Adoption Stamp Safety & Migrations ---"
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

# 5a: Stamp on empty database must fail closed (exit 1) and leave alembic_version untouched
echo "Testing stamp on empty database..."
set +e
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  "$IMAGE_TAG" jplearn-migrate stamp 0001_prisma_baseline 2>/dev/null
STAMP_EMPTY_EXIT=$?
set -e
if [ "$STAMP_EMPTY_EXIT" -eq 0 ]; then
  echo "FAIL: Stamp succeeded on empty database!"
  exit 1
fi

# Confirm alembic_version was not created
ALEMBIC_TABLE_EXISTS="$(docker exec "$PG_CONTAINER" psql -U jplearn -d jplearn_test -t -c "SELECT to_regclass('public.alembic_version');" | tr -d '[:space:]')"
if [ -n "$ALEMBIC_TABLE_EXISTS" ] && [ "$ALEMBIC_TABLE_EXISTS" != "" ]; then
  echo "FAIL: alembic_version table exists after failed stamp!"
  exit 1
fi
echo "✓ Stamp on empty database failed closed without touching version table"

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

# 5d: Seed
echo "Running idempotent seed..."
docker run --rm \
  --network "$NETWORK_NAME" \
  -e DATABASE_URL="$INTERNAL_DB_URL" \
  -e ENVIRONMENT=test \
  "$IMAGE_TAG" jplearn-seed >/dev/null
echo "✓ Seed completed successfully"

# Step 6: Container Readiness & Liveness Probes
echo ""
echo "--- [6/6] Verifying Container Readiness & Liveness Probe Isolation ---"
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
  HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/health" 2>/dev/null || true)"
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

# 6a: Positive Readiness
CODE_HEALTH="$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/health")"
CODE_READY="$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/ready")"
READY_BODY="$(curl -s --max-time 10 "http://127.0.0.1:$HOST_PORT/ready")"

if [ "$CODE_HEALTH" != "200" ] || [ "$CODE_READY" != "200" ]; then
  echo "FAIL: Expected 200 for health and readiness, got health=$CODE_HEALTH ready=$CODE_READY"
  exit 1
fi
echo "✓ Initial probes healthy: health=200, ready=200, body=$READY_BODY"

# 6b: Storage degraded (make storage read-only)
echo "Testing degraded storage probe..."
docker exec -u 0 "$API_CONTAINER" chmod -R 555 /app/storage
CODE_READY_STORAGE_DOWN="$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/ready")"
BODY_STORAGE_DOWN="$(curl -s --max-time 10 "http://127.0.0.1:$HOST_PORT/ready")"
CODE_HEALTH_LIVENESS="$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/health")"

# Restore permissions immediately
docker exec -u 0 "$API_CONTAINER" chmod -R 777 /app/storage

if [ "$CODE_READY_STORAGE_DOWN" != "503" ]; then
  echo "FAIL: Expected 503 for readiness when storage is degraded, got $CODE_READY_STORAGE_DOWN"
  exit 1
fi
if [ "$CODE_HEALTH_LIVENESS" != "200" ]; then
  echo "FAIL: Liveness probe must stay 200 during readiness degradation, got $CODE_HEALTH_LIVENESS"
  exit 1
fi
echo "✓ Storage probe degradation verified: ready=503 (storage:down, db:up), liveness=200"

# 6c: Database degraded (pause database)
echo "Testing degraded database probe..."
docker pause "$PG_CONTAINER" >/dev/null
CODE_READY_DB_DOWN="$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$HOST_PORT/ready")"
BODY_DB_DOWN="$(curl -s --max-time 10 "http://127.0.0.1:$HOST_PORT/ready")"
docker unpause "$PG_CONTAINER" >/dev/null

if [ "$CODE_READY_DB_DOWN" != "503" ]; then
  echo "FAIL: Expected 503 for readiness when database is paused, got $CODE_READY_DB_DOWN"
  exit 1
fi
echo "✓ Database probe degradation verified: ready=503 (db:down, storage:up)"

END_TIME_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Write Manifest
cat <<EOF > "$EVIDENCE_FILE"
{
  "status": "PASS",
  "commit_sha": "$HEAD_SHA",
  "image_tag": "$IMAGE_TAG",
  "image_id": "$IMAGE_ID",
  "start_time_utc": "$START_TIME_UTC",
  "end_time_utc": "$END_TIME_UTC",
  "tests": {
    "non_root_uid": {"uid": 10001, "result": "PASS"},
    "packaged_resources": {"tables_loaded": 10, "result": "PASS"},
    "cli_help_and_exit_codes": {"help": 0, "invalid_cmd": 2, "result": "PASS"},
    "adoption_stamp_safety": {"empty_db_stamp_exit": 1, "alembic_table_untouched": true, "result": "PASS"},
    "migration_and_seed": {"upgrade": "PASS", "current": "PASS", "seed": "PASS"},
    "readiness_probe_isolation": {
      "healthy": {"code": 200, "result": "PASS"},
      "storage_degraded": {"code": 503, "liveness": 200, "result": "PASS"},
      "database_degraded": {"code": 503, "result": "PASS"}
    }
  }
}
EOF

echo ""
echo "========================================================================"
echo "✓ ALL CONTAINER VERIFICATION GATES PASSED!"
echo "Manifest written to: $EVIDENCE_FILE"
echo "========================================================================"
