"""Dareful stock video source adapter.

Scrapes the Dareful website (``dareful.com``, formerly
StockFootageForFree.com) for free 4K nature footage. Dareful is a
boutique collection curated by a single creator (Joel Holland) offering
high-quality landscape, forest, mountain, waterfall, and time-lapse
footage.

Licensed under CC BY 4.0 (attribution required). No API available.

What Dareful is good for
------------------------
- 4K nature B-roll (mountains, forests, waterfalls, oceans)
- Aerial landscape footage
- Time-lapse sequences (sunrise, clouds, stars)
- Consistent visual style (single creator)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_BASE_URL = "https://www.dareful.com"
_LICENSE = "Creative Commons Attribution 4.0 (CC BY 4.0, attribution required)"


class DarefulSource:
    """Dareful nature footage adapter. Satisfies `StockSource`."""

    name = "dareful"
    display_name = "Dareful"
    provider = "dareful"
    priority = 50
    install_instructions = (
        "Dareful works without an API key. Scrapes the Dareful website. "
        "Requires beautifulsoup4: pip install beautifulsoup4"
    )
    supports = {"video": True, "image": False}

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
            return []

        try:
            r = requests.get(
                _BASE_URL,
                params={"s": query},
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
        except Exception as e:
            _log.warning("Dareful search failed: %s", e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []

        # Find video post cards
        cards = soup.select("article, .post, .entry, .video-item, .grid-item")
        for card in cards[:filters.per_page]:
            link_el = card.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = f"{_BASE_URL}{href}"

            title = ""
            title_el = card.select_one("h2, h3, .entry-title, .title")
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                title = link_el.get_text(strip=True)

            thumb = ""
            img_el = card.select_one("img")
            if img_el:
                thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""

            clip_id = href.rstrip("/").rsplit("/", 1)[-1]

            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"dareful_{clip_id}",
                    source_url=href,
                    download_url=href,
                    kind="video",
                    width=3840,  # Dareful is primarily 4K
                    height=2160,
                    duration=0.0,
                    creator="Joel Holland (Dareful)",
                    license=_LICENSE,
                    source_tags=f"{title} nature landscape 4k {query}",
                    thumbnail_url=thumb,
                    extra={"detail_url": href},
                )
            )

        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Download by resolving the detail page for the actual file URL."""
        import requests
        from bs4 import BeautifulSoup

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        detail_url = candidate.extra.get("detail_url", candidate.download_url)

        if any(detail_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")):
            return self._stream_download(detail_url, out_path)

        try:
            r = requests.get(
                detail_url, timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            download_url = None

            # Look for download links
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = (a.get_text(strip=True) or "").lower()
                if any(ext in href.lower() for ext in [".mp4", ".mov", ".webm"]):
                    download_url = href
                    break
                if "download" in text and href:
                    download_url = href
                    break

            # Check video elements
            if not download_url:
                for source in soup.select("video source[src], video[src]"):
                    src = source.get("src", "")
                    if src:
                        download_url = src
                        break

            if not download_url:
                raise ValueError(f"Could not find download URL on Dareful page: {detail_url}")

            if not download_url.startswith("http"):
                download_url = f"{_BASE_URL}{download_url}"

            return self._stream_download(download_url, out_path)

        except Exception as e:
            raise RuntimeError(f"Dareful download failed for {detail_url}: {e}") from e

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
