#!/usr/bin/env bash
# NFR-PERF-002: transcode an uploaded media asset (MP4) into a local HLS bundle,
# then register it so the API serves /media/<asset-id>/hls/index.m3u8.
#
# Usage:
#   ./scripts/transcode-hls.sh <asset-id> <staff-token> [api-url]
#
# Run from apps/api. Requires ffmpeg on PATH. Q1 keeps the MP4 playback_url as fallback.
set -euo pipefail

ASSET_ID="${1:?asset id required}"
TOKEN="${2:?staff bearer token required}"
API_URL="${3:-http://localhost:3001}"
STORAGE_ROOT="${STORAGE_ROOT:-storage}"
SOURCE="${STORAGE_ROOT}/${ASSET_ID}.bin"
OUT_DIR="${STORAGE_ROOT}/hls/${ASSET_ID}"

if [[ ! -f "${SOURCE}" ]]; then
  echo "missing source file ${SOURCE} (upload media first)" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
ffmpeg -y -i "${SOURCE}" \
  -codec: copy -start_number 0 \
  -hls_time 4 -hls_list_size 0 -f hls \
  -hls_segment_filename "${OUT_DIR}/segment-%03d.ts" \
  "${OUT_DIR}/index.m3u8"

curl -fsS -X POST "${API_URL}/staff/media/${ASSET_ID}/hls" \
  -H "Authorization: Bearer ${TOKEN}"
echo
echo "hls_url registered for asset ${ASSET_ID}"
