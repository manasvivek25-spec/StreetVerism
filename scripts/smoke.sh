#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://localhost:8000}}"
AUTHORITY_KEY="${2:-${AUTHORITY_KEY:-}}"

python3 scripts/smoke.py --base-url "$BASE_URL" ${AUTHORITY_KEY:+--authority-key "$AUTHORITY_KEY"}
