"""GIF search via Giphy API.

Returns animated GIF URLs for use as engagement overlays, reaction inserts,
and emotional reinforcement in video compositions.
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


class GiphySearch(BaseTool):
    name = "giphy_search"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "gif_search"
    provider = "giphy"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    install_instructions = (
        "Set GIPHY_API_KEY to your Giphy API key.\n"
        "  Get a free key at https://developers.giphy.com/dashboard/"
    )
    agent_skills = []

    capabilities = ["search_gif", "trending_gif", "reaction_overlay"]
    supports = {
        "search": True,
        "trending": True,
        "rating_filter": True,
        "mp4_output": True,
        "webp_output": True,
        "free_commercial_use": False,
    }
    best_for = [
        "reaction GIF overlays for engagement",
        "emotion and mood reinforcement",
        "social media style inserts",
        "meme-style video elements",
    ]
    not_good_for = [
        "commercial productions without Giphy licensing",
        "offline workflows",
    ]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search term (e.g. 'excited', 'mind blown')"},
            "limit": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 25,
                "description": "Number of GIFs to return",
            },
            "rating": {
                "type": "string",
                "enum": ["g", "pg", "pg-13", "r"],
                "default": "pg",
                "description": "Content rating filter",
            },
            "lang": {
                "type": "string",
                "default": "en",
                "description": "Language for search",
            },
            "trending": {
                "type": "boolean",
                "default": False,
                "description": "Return trending GIFs instead of search results",
            },
            "output_dir": {
                "type": "string",
                "description": "If provided, download MP4 version of each GIF to this directory",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["query", "limit", "rating", "lang", "trending"]
    side_effects = ["calls Giphy API"]
    user_visible_verification = ["Review returned GIF URLs match the intended emotion/reaction"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("GIPHY_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Giphy free tier

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 2.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("GIPHY_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="GIPHY_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        limit = int(inputs.get("limit", 3))
        rating = inputs.get("rating", "pg")
        lang = inputs.get("lang", "en")
        trending = bool(inputs.get("trending", False))

        try:
            if trending:
                url = "https://api.giphy.com/v1/gifs/trending"
                params: dict[str, Any] = {
                    "api_key": api_key,
                    "limit": limit,
                    "rating": rating,
                }
            else:
                url = "https://api.giphy.com/v1/gifs/search"
                params = {
                    "api_key": api_key,
                    "q": inputs["query"],
                    "limit": limit,
                    "rating": rating,
                    "lang": lang,
                }

            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            gifs = data.get("data", [])
            if not gifs:
                return ToolResult(
                    success=False,
                    error=f"No GIFs found for query: {inputs.get('query', 'trending')}",
                    data={"total_count": data.get("pagination", {}).get("total_count", 0)},
                )

            results = []
            for gif in gifs:
                images = gif.get("images", {})
                original = images.get("original", {})
                mp4_data = images.get("original_mp4") or images.get("looping", {})
                downsized = images.get("downsized_medium") or images.get("downsized", {})

                results.append({
                    "id": gif["id"],
                    "title": gif.get("title", ""),
                    "rating": gif.get("rating", ""),
                    "url": gif.get("url", ""),
                    "gif_url": original.get("url", ""),
                    "mp4_url": mp4_data.get("mp4", ""),
                    "webp_url": original.get("webp", ""),
                    "preview_url": downsized.get("url", ""),
                    "width": int(original.get("width", 0)),
                    "height": int(original.get("height", 0)),
                    "size_bytes": int(original.get("size", 0)),
                })

        except Exception as exc:
            return ToolResult(success=False, error=f"Giphy search failed: {exc}")

        # Download MP4 files if output_dir is specified
        artifacts: list[str] = []
        output_dir = inputs.get("output_dir")
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            for result in results:
                mp4_url = result.get("mp4_url")
                if not mp4_url:
                    continue
                try:
                    dl = requests.get(mp4_url, timeout=30)
                    dl.raise_for_status()
                    dest = out / f"giphy_{result['id']}.mp4"
                    dest.write_bytes(dl.content)
                    result["local_path"] = str(dest)
                    artifacts.append(str(dest))
                except Exception:
                    pass  # URL still available even if download fails

        return ToolResult(
            success=True,
            data={
                "provider": "giphy",
                "query": inputs.get("query", "trending"),
                "trending": trending,
                "count": len(results),
                "total_count": data.get("pagination", {}).get("total_count", 0),
                "gifs": results,
                # Convenience: first result's MP4 for quick overlay use
                "primary_mp4_url": results[0]["mp4_url"] if results else "",
                "primary_gif_url": results[0]["gif_url"] if results else "",
                "primary_local_path": results[0].get("local_path", "") if results else "",
            },
            artifacts=artifacts,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )
