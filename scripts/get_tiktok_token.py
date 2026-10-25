"""One-time: get a TikTok refresh token.

1. In developers.tiktok.com, add Login Kit + Content Posting API to your app and register a
   redirect URI you control, e.g. https://your-site.vercel.app/tiktok-callback (the page can 404).
2. Run:  python scripts/get_tiktok_token.py
3. Open the printed URL, approve, then paste the full URL you were redirected to.
"""
import secrets
import urllib.parse

import requests

client_key = input("TikTok client key: ").strip()
client_secret = input("TikTok client secret: ").strip()
redirect_uri = input("Redirect URI (exactly as registered): ").strip()
state = secrets.token_urlsafe(16)  # CSRF protection

params = {
    "client_key": client_key,
    "scope": "user.info.basic,video.upload,video.publish",
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "state": state,
}
print("\nOpen this URL and approve:\n")
print("https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params))

back = input("\nPaste the full redirected URL: ").strip()
query = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
if query.get("state", [""])[0] != state:
    raise SystemExit("State mismatch — possible CSRF. Start again.")

r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
    "client_key": client_key,
    "client_secret": client_secret,
    "code": query["code"][0],
    "grant_type": "authorization_code",
    "redirect_uri": redirect_uri,
}, timeout=30)
data = r.json()
if "refresh_token" not in data:
    raise SystemExit(f"Token exchange failed: {data}")
print("\nSave these as secrets (never commit them):")
print(f"TIKTOK_CLIENT_KEY={client_key}")
print(f"TIKTOK_CLIENT_SECRET={client_secret}")
print(f"TIKTOK_REFRESH_TOKEN={data['refresh_token']}")
print(f"(refresh token valid ~{int(data.get('refresh_expires_in', 0)) // 86400} days)")
