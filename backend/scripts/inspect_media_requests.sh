#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]]; then
    PYTHON_BIN="$BACKEND_DIR/.venv/Scripts/python.exe"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "No Python interpreter found. Set PYTHON_BIN or create backend/.venv." >&2
    exit 1
  fi
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/inspect_media_requests.py" "$@"
