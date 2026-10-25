"""One-time: get a YouTube refresh token. Run on YOUR computer (it opens a browser).

  pip install google-auth-oauthlib
  python scripts/get_youtube_token.py path/to/client_secret.json
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]  # upload only — least privilege

if len(sys.argv) != 2:
    sys.exit("usage: python scripts/get_youtube_token.py client_secret.json")

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nSave these as secrets (never commit them):")
print(f"YT_CLIENT_ID={creds.client_id}")
print(f"YT_CLIENT_SECRET={creds.client_secret}")
print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
