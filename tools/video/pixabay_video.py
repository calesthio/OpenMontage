"""Stock video acquisition from Pixabay API (free)."""

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


class PixabayVideo(BaseTool):
    name = "pixabay_video"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "video_generation"
    provider = "pixabay"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set PIXABAY_API_KEY to your Pixabay API key.\n"
        "  Get one free at https://pixabay.com/api/docs/"
    )
    agent_skills = []

    capabilities = ["search_video", "download_video", "stock_video"]
    supports = {
        "video_type_filter": True,
        "category_filter": True,
        "editors_choice": True,
        "free_commercial_use": True,
    }
    best_for = [
        "large royalty-free video library",
        "category-based filtering",
        "free stock video — no cost, no attribution required",
    ]
    not_good_for = [
        "4K footage (max 1080p on standard API)",
        "custom scenes",
        "offline use",
    ]
    fallback_tools = ["pexels_video"]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search term (max 100 chars)"},
            "video_type": {
                "type": "string",
                "enum": ["all", "film", "animation"],
                "default": "all",
            },
            "category": {
                "type": "string",
                "enum": [
                    "backgrounds", "fashion", "nature", "science", "education",
                    "feelings", "health", "people", "religion", "places",
                    "animals", "industry", "computer", "food", "sports",
                    "transportation", "travel", "buildings", "business", "music",
                ],
            },
            "min_duration": {
                "type": "integer",
                "description": "Minimum duration in seconds",
            },
            "max_duration": {
                "type": "integer",
                "description": "Maximum duration in seconds",
            },
            "editors_choice": {"type": "boolean", "default": False},
            "safesearch": {"type": "boolean", "default": True},
            "per_page": {"type": "integer", "default": 5, "minimum": 3, "maximum": 200},
            "page": {"type": "integer", "default": 1},
            "preferred_quality": {
                "type": "string",
                "enum": ["large", "medium", "small", "tiny"],
                "default": "large",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["query", "video_type", "category", "page"]
    side_effects = ["writes video file to output_path", "calls Pixabay API"]
    user_visible_verification = ["Watch downloaded clip to verify it matches the intended scene"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("PIXABAY_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("PIXABAY_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="PIXABAY_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        query = inputs["query"]

        params: dict[str, Any] = {
            "key": api_key,
            "q": query,
            # Pixabay rejects per_page outside 3-200 with HTTP 400
            "per_page": max(3, min(inputs.get("per_page", 5), 200)),
            "page": inputs.get("page", 1),
            "safesearch": str(inputs.get("safesearch", True)).lower(),
        }
        if inputs.get("video_type") and inputs["video_type"] != "all":
            params["video_type"] = inputs["video_type"]
        if inputs.get("category"):
            params["category"] = inputs["category"]
        if inputs.get("editors_choice"):
            params["editors_choice"] = "true"

        try:
            search_response = requests.get(
                "https://pixabay.com/api/videos/",
                params=params,
                timeout=30,
            )
            search_response.raise_for_status()
            data = search_response.json()

            hits = data.get("hits", [])

            # Filter by duration if specified
            min_dur = inputs.get("min_duration")
            max_dur = inputs.get("max_duration")
            if min_dur or max_dur:
                filtered = []
                for h in hits:
                    dur = h.get("duration", 0)
                    if min_dur and dur < min_dur:
                        continue
                    if max_dur and dur > max_dur:
                        continue
                    filtered.append(h)
                hits = filtered

            if not hits:
                return ToolResult(
                    success=False,
                    error=f"No videos found for query: {query}",
                    data={"total_results": data.get("total", 0)},
                )

            hit = hits[0]
            preferred = inputs.get("preferred_quality", "large")
            video_info = hit.get("videos", {}).get(preferred)
            if not video_info:
                # Fallback to best available
                for quality in ["large", "medium", "small", "tiny"]:
                    video_info = hit.get("videos", {}).get(quality)
                    if video_info:
                        break

            if not video_info:
                return ToolResult(success=False, error="No downloadable video file found.")

            # Download immediately — Pixabay URLs expire
            video_url = video_info["url"]
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", f"pixabay_video_{hit['id']}.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Pixabay video search failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "pixabay",
                "video_id": hit["id"],
                "user": hit.get("user", "Unknown"),
                "tags": hit.get("tags", ""),
                "duration_seconds": hit.get("duration"),
                "width": video_info.get("width"),
                "height": video_info.get("height"),
                "query": query,
                "output": str(output_path),
                "total_results": data.get("total", 0),
                "results_returned": len(hits),
                "license": "Pixabay Content License (free, no attribution required)",
                "page_url": hit.get("pageURL", ""),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )
