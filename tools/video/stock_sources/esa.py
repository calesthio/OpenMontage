"""European Space Agency (ESA) stock source adapter.

Scrapes the ESA Multimedia gallery (``www.esa.int/ESA_Multimedia/``) for
free space footage. ESA content is licensed under CC BY-SA 3.0 IGO
(general) or CC BY 4.0 (Webb/Hubble imagery). Attribution is required.

No API available — this adapter scrapes the ESA website's search and
detail pages. Content includes satellite imagery, mission footage,
astronaut activities, rocket launches, Earth observation, and Hubble/Webb
telescope imagery and animations.

What ESA is good for
--------------------
- European space missions (Rosetta, ExoMars, Galileo)
- Hubble and James Webb Space Telescope imagery
- Earth observation from space
- ISS footage (European contributions)
- Ariane rocket launches
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.esa.int/ESA_Multimedia/Search"
_VIDEO_SEARCH_URL = "https://www.esa.int/ESA_Multimedia/Videos"
_LICENSE = "CC BY-SA 3.0 IGO (ESA, attribution required)"


class ESASource:
    """European Space Agency multimedia adapter. Satisfies `StockSource`."""

    name = "esa"
    display_name = "ESA (European Space Agency)"
    provider = "esa"
    priority = 45
    install_instructions = (
        "ESA works without an API key. Scrapes the ESA Multimedia gallery. "
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
            "SearchText": query,
            "result_type": "videos" if kind == "video" else "images" if kind == "image" else "",
        }

        try:
            r = requests.get(
                _SEARCH_URL,
                params=params,
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
        except Exception as e:
            _log.warning("ESA search failed: %s", e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []

        # Find video/image cards on the search results page
        cards = soup.select(".grid-item, .media-item, .search-result-item, article")
        for card in cards[:filters.per_page]:
            link_el = card.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = f"https://www.esa.int{href}"

            title = ""
            title_el = card.select_one("h3, h2, .title, .card-title")
            if title_el:
                title = title_el.get_text(strip=True)

            img_el = card.select_one("img")
            thumb = ""
            if img_el:
                thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""
                if thumb and not thumb.startswith("http"):
                    thumb = f"https://www.esa.int{thumb}"

            # Determine kind from URL or content
            is_video = "/Videos/" in href or "/Video/" in href
            candidate_kind = "video" if is_video else "image"

            if kind == "video" and not is_video:
                continue
            if kind == "image" and is_video:
                continue

            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"esa_{hash(href) & 0xFFFFFFFF:08x}",
                    source_url=href,
                    download_url=href,  # Will be resolved in download()
                    kind=candidate_kind,
                    width=0,
                    height=0,
                    duration=0.0,
                    creator="European Space Agency (ESA)",
                    license=_LICENSE,
                    source_tags=title,
                    thumbnail_url=thumb,
                    extra={"detail_url": href},
                )
            )

        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Download by first resolving the detail page for the actual file URL."""
        import requests
        from bs4 import BeautifulSoup

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        detail_url = candidate.extra.get("detail_url", candidate.download_url)

        # If it's already a direct media URL, download directly
        if any(detail_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".jpg", ".png")):
            return self._stream_download(detail_url, out_path)

        # Otherwise, scrape the detail page for the download link
        try:
            r = requests.get(
                detail_url,
                timeout=30,
                headers={"User-Agent": "OpenMontage/1.0"},
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Look for video download links
            download_url = None
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if any(ext in href.lower() for ext in [".mp4", ".mov", ".webm"]):
                    download_url = href
                    break
                if "download" in text and href:
                    download_url = href
                    break

            # Check for video source tags
            if not download_url:
                for source in soup.select("video source[src], source[src]"):
                    src = source.get("src", "")
                    if src:
                        download_url = src
                        break

            if not download_url:
                raise ValueError(f"Could not find download URL on ESA detail page: {detail_url}")

            if not download_url.startswith("http"):
                download_url = f"https://www.esa.int{download_url}"

            return self._stream_download(download_url, out_path)

        except Exception as e:
            raise RuntimeError(f"ESA download failed for {detail_url}: {e}") from e

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
