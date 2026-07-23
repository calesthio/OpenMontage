YouTube uploader for OpenMontage

Purpose

This folder contains a minimal CLI uploader that reads an OpenMontage export bundle (exports/<project>) and uploads the final video plus metadata and thumbnail to YouTube using the OAuth installed-app flow.

Quick start

1. Create OAuth 2.0 Client ID credentials in Google Cloud Console (Application type: Desktop) and download client_secrets.json.
2. Install dependencies:
   pip install -r requirements.txt
3. Run the uploader:
   python tools/publish/youtube_uploader.py --export-path exports/<project> --client-secrets /path/to/client_secrets.json --privacy private

Notes

- The script caches credentials in youtube_token.json.
- The script expects the export bundle layout produced by the publish director: metadata/metadata.json, video/, thumbnails/.
- For full pipeline integration, call this script in the pipeline's publish stage after export_bundle produces the export directory. This script is intentionally standalone to keep network operations separate from the pipeline engine.
