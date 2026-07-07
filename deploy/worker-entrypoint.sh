#!/usr/bin/env bash
# Render-worker entrypoint.
#
# Two modes:
#   - k8s / env-driven: set TUTORIAL + PROJECT_ID (+ BASE_URL/OFFLINE/MUSIC). After
#     rendering, uploads renders/final.mp4 to object storage when RESULT_BUCKET is set.
#   - local / passthrough: no TUTORIAL env -> forwards "$@" to render_tutorial.py.
#
# Optionally fast-forwards the baked client checkout to CLIENT_REF (specs are
# versioned) and waits for the ttsd narration sidecar first.
set -euo pipefail

CLIENT_DIR="${CLIENT_DIR:-/app/client}"

if [ -n "${CLIENT_REF:-}" ]; then
  echo "[worker] updating client checkout to ref ${CLIENT_REF}"
  git -C "$CLIENT_DIR" fetch origin "${CLIENT_REF}" || git -C "$CLIENT_DIR" fetch origin
  git -C "$CLIENT_DIR" checkout -f "${CLIENT_REF}"
  (cd "$CLIENT_DIR" && npm ci --prefer-offline >/dev/null 2>&1 || true)
fi

wait_for_ttsd() {
  if [ "${OFFLINE:-0}" = "1" ] || [ -z "${NARRATION_URL:-}" ]; then return; fi
  echo "[worker] waiting for ttsd at ${NARRATION_URL} ..."
  for _ in $(seq 1 60); do
    if curl -fsS "${NARRATION_URL}/health" >/dev/null 2>&1; then echo "[worker] ttsd ready"; return; fi
    sleep 2
  done
  echo "[worker] WARNING ttsd not ready after timeout; continuing"
}

if [ -n "${TUTORIAL:-}" ]; then
  : "${PROJECT_ID:?PROJECT_ID is required in env-driven mode}"
  wait_for_ttsd
  ARGS=(--tutorial "$TUTORIAL" --project-id "$PROJECT_ID" --client-dir "$CLIENT_DIR")
  ARGS+=(--render-runtime "${RENDER_RUNTIME:-remotion}")
  [ -n "${BASE_URL:-}" ] && ARGS+=(--base-url "$BASE_URL")
  [ "${OFFLINE:-0}" = "1" ] && ARGS+=(--offline-narration)
  [ -n "${MUSIC:-}" ] && ARGS+=(--music "$MUSIC")

  python3 /app/openmontage/render_tutorial.py "${ARGS[@]}"

  if [ -n "${RESULT_BUCKET:-}" ]; then
    echo "[worker] uploading result to bucket ${RESULT_BUCKET}"
    python3 /app/openmontage/deploy/upload_result.py \
      --project-id "$PROJECT_ID" --bucket "$RESULT_BUCKET" --key "${PROJECT_ID}/final.mp4"
  fi
else
  wait_for_ttsd
  exec python3 /app/openmontage/render_tutorial.py --client-dir "$CLIENT_DIR" "$@"
fi
