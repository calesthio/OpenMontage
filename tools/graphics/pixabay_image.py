"""Stock image acquisition from Pixabay API (free)."""

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


class PixabayImage(BaseTool):
    name = "pixabay_image"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "image_generation"
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

    capabilities = ["search_image", "download_image", "stock_image"]
    supports = {
        "orientation_filter": True,
        "category_filter": True,
        "color_filter": True,
        "image_type_filter": True,
        "editors_choice": True,
        "free_commercial_use": True,
    }
    best_for = [
        "large royalty-free library (5M+ images)",
        "category-based filtering (nature, business, science, etc.)",
        "free stock images — no cost, no attribution required",
    ]
    not_good_for = [
        "full-resolution originals (standard API limited to 1280px)",
        "custom compositions",
        "offline use",
    ]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search term (max 100 chars)"},
            "image_type": {
                "type": "string",
                "enum": ["all", "photo", "illustration", "vector"],
                "default": "all",
            },
            "orientation": {
                "type": "string",
                "enum": ["all", "horizontal", "vertical"],
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
            "colors": {
                "type": "string",
                "description": "Comma-separated: grayscale, transparent, red, orange, yellow, green, turquoise, blue, lilac, pink, white, gray, black, brown",
            },
            "editors_choice": {"type": "boolean", "default": False},
            "safesearch": {"type": "boolean", "default": True},
            "per_page": {"type": "integer", "default": 5, "minimum": 3, "maximum": 200},
            "page": {"type": "integer", "default": 1},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["query", "image_type", "orientation", "category", "page"]
    side_effects = ["writes image file to output_path", "calls Pixabay API"]
    user_visible_verification = ["Check that downloaded image matches the intended scene"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("PIXABAY_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Pixabay is free

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
        if inputs.get("image_type") and inputs["image_type"] != "all":
            params["image_type"] = inputs["image_type"]
        if inputs.get("orientation") and inputs["orientation"] != "all":
            params["orientation"] = inputs["orientation"]
        if inputs.get("category"):
            params["category"] = inputs["category"]
        if inputs.get("colors"):
            params["colors"] = inputs["colors"]
        if inputs.get("editors_choice"):
            params["editors_choice"] = "true"

        try:
            search_response = requests.get(
                "https://pixabay.com/api/",
                params=params,
                timeout=30,
            )
            search_response.raise_for_status()
            data = search_response.json()

            hits = data.get("hits", [])
            if not hits:
                return ToolResult(
                    success=False,
                    error=f"No images found for query: {query}",
                    data={"total_results": data.get("total", 0)},
                )

            hit = hits[0]
            # largeImageURL is the best available at standard API tier (1280px)
            image_url = hit.get("largeImageURL", hit.get("webformatURL"))

            # Download immediately — Pixabay URLs contain embedded tokens that expire
            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()

            output_path = Path(inputs.get("output_path", f"pixabay_{hit['id']}.jpg"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Pixabay image search failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "pixabay",
                "image_id": hit["id"],
                "user": hit.get("user", "Unknown"),
                "tags": hit.get("tags", ""),
                "image_width": hit.get("imageWidth"),
                "image_height": hit.get("imageHeight"),
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
