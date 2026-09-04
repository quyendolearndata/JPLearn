#!/usr/bin/env bash
# Web E2E (Playwright) against the FastAPI backend — the only backend as of ADR-004.
#
#   apps/api-python/differential/web-e2e-python.sh [--project=chromium ...]
#
# Dựng DB test riêng (Alembic migrate + seed), chạy FastAPI trên port động, dựng nội dung
# thật (upload MP4 kho stock → submit-qa → publish → transcode HLS → register),
# build + serve web trỏ vào API, rồi playwright test.
# Mặc định chạy mọi project trong playwright.config.ts (chromium + webkit).
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_PY="$REPO/apps/api-python/.venv/bin/python"

get_free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()'
}

PY_PORT="${PY_PORT:-$(get_free_port)}"
WEB_PORT="${WEB_PORT:-$(get_free_port)}"
RUN_ID="$(date +%Y%m%d%H%M%S)_$RANDOM"
E2E_PROJECT="jplearn-web-e2e-${RUN_ID}"
STORAGE="$(mktemp -d /tmp/jplearn-web-e2e-py-storage.XXXXXX)"
API_PID=""
WEB_PID=""
ITEM_ID="00000000-0000-4000-8000-0000000000c1" # seed-ci0-daily-home (draft 30s)
SOURCE_MP4="$REPO/media/stock/mp4/level-0-wash-hands.mp4"

cleanup() {
  set +e
  echo "== Cleaning up E2E resources =="
  if [[ -n "$WEB_PID" ]] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
  "$VENV_PY" "$REPO/apps/api-python/differential/db.py" --project "$E2E_PROJECT" down >/dev/null 2>&1 || true
  rm -rf "$STORAGE"
}
trap cleanup EXIT ERR INT TERM

wait_http() { # url, name
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null "$1" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "timeout waiting for $2 at $1" >&2
  exit 1
}

echo "== 1/5 docker db-test (Alembic migrate + seed) [project=$E2E_PROJECT] =="
DB_LINE="$("$VENV_PY" "$REPO/apps/api-python/differential/db.py" --project "$E2E_PROJECT" up | grep E2E_DB_READY)"
DATABASE_URL="${DB_LINE#E2E_DB_READY }"

echo "== 2/5 FastAPI :$PY_PORT =="
(
  cd "$REPO/apps/api-python"
  DATABASE_URL="$DATABASE_URL" \
  JWT_SECRET="test-secret-at-least-32-bytes-long-for-pyjwt-security" \
  API_PUBLIC_URL="http://localhost:$PY_PORT" \
  STORAGE_ROOT="$STORAGE" \
  ENVIRONMENT="test" \
  CORS_ORIGIN_REGEX="^https?://(localhost|127\\.0\\.0\\.1)(:[0-9]+)?$" \
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
PLAYWRIGHT_TEST_BASE_URL="http://localhost:$WEB_PORT" \
  env -u PLAYWRIGHT_BROWSERS_PATH ./node_modules/.bin/playwright test "$@"
