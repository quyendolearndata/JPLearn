#!/usr/bin/env bash
# Web E2E (Playwright) against the FastAPI backend — the only backend as of ADR-004.
#
#   apps/api-python/differential/web-e2e-python.sh [--project=chromium ...]
#
# Dựng DB test riêng (Alembic migrate + seed), chạy FastAPI :3002, dựng nội dung
# thật (upload MP4 kho stock → submit-qa → publish → transcode HLS → register),
# build + serve web :3000 trỏ vào :3002, rồi playwright test.
# Mặc định chạy mọi project trong playwright.config.ts (chromium + webkit).
#
# Baseline Nest cũ: xem tag `pre-adr-004-nest-retire` (apps/api đã bị xóa).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_PY="$REPO/apps/api-python/.venv/bin/python"
PY_PORT=3002
WEB_PORT=3000
STORAGE="$(mktemp -d /tmp/jplearn-web-e2e-py-storage.XXXXXX)"
API_PID=""
WEB_PID=""
ITEM_ID="00000000-0000-4000-8000-0000000000c1" # seed-ci0-daily-home (draft 30s)
SOURCE_MP4="$REPO/media/stock/mp4/level-0-wash-hands.mp4"

cleanup() {
  set +e
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null
  lsof -ti :"$PY_PORT" | xargs kill -9 2>/dev/null || true
  lsof -ti :"$WEB_PORT" | xargs kill -9 2>/dev/null || true
  "$VENV_PY" "$REPO/apps/api-python/differential/db.py" down >/dev/null 2>&1
  rm -rf "$STORAGE"
}
trap cleanup EXIT

# Pre-clean any stale processes on target ports
lsof -ti :"$PY_PORT" | xargs kill -9 2>/dev/null || true
lsof -ti :"$WEB_PORT" | xargs kill -9 2>/dev/null || true

wait_http() { # url, name
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null "$1" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "timeout waiting for $2 at $1" >&2
  exit 1
}

echo "== 1/5 docker db-test (Alembic migrate + seed) =="
DB_LINE="$("$VENV_PY" "$REPO/apps/api-python/differential/db.py" up | grep E2E_DB_READY)"
DATABASE_URL="${DB_LINE#E2E_DB_READY }"

echo "== 2/5 FastAPI :$PY_PORT =="
(
  cd "$REPO/apps/api-python"
  DATABASE_URL="$DATABASE_URL" \
  JWT_SECRET="test-secret-at-least-32-bytes-long-for-pyjwt-security" \
  API_PUBLIC_URL="http://localhost:$PY_PORT" \
  STORAGE_ROOT="$STORAGE" \
  PYTHONPATH=src \
  exec .venv/bin/uvicorn jplearn_api.main:app --port "$PY_PORT" >/tmp/jplearn-web-e2e-py-api.log 2>&1
) &
API_PID=$!
wait_http "http://localhost:$PY_PORT/ready" "FastAPI"

echo "== 3/5 seed nội dung published + HLS thật =="
TOKEN="$(curl -fsS -X POST "http://localhost:$PY_PORT/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@jplearn.local","password":"password10"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

ASSET_ID="$(curl -fsS -X POST "http://localhost:$PY_PORT/staff/catalog/$ITEM_ID/media" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$SOURCE_MP4;type=video/mp4" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

curl -fsS -X POST "http://localhost:$PY_PORT/staff/catalog/$ITEM_ID/submit-qa" \
  -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS -X POST "http://localhost:$PY_PORT/staff/catalog/$ITEM_ID/publish" \
  -H "Authorization: Bearer $TOKEN" >/dev/null

mkdir -p "$STORAGE/hls/$ASSET_ID"
ffmpeg -loglevel error -y -i "$STORAGE/$ASSET_ID.bin" \
  -codec: copy -start_number 0 -hls_time 4 -hls_list_size 0 -f hls \
  -hls_segment_filename "$STORAGE/hls/$ASSET_ID/segment-%03d.ts" \
  "$STORAGE/hls/$ASSET_ID/index.m3u8"
curl -fsS -X POST "http://localhost:$PY_PORT/staff/media/$ASSET_ID/hls" \
  -H "Authorization: Bearer $TOKEN" >/dev/null
echo "   published item $ITEM_ID, asset $ASSET_ID (+hls)"

echo "== 4/5 web :$WEB_PORT → API :$PY_PORT =="
# Build prod thay vì dev: on-demand compile của next dev làm WebKit gãy navigation
# (flake độc lập backend — đã đối chứng trên Nest trước khi retire).
(
  cd "$REPO/apps/web"
  NEXT_PUBLIC_API_URL="http://localhost:$PY_PORT" ./node_modules/.bin/next build \
    >/tmp/jplearn-web-e2e-web-build.log 2>&1
  NEXT_PUBLIC_API_URL="http://localhost:$PY_PORT" \
  exec ./node_modules/.bin/next start -p "$WEB_PORT" >/tmp/jplearn-web-e2e-py-web.log 2>&1
) &
WEB_PID=$!
wait_http "http://localhost:$WEB_PORT/login" "Next"

echo "== 5/5 playwright $* =="
cd "$REPO/apps/web"
# Sandbox của Cursor trỏ PLAYWRIGHT_BROWSERS_PATH vào cache rỗng; dùng cache mặc định.
env -u PLAYWRIGHT_BROWSERS_PATH ./node_modules/.bin/playwright test "$@"
