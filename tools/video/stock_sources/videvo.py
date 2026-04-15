"""Videvo stock video source adapter.

Wraps the Videvo API behind the unified `StockSource` protocol. Videvo
offers 90,000+ free video clips (HD and 4K) plus a larger premium
library. Free clips use either the Videvo Attribution License (credit
required) or Creative Commons 3.0 (CC BY 3.0).

Videvo API: Announced at https://www.videvo.net/blog/announcing-the-new-api/.
Requires an API key for access. Unlimited requests claimed.

What Videvo is good for
-----------------------
- Large free video library (90K+ clips)
- Nature, aerial, city, abstract, time-lapses
- Modern HD/4K footage
- Complements Pexels with a different contributor base
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_API_URL = "https://api.videvo.net/v1/search"
_LICENSE_ATTR = "Videvo Attribution License (free, attribution required)"
_LICENSE_CC = "Creative Commons 3.0 (CC BY 3.0, attribution required)"


class VidevoSource:
    """Videvo video adapter. Satisfies `StockSource`."""

    name = "videvo"
    display_name = "Videvo"
    provider = "videvo"
    priority = 22
    install_instructions = (
        "Set VIDEVO_API_KEY in .env to enable Videvo stock search "
        "(get API access at https://www.videvo.net/api/)."
    )
    supports = {"video": True, "image": False}

    def is_available(self) -> bool:
        return bool(os.environ.get("VIDEVO_API_KEY"))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests

        kind = (filters.kind or "video").lower()
        if kind == "image":
            return []

        api_key = os.environ.get("VIDEVO_API_KEY")
        if not api_key:
            return []

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        params: dict[str, Any] = {
            "query": query,
            "page": max(1, filters.page),
            "per_page": max(1, min(filters.per_page, 50)),
            "license_type": "free",  # Only free clips
        }

        if filters.orientation:
            params["orientation"] = filters.orientation

        try:
            r = requests.get(
                _API_URL,
                headers=headers,
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            _log.warning("Videvo search failed: %s", e)
            return []

        hits = data.get("data", []) or data.get("results", []) or data.get("clips", []) or []
        out: list[Candidate] = []

        for v in hits:
            duration = float(v.get("duration", 0) or 0)
            if filters.min_duration is not None and duration < filters.min_duration:
                continue
            if filters.max_duration is not None and duration > filters.max_duration:
                continue

            # Get best download URL
            download_url = (
                v.get("download_url", "")
                or v.get("url_hd", "")
                or v.get("url_sd", "")
                or v.get("preview_url", "")
                or ""
            )
            if not download_url:
                continue

            width = int(v.get("width") or 0)
            height = int(v.get("height") or 0)
            if filters.min_width and width and width < filters.min_width:
                continue

            # Tags
            title = v.get("title", "") or ""
            tags = v.get("tags", "") or v.get("keywords", "") or ""
            if isinstance(tags, list):
                tags = " ".join(tags)
            source_tags = f"{title} {tags}".strip()

            # License type
            lic_type = (v.get("license_type", "") or "").lower()
            lic = _LICENSE_CC if "creative commons" in lic_type or "cc" in lic_type else _LICENSE_ATTR

            clip_id = str(v.get("id", "") or "")
            source_url = v.get("page_url", "") or v.get("url", "") or f"https://www.videvo.net/video/{clip_id}/"

            out.append(
                Candidate(
                    source=self.name,
                    source_id=clip_id,
                    source_url=source_url,
                    download_url=download_url,
                    kind="video",
                    width=width,
                    height=height,
                    duration=duration,
                    creator=v.get("author", "") or v.get("contributor", "") or "",
                    license=lic,
                    source_tags=source_tags,
                    thumbnail_url=v.get("thumbnail_url", "") or v.get("poster_url", "") or "",
                    extra={
                        "fps": v.get("fps"),
                        "resolution": v.get("resolution"),
                        "category": v.get("category"),
                    },
                )
            )
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            candidate.download_url, stream=True, timeout=120
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path
