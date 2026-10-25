"""YouTube publisher — uploads a finished render via the YouTube Data API v3.

Networked provider under the `publish` capability (sibling of `export_bundle`).
Defaults to a PRIVATE upload so a human reviews it in YouTube Studio before it
goes public. Vertical videos up to 3 minutes are surfaced as Shorts automatically.

Auth: OAuth refresh token with the `youtube.upload` scope only (least privilege —
the token cannot delete videos or read account data). Generate one with
`scripts/get_youtube_token.py`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.publishers import _social

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubePublish(BaseTool):
    name = "youtube_publish"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "youtube"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["env:YT_CLIENT_ID", "env:YT_CLIENT_SECRET", "env:YT_REFRESH_TOKEN"]
    install_instructions = (
        "Set YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN.\n"
        "  1. console.cloud.google.com -> enable 'YouTube Data API v3'.\n"
        "  2. OAuth consent screen (External, then Publish the app so tokens don't expire in 7 days).\n"
        "  3. Credentials -> OAuth client ID -> Desktop app -> download client_secret.json.\n"
        "  4. python scripts/get_youtube_token.py client_secret.json"
    )
    agent_skills = []

    capabilities = ["upload_video", "write_publish_log"]
    supports = {
        "shorts": True,
        "privacy_control": True,
        "synthetic_media_disclosure": True,
        "uploads": True,
    }
    best_for = [
        "uploading a finished render to YouTube / YouTube Shorts",
        "unattended publishing with a private-first review step",
    ]
    not_good_for = [
        "custom thumbnails for Shorts (YouTube picks Shorts thumbnails from frames)",
        "more than ~6 uploads/day on default API quota",
    ]
    fallback_tools = ["export_bundle"]

    input_schema = {
        "type": "object",
        "required": ["video_path", "title"],
        "properties": {
            "video_path": {"type": "string", "description": "Final render (render_report output)."},
            "title": {"type": "string", "description": "Max 100 chars; < and > are stripped."},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "hashtags": {"type": "array", "items": {"type": "string"},
                         "description": "Appended to the description, e.g. ['#Shorts', '#cybersecurity']."},
            "privacy": {"type": "string", "enum": ["private", "unlisted", "public"], "default": "private"},
            "category_id": {"type": "string", "default": "28", "description": "28 = Science & Technology."},
            "made_for_kids": {"type": "boolean", "default": False},
            "contains_synthetic_media": {"type": "boolean", "default": True,
                                         "description": "YouTube's altered/synthetic content disclosure."},
            "dry_run": {"type": "boolean", "default": False,
                        "description": "Validate and build the request without uploading."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "publish_log": {"type": "object"},
            "video_id": {"type": "string"},
            "url": {"type": "string"},
            "request_body": {"type": "object"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=True)
    retry_policy = RetryPolicy(max_retries=0)  # never auto-retry: a retried upload can double-post
    side_effects = ["uploads a video to the authenticated YouTube channel"]
    user_visible_verification = [
        "Open the returned URL (or YouTube Studio) and check title, description and visibility",
    ]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # free; costs ~1600 of the 10,000 daily quota units per upload

    def build_body(self, inputs: dict[str, Any]) -> dict[str, Any]:
        description = _social.clean_text(inputs.get("description"), 4500)
        hashtags = [h if h.startswith("#") else f"#{h}" for h in (inputs.get("hashtags") or [])]
        if hashtags:
            description = (description + "\n\n" + " ".join(_social.clean_text(h, 60) for h in hashtags)).strip()
        return {
            "snippet": {
                "title": _social.clean_text(inputs["title"], 100) or "Untitled",
                "description": _social.clean_text(description, 4900),
                "tags": _social.clean_tags(inputs.get("tags")),
                "categoryId": str(inputs.get("category_id", "28")),
            },
            "status": {
                "privacyStatus": inputs.get("privacy", "private"),
                "selfDeclaredMadeForKids": bool(inputs.get("made_for_kids", False)),
                "containsSyntheticMedia": bool(inputs.get("contains_synthetic_media", True)),
            },
        }

    @staticmethod
    def _access_token() -> str:
        r = requests.post(TOKEN_URL, data={
            "client_id": os.environ["YT_CLIENT_ID"],
            "client_secret": os.environ["YT_CLIENT_SECRET"],
            "refresh_token": os.environ["YT_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }, timeout=30)
        if r.status_code != 200 or "access_token" not in r.json():
            raise RuntimeError(f"YouTube token refresh failed ({r.status_code}): {r.text[:300]}")
        return r.json()["access_token"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video = Path(inputs["video_path"]).expanduser()
        err = _social.validate_video(video)
        if err:
            return ToolResult(success=False, error=err)

        body = self.build_body(inputs)
        privacy = body["status"]["privacyStatus"]
        meta = {"title": body["snippet"]["title"], "description": body["snippet"]["description"],
                "hashtags": inputs.get("hashtags") or []}

        if inputs.get("dry_run"):
            return ToolResult(success=True, data={"request_body": body, "dry_run": True})
        if self.get_status().value != "available":
            return ToolResult(success=False, error=f"YouTube credentials missing. {self.install_instructions}")

        try:
            token = self._access_token()
            size = video.stat().st_size
            init = requests.post(
                UPLOAD_URL,
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json; charset=UTF-8",
                         "X-Upload-Content-Type": "video/mp4",
                         "X-Upload-Content-Length": str(size)},
                json=body, timeout=60,
            )
            if init.status_code != 200 or "Location" not in init.headers:
                raise RuntimeError(f"upload init failed ({init.status_code}): {init.text[:500]}")
            with video.open("rb") as fh:
                up = requests.put(init.headers["Location"], data=fh, timeout=1800,
                                  headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
            if up.status_code not in (200, 201):
                raise RuntimeError(f"upload failed ({up.status_code}): {up.text[:500]}")
            video_id = up.json()["id"]
        except Exception as exc:
            entry = _social.log_entry("youtube", "failed", metadata=meta, visibility=privacy, error=str(exc))
            return ToolResult(success=False, error=str(exc), data={"publish_log": _social.publish_log(entry)})

        url = f"https://www.youtube.com/shorts/{video_id}"
        status = "published" if privacy == "public" else "pending_review"
        entry = _social.log_entry("youtube", status, metadata=meta, visibility=privacy, url=url, video_id=video_id)
        return ToolResult(success=True, data={"publish_log": _social.publish_log(entry),
                                              "video_id": video_id, "url": url})
