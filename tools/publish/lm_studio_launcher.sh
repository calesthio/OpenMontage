#!/usr/bin/env bash
set -euo pipefail

# LM Studio launcher for OpenMontage YouTube uploader
# Usage (LM Studio task):
#   ./tools/publish/lm_studio_launcher.sh --export-path exports/<project> --client-secrets /path/to/client_secrets.json --privacy private
# LM Studio can set CLIENT_SECRETS as a secret/environment variable instead of passing on CLI.

EXPORT_PATH=""
CLIENT_SECRETS=""
PRIVACY="private"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --export-path) EXPORT_PATH="$2"; shift 2;;
    --client-secrets) CLIENT_SECRETS="$2"; shift 2;;
    --privacy) PRIVACY="$2"; shift 2;;
    -h|--help) echo "Usage: $0 --export-path exports/<project> --client-secrets /path/to/client_secrets.json [--privacy public|private|unlisted]"; exit 0;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

# allow environment override (useful for LM Studio secrets)
CLIENT_SECRETS=${CLIENT_SECRETS:-${CLIENT_SECRETS_ENV:-}}

if [ -z "$EXPORT_PATH" ]; then
  echo "ERROR: --export-path is required"
  exit 1
fi

if [ -z "$CLIENT_SECRETS" ]; then
  echo "ERROR: --client-secrets is required (or set CLIENT_SECRETS_ENV env var)"
  exit 1
fi

# Use the repo's python by default
PYTHON=${PYTHON:-python}

# Ensure dependencies are installed (best-effort - will not auto-upgrade)
echo "Checking dependencies (pip list may show missing packages)"
# (Assume user installed requirements via: pip install -r requirements.txt)

echo "Launching uploader for $EXPORT_PATH (privacy=$PRIVACY)"
$PYTHON tools/publish/youtube_uploader.py --export-path "$EXPORT_PATH" --client-secrets "$CLIENT_SECRETS" --privacy "$PRIVACY"

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo "Uploader exited with code $EXIT_CODE"
  exit $EXIT_CODE
fi

echo "Uploader finished."
