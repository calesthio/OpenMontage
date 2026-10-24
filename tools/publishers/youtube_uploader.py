"""
youtube_uploader.py
Automated YouTube Shorts Uploader for OpenMontage using YouTube Data API v3.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from tools.base_tool import BaseTool, ToolResult
except ImportError:
    class ToolResult:
        def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
            self.success = success
            self.data = data or {}
            self.error = error

    class BaseTool:
        pass


class YouTubeUploader(BaseTool):
    name = "youtube_uploader"
    tool_name = "youtube_uploader"
    category = "publishers"
    description = (
        "Uploads rendered MP4 videos directly to YouTube Shorts via YouTube Data API v3. "
        "Supports OAuth2 refresh tokens, tags, category, and scheduled privacy status."
    )
    inputs_schema = {
        "type": "object",
        "properties": {
            "video_path": {"type": "string", "description": "Absolute or relative path to MP4 video"},
            "title": {"type": "string", "description": "Short title including hashtags (max 100 chars)"},
            "description": {"type": "string", "description": "Short description and hashtags"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "SEO keyword tags"},
            "privacy_status": {
                "type": "string",
                "enum": ["public", "private", "unlisted"],
                "default": "public",
                "description": "Video privacy status",
            },
            "category_id": {"type": "string", "default": "15", "description": "15 = Pets & Animals, 28 = Science & Tech"},
        },
        "required": ["video_path", "title"],
    }
    outputs_schema = {
        "type": "object",
        "properties": {
            "video_id": {"type": "string"},
            "video_url": {"type": "string"},
            "title": {"type": "string"},
            "privacy_status": {"type": "string"},
        },
    }

    def _get_authenticated_service(self):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
        except ImportError:
            raise RuntimeError("google-api-python-client and google-auth-oauthlib are required.")

        client_id = os.environ.get("YOUTUBE_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN") or os.environ.get("YT_REFRESH_TOKEN")

        token_file = Path("token.json")
        creds = None

        if refresh_token and client_id and client_secret:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )
        elif token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file))

        if not creds:
            raise RuntimeError(
                "YouTube OAuth credentials missing. Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                "and YOUTUBE_REFRESH_TOKEN in environment variables, or provide token.json."
            )

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build("youtube", "v3", credentials=creds)

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        video_path = Path(inputs["video_path"]).resolve()
        if not video_path.exists():
            return ToolResult(success=False, error=f"Video file not found: {video_path}")

        title = inputs["title"][:100]
        description = inputs.get("description", title)
        tags = inputs.get("tags", ["shorts", "wildlife", "nature", "animals", "documentary"])
        privacy_status = inputs.get("privacy_status", "public")
        category_id = inputs.get("category_id", "15")

        try:
            from googleapiclient.http import MediaFileUpload
            youtube = self._get_authenticated_service()

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024 * 1024 * 5,  # 5MB chunks
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"[YOUTUBE UPLOAD] Progress: {int(status.progress() * 100)}%")

            video_id = response.get("id")
            video_url = f"https://youtube.com/shorts/{video_id}"
            print(f"[YOUTUBE UPLOAD] Video published successfully: {video_url}")

            # Upload Custom Thumbnail if provided
            thumbnail_path = inputs.get("thumbnail_path")
            if thumbnail_path and Path(thumbnail_path).exists():
                try:
                    thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
                    youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
                    print(f"[YOUTUBE UPLOAD] Custom High-CTR Thumbnail set: {thumbnail_path}")
                except Exception as te:
                    print(f"[YOUTUBE UPLOAD] Thumbnail upload note: {te}")

            return ToolResult(
                success=True,
                data={
                    "video_id": video_id,
                    "video_url": video_url,
                    "title": title,
                    "privacy_status": privacy_status,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"YouTube upload failed: {e}")
