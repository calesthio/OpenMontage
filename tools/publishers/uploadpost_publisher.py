"""Upload-Post publisher — publish videos and photos to 11 social platforms via a single API.

Upload-Post (https://upload-post.com) provides a unified API that publishes to
Instagram, TikTok, YouTube, LinkedIn, Facebook, X (Twitter), Threads, Pinterest,
Bluesky, Reddit, and Google Business Profile.

Users connect their social accounts through Upload-Post's dashboard with two clicks
(no app creation, no developer tokens) and get a single API key for all platforms.
Free tier includes 10 uploads/month with no credit card required.

Docs: https://docs.upload-post.com
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

SUPPORTED_PLATFORMS = [
    "instagram",
    "tiktok",
    "youtube",
    "linkedin",
    "facebook",
    "x",
    "threads",
    "pinterest",
    "bluesky",
    "reddit",
    "google_business",
]

BASE_URL = "https://api.upload-post.com/api"


class UploadPostPublisher(BaseTool):
    name = "uploadpost_publisher"
    version = "1.0.0"
    tier = ToolTier.PUBLISH
    capability = "social_publishing"
    provider = "uploadpost"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["env:UPLOADPOST_API_KEY"]
    install_instructions = (
        "1. Create a free account at https://upload-post.com (no credit card needed).\n"
        "2. Connect your social accounts with two clicks — no app creation or developer tokens required.\n"
        "3. Generate an API key from the dashboard.\n"
        "4. Set UPLOADPOST_API_KEY in your .env file.\n"
        "Free tier: 10 uploads/month across all platforms."
    )

    capabilities = [
        "publish_video",
        "publish_photo",
        "publish_text",
        "schedule_post",
        "queue_post",
        "multi_platform",
    ]
    supports = {
        "video": True,
        "photo": True,
        "carousel": True,
        "text_only": True,
        "scheduling": True,
        "queue": True,
        "async_upload": True,
        "first_comment": True,
        "multi_platform_single_request": True,
        "platforms": SUPPORTED_PLATFORMS,
    }
    best_for = [
        "publishing finished videos to multiple social platforms at once",
        "scheduling posts across Instagram, TikTok, YouTube, LinkedIn, X, and more",
        "zero-config social publishing — no app creation or OAuth setup per platform",
    ]
    not_good_for = [
        "video generation (use video generation tools instead)",
        "editing or post-processing (use FFmpeg or Remotion tools)",
    ]
    fallback_tools = []

    input_schema = {
        "type": "object",
        "required": ["platforms", "profile_username"],
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Path to the video file to publish",
            },
            "photo_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paths to photo files (for photo posts or carousels)",
            },
            "platforms": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": SUPPORTED_PLATFORMS,
                },
                "description": "Platforms to publish to",
            },
            "profile_username": {
                "type": "string",
                "description": "Upload-Post profile username (linked social accounts)",
            },
            "title": {
                "type": "string",
                "description": "Post title (required for YouTube, Reddit)",
            },
            "description": {
                "type": "string",
                "description": "Post description / caption",
            },
            "scheduled_date": {
                "type": "string",
                "description": "ISO-8601 datetime for scheduling (e.g. 2025-01-15T14:00:00Z)",
            },
            "timezone": {
                "type": "string",
                "description": "IANA timezone (e.g. America/New_York, Europe/Madrid)",
            },
            "add_to_queue": {
                "type": "boolean",
                "default": False,
                "description": "Auto-schedule to next available queue slot",
            },
            "first_comment": {
                "type": "string",
                "description": "Auto-post a comment after publishing (e.g. hashtags)",
            },
            "facebook_page_id": {"type": "string"},
            "pinterest_board_id": {"type": "string"},
            "target_linkedin_page_id": {"type": "string"},
            "document_path": {
                "type": "string",
                "description": "Path to document file for LinkedIn (PDF, PPT, PPTX, DOC, DOCX)",
            },
            "media_type": {
                "type": "string",
                "enum": ["IMAGE", "STORIES", "POSTS"],
                "description": "Platform-specific media type override",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, backoff_seconds=5.0, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["video_path", "platforms", "profile_username"]
    side_effects = [
        "publishes content to social media platforms",
        "calls Upload-Post API",
    ]
    user_visible_verification = [
        "Check post URL(s) returned in the publish log",
        "Verify post appears on each target platform",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("UPLOADPOST_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Upload-Post free tier: 10 uploads/month, no cost per call
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Async upload + polling typically takes 30-120s depending on file size
        return 60.0

    def _poll_status(
        self,
        headers: dict[str, str],
        request_id: str | None = None,
        job_id: str | None = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Poll Upload-Post status endpoint until completion or timeout."""
        import requests

        params: dict[str, str] = {}
        if request_id:
            params["request_id"] = request_id
        elif job_id:
            params["job_id"] = job_id
        else:
            return {"status": "ERROR", "error": "No request_id or job_id to poll"}

        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{BASE_URL}/uploadposts/status",
                headers=headers,
                params=params,
                timeout=30,
            )
            if not resp.ok:
                return {"status": "ERROR", "error": f"Status poll failed: {resp.status_code}"}
            data = resp.json()
            status = data.get("status", "UNKNOWN")
            if status in ("FINISHED", "ERROR"):
                return data
            time.sleep(5)

        return {"status": "ERROR", "error": "Upload timed out waiting for completion"}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="UPLOADPOST_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        headers = {"Authorization": f"Apikey {api_key}"}

        platforms = inputs["platforms"]
        profile = inputs["profile_username"]
        title = inputs.get("title", "")
        description = inputs.get("description", "")
        video_path = inputs.get("video_path")
        photo_paths = inputs.get("photo_paths") or []

        # Build the multipart form data
        form_data: dict[str, Any] = {"user": profile}
        if title:
            form_data["title"] = title
        if description:
            form_data["description"] = description
        if inputs.get("scheduled_date"):
            form_data["scheduled_date"] = inputs["scheduled_date"]
        if inputs.get("timezone"):
            form_data["timezone"] = inputs["timezone"]
        if inputs.get("add_to_queue"):
            form_data["add_to_queue"] = "true"
        if inputs.get("first_comment"):
            form_data["first_comment"] = inputs["first_comment"]
        if inputs.get("facebook_page_id"):
            form_data["facebook_page_id"] = inputs["facebook_page_id"]
        if inputs.get("pinterest_board_id"):
            form_data["pinterest_board_id"] = inputs["pinterest_board_id"]
        if inputs.get("target_linkedin_page_id"):
            form_data["target_linkedin_page_id"] = inputs["target_linkedin_page_id"]
        if inputs.get("media_type"):
            form_data["media_type"] = inputs["media_type"]

        # Always use async for non-blocking pipeline execution
        form_data["async_upload"] = "true"

        # Build platform[] fields
        platform_fields = [("platform[]", p) for p in platforms]

        try:
            # Decide endpoint based on content type
            document_path = inputs.get("document_path")
            if video_path and Path(video_path).exists():
                files = [("video", open(video_path, "rb"))]
                endpoint = f"{BASE_URL}/upload"
            elif photo_paths:
                files = []
                for p in photo_paths:
                    if Path(p).exists():
                        files.append(("photos[]", open(p, "rb")))
                endpoint = f"{BASE_URL}/upload_photos"
            elif document_path and Path(document_path).exists():
                files = [("document", open(document_path, "rb"))]
                endpoint = f"{BASE_URL}/upload_document"
            elif title:
                # Text-only post
                files = []
                endpoint = f"{BASE_URL}/upload_text"
            else:
                return ToolResult(
                    success=False,
                    error="No video_path, photo_paths, or title provided — nothing to publish",
                )

            # Merge platform[] into form_data list for requests
            form_fields = list(form_data.items()) + platform_fields

            resp = requests.post(
                endpoint,
                headers=headers,
                data=form_fields,
                files=files if files else None,
                timeout=120,
            )

            # Close opened files
            for _, f in (files if files else []):
                if hasattr(f, "close"):
                    f.close()

            if not resp.ok:
                detail = resp.text[:500]
                return ToolResult(
                    success=False,
                    error=f"Upload-Post API error ({resp.status_code}): {detail}",
                )

            result_data = resp.json()
            request_id = result_data.get("request_id")
            job_id = result_data.get("job_id")

            # If scheduled, return immediately with job_id
            if inputs.get("scheduled_date") or inputs.get("add_to_queue"):
                return ToolResult(
                    success=True,
                    data={
                        "provider": "uploadpost",
                        "status": "scheduled",
                        "job_id": job_id,
                        "request_id": request_id,
                        "platforms": platforms,
                        "profile": profile,
                    },
                    artifacts=[],
                    cost_usd=0.0,
                    duration_seconds=round(time.time() - start, 2),
                )

            # Poll for async result
            poll_result = self._poll_status(
                headers, request_id=request_id, job_id=job_id
            )

            if poll_result.get("status") == "FINISHED":
                platform_results = poll_result.get("result", {})
                publish_entries = []
                post_urls = []
                for plat, plat_data in platform_results.items():
                    url = plat_data.get("post_url", "")
                    if url:
                        post_urls.append(url)
                    publish_entries.append(
                        {
                            "platform": plat,
                            "success": plat_data.get("success", False),
                            "post_url": url,
                            "platform_post_id": plat_data.get("platform_post_id", ""),
                        }
                    )

                return ToolResult(
                    success=True,
                    data={
                        "provider": "uploadpost",
                        "status": "published",
                        "platforms": platforms,
                        "profile": profile,
                        "results": publish_entries,
                        "post_urls": post_urls,
                        "request_id": request_id,
                    },
                    artifacts=post_urls,
                    cost_usd=0.0,
                    duration_seconds=round(time.time() - start, 2),
                )
            else:
                error_msg = poll_result.get("error", "Unknown error during upload")
                return ToolResult(
                    success=False,
                    error=f"Upload-Post publish failed: {error_msg}",
                    data={"request_id": request_id, "poll_result": poll_result},
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Upload-Post publish failed: {e}",
            )

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Preflight check: verify API key and list target platforms."""
        api_key = self._get_api_key()
        platforms = inputs.get("platforms", [])
        video_path = inputs.get("video_path", "")
        photo_paths = inputs.get("photo_paths", [])

        issues = []
        if not api_key:
            issues.append("UPLOADPOST_API_KEY not set")
        if video_path and not Path(video_path).exists():
            issues.append(f"Video file not found: {video_path}")
        for p in photo_paths:
            if not Path(p).exists():
                issues.append(f"Photo file not found: {p}")

        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": len(issues) == 0,
            "target_platforms": platforms,
            "issues": issues,
        }
