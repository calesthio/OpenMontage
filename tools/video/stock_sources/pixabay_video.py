"""Pixabay Video stock source adapter.

Wraps the Pixabay Video API (``pixabay.com/api/videos/``) behind the
unified `StockSource` protocol. Pixabay has a large community-contributed
video library (hundreds of thousands of clips) with a CC0-like licence
that allows free commercial use without attribution.

Uses the same ``PIXABAY_API_KEY`` as the Pixabay Music tool — if you've
already set it for music search, this adapter is automatically available.

Rate limit: 100 requests per 60 seconds (free tier). The adapter trusts
the API to enforce this and does not self-throttle.

What Pixabay Video is good for
------------------------------
- Broad general-purpose footage: nature, people, technology, food, city
- Modern, community-contributed clips (skews recent / lifestyle)
- Quick gap-fills when Pexels doesn't cover a query
- Available up to 1080p (some clips have 4K)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from .base import Candidate, SearchFilters


_API_URL = "https://pixabay.com/api/videos/"
_LICENSE = "Pixabay Content License (free, no attribution required)"


class PixabayVideoSource:
    """Pixabay Video adapter. Satisfies `StockSource`."""

    name = "pixabay_video"
    display_name = "Pixabay Video"
    provider = "pixabay"
    priority = 15
    install_instructions = (
        "Set PIXABAY_API_KEY in .env to enable Pixabay Video search "
        "(free key at https://pixabay.com/api/docs/)."
    )
    supports = {"video": True, "image": False}

    def is_available(self) -> bool:
        return bool(os.environ.get("PIXABAY_API_KEY"))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests

        kind = (filters.kind or "video").lower()
        if kind == "image":
            return []  # video-only adapter

        params: dict[str, Any] = {
            "key": os.environ["PIXABAY_API_KEY"],
            "q": query,
            "per_page": max(3, min(filters.per_page, 200)),
            "page": max(1, filters.page),
            "safesearch": "true",
        }
        if filters.min_duration is not None:
            params["min_duration"] = int(filters.min_duration)
        if filters.max_duration is not None:
            params["max_duration"] = int(filters.max_duration)

        r = requests.get(_API_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", []) or []

        out: list[Candidate] = []
        for h in hits:
            videos = h.get("videos", {})
            rend = _pick_rendition(videos, min_width=filters.min_width or 0)
            if rend is None:
                continue

            duration = float(h.get("duration", 0) or 0)
            tags = h.get("tags", "") or ""

            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(h.get("id")),
                    source_url=h.get("pageURL", "") or "",
                    download_url=rend["url"],
                    kind="video",
                    width=rend["width"],
                    height=rend["height"],
                    duration=duration,
                    creator=h.get("user", "") or "",
                    license=_LICENSE,
                    source_tags=tags,
                    thumbnail_url=(
                        h.get("userImageURL", "")
                        or videos.get("tiny", {}).get("thumbnail", "")
                        or ""
                    ),
                    extra={
                        "views": h.get("views"),
                        "downloads": h.get("downloads"),
                        "rendition_size": rend.get("size"),
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


def _pick_rendition(
    videos: dict[str, Any],
    min_width: int = 0,
) -> Optional[dict[str, Any]]:
    """Pick the best rendition from Pixabay's nested video dict.

    Pixabay returns renditions keyed by quality tier:
    large (1920), medium (1280), small (960), tiny (640).
    We pick the largest that's at most 1920px wide.
    """
    preference = ["large", "medium", "small", "tiny"]
    for tier in preference:
        rend = videos.get(tier)
        if not rend or not rend.get("url"):
            continue
        w = int(rend.get("width") or 0)
        h = int(rend.get("height") or 0)
        if w >= min_width:
            return {"url": rend["url"], "width": w, "height": h, "size": rend.get("size")}
    return None
