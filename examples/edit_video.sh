#!/usr/bin/env bash
# Edit a video you already have: the result keeps its length and aspect ratio.
set -euo pipefail
: "${SEEDANCE_API_KEY:?export SEEDANCE_API_KEY first}"
BASE="${SEEDANCE_BASE_URL:-https://argolink.io/v1}"

REQUEST_ID=$(curl -fsS "$BASE/videos/generations" \
  -H "Authorization: Bearer $SEEDANCE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance-2.5",
    "omni_reference_task_type": "edit",
    "prompt": "Make the colors warmer and keep everything else",
    "resolution": "720p",
    "reference_videos": [{"url": "https://example.com/street.mp4"}]
  }' | jq -er .request_id)

while :; do
  STATUS=$(curl -fsS "$BASE/videos/$REQUEST_ID" -H "Authorization: Bearer $SEEDANCE_API_KEY")
  case "$(jq -r .status <<<"$STATUS")" in
    done) break ;;
    failed|expired) jq . <<<"$STATUS" >&2; exit 1 ;;
    *) echo "$(jq -r '.progress // 0' <<<"$STATUS")%" >&2; sleep 5 ;;
  esac
done

curl -fsSL "$BASE/videos/$REQUEST_ID/content" -H "Authorization: Bearer $SEEDANCE_API_KEY" -o edited.mp4
jq .usage <<<"$STATUS"
