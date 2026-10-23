"""Music search and download from Mixkit (free, no API key).

Reads the schema.org JSON-LD that Mixkit embeds in its music listing pages
(tag pages and discover/search pages). Tracks are covered by the Mixkit
Stock Music Free License: commercial use, no attribution required.
"""

from __future__ import annotations

import json
import re
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

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_ISO_DUR = re.compile(r"PT(?:(\d+)M)?(?:(\d+)S)?")


def _seconds(iso: str) -> int:
    m = _ISO_DUR.fullmatch(iso or "")
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) if m else 0


class MixkitMusic(BaseTool):
    name = "mixkit_music"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "music_search"
    provider = "mixkit_music"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "No setup required. Mixkit music is free and needs no API key."
    agent_skills = ["music"]
    capabilities = ["search_music", "download_music", "stock_music"]
    supports = {"duration_filter": True, "free_commercial_use": True, "no_api_key": True}
    best_for = ["free royalty-free background beds without attribution", "quick keyless music search"]
    not_good_for = ["custom-composed scores", "exact-length tracks"]
    fallback_tools = ["pixabay_music", "music_gen"]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Mixkit tag (e.g. 'cartoons') or free-text search"},
            "min_duration": {"type": "number", "default": 30},
            "max_duration": {"type": "number", "default": 600},
            "pick": {
                "type": "integer",
                "description": "Index into the filtered results to download. Omit to only list tracks.",
            },
            "output_path": {"type": "string", "description": "Where to save the MP3 when pick is given"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=50, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout"])
    idempotency_key_fields = ["query", "min_duration", "max_duration", "pick"]
    side_effects = ["writes audio file to output_path when pick is given", "reads mixkit.co pages"]
    user_visible_verification = ["Listen to the track for mood and loopability"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            tracks = self._search(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Mixkit music search failed: {exc}")

        data: dict[str, Any] = {"provider": self.provider, "query": inputs["query"], "tracks": tracks}
        artifacts: list[str] = []
        pick = inputs.get("pick")
        if pick is not None:
            if not 0 <= pick < len(tracks):
                return ToolResult(success=False, error=f"pick {pick} out of range ({len(tracks)} tracks)")
            out = Path(inputs.get("output_path") or f"mixkit_{tracks[pick]['id']}.mp3")
            out.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(tracks[pick]["url"], headers={"User-Agent": _UA})
            out.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            data["selected"] = tracks[pick] | {"output": str(out)}
            artifacts.append(str(out))
        return ToolResult(success=True, data=data, artifacts=artifacts,
                          duration_seconds=round(time.time() - start, 2), cost_usd=0.0)

    def _search(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        q = inputs["query"].strip().lower()
        slug = urllib.parse.quote(q.replace(" ", "-"))
        urls = [f"https://mixkit.co/free-stock-music/tag/{slug}/",
                f"https://mixkit.co/free-stock-music/discover/{slug}/"]
        lo, hi = inputs.get("min_duration", 30), inputs.get("max_duration", 600)
        for url in urls:
            tracks = [t for t in self._parse(url) if lo <= t["duration_seconds"] <= hi]
            if tracks:
                return tracks
        return []

    def _parse(self, url: str) -> list[dict[str, Any]]:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            raise
        out = []
        for block in _LD_RE.findall(html):
            for node in json.loads(block).get("@graph", []):
                for item in node.get("itemListElement", []) if node.get("@type") == "ItemList" else []:
                    if item.get("@type") != "MusicRecording":
                        continue
                    out.append({
                        "id": item["url"].rstrip("/").rsplit("/", 2)[-2],
                        "title": item.get("name", ""),
                        "artist": item.get("byArtist", ""),
                        "genre": item.get("genre", ""),
                        "duration_seconds": _seconds(item.get("duration", "")),
                        "url": item["url"],
                        "license": item.get("license", "https://mixkit.co/license/#musicFree"),
                        "page": url,
                    })
        return out
