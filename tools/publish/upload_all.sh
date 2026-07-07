#!/usr/bin/env bash
# Upload all export bundles found under exports/*
set -euo pipefail

CLIENT_SECRETS=${1:-"client_secrets.json"}
PYTHON=${PYTHON:-python}

if [ ! -f "$CLIENT_SECRETS" ]; then
  echo "Client secrets not found: $CLIENT_SECRETS"
  echo "Pass path as first argument or place client_secrets.json in repo root."
  exit 1
fi

for d in exports/*/ ; do
  [ -d "$d" ] || continue
  echo "Uploading export: $d"
  $PYTHON tools/publish/youtube_uploader.py --export-path "$d" --client-secrets "$CLIENT_SECRETS" || echo "Upload failed for $d"
done

echo "Done." 
