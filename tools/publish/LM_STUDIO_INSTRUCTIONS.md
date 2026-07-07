LM Studio integration for OpenMontage YouTube uploader

Overview

This repo includes a small CLI uploader (tools/publish/youtube_uploader.py) and a launcher script (tools/publish/lm_studio_launcher.sh) that LM Studio can call as a task. The launcher forwards arguments and uses the OAuth browser flow to authenticate the uploader.

Prerequisites

1. Create Google OAuth 2.0 Client ID (Application type: Desktop) in Google Cloud Console and download client_secrets.json.
2. Ensure LM Studio has access to the repo folder and can run Python.
3. Install dependencies locally or in the environment LM Studio uses:
   pip install -r requirements.txt

Notes about OAuth in LM Studio

- The uploader uses the installed-app flow (opens a local browser window for consent). LM Studio desktop should allow opening the browser; if LM Studio prevents opening the browser, run the uploader from a local shell instead to complete the OAuth step, which will save youtube_token.json.
- As an alternative, generate credentials via a local run and copy youtube_token.json to LM Studio's working directory.

Recommended LM Studio task configuration

- Working directory: project root (the OpenMontage repo path)
- Command: ./tools/publish/lm_studio_launcher.sh --export-path exports/<project> --client-secrets /absolute/path/to/client_secrets.json --privacy private
- Environment variables (optional):
  - PYTHON: path to python interpreter to use
  - CLIENT_SECRETS_ENV: path to client_secrets.json (instead of CLI arg)

Example (LM Studio command):

./tools/publish/lm_studio_launcher.sh --export-path "exports/my-project/" --client-secrets "/Users/me/keys/client_secrets.json" --privacy private

Headless / CI notes

- For fully headless systems where browser-based OAuth is impossible, run the uploader once on a machine that can open the browser to produce youtube_token.json, then copy youtube_token.json to the headless environment. The token contains a refresh token (if consented) and will allow future uploads without re-authorizing.

Security

- Treat client_secrets.json and youtube_token.json as secrets. Store them using LM Studio's secret management or restrict file permissions.

Troubleshooting

- If the uploader fails with credential errors, delete youtube_token.json and re-run the launcher to re-authenticate.
- If thumbnail doesn't set, verify thumbnail file exists in exports/<project>/thumbnails/ and is a supported image type (.png/.jpg/.jpeg).

Support

If anything fails when running inside LM Studio, share the uploader logs (stdout/stderr) and the contents of exports/<project>/metadata/metadata.json (remove any secrets) so the issue can be diagnosed.
