"""YouTube competitor research tool.

Uses yt-dlp (free, no API key) to search YouTube for a topic and collect
structured metadata about competing videos, then optionally fetches public
captions via youtube-transcript-api for hook/structure analysis.

Integrates the "creator research" workflow (kabo-plugins) adapted to
OpenMontage: returns a JSON-friendly result suitable for the research stage.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
    ToolRuntime,
)


class YouTubeCompetitorResearch(BaseTool):
    name = "youtube_competitor_research"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "yt-dlp"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:yt-dlp"]
    install_instructions = (
        "Install yt-dlp: pip install yt-dlp (already in many envs). "
        "Transcript analysis also needs youtube-transcript-api (pip install youtube-transcript-api)."
    )
    agent_skills = []

    capabilities = [
        "search_competitors",
        "fetch_competitor_metadata",
        "fetch_competitor_transcripts",
    ]

    best_for = [
        "YouTube niche and competitor research before scripting",
        "hook and title pattern extraction from public videos",
        "transcript-based structure analysis of successful videos",
    ]

    not_good_for = [
        "private or age-restricted videos",
        "channels without public metadata",
        "guaranteed accuracy of view counts (yt-dlp estimates)",
    ]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search query or topic."},
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Number of competitor videos to return.",
            },
            "fetch_transcripts": {
                "type": "boolean",
                "default": False,
                "description": "Fetch public captions for the top results.",
            },
            "transcript_languages": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["en"],
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "results": {"type": "array"},
            "result_count": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=50, network_required=True
    )
    idempotency_key_fields = ["query", "max_results"]
    side_effects = []
    fallback = "transcript_fetcher"

    def _search(self, query: str, n: int) -> list[dict[str, Any]]:
        url = f"ytsearch{n}:{query}"
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            "--skip-download",
            url,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        results: list[dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            results.append(data)
        return results

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "video_id": raw.get("id"),
            "title": raw.get("title"),
            "channel": raw.get("channel") or raw.get("uploader"),
            "url": raw.get("webpage_url") or raw.get("url"),
            "view_count": raw.get("view_count"),
            "duration": raw.get("duration"),
            "upload_date": raw.get("upload_date"),
            "description": (raw.get("description") or "")[:500],
        }

    def _fetch_transcript(self, video_id: str, languages: list[str]) -> dict[str, Any]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            ytt = YouTubeTranscriptApi()
            tr = ytt.fetch(video_id, languages=languages)
            text = " ".join(s.text for s in tr.snippets)
            return {
                "language": getattr(tr, "language", languages[0]),
                "word_count": len(text.split()),
                "preview": text[:1000],
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        query = inputs["query"]
        n = int(inputs.get("max_results", 5))
        fetch_tr = bool(inputs.get("fetch_transcripts", False))
        langs = inputs.get("transcript_languages", ["en"])
        start = time.time()
        try:
            raw_results = self._search(query, n)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"Competitor search failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

        results = [self._normalize(r) for r in raw_results[:n]]
        if fetch_tr:
            for r in results:
                vid = r.get("video_id")
                if vid:
                    r["transcript"] = self._fetch_transcript(vid, langs)

        return ToolResult(
            success=True,
            data={
                "query": query,
                "result_count": len(results),
                "results": results,
                "source": "yt-dlp + youtube-transcript-api",
            },
            duration_seconds=round(time.time() - start, 2),
        )
