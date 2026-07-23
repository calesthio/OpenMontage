"""Music search and download from Pixabay Music (free, no API key).

Scrapes Pixabay's music section to find and download royalty-free
background music tracks. No API key required — uses web scraping.

Stability: EXPERIMENTAL — Pixabay's HTML structure may change without
notice, which could break the scraper. Use freesound_music or music_gen
as more stable alternatives.
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


class PixabayMusic(BaseTool):
    name = "pixabay_music"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "music_search"
    provider = "pixabay_music"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    # Genuinely free: no provider charge can ever be incurred (see BaseTool.paid).
    paid = False

    dependencies = []  # no API key needed — web scraping
    install_instructions = (
        "No setup required. Pixabay Music is free and needs no API key.\n"
        "Note: This tool scrapes the Pixabay website. If it breaks, the\n"
        "site's HTML structure may have changed. Use freesound_music as fallback."
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
        "reliable long-term automation (scraping may break)",
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
    side_effects = ["writes audio file to output_path", "scrapes Pixabay website"]
    user_visible_verification = [
        "Listen to downloaded track for mood and quality",
    ]

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    _BROWSER_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    def get_status(self) -> ToolStatus:
        # Always available — no API key required
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Pixabay Music is free

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()

        try:
            # Step 1: Search Pixabay Music
            tracks = self._search(inputs)
            if not tracks:
                return ToolResult(
                    success=False,
                    error=f"No music found on Pixabay for query: {inputs['query']}",
                    data={"query": inputs["query"]},
                    duration_seconds=round(time.time() - start, 2),
                )

            # Step 2: Filter by duration
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

            # Step 3: Pick the first matching track
            track = filtered[0]

            # Step 4: Download the audio
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

    def _build_opener(self) -> urllib.request.OpenerDirector:
        """Build a URL opener with cookie support for session persistence."""
        import http.cookiejar

        cj = http.cookiejar.CookieJar()
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj)
        )

    def _search(self, inputs: dict[str, Any]) -> list[dict]:
        """Search Pixabay Music via the bootstrap JSON API.

        Pixabay's music page loads track data from a bootstrap JSON endpoint
        whose URL is embedded in the HTML. We:
        1. Fetch the search page HTML (which sets session cookies).
        2. Extract the __BOOTSTRAP_URL__ from an inline script tag.
        3. Fetch the bootstrap JSON (same session) to get structured track data
           including direct CDN MP3 URLs, durations, and metadata.
        4. Fall back to HTML-scraping if bootstrap extraction fails.
        """
        query = inputs["query"]
        slug = re.sub(r"\s+", "-", query.strip().lower())
        slug = urllib.parse.quote(slug, safe="-")
        search_url = f"https://pixabay.com/music/search/{slug}/"

        opener = self._build_opener()

        # Step 1: Fetch search page HTML (sets cookies)
        request = urllib.request.Request(search_url)
        request.add_header("User-Agent", self._USER_AGENT)
        for key, val in self._BROWSER_HEADERS.items():
            request.add_header(key, val)

        with opener.open(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Step 2: Extract bootstrap URL and fetch track data
        tracks = self._parse_bootstrap(html, search_url, opener)
        if tracks:
            return tracks

        # Step 3: Fallback — scrape HTML directly (legacy strategies)
        return self._parse_tracks_html(html)

    def _parse_bootstrap(
        self,
        html: str,
        referer: str,
        opener: urllib.request.OpenerDirector,
    ) -> list[dict]:
        """Extract tracks from Pixabay's bootstrap JSON endpoint."""
        match = re.search(
            r'window\.__BOOTSTRAP_URL__\s*=\s*["\']([^"\']+)["\']',
            html,
        )
        if not match:
            return []

        bootstrap_path = match.group(1)
        if not bootstrap_path or bootstrap_path == "":
            return []

        bootstrap_url = f"https://pixabay.com{bootstrap_path}"

        req = urllib.request.Request(bootstrap_url)
        req.add_header("User-Agent", self._USER_AGENT)
        req.add_header("Accept", "application/json, text/plain, */*")
        req.add_header("Referer", referer)
        req.add_header("Sec-Fetch-Dest", "empty")
        req.add_header("Sec-Fetch-Mode", "cors")
        req.add_header("Sec-Fetch-Site", "same-origin")

        try:
            with opener.open(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

        results = data.get("page", {}).get("results", [])
        tracks: list[dict] = []

        for item in results:
            sources = item.get("sources", {})
            audio_url = sources.get("src")
            if not audio_url:
                continue

            user = item.get("user", {}) or {}
            tracks.append({
                "title": item.get("name") or sources.get("filename", "Unknown"),
                "audio_url": audio_url,
                "duration": item.get("duration"),
                "artist": user.get("username", "Unknown"),
                "rating": item.get("rating"),
                "download_count": item.get("downloadCount"),
                "pixabay_id": item.get("id"),
            })

        return tracks

    def _parse_tracks_html(self, html: str) -> list[dict]:
        """Fallback: extract track info from HTML when bootstrap fails.

        Tries brute-force scan for CDN MP3 URLs in the page source.
        """
        tracks: list[dict] = []

        mp3_urls = re.findall(
            r'(https?://cdn\.pixabay\.com/audio/[^\s"\'<>]+\.mp3[^\s"\'<>]*)',
            html,
        )
        seen: set[str] = set()
        for url in mp3_urls:
            if url not in seen:
                seen.add(url)
                tracks.append({
                    "title": "Unknown",
                    "audio_url": url,
                    "duration": None,
                    "artist": "Unknown",
                })

        return tracks

    def _download(self, track: dict, inputs: dict[str, Any]) -> Path:
        """Download an MP3 track to the output path."""
        audio_url = track.get("audio_url")
        if not audio_url:
            raise RuntimeError("No audio URL found for the selected track.")

        # Ensure URL is absolute
        if audio_url.startswith("//"):
            audio_url = "https:" + audio_url
        elif audio_url.startswith("/"):
            audio_url = "https://pixabay.com" + audio_url

        # Build output path
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
