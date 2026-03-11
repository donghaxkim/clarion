#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CASE_ID="${CASE_ID:-real_report_case_veo_001}"
CASE_SUMMARY="${CASE_SUMMARY:-Intersection collision with witness, dashcam, and a requested Veo reconstruction.}"
GENERATION_INSTRUCTIONS="${GENERATION_INSTRUCTIONS:-Prioritize one reconstruction request for the clearest collision event and keep the chronology evidence-grounded.}"
ENABLE_PUBLIC_CONTEXT="${ENABLE_PUBLIC_CONTEXT:-true}"
MAX_IMAGES="${MAX_IMAGES:-0}"
MAX_RECONSTRUCTIONS="${MAX_RECONSTRUCTIONS:-1}"
POLL_TIMEOUT_SEC="${POLL_TIMEOUT_SEC:-1200}"

EVENT_CANDIDATES_JSON="${EVENT_CANDIDATES_JSON:-$(cat <<'JSON'
[
  {
    "event_id": "approach",
    "title": "Approach to Intersection",
    "description": "The sedan approaches the intersection and enters before the conflict is cleared.",
    "sort_key": "0001",
    "evidence_refs": ["ev-1"],
    "public_context_queries": ["urban intersection sight distance standards"]
  },
  {
    "event_id": "impact",
    "title": "Collision",
    "description": "The dashcam records the collision sequence and the vehicles' post-impact positions.",
    "sort_key": "0002",
    "evidence_refs": ["ev-2"],
    "scene_description": "Daylight urban four-way signalized intersection viewed from a neutral, evidence-style perspective with no cinematic movement. A dark midsize sedan enters the conflict zone late and is struck by a white compact SUV proceeding through the intersection. The impact occurs near the center of the intersection, followed by physically plausible rotation and short post-impact travel to final rest positions. Keep vehicle spacing, timing, and post-impact motion neutral and realistic. Show no pedestrians, emergency vehicles, weather effects, or exaggerated crash damage."
  }
]
JSON
)}"

export CASE_ID
export CASE_SUMMARY
export GENERATION_INSTRUCTIONS
export ENABLE_PUBLIC_CONTEXT
export MAX_IMAGES
export MAX_RECONSTRUCTIONS
export POLL_TIMEOUT_SEC
export EVENT_CANDIDATES_JSON

exec bash "${SCRIPT_DIR}/test_real_report_generation.sh"
