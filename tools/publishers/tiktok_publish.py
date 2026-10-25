"""TikTok publisher — uploads a finished render via the TikTok Content Posting API.

Two modes:
  * draft  (default) — sends the video to the creator's TikTok inbox. The human
    opens TikTok, optionally adds a trending sound, and posts. Needs scope
    `video.upload` and works before TikTok audits your developer app.
  * direct — posts immediately (scope `video.publish`). Until TikTok audits the
    app, direct posts are forced to private (SELF_ONLY).

Auth: refresh token from `scripts/get_tiktok_token.py`.
"""

from __future__ import annotations

import os
import time
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

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024  # TikTok: chunks 5-64 MB; files under 5 MB go as one chunk


class TikTokPublish(BaseTool):
    name = "tiktok_publish"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "tiktok"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["env:TIKTOK_CLIENT_KEY", "env:TIKTOK_CLIENT_SECRET", "env:TIKTOK_REFRESH_TOKEN"]
    install_instructions = (
        "Set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET and TIKTOK_REFRESH_TOKEN.\n"
        "  1. developers.tiktok.com -> create app -> add Login Kit + Content Posting API.\n"
        "  2. Register a redirect URI you control.\n"
        "  3. python scripts/get_tiktok_token.py"
    )
    agent_skills = []

    capabilities = ["upload_video", "draft_to_inbox", "write_publish_log"]
    supports = {"draft_mode": True, "direct_post": True, "aigc_label": True, "uploads": True}
    best_for = ["sending a finished vertical render to TikTok as a draft or direct post"]
    not_good_for = ["public direct posts before TikTok has audited your developer app"]
    fallback_tools = ["export_bundle"]

    input_schema = {
        "type": "object",
        "required": ["video_path"],
        "properties": {
            "video_path": {"type": "string"},
            "caption": {"type": "string", "description": "Caption incl. hashtags (direct mode only)."},
            "mode": {"type": "string", "enum": ["draft", "direct"], "default": "draft"},
            "is_aigc": {"type": "boolean", "default": True, "description": "TikTok AI-generated content label."},
            "dry_run": {"type": "boolean", "default": False},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"publish_log": {"type": "object"}, "publish_id": {"type": "string"},
                       "tiktok_status": {"type": "string"}},
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=0, network_required=True)
    retry_policy = RetryPolicy(max_retries=0)  # never auto-retry: a retried upload can double-post
    side_effects = ["uploads a video to the authenticated TikTok account (inbox draft or post)"]
    user_visible_verification = ["Open the TikTok app inbox / profile and confirm the video arrived"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    @staticmethod
    def chunk_plan(size: int) -> tuple[int, int]:
        """Return (chunk_size, total_chunk_count). The last chunk absorbs the remainder."""
        if size < CHUNK:
            return size, 1
        return CHUNK, size // CHUNK

    @staticmethod
    def _access_token() -> str:
        r = requests.post(f"{API}/oauth/token/", data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
        }, timeout=30)
        data = r.json()
        if "access_token" not in data:
            raise RuntimeError(f"TikTok token refresh failed: {str(data)[:300]}")
        return data["access_token"]

    @staticmethod
    def _check(r: requests.Response) -> dict[str, Any]:
        data = r.json()
        code = (data.get("error") or {}).get("code")
        if r.status_code != 200 or code not in (None, "ok"):
            raise RuntimeError(f"TikTok API error {r.status_code}: {str(data)[:500]}")
        return data.get("data") or {}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video = Path(inputs["video_path"]).expanduser()
        err = _social.validate_video(video)
        if err:
            return ToolResult(success=False, error=err)

        mode = inputs.get("mode", "draft")
        caption = _social.clean_text(inputs.get("caption"), 2000, strip_angle_brackets=False)
        size = video.stat().st_size
        chunk_size, count = self.chunk_plan(size)
        source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size, "total_chunk_count": count}
        meta = {"title": caption[:150], "description": caption}

        if inputs.get("dry_run"):
            return ToolResult(success=True, data={"dry_run": True, "mode": mode, "source_info": source})
        if self.get_status().value != "available":
            return ToolResult(success=False, error=f"TikTok credentials missing. {self.install_instructions}")

        try:
            headers = {"Authorization": f"Bearer {self._access_token()}",
                       "Content-Type": "application/json; charset=UTF-8"}
            if mode == "direct":
                creator = self._check(requests.post(f"{API}/post/publish/creator_info/query/",
                                                    headers=headers, timeout=30))
                options = creator.get("privacy_level_options") or []
                privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else "SELF_ONLY"
                body = {"post_info": {"title": caption, "privacy_level": privacy, "disable_comment": False,
                                      "disable_duet": False, "disable_stitch": False,
                                      "is_aigc": bool(inputs.get("is_aigc", True))},
                        "source_info": source}
                init = self._check(requests.post(f"{API}/post/publish/video/init/", headers=headers,
                                                 json=body, timeout=30))
            else:
                privacy = None
                init = self._check(requests.post(f"{API}/post/publish/inbox/video/init/", headers=headers,
                                                 json={"source_info": source}, timeout=30))

            with video.open("rb") as fh:
                for i in range(count):
                    start = i * chunk_size
                    data = fh.read(chunk_size if i < count - 1 else size - start)
                    end = start + len(data) - 1
                    r = requests.put(init["upload_url"], data=data, timeout=600, headers={
                        "Content-Type": "video/mp4", "Content-Length": str(len(data)),
                        "Content-Range": f"bytes {start}-{end}/{size}"})
                    if r.status_code not in (200, 201, 206):
                        raise RuntimeError(f"chunk {i} upload failed: {r.status_code} {r.text[:300]}")

            publish_id = init["publish_id"]
            state = "PROCESSING"
            for _ in range(30):
                time.sleep(5)
                st = self._check(requests.post(f"{API}/post/publish/status/fetch/", headers=headers,
                                               json={"publish_id": publish_id}, timeout=30))
                state = st.get("status", state)
                if state == "FAILED":
                    raise RuntimeError(f"TikTok processing failed: {st.get('fail_reason', st)}")
                if state in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                    break
        except Exception as exc:
            entry = _social.log_entry("tiktok", "failed", metadata=meta, error=str(exc))
            return ToolResult(success=False, error=str(exc), data={"publish_log": _social.publish_log(entry)})

        status = {"PUBLISH_COMPLETE": "published", "SEND_TO_USER_INBOX": "draft"}.get(state, "pending_review")
        if status == "published" and privacy == "SELF_ONLY":
            status, visibility = "pending_review", "private"
        else:
            visibility = "public" if status == "published" else None
        entry = _social.log_entry("tiktok", status, metadata=meta, visibility=visibility, video_id=publish_id)
        return ToolResult(success=True, data={"publish_log": _social.publish_log(entry),
                                              "publish_id": publish_id, "tiktok_status": state})
