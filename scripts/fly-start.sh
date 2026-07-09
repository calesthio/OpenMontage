#!/usr/bin/env bash
set -euo pipefail

export OPENMONTAGE_PROJECTS_DIR="${OPENMONTAGE_PROJECTS_DIR:-/data/projects}"
mkdir -p "$OPENMONTAGE_PROJECTS_DIR"

process="${1:-${FLY_PROCESS_GROUP:-mcp}}"

case "$process" in
  mcp|app)
    if [[ "${CREATE_DEMO_PROJECT:-true}" == "true" && ! -f "$OPENMONTAGE_PROJECTS_DIR/.demo_created" ]]; then
      if python scripts/backlot_simulate_run.py --project ray-demo --fast; then
        date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OPENMONTAGE_PROJECTS_DIR/.demo_created"
      else
        echo "[startup] demo project seed failed; continuing without marker"
      fi
    fi
    exec uvicorn backlot.server:app --host 0.0.0.0 --port "${PORT:-8080}"
    ;;
  worker)
    exec python -m hosted_pipeline.worker
    ;;
  *)
    echo "Unknown process group: $process" >&2
    exit 64
    ;;
esac
