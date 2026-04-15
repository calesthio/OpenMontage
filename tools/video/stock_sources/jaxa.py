"""JAXA (Japan Aerospace Exploration Agency) stock source adapter.

Scrapes the JAXA Digital Archives (``jda.jaxa.jp``) for Japanese space
agency footage. Content includes satellite launches, ISS operations,
Earth observation, planetary probes, and moon/planetary imagery.

Generally available for educational/informational use. Specific terms
vary per item — check JAXA's usage guidelines. No API available.

What JAXA is good for
---------------------
- Japanese space missions (Hayabusa, SLIM, H-IIA/H3 rockets)
- ISS footage (Japanese module Kibo)
- Earth observation from JAXA satellites
- Moon and asteroid imagery
- Complement to NASA for non-U.S. space footage
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_BASE_URL = "https://jda.jaxa.jp"
_SEARCH_URL = "https://jda.jaxa.jp/result.php"
_LICENSE = "JAXA Digital Archives License (educational/informational use, verify per item)"


class JAXASource:
    """JAXA Digital Archives adapter. Satisfies `StockSource`."""

    name = "jaxa"
    display_name = "JAXA (Japan Space Agency)"
    provider = "jaxa"
    priority = 55
    install_instructions = (
        "JAXA works without an API key. Scrapes the JAXA Digital Archives. "
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

        params: dict[str, Any] = {
            "lang": "e",  # English
            "keyword": query,
        }

        # JAXA category filter
        if kind == "video":
            params["category"] = "3"  # Videos/movies
        elif kind == "image":
            params["category"] = "1"  # Photos

        try:
            r = requests.get(
                _SEARCH_URL,
                params=params,
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
        except Exception as e:
            _log.warning("JAXA search failed: %s", e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []

        # Find result items
        items = soup.select(".result-item, .photo-item, .movie-item, .item, li.list-item, .gallery-item")
        for item in items[:filters.per_page]:
            link_el = item.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = f"{_BASE_URL}/{href.lstrip('/')}"

            title = ""
            title_el = item.select_one(".title, h3, h2, p, .caption")
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                title = link_el.get("title", "") or link_el.get_text(strip=True)

            thumb = ""
            img_el = item.select_one("img")
            if img_el:
                thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""
                if thumb and not thumb.startswith("http"):
                    thumb = f"{_BASE_URL}/{thumb.lstrip('/')}"

            candidate_kind = "video" if kind == "video" else "image"
            clip_id = href.rstrip("/").rsplit("/", 1)[-1].split("?")[0].split(".")[0]

            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"jaxa_{clip_id}",
                    source_url=href,
                    download_url=href,
                    kind=candidate_kind,
                    width=0,
                    height=0,
                    duration=0.0,
                    creator="JAXA",
                    license=_LICENSE,
                    source_tags=f"{title} space japan {query}",
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

        if any(detail_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm", ".jpg", ".png")):
            return self._stream_download(detail_url, out_path)

        try:
            r = requests.get(
                detail_url, timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            download_url = None

            # Look for download links or video sources
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = (a.get_text(strip=True) or "").lower()
                if any(ext in href.lower() for ext in [".mp4", ".mov", ".wmv", ".mpg"]):
                    download_url = href
                    break
                if "download" in text and href:
                    download_url = href
                    break

            # Video elements
            if not download_url:
                for source in soup.select("video source[src], video[src]"):
                    src = source.get("src", "")
                    if src:
                        download_url = src
                        break

            # High-res image links
            if not download_url and candidate.kind == "image":
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if any(ext in href.lower() for ext in [".jpg", ".jpeg", ".png", ".tif"]):
                        download_url = href
                        break

            if not download_url:
                raise ValueError(f"Could not find download URL on JAXA page: {detail_url}")

            if not download_url.startswith("http"):
                download_url = f"{_BASE_URL}/{download_url.lstrip('/')}"

            return self._stream_download(download_url, out_path)

        except Exception as e:
            raise RuntimeError(f"JAXA download failed for {detail_url}: {e}") from e

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
