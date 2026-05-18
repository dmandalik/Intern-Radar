#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PACK="${INTERNRADAR_PACK:-quant_engineering}"
MAX_FIRMS="${INTERNRADAR_MAX_FIRMS:-10}"
PORT="${INTERNRADAR_PORT:-8765}"
SCAN_MODE="auto"
OPEN_BROWSER=0

usage() {
  cat <<EOF
Usage: ./scripts/start_local.sh [options]

Starts Intern Radar locally with one command:
  1. Ensures Python deps are installed
  2. Ensures frontend deps are installed
  3. Builds the Svelte dashboard
  4. Initializes local app state
  5. Runs an initial scan when the local DB does not exist yet
  6. Launches the dashboard

Options:
  --scan               Always run a scan before launching
  --no-scan            Never run a scan before launching
  --pack PACK          Domain pack to scan (default: ${PACK})
  --max-firms N        Limit firms for startup scan (default: ${MAX_FIRMS})
  --port PORT          Dashboard port (default: ${PORT})
  --open-browser       Pass --open-browser to the dashboard command
  --help               Show this message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scan)
      SCAN_MODE="always"
      shift
      ;;
    --no-scan)
      SCAN_MODE="never"
      shift
      ;;
    --pack)
      PACK="$2"
      shift 2
      ;;
    --max-firms)
      MAX_FIRMS="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --open-browser)
      OPEN_BROWSER=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

log() {
  printf '\n[%s] %s\n' "Intern Radar" "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' is not available." >&2
    exit 1
  fi
}

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
  require_command python3
  PYTHON_BIN="$(command -v python3)"
fi

if ! "${PYTHON_BIN}" -c "import bs4, fastapi, httpx, jinja2, openpyxl, yaml, pydantic, typer, uvicorn" >/dev/null 2>&1; then
  log "Installing Python dependencies"
  "${PYTHON_BIN}" -m pip install -e "${ROOT_DIR}[dev]"
fi

require_command npm

FRONTEND_DIR="${ROOT_DIR}/internradar/dashboard/frontend"
if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  log "Installing frontend dependencies"
  if [[ -f "${FRONTEND_DIR}/package-lock.json" ]]; then
    (cd "${FRONTEND_DIR}" && npm ci)
  else
    (cd "${FRONTEND_DIR}" && npm install)
  fi
fi

log "Building dashboard frontend"
(cd "${FRONTEND_DIR}" && npm run build)

DB_PATH="${ROOT_DIR}/.internradar/internradar.sqlite3"
HAD_DB=0
if [[ -f "${DB_PATH}" ]]; then
  HAD_DB=1
fi

log "Initializing local state"
(cd "${ROOT_DIR}" && "${PYTHON_BIN}" -m internradar init --local)

if [[ "${SCAN_MODE}" == "always" ]] || [[ "${SCAN_MODE}" == "auto" && "${HAD_DB}" -eq 0 ]]; then
  log "Running startup scan for pack '${PACK}' with max ${MAX_FIRMS} firms"
  (cd "${ROOT_DIR}" && "${PYTHON_BIN}" -m internradar scan --pack "${PACK}" --max-firms "${MAX_FIRMS}")
fi

log "Launching dashboard on http://127.0.0.1:${PORT}"
if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  exec "${PYTHON_BIN}" -m internradar dashboard --port "${PORT}" --open-browser
fi

exec "${PYTHON_BIN}" -m internradar dashboard --port "${PORT}"
