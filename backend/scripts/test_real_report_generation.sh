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

USER_ID="${USER_ID:-demo-user}"
CASE_ID="${CASE_ID:-real_report_case_001}"
CASE_SUMMARY="${CASE_SUMMARY:-Intersection collision with witness and dashcam evidence.}"
GENERATION_INSTRUCTIONS="${GENERATION_INSTRUCTIONS:-}"
ENABLE_PUBLIC_CONTEXT="${ENABLE_PUBLIC_CONTEXT:-true}"
MAX_IMAGES="${MAX_IMAGES:-1}"
MAX_RECONSTRUCTIONS="${MAX_RECONSTRUCTIONS:-0}"
PRINT_FINAL_REPORT_JSON="${PRINT_FINAL_REPORT_JSON:-true}"

EVIDENCE_ITEMS_JSON="${EVIDENCE_ITEMS_JSON:-$(cat <<'JSON'
[
  {
    "evidence_id": "ev-1",
    "kind": "transcript",
    "title": "Witness Statement",
    "summary": "Witness says the sedan entered the intersection first and did not clear before impact."
  },
  {
    "evidence_id": "ev-2",
    "kind": "video",
    "title": "Dashcam Clip",
    "summary": "Dashcam captures approach, collision, and final rest positions."
  }
]
JSON
)}"

EVENT_CANDIDATES_JSON="${EVENT_CANDIDATES_JSON:-$(cat <<'JSON'
[
  {
    "event_id": "approach",
    "title": "Approach to Intersection",
    "description": "The sedan approaches the intersection and enters before the conflict is cleared.",
    "sort_key": "0001",
    "evidence_refs": ["ev-1"],
    "image_prompt_hint": "A dark sedan approaching a daylight urban intersection from a neutral evidence-style viewpoint.",
    "public_context_queries": ["urban intersection sight distance standards"]
  },
  {
    "event_id": "impact",
    "title": "Collision",
    "description": "The dashcam records the collision sequence and the vehicles' post-impact positions.",
    "sort_key": "0002",
    "evidence_refs": ["ev-2"],
    "scene_description": "A neutral, evidence-style collision at a daylight urban intersection with two vehicles entering the conflict zone and coming to rest after impact."
  }
]
JSON
)}"

ENTITIES_JSON="${ENTITIES_JSON:-[]}"

submit_body="$(jq -n \
  --arg user_id "$USER_ID" \
  --arg case_id "$CASE_ID" \
  --arg case_summary "$CASE_SUMMARY" \
  --arg generation_instructions "$GENERATION_INSTRUCTIONS" \
  --argjson enable_public_context "$ENABLE_PUBLIC_CONTEXT" \
  --argjson max_images "$MAX_IMAGES" \
  --argjson max_reconstructions "$MAX_RECONSTRUCTIONS" \
  --argjson evidence_items "$EVIDENCE_ITEMS_JSON" \
  --argjson event_candidates "$EVENT_CANDIDATES_JSON" \
  --argjson entities "$ENTITIES_JSON" \
  '{
    user_id: $user_id,
    enable_public_context: $enable_public_context,
    max_images: $max_images,
    max_reconstructions: $max_reconstructions,
    bundle: {
      case_id: $case_id,
      case_summary: (if $case_summary == "" then null else $case_summary end),
      generation_instructions: (if $generation_instructions == "" then null else $generation_instructions end),
      evidence_items: $evidence_items,
      event_candidates: $event_candidates,
      entities: $entities
    }
  }'
)"

submit_response_file="$(mktemp)"
status_response_file="$(mktemp)"
report_response_file="$(mktemp)"
trap 'rm -f "$submit_response_file" "$status_response_file" "$report_response_file"' EXIT

submit_http_status="$(
  curl -sS \
    -o "$submit_response_file" \
    -w "%{http_code}" \
    -X POST "${API_BASE_URL}/generate/jobs" \
    -H "Content-Type: application/json" \
    -d "$submit_body"
)"

if [[ "$submit_http_status" != "202" ]]; then
  echo "Report job creation failed with HTTP ${submit_http_status}" >&2
  cat "$submit_response_file" >&2
  exit 1
fi

job_id="$(jq -r '.job_id // empty' "$submit_response_file")"
status_url="$(jq -r '.status_url // empty' "$submit_response_file")"
stream_url="$(jq -r '.stream_url // empty' "$submit_response_file")"
report_url="$(jq -r '.report_url // empty' "$submit_response_file")"

if [[ -z "$job_id" || -z "$status_url" || -z "$report_url" ]]; then
  echo "Job creation response did not include job_id, status_url, or report_url" >&2
  cat "$submit_response_file" >&2
  exit 1
fi

echo "Submitted report generation job: ${job_id}"
echo "Status URL: ${API_BASE_URL}${status_url}"
if [[ -n "$stream_url" ]]; then
  echo "Stream URL: ${API_BASE_URL}${stream_url}"
fi
echo "Report URL: ${API_BASE_URL}${report_url}"

deadline_epoch="$(( $(date +%s) + POLL_TIMEOUT_SEC ))"

while true; do
  now_epoch="$(date +%s)"
  if (( now_epoch >= deadline_epoch )); then
    echo "Timed out waiting for report job ${job_id}" >&2
    exit 1
  fi

  poll_http_status="$(
    curl -sS \
      -o "$status_response_file" \
      -w "%{http_code}" \
      "${API_BASE_URL}${status_url}"
  )"

  if [[ "$poll_http_status" != "200" ]]; then
    echo "Polling failed with HTTP ${poll_http_status}" >&2
    cat "$status_response_file" >&2
    exit 1
  fi

  job_status="$(jq -r '.status // empty' "$status_response_file")"
  progress="$(jq -r '.progress // 0' "$status_response_file")"
  warning_count="$(jq -r '(.warnings // []) | length' "$status_response_file")"
  error_message="$(jq -r '.error // empty' "$status_response_file")"

  echo "status=${job_status} progress=${progress} warnings=${warning_count}"

  if [[ "$job_status" == "completed" ]]; then
    report_http_status="$(
      curl -sS \
        -o "$report_response_file" \
        -w "%{http_code}" \
        "${API_BASE_URL}${report_url}"
    )"

    if [[ "$report_http_status" != "200" ]]; then
      echo "Final report fetch failed with HTTP ${report_http_status}" >&2
      cat "$report_response_file" >&2
      exit 1
    fi

    echo
    echo "Final job payload:"
    jq . "$status_response_file"

    if [[ "$PRINT_FINAL_REPORT_JSON" == "true" ]]; then
      echo
      echo "Final report payload:"
      jq . "$report_response_file"
    fi

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
