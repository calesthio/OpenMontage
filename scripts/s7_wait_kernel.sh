#!/usr/bin/env bash
# Wait for one Kaggle kernel run to reach a terminal status.
#
# Bounded: one status call per 45 s, at most $2 minutes of waiting per call
# ($3 = max attempts). This is the "one status call between phases" rule
# implemented as a single background watcher instead of an agent poll loop.
#
# Usage: scripts/s7_wait_kernel.sh [slug] [max_minutes]
set -u
SLUG="${1:-forts845/openmontage-runner}"
MAX_MIN="${2:-25}"
DEADLINE=$(( $(date +%s) + MAX_MIN * 60 ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  LINE="$(kaggle kernels status "$SLUG" 2>&1 | tail -1)"
  echo "[$(date -u +%H:%M:%SZ)] $LINE"
  case "$LINE" in
    *COMPLETE*|*ERROR*|*CANCEL*|*FAIL*|*COMPLETED*)
      echo "TERMINAL: $LINE"
      exit 0
      ;;
  esac
  sleep 45
done
echo "TIMEOUT after ${MAX_MIN} min (no terminal status yet)"
exit 3
