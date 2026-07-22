"""Music search and download from Freesound.org (free with API key).

Searches Freesound's extensive library of Creative Commons audio and
downloads high-quality MP3 previews for use as background music.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
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


class FreesoundMusic(BaseTool):
    name = "freesound_music"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "music_search"
    provider = "freesound"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    # Genuinely free: no provider charge can ever be incurred (see BaseTool.paid).
    paid = False

    dependencies = []  # checked dynamically via env var
    install_instructions = (
        "Set the FREESOUND_API_KEY environment variable:\n"
        "  export FREESOUND_API_KEY=your_key_here\n"
        "Get a free key at https://freesound.org/apiv2/apply/"
    )

    agent_skills = ["music"]

    capabilities = ["search_music", "download_music", "stock_music"]
    supports = {
        "duration_filter": True,
        "rating_sort": True,
        "tag_metadata": True,
        "free_creative_commons": True,
    }
    best_for = [
        "ambient and atmospheric background music",
        "free Creative Commons licensed audio",
        "searching by mood, genre, or instrument tags",
        "finding loops, drones, and textural audio",
    ]
    not_good_for = [
        "full produced songs with vocals",
        "commercially licensed music (check individual CC licenses)",
        "offline use",
    ]

    fallback_tools = ["pixabay_music", "music_gen"]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query describing desired music mood/genre (e.g., 'dark ambient cinematic underwater')",
            },
            "min_duration": {
                "type": "number",
                "default": 30,
                "minimum": 1,
                "description": "Minimum duration in seconds",
            },
            "max_duration": {
                "type": "number",
                "default": 120,
                "maximum": 600,
                "description": "Maximum duration in seconds",
            },
            "output_path": {
                "type": "string",
                "description": "File path to save the downloaded MP3",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["query", "min_duration", "max_duration"]
    side_effects = ["writes audio file to output_path", "calls Freesound API"]
    user_visible_verification = [
        "Listen to downloaded track for mood and quality",
        "Check Creative Commons license terms for your use case",
    ]

    _BASE_URL = "https://freesound.org/apiv2"

    def get_status(self) -> ToolStatus:
        if os.environ.get("FREESOUND_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Freesound is free

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("FREESOUND_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="FREESOUND_API_KEY not set. " + self.install_instructions,
            )

        start = time.time()

        try:
            # Step 1: Search for matching sounds
            search_result = self._search(inputs, api_key)
            if not search_result:
                return ToolResult(
                    success=False,
                    error=f"No music found on Freesound for query: {inputs['query']}",
                    data={"query": inputs["query"]},
                    duration_seconds=round(time.time() - start, 2),
                )

            # Step 2: Pick the top result (sorted by rating)
            sound = search_result[0]

            # Step 3: Download the HQ MP3 preview
            output_path = self._download(sound, inputs, api_key)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Freesound music search failed: {e}",
                duration_seconds=round(time.time() - start, 2),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "freesound",
                "sound_id": sound.get("id"),
                "name": sound.get("name", "Unknown"),
                "duration_seconds": sound.get("duration"),
                "avg_rating": sound.get("avg_rating"),
                "tags": sound.get("tags", []),
                "query": inputs["query"],
                "output": str(output_path),
                "format": "mp3",
                "license": "Creative Commons (check individual sound license)",
                "freesound_url": f"https://freesound.org/people/{sound.get('username', '')}/sounds/{sound.get('id', '')}/",
                "results_found": len(search_result),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )

    def _search(self, inputs: dict[str, Any], api_key: str) -> list[dict]:
        """Search Freesound for sounds matching the query and duration filter."""
        query = inputs["query"]
        min_dur = inputs.get("min_duration", 30)
        max_dur = inputs.get("max_duration", 120)

        params = urllib.parse.urlencode({
            "query": query,
            "filter": f"duration:[{min_dur} TO {max_dur}]",
            "sort": "rating_desc",
            "fields": "id,name,duration,previews,tags,avg_rating,username",
            "token": api_key,
            "page_size": 15,
        })

        url = f"{self._BASE_URL}/search/text/?{params}"

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "OpenMontage/0.1 (music acquisition tool)"},
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = data.get("results", [])
        return results

    def _download(self, sound: dict, inputs: dict[str, Any], api_key: str) -> Path:
        """Download the HQ MP3 preview of a Freesound sound."""
        previews = sound.get("previews", {})
        # Prefer the HQ MP3 preview; fall back to LQ MP3
        audio_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

        if not audio_url:
            raise RuntimeError(
                f"No preview URL available for sound {sound.get('id')} ({sound.get('name')})"
            )

        # Build output path
        sound_name = sound.get("name", f"freesound_{sound.get('id', 'unknown')}")
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in sound_name)
        default_filename = f"freesound_{sound.get('id')}_{safe_name}.mp3"
        output_path = Path(inputs.get("output_path", default_filename))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(
            audio_url,
            headers={"User-Agent": "OpenMontage/0.1 (music acquisition tool)"},
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            output_path.write_bytes(response.read())

        return output_path
