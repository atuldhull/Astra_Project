#!/usr/bin/env bash
#
# dev-restart.sh — kill any process holding port 8000 and start uvicorn fresh.
#
# Solves the recurring "WinError 10013 / port already in use" zombie that
# happens when uvicorn is killed by a hard interrupt instead of SIGTERM.
# Safe to run repeatedly.
#
# Usage:
#   ./scripts/dev-restart.sh              # foreground
#   ./scripts/dev-restart.sh --background # background, log to .dev-restart.log
#

set -uo pipefail

PORT="${ASTRA_BACKEND_PORT:-8000}"
HOST="${ASTRA_BACKEND_HOST:-127.0.0.1}"
PYTHON="${ASTRA_PYTHON:-D:/astra-data/venvs/astra/Scripts/python.exe}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
LOG_FILE="${REPO_ROOT}/.dev-restart.log"

bg=false
for arg in "$@"; do
  case "$arg" in
    --background|-b) bg=true ;;
    --help|-h)
      sed -n '2,15p' "$0"; exit 0 ;;
  esac
done

echo "[dev-restart] killing anything on :${PORT}"
pids=$(netstat -ano 2>/dev/null | grep ":${PORT} " | grep LISTENING | awk '{print $NF}' | sort -u)
if [[ -n "${pids}" ]]; then
  for pid in ${pids}; do
    echo "[dev-restart]   killing PID ${pid}"
    taskkill //PID "${pid}" //F >/dev/null 2>&1 || true
  done
  sleep 1
else
  echo "[dev-restart]   port :${PORT} already free"
fi

cd "${BACKEND_DIR}"
echo "[dev-restart] launching uvicorn on ${HOST}:${PORT}"
cmd=("${PYTHON}" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload)
if ${bg}; then
  nohup "${cmd[@]}" >"${LOG_FILE}" 2>&1 &
  pid=$!
  echo "[dev-restart] backend PID ${pid} (background; tail -f ${LOG_FILE})"
else
  exec "${cmd[@]}"
fi
