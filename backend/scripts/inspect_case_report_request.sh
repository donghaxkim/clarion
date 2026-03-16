#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSPECTOR="${SCRIPT_DIR}/inspect_report_request.py"

find_python() {
  local candidates=(
    "${BACKEND_DIR}/.venv/Scripts/python.exe"
    "${BACKEND_DIR}/.venv/bin/python"
    "python3"
    "python"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return 0
    fi
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  echo "Could not find a Python interpreter. Set up backend/.venv or add python to PATH." >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd jq

CASE_ID="${CASE_ID:-}"
if [[ -z "${CASE_ID}" ]]; then
  echo "Set CASE_ID to an existing backend case ID." >&2
  exit 1
fi

PYTHON_BIN="$(find_python)"
OUTPUT_DIR="${OUTPUT_DIR:-$(mktemp -d)}"
RAW_JSON="${OUTPUT_DIR}/inspection.json"
INSPECT_ARGS=(
  --case-id "${CASE_ID}"
  --user-id "${USER_ID:-clarion-user}"
  --enable-public-context "${ENABLE_PUBLIC_CONTEXT:-null}"
  --pretty
)

if [[ -n "${MAX_IMAGES:-}" ]]; then
  INSPECT_ARGS+=(--max-images "${MAX_IMAGES}")
fi

if [[ -n "${MAX_RECONSTRUCTIONS:-}" ]]; then
  INSPECT_ARGS+=(--max-reconstructions "${MAX_RECONSTRUCTIONS}")
fi

"${PYTHON_BIN}" "${INSPECTOR}" "${INSPECT_ARGS[@]}" > "${RAW_JSON}"

jq '.current_request' "${RAW_JSON}" > "${OUTPUT_DIR}/current-request.json"
jq '.enriched_request_preview' "${RAW_JSON}" > "${OUTPUT_DIR}/enriched-request-preview.json"
jq '.parser_analysis_summary' "${RAW_JSON}" > "${OUTPUT_DIR}/parser-analysis-summary.json"
jq '.comparison_summary' "${RAW_JSON}" > "${OUTPUT_DIR}/comparison-summary.json"
jq '.derived_event_candidates_summary' "${RAW_JSON}" > "${OUTPUT_DIR}/derived-event-candidates-summary.json"

echo "Wrote inspection files to: ${OUTPUT_DIR}"
echo "  ${OUTPUT_DIR}/current-request.json"
echo "  ${OUTPUT_DIR}/enriched-request-preview.json"
echo "  ${OUTPUT_DIR}/parser-analysis-summary.json"
echo "  ${OUTPUT_DIR}/comparison-summary.json"
echo "  ${OUTPUT_DIR}/derived-event-candidates-summary.json"
echo
echo "Current vs enriched summary:"
jq '.comparison_summary' "${RAW_JSON}"
