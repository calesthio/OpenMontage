"""YouTube uploader for OpenMontage export bundles.

Usage:
  python tools/publish/youtube_uploader.py --export-path path/to/exports/<project> \
    --client-secrets client_secrets.json

The script performs an OAuth2 installed-app flow (opens browser), caches credentials
in youtube_token.json, reads metadata from the export bundle (metadata/metadata.json),
and uploads the video with metadata and optional thumbnail.

Dependencies (added to requirements.txt):
  google-api-python-client, google-auth-oauthlib, google-auth-httplib2

This uploader is intentionally minimal and uses resumable uploads.
"""
import argparse
import json
import os
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes required for uploading videos and setting thumbnails
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

TOKEN_PATH = "youtube_token.json"


def load_metadata(export_path):
    meta_file = os.path.join(export_path, "metadata", "metadata.json")
    if not os.path.exists(meta_file):
        raise FileNotFoundError(f"metadata.json not found at {meta_file}")
    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_video_file(export_path):
    video_dir = os.path.join(export_path, "video")
    if not os.path.isdir(video_dir):
        raise FileNotFoundError(f"video directory not found at {video_dir}")
    # pick first mp4 (deterministic sort)
    files = sorted([p for p in os.listdir(video_dir) if p.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))])
    if not files:
        raise FileNotFoundError("No video file found in video/ directory")
    return os.path.join(video_dir, files[0])


def build_youtube_client(client_secrets_file):
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_PATH, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    youtube = build("youtube", "v3", credentials=creds)
    return youtube


def resumable_upload(youtube, body, media_file):
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(media_file, chunksize=10 * 1024 * 1024, resumable=True)
    )

    response = None
    error = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
        except Exception as e:
            error = e
            retry += 1
            if retry > 10:
                raise
            print(f"Transient error during upload: {e}. Retrying in {2 ** retry} seconds...")
            time.sleep(2 ** retry)
    return response


def set_thumbnail(youtube, video_id, thumbnail_path):
    try:
        request = youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path)
        )
        response = request.execute()
        return response
    except Exception as e:
        print(f"Failed to set thumbnail: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Upload OpenMontage export bundle to YouTube")
    parser.add_argument("--export-path", required=True, help="Path to the export bundle (exports/<project>)")
    parser.add_argument("--client-secrets", required=True, help="Path to Google OAuth client_secrets.json")
    parser.add_argument("--privacy", choices=["public", "private", "unlisted"], default="private")
    parser.add_argument("--thumbnail", default=None, help="Optional thumbnail path (overrides exported thumbnail)")
    args = parser.parse_args()

    export_path = args.export_path
    client_secrets = args.client_secrets

    if not os.path.exists(client_secrets):
        print("client_secrets file not found. Create OAuth 2.0 Client ID credentials in Google Cloud and download JSON.")
        sys.exit(1)

    metadata = load_metadata(export_path)
    video_file = get_video_file(export_path)

    title = metadata.get("title") or os.path.basename(video_file)
    description = metadata.get("description") or ""
    tags = metadata.get("tags") or []

    youtube = build_youtube_client(client_secrets)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags
        },
        "status": {
            "privacyStatus": args.privacy
        }
    }

    print(f"Uploading {video_file} to YouTube as '{title}' (privacy={args.privacy})...")
    result = resumable_upload(youtube, {"snippet,status": body}, video_file)
    video_id = result.get("id")
    if not video_id:
        print(f"Upload failed, response: {result}")
        sys.exit(1)

    video_url = f"https://youtu.be/{video_id}"
    print(f"Upload complete: {video_url}")

    # set thumbnail if available
    thumb_path = args.thumbnail
    if not thumb_path:
        exported_thumb = os.path.join(export_path, "thumbnails")
        if os.path.isdir(exported_thumb):
            # pick first image file
            thumbs = sorted([p for p in os.listdir(exported_thumb) if p.lower().endswith((".png", ".jpg", ".jpeg"))])
            if thumbs:
                thumb_path = os.path.join(exported_thumb, thumbs[0])
    if thumb_path and os.path.exists(thumb_path):
        print(f"Setting thumbnail: {thumb_path}")
        set_thumbnail(youtube, video_id, thumb_path)

    print("Done.")


if __name__ == "__main__":
    main()
