"""Mixkit (by Envato) stock video source adapter.

Scrapes the Mixkit website (``mixkit.co``) for free stock video clips.
Mixkit offers curated, high-quality footage (HD and 4K) under a free
licence with no attribution required. The library is smaller than
Pixabay/Pexels but has higher average quality due to Envato's curation.

No API available — this adapter scrapes Mixkit search pages.

What Mixkit is good for
-----------------------
- High-quality curated B-roll (nature, business, technology, lifestyle)
- Clean, modern footage with consistent quality
- No-attribution-needed clips for quick gap-fills
- Nature and landscape establishing shots
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_SEARCH_URL = "https://mixkit.co/free-stock-video/"
_LICENSE = "Mixkit License (free for commercial and personal use, no attribution required)"


class MixkitSource:
    """Mixkit video adapter. Satisfies `StockSource`."""

    name = "mixkit"
    display_name = "Mixkit"
    provider = "envato"
    priority = 19
    install_instructions = (
        "Mixkit works without an API key. Scrapes the Mixkit website. "
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

        # Mixkit search URL pattern
        slug = query.lower().replace(" ", "-")
        search_url = f"https://mixkit.co/free-stock-video/{slug}/"

        try:
            r = requests.get(
                search_url,
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
        except Exception as e:
            _log.warning("Mixkit search failed: %s", e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []

        # Mixkit lists video cards with preview videos and download links
        cards = soup.select(".item-grid__item, .video-item, article, [class*='VideoCard']")
        for card in cards[:filters.per_page]:
            link_el = card.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = f"https://mixkit.co{href}"

            # Skip non-video links
            if "/free-stock-video/" not in href and "/video/" not in href:
                continue

            title = ""
            title_el = card.select_one("h3, h2, .title, [class*='title']")
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                title = link_el.get_text(strip=True)

            # Thumbnail
            thumb = ""
            img_el = card.select_one("img")
            if img_el:
                thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""

            # Video preview
            video_el = card.select_one("video source[src], video[src]")
            preview_url = ""
            if video_el:
                preview_url = video_el.get("src", "") or ""

            # Extract ID from URL
            clip_id = href.rstrip("/").rsplit("/", 1)[-1] if href else ""

            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"mixkit_{clip_id}",
                    source_url=href,
                    download_url=href,  # Resolved in download()
                    kind="video",
                    width=0,
                    height=0,
                    duration=0.0,
                    creator="Mixkit",
                    license=_LICENSE,
                    source_tags=f"{title} {query}",
                    thumbnail_url=thumb,
                    extra={
                        "detail_url": href,
                        "preview_url": preview_url,
                    },
                )
            )

        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Download by resolving the detail page for the actual download URL."""
        import requests
        from bs4 import BeautifulSoup

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        detail_url = candidate.extra.get("detail_url", candidate.download_url)

        # Direct media URL
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

            # Look for download button/link
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = (a.get_text(strip=True) or "").lower()
                classes = " ".join(a.get("class", []))
                if "download" in text or "download" in classes:
                    if href and any(ext in href.lower() for ext in [".mp4", ".mov", ".webm"]):
                        download_url = href
                        break
                    elif href and "/download/" in href:
                        download_url = href
                        break

            # Look for video source tags
            if not download_url:
                for source in soup.select("video source[src]"):
                    src = source.get("src", "")
                    if src and any(ext in src.lower() for ext in [".mp4", ".mov"]):
                        download_url = src
                        break

            # Look for data attributes with video URLs
            if not download_url:
                for el in soup.select("[data-video-url], [data-download-url], [data-src]"):
                    url = el.get("data-video-url") or el.get("data-download-url") or el.get("data-src") or ""
                    if url and any(ext in url.lower() for ext in [".mp4", ".mov"]):
                        download_url = url
                        break

            if not download_url:
                raise ValueError(f"Could not find download URL on Mixkit page: {detail_url}")

            if not download_url.startswith("http"):
                download_url = f"https://mixkit.co{download_url}"

            return self._stream_download(download_url, out_path)

        except Exception as e:
            raise RuntimeError(f"Mixkit download failed for {detail_url}: {e}") from e

    def _stream_download(self, url: str, out_path: Path) -> Path:
        import requests

        with requests.get(
            url, stream=True, timeout=120,
            headers={"User-Agent": "OpenMontage/1.0"},
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path
