#!/usr/bin/env bash
#
# preflight.sh — pre-demo readiness gate. MUST be ALL GREEN before any
# judged demo or release tag.
#
# Checks (in order):
#   1. Backend health (HTTP 200 on /health)
#   2. Audit chain integrity (verify endpoint returns ok=true)
#   3. Phi-3.5 LLM availability (informational only — not a blocker)
#   4. Latest mission has detections (sanity check)
#
# Exits 0 if ALL GREEN, 1 if any blocking check fails.
#
# Usage:
#   ./scripts/preflight.sh
#

set -uo pipefail

PORT="${ASTRA_BACKEND_PORT:-8000}"
HOST="${ASTRA_BACKEND_HOST:-127.0.0.1}"
BASE="http://${HOST}:${PORT}"

green='\033[0;32m'; red='\033[0;31m'; yellow='\033[0;33m'; reset='\033[0m'
fail=0

check() {
  local label="$1"; local cmd="$2"; local blocking="${3:-1}"
  if eval "${cmd}" >/dev/null 2>&1; then
    printf "  ${green}[OK]${reset}   %s\n" "${label}"
  else
    if [[ "${blocking}" == "1" ]]; then
      printf "  ${red}[FAIL]${reset} %s\n" "${label}"
      fail=$((fail + 1))
    else
      printf "  ${yellow}[skip]${reset} %s\n" "${label}"
    fi
  fi
}

echo "[preflight] target ${BASE}"
echo

check "backend /health returns 200" \
  "curl -s -o /dev/null -w '%{http_code}' ${BASE}/health | grep -q 200"

check "audit chain verify ok=true" \
  "curl -s ${BASE}/api/v1/audit/verify | grep -q '\"ok\":true'"

check "Phi-3.5 LLM available (informational)" \
  "curl -s ${BASE}/api/v1/chat/status | grep -q '\"llm_available\":true'" 0

check "at least one mission ingested" \
  "curl -s ${BASE}/api/v1/ingest?limit=1 | grep -q '\"id\":'"

echo
if [[ "${fail}" == "0" ]]; then
  printf "${green}[preflight] ALL GREEN${reset}\n"
  exit 0
else
  printf "${red}[preflight] %d check(s) failed — DO NOT DEMO${reset}\n" "${fail}"
  exit 1
fi
