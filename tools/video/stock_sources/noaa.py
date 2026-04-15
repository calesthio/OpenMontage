"""NOAA (National Oceanic and Atmospheric Administration) stock source adapter.

Scrapes the NOAA Ocean Exploration Video Portal and NOAA multimedia pages
for free ocean, weather, and atmospheric footage. All content is public
domain (U.S. federal government work).

No API available for video — this adapter scrapes NOAA web pages.
Content includes deep-sea ROV footage, marine life, coral reefs,
underwater volcanism, weather events, and atmospheric phenomena.

What NOAA is good for
---------------------
- Deep-sea ROV footage (unique content not available anywhere else)
- Marine life close-ups (jellyfish, octopus, deep-sea creatures)
- Coral reef ecosystems
- Hurricane and storm footage
- Weather satellite imagery
- Coastal and oceanic research footage
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.ncei.noaa.gov/access/ocean-exploration/video/"
_MULTIMEDIA_URL = "https://www.noaa.gov/multimedia/videos"
_LICENSE = "Public domain (U.S. federal government work, NOAA)"


class NOAASource:
    """NOAA ocean and atmospheric multimedia adapter. Satisfies `StockSource`."""

    name = "noaa"
    display_name = "NOAA (Ocean & Atmosphere)"
    provider = "noaa"
    priority = 48
    install_instructions = (
        "NOAA works without an API key. Scrapes the NOAA multimedia pages. "
        "Requires beautifulsoup4: pip install beautifulsoup4"
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        try:
            import bs4  # noqa: F401
            return True
        except ImportError:
            return False

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests
        from bs4 import BeautifulSoup

        kind = (filters.kind or "video").lower()
        if kind == "image":
            return []  # Primarily a video source

        # Try the NOAA Ocean Exploration video portal
        out: list[Candidate] = []

        try:
            # NOAA multimedia search
            r = requests.get(
                "https://www.noaa.gov/search",
                params={"query": query, "type": "video"},
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.select(".views-row, .search-result, article, .media-item")
            for card in cards[:filters.per_page]:
                link_el = card.select_one("a[href]")
                if not link_el:
                    continue

                href = link_el.get("href", "")
                if not href:
                    continue
                if not href.startswith("http"):
                    href = f"https://www.noaa.gov{href}"

                title = ""
                title_el = card.select_one("h2, h3, .title, .field-content")
                if title_el:
                    title = title_el.get_text(strip=True)
                if not title:
                    title = link_el.get_text(strip=True)

                img_el = card.select_one("img")
                thumb = ""
                if img_el:
                    thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""
                    if thumb and not thumb.startswith("http"):
                        thumb = f"https://www.noaa.gov{thumb}"

                out.append(
                    Candidate(
                        source=self.name,
                        source_id=f"noaa_{hash(href) & 0xFFFFFFFF:08x}",
                        source_url=href,
                        download_url=href,  # Resolved in download()
                        kind="video",
                        width=0,
                        height=0,
                        duration=0.0,
                        creator="NOAA",
                        license=_LICENSE,
                        source_tags=f"{title} ocean marine weather atmosphere {query}",
                        thumbnail_url=thumb,
                        extra={"detail_url": href},
                    )
                )

        except Exception as e:
            _log.warning("NOAA search failed: %s", e)

        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Download by resolving the detail page for the actual file URL."""
        import requests
        from bs4 import BeautifulSoup

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        detail_url = candidate.extra.get("detail_url", candidate.download_url)

        # Direct media URL
        if any(detail_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")):
            return self._stream_download(detail_url, out_path)

        # Scrape detail page
        try:
            r = requests.get(
                detail_url, timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            download_url = None

            # Look for video elements
            for video in soup.select("video source[src], video[src]"):
                src = video.get("src", "")
                if src:
                    download_url = src
                    break

            # Look for download links
            if not download_url:
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if any(ext in href.lower() for ext in [".mp4", ".mov", ".webm"]):
                        download_url = href
                        break

            # Look for YouTube embeds
            if not download_url:
                for iframe in soup.select("iframe[src]"):
                    src = iframe.get("src", "")
                    if "youtube" in src or "vimeo" in src:
                        _log.warning("NOAA video is embedded from %s — cannot download directly", src)
                        raise ValueError(f"Video is embedded from external platform: {src}")

            if not download_url:
                raise ValueError(f"Could not find video URL on NOAA page: {detail_url}")

            if not download_url.startswith("http"):
                download_url = f"https://www.noaa.gov{download_url}"

            return self._stream_download(download_url, out_path)

        except Exception as e:
            raise RuntimeError(f"NOAA download failed for {detail_url}: {e}") from e

    def _stream_download(self, url: str, out_path: Path) -> Path:
        import requests

        with requests.get(
            url, stream=True, timeout=180,
            headers={"User-Agent": "OpenMontage/1.0"},
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path
