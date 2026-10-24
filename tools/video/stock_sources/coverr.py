"""Coverr stock video source adapter.

Wraps the Coverr API (``api.coverr.co``) behind the unified `StockSource`
protocol. Coverr offers curated, high-quality stock footage (HD and 4K)
under a free commercial-use licence with no attribution required.

Requires ``COVERR_API_KEY``. The adapter previously advertised a keyless
free tier and hardcoded ``is_available() -> True``; `api.coverr.co` now
answers every unauthenticated request with 401, so the source reported
itself configured and then failed on every search. `is_available()` is a
declaration, not a probe, so nothing caught it — see
`tests/tools/test_stock_source_health.py`.

What Coverr is good for
-----------------------
- Modern lifestyle / cinematic B-roll
- Nature, urban, technology, abstract backgrounds
- High production quality (curated library)
- Quick establishing shots and mood-setters
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters


_SEARCH_URL = "https://api.coverr.co/videos"
_LICENSE = "Coverr License (free for commercial and personal use, no attribution required)"


class CoverrSource:
    """Coverr video adapter. Satisfies `StockSource`."""

    name = "coverr"
    display_name = "Coverr"
    provider = "coverr"
    priority = 16
    install_instructions = (
        "Set COVERR_API_KEY in .env. Get a key at https://coverr.co/ — "
        "api.coverr.co rejects unauthenticated requests with 401."
    )
    supports = {"video": True, "image": False}

    def is_available(self) -> bool:
        # Unauthenticated requests are rejected with 401, so a missing key
        # means unavailable — claiming otherwise put a dead source into the
        # preflight menu and into corpus_builder's fan-out.
        return bool(os.environ.get("COVERR_API_KEY"))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests

        kind = (filters.kind or "video").lower()
        if kind == "image":
            return []

        headers: dict[str, str] = {}
        api_key = os.environ.get("COVERR_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        params: dict[str, Any] = {
            "query": query,
            "page_size": max(1, min(filters.per_page, 25)),
            "page": max(1, filters.page),
        }

        r = requests.get(
            _SEARCH_URL,
            headers=headers,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", []) or data.get("videos", []) or []

        out: list[Candidate] = []
        for v in hits:
            duration = float(v.get("duration", 0) or 0)
            if filters.min_duration is not None and duration < filters.min_duration:
                continue
            if filters.max_duration is not None and duration > filters.max_duration:
                continue

            # Coverr provides multiple URLs for different qualities
            urls = v.get("urls", {}) or {}
            download_url = (
                urls.get("mp4_download")
                or urls.get("mp4_1080")
                or urls.get("mp4_720")
                or urls.get("mp4_preview")
                or ""
            )
            if not download_url:
                continue

            width = int(v.get("width") or 1920)
            height = int(v.get("height") or 1080)
            if filters.min_width and width < filters.min_width:
                continue

            tags = v.get("tags", "") or ""
            if isinstance(tags, list):
                tags = " ".join(tags)
            title = v.get("title", "") or ""
            source_tags = f"{title} {tags}".strip()

            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(v.get("id") or v.get("slug", "")),
                    source_url=v.get("url", "") or f"https://coverr.co/videos/{v.get('slug', '')}",
                    download_url=download_url,
                    kind="video",
                    width=width,
                    height=height,
                    duration=duration,
                    creator=v.get("creator", {}).get("name", "") if isinstance(v.get("creator"), dict) else "",
                    license=_LICENSE,
                    source_tags=source_tags,
                    thumbnail_url=urls.get("poster") or urls.get("thumbnail") or "",
                    extra={
                        "slug": v.get("slug"),
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
