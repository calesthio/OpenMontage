"""YouTube uploader — the first NETWORKED publish-tier tool (roadmap 3.4).

export_bundle packages a deliverable locally; this tool actually publishes
it: a resumable upload to YouTube via the Data API v3, returning a
schema-valid publish_log entry with the real video id/URL. Ships the "real
uploader seam" so the publish stage stops ending at a folder on disk.

Auth is standard Google OAuth2 installed-app flow, prepared OUT OF BAND
(this is an agent tool — it must never open an interactive browser consent
mid-pipeline):

  1. Create an OAuth client (Desktop) in Google Cloud Console with the
     youtube.upload scope; download client_secret.json.
  2. Run any standard one-time authorize script to produce a token JSON
     (refresh token included).
  3. Point the env vars at both files:
       YOUTUBE_CLIENT_SECRETS_FILE=/path/client_secret.json
       YOUTUBE_TOKEN_FILE=/path/token.json

The tool reports UNAVAILABLE until both files exist, so preflight surfaces
the setup as a 1-minute env-var fix per the Setup Offer Protocol.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUpload(BaseTool):
    name = "youtube_upload"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "youtube"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = [
        "env:YOUTUBE_CLIENT_SECRETS_FILE",
        "env:YOUTUBE_TOKEN_FILE",
    ]
    install_instructions = (
        "1) Google Cloud Console → create an OAuth client (Desktop) with the "
        "youtube.upload scope and download client_secret.json. 2) Run a "
        "one-time OAuth authorize to produce token.json (refresh token). "
        "3) Set YOUTUBE_CLIENT_SECRETS_FILE and YOUTUBE_TOKEN_FILE to those "
        "paths, and `pip install google-api-python-client google-auth "
        "google-auth-oauthlib`."
    )

    agent_skills = []
    capabilities = ["upload_video", "write_publish_log"]
    supports = {"uploads": True, "resumable": True, "free": True}
    best_for = [
        "actually publishing a finished render to YouTube",
        "producing a publish_log entry with the real video id/URL",
    ]
    not_good_for = [
        "platforms other than YouTube",
        "interactive OAuth consent (must be prepared out of band)",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "title"],
        "properties": {
            "video_path": {"type": "string"},
            "title": {"type": "string", "maxLength": 100},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "category_id": {"type": "string", "description": "YouTube category id; default 22 (People & Blogs)."},
            "visibility": {"type": "string", "enum": ["public", "private", "unlisted"], "default": "private"},
            "timestamp": {"type": "string", "description": "Override ISO-8601 timestamp (tests)."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "publish_log": {"type": "object"},
            "video_id": {"type": "string"},
            "url": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=True)
    side_effects = ["uploads a video to the authorized YouTube channel"]
    user_visible_verification = [
        "Open the returned URL in YouTube Studio and confirm the video, title, and visibility",
    ]

    def get_status(self) -> ToolStatus:
        try:
            self.check_dependencies()
        except Exception:
            return ToolStatus.UNAVAILABLE
        # Env vars must also point at real files, and the client libs must
        # be importable — an env var full of a dead path isn't "available".
        for var in ("YOUTUBE_CLIENT_SECRETS_FILE", "YOUTUBE_TOKEN_FILE"):
            if not Path(os.environ.get(var, "")).is_file():
                return ToolStatus.UNAVAILABLE
        try:
            import googleapiclient  # noqa: F401
            import google.oauth2.credentials  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0   # the API is free; the account bears platform policies

    # ---- Execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_path = Path(inputs["video_path"]).expanduser()
        if not video_path.is_file():
            return ToolResult(success=False, error=f"video_path not found: {video_path}")
        if self.get_status() is not ToolStatus.AVAILABLE:
            return ToolResult(success=False, error=(
                "youtube_upload is not configured. " + self.install_instructions
            ))

        title = inputs["title"]
        visibility = inputs.get("visibility", "private")

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials.from_authorized_user_file(
                os.environ["YOUTUBE_TOKEN_FILE"], _SCOPES
            )
            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": title,
                    "description": inputs.get("description", ""),
                    "tags": inputs.get("tags", []) or [],
                    "categoryId": inputs.get("category_id", "22"),
                },
                "status": {"privacyStatus": visibility},
            }
            media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                _status, response = request.next_chunk()
            video_id = response["id"]
        except Exception as exc:
            return ToolResult(success=False, error=f"YouTube upload failed: {exc}")

        url = f"https://www.youtube.com/watch?v={video_id}"
        timestamp = inputs.get("timestamp") or datetime.now(timezone.utc).isoformat()
        entry: dict[str, Any] = {
            "platform": "youtube",
            "status": "published",
            "url": url,
            "video_id": video_id,
            "visibility": visibility,
            "timestamp": timestamp,
            "metadata_used": {"title": title, "description": inputs.get("description", "")},
        }
        publish_log = {"version": "1.0", "entries": [entry]}
        try:
            from schemas.artifacts import validate_artifact
            validate_artifact("publish_log", publish_log)
        except Exception as exc:  # pragma: no cover - defensive
            return ToolResult(success=False, error=f"publish_log failed schema validation: {exc}")

        return ToolResult(
            success=True,
            data={"publish_log": publish_log, "video_id": video_id, "url": url},
            artifacts=[],
        )
