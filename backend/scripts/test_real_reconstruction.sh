#!/usr/bin/env bash

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd jq

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
API_BASE_URL="${API_BASE_URL%/}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-5}"
POLL_TIMEOUT_SEC="${POLL_TIMEOUT_SEC:-600}"

CASE_ID="${CASE_ID:-real_case_001}"
SECTION_ID="${SECTION_ID:-section_1}"
ASPECT_RATIO="${ASPECT_RATIO:-16:9}"
DURATION_SEC="${DURATION_SEC:-4}"
QUALITY_MODE="${QUALITY_MODE:-fast_only}"
SEED="${SEED:-}"
EVIDENCE_REFS_JSON="${EVIDENCE_REFS_JSON:-[\"ev_1\",\"ev_2\"]}"
REFERENCE_IMAGE_URIS_JSON="${REFERENCE_IMAGE_URIS_JSON:-[]}"
NEGATIVE_PROMPT="${NEGATIVE_PROMPT:-no dramatic explosion, fire, smoke, cinematic crash effects, stylized motion blur, invented pedestrians, or extra vehicles not supported by evidence}"

DEFAULT_SCENE_DESCRIPTION="$(cat <<'EOF'
Daylight urban four-way signalized intersection viewed from a fixed, evidence-style camera perspective with no cinematic movement. The roadway is dry asphalt with clear lane markings, marked crosswalks, and two travel lanes in each direction. Vehicle A, a dark midsize sedan, travels southbound in the left through lane at a moderate city speed and enters the intersection late in the signal cycle. Vehicle B, a white compact SUV, travels eastbound in the inside through lane and proceeds into the intersection on the next green phase. Vehicle A does not clear the conflict zone before Vehicle B arrives. The front-right corner of Vehicle A strikes the driver-side front quarter of Vehicle B near the center of the intersection. After impact, Vehicle A rotates clockwise roughly 30 to 45 degrees and comes to rest angled southeast within the southbound lanes. Vehicle B is displaced laterally toward the northeast, rotates slightly counterclockwise, and stops near the eastbound crosswalk. Keep timing, trajectories, vehicle spacing, and post-impact motion physically plausible and neutral. Show no pedestrians, no emergency vehicles, no weather change, and no damage details beyond what is necessary to communicate the collision mechanics.
EOF
)"
SCENE_DESCRIPTION="${SCENE_DESCRIPTION:-$DEFAULT_SCENE_DESCRIPTION}"

if [[ -n "$SEED" ]]; then
  SEED_JSON="$SEED"
else
  SEED_JSON="null"
fi

submit_body="$(jq -n \
  --arg case_id "$CASE_ID" \
  --arg section_id "$SECTION_ID" \
  --arg scene_description "$SCENE_DESCRIPTION" \
  --arg aspect_ratio "$ASPECT_RATIO" \
  --arg quality_mode "$QUALITY_MODE" \
  --arg negative_prompt "$NEGATIVE_PROMPT" \
  --argjson duration_sec "$DURATION_SEC" \
  --argjson seed "$SEED_JSON" \
  --argjson evidence_refs "$EVIDENCE_REFS_JSON" \
  --argjson reference_image_uris "$REFERENCE_IMAGE_URIS_JSON" \
  '{
    case_id: $case_id,
    section_id: $section_id,
    scene_description: $scene_description,
    evidence_refs: $evidence_refs,
    reference_image_uris: $reference_image_uris,
    duration_sec: $duration_sec,
    aspect_ratio: $aspect_ratio,
    negative_prompt: $negative_prompt,
    seed: $seed,
    quality_mode: $quality_mode
  }'
)"

submit_response_file="$(mktemp)"
status_response_file="$(mktemp)"
trap 'rm -f "$submit_response_file" "$status_response_file"' EXIT

submit_http_status="$(
  curl -sS \
    -o "$submit_response_file" \
    -w "%{http_code}" \
    -X POST "${API_BASE_URL}/reconstruction/jobs" \
    -H "Content-Type: application/json" \
    -d "$submit_body"
)"

if [[ "$submit_http_status" != "202" ]]; then
  echo "Reconstruction job creation failed with HTTP ${submit_http_status}" >&2
  cat "$submit_response_file" >&2
  exit 1
fi

job_id="$(jq -r '.job_id // empty' "$submit_response_file")"
poll_url="$(jq -r '.poll_url // empty' "$submit_response_file")"

if [[ -z "$job_id" || -z "$poll_url" ]]; then
  echo "Job creation response did not include job_id or poll_url" >&2
  cat "$submit_response_file" >&2
  exit 1
fi

echo "Submitted reconstruction job: ${job_id}"
echo "Polling: ${API_BASE_URL}${poll_url}"

deadline_epoch="$(( $(date +%s) + POLL_TIMEOUT_SEC ))"

while true; do
  now_epoch="$(date +%s)"
  if (( now_epoch >= deadline_epoch )); then
    echo "Timed out waiting for reconstruction job ${job_id}" >&2
    exit 1
  fi

  poll_http_status="$(
    curl -sS \
      -o "$status_response_file" \
      -w "%{http_code}" \
      "${API_BASE_URL}${poll_url}"
  )"

  if [[ "$poll_http_status" != "200" ]]; then
    echo "Polling failed with HTTP ${poll_http_status}" >&2
    cat "$status_response_file" >&2
    exit 1
  fi

  job_status="$(jq -r '.status // empty' "$status_response_file")"
  progress="$(jq -r '.progress // 0' "$status_response_file")"
  error_message="$(jq -r '.error // empty' "$status_response_file")"

  echo "status=${job_status} progress=${progress}"

  if [[ "$job_status" == "completed" ]]; then
    echo
    echo "Final job payload:"
    jq . "$status_response_file"
    exit 0
  fi

  if [[ "$job_status" == "failed" ]]; then
    echo
    echo "Job failed: ${error_message}" >&2
    jq . "$status_response_file" >&2
    exit 1
  fi

  sleep "$POLL_INTERVAL_SEC"
done
