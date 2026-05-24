"""Music search and download from Pixabay Music (free, no API key).

Searches Pixabay's music section by calling the same JSON endpoint the SPA
itself uses (`Accept: application/json` + `X-Fetch-Bootstrap: 1` against
`/music/search/<query>/`). Cloudflare guards the page, so the search call
goes through `cloudscraper`. The returned CDN MP3 URL is then fetched with
plain `urllib`.

Stability: EXPERIMENTAL — depends on Pixabay's bootstrap-fetch contract
(headers + JSON shape). If it breaks again, fall back to `freesound_music`
or `music_gen`.
"""

from __future__ import annotations

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

try:
    import cloudscraper as _cloudscraper
    _HAVE_CLOUDSCRAPER = True
except ImportError:
    _cloudscraper = None
    _HAVE_CLOUDSCRAPER = False


class PixabayMusic(BaseTool):
    name = "pixabay_music"
    version = "0.2.0"
    tier = ToolTier.SOURCE
    capability = "music_search"
    provider = "pixabay_music"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []  # cloudscraper is a soft dependency — see get_status()
    install_instructions = (
        "Install cloudscraper to bypass Pixabay's Cloudflare challenge:\n"
        "  pip install cloudscraper\n"
        "No API key required. Pixabay Music is free and royalty-free.\n"
        "If the search keeps failing, the bootstrap-fetch contract may have\n"
        "changed again — fall back to freesound_music or music_gen."
    )

    agent_skills = ["music"]

    capabilities = ["search_music", "download_music", "stock_music"]
    supports = {
        "duration_filter": True,
        "free_commercial_use": True,
        "no_api_key": True,
    }
    best_for = [
        "quick background music with zero setup (no API key)",
        "royalty-free music for any commercial project",
        "high-quality produced tracks (not raw samples)",
    ]
    not_good_for = [
        "reliable long-term automation (Pixabay may change the bootstrap contract)",
        "precise metadata filtering",
        "offline use",
    ]

    fallback_tools = ["freesound_music", "music_gen"]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for music (e.g., 'upbeat corporate background')",
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
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout"])
    idempotency_key_fields = ["query", "min_duration", "max_duration"]
    side_effects = ["writes audio file to output_path", "calls Pixabay's bootstrap-fetch endpoint"]
    user_visible_verification = [
        "Listen to downloaded track for mood and quality",
    ]

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    _SEARCH_HEADERS = {
        "Accept": "application/json",
        "X-Fetch-Bootstrap": "1",
        "Referer": "https://pixabay.com/music/",
    }
    _MAX_PAGES = 5  # cap pagination at 100 tracks before giving up on the window

    def get_status(self) -> ToolStatus:
        if not _HAVE_CLOUDSCRAPER:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Pixabay Music is free

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()

        if not _HAVE_CLOUDSCRAPER:
            return ToolResult(
                success=False,
                error=(
                    "cloudscraper not installed — required to bypass Pixabay's "
                    "Cloudflare challenge. Run: pip install cloudscraper"
                ),
                duration_seconds=round(time.time() - start, 2),
            )

        try:
            tracks = self._search(inputs)
            if not tracks:
                return ToolResult(
                    success=False,
                    error=f"No music found on Pixabay for query: {inputs['query']}",
                    data={"query": inputs["query"]},
                    duration_seconds=round(time.time() - start, 2),
                )

            min_dur = inputs.get("min_duration", 30)
            max_dur = inputs.get("max_duration", 120)
            filtered = [
                t for t in tracks
                if t.get("duration") is not None
                and min_dur <= t["duration"] <= max_dur
            ]
            # Fall back to unfiltered if no matches within duration range
            if not filtered:
                filtered = tracks

            track = filtered[0]
            output_path = self._download(track, inputs)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Pixabay music search failed: {e}",
                duration_seconds=round(time.time() - start, 2),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "pixabay_music",
                "track_title": track.get("title", "Unknown"),
                "artist": track.get("artist", "Unknown"),
                "duration_seconds": track.get("duration"),
                "query": inputs["query"],
                "output": str(output_path),
                "format": "mp3",
                "license": "Pixabay Content License (free, no attribution required)",
                "results_found": len(tracks),
                "results_after_filter": len(filtered),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )

    def _search(self, inputs: dict[str, Any]) -> list[dict]:
        """Search Pixabay Music via the bootstrap-fetch JSON endpoint.

        Pixabay's SPA loads track data by re-requesting the same `/music/search/<slug>/`
        URL with `Accept: application/json` and `X-Fetch-Bootstrap: 1`. The server
        does content negotiation and returns the page state as JSON instead of HTML.
        Cloudflare guards the path, so we go through `cloudscraper`.

        Pagination uses `?pagi=N`. We page up to `_MAX_PAGES` looking for tracks
        that fit the requested duration window before returning whatever we have.
        """
        query = inputs["query"]
        slug = re.sub(r"\s+", "-", query.strip().lower())
        slug = urllib.parse.quote(slug, safe="-")
        search_url = f"https://pixabay.com/music/search/{slug}/"

        min_dur = inputs.get("min_duration", 30)
        max_dur = inputs.get("max_duration", 120)

        scraper = _cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
        )

        all_tracks: list[dict] = []
        for pagi in range(1, self._MAX_PAGES + 1):
            params = None if pagi == 1 else {"pagi": pagi}
            try:
                response = scraper.get(
                    search_url,
                    params=params,
                    headers=self._SEARCH_HEADERS,
                    timeout=30,
                )
            except Exception as exc:
                if pagi == 1:
                    raise RuntimeError(f"Cloudflare/network failure: {exc}") from exc
                break

            content_type = (response.headers.get("content-type") or "").lower()
            if response.status_code != 200 or "json" not in content_type:
                if pagi == 1:
                    raise RuntimeError(
                        f"Pixabay returned status={response.status_code} "
                        f"content-type={content_type or 'unknown'} "
                        f"— bootstrap-fetch contract may have changed"
                    )
                break

            data = response.json()
            page = data.get("page") or {}
            results = page.get("results") or []

            for item in results:
                sources = item.get("sources") or {}
                audio_url = sources.get("src")
                if not audio_url:
                    continue
                user = item.get("user") or {}
                all_tracks.append({
                    "title": item.get("name") or sources.get("filename", "Unknown"),
                    "audio_url": audio_url,
                    "duration": item.get("duration"),
                    "artist": user.get("username", "Unknown"),
                    "rating": item.get("rating"),
                    "download_count": item.get("downloadCount"),
                    "pixabay_id": item.get("id"),
                })

            in_window = [
                t for t in all_tracks
                if t.get("duration") is not None
                and min_dur <= t["duration"] <= max_dur
            ]
            if len(in_window) >= 5:
                break

            total_pages = page.get("pages") or 1
            if pagi >= total_pages:
                break

        return all_tracks

    def _download(self, track: dict, inputs: dict[str, Any]) -> Path:
        """Download an MP3 track to the output path.

        The CDN at `cdn.pixabay.com` is not Cloudflare-protected, so plain
        `urllib` is sufficient — no need to drag the scraper into the audio fetch.
        """
        audio_url = track.get("audio_url")
        if not audio_url:
            raise RuntimeError("No audio URL found for the selected track.")

        if audio_url.startswith("//"):
            audio_url = "https:" + audio_url
        elif audio_url.startswith("/"):
            audio_url = "https://pixabay.com" + audio_url

        track_title = track.get("title", "pixabay_music")
        safe_title = "".join(
            c if c.isalnum() or c in "._- " else "_" for c in track_title
        )
        default_filename = f"pixabay_music_{safe_title[:60]}.mp3"
        output_path = Path(inputs.get("output_path", default_filename))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(
            audio_url,
            headers={
                "User-Agent": self._USER_AGENT,
                "Referer": "https://pixabay.com/music/",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            output_path.write_bytes(response.read())

        return output_path
