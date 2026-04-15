"""U.S. National Archives (NARA) stock source adapter.

Wraps the NARA Catalog API (``catalog.archives.gov/api/v2``) behind the
unified `StockSource` protocol. NARA holds billions of records including
significant film and video holdings — all U.S. federal government work
and therefore public domain.

No API key required for basic searching. For higher rate limits, email
Catalog_API@nara.gov to request a key. Rate limit: ~10,000 queries per
month per API key.

Fetch pattern
-------------
Two-stage like NASA. The search endpoint returns metadata records. Each
record may contain digital objects (files) in ``objects``. We follow
those to find downloadable video files.

What NARA is good for
---------------------
- U.S. historical footage (military, presidential, space, civil rights)
- WWII, Cold War, Apollo era footage
- Government program footage and newsreels
- Any "march of history" documentary sequence
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_SEARCH_URL = "https://catalog.archives.gov/api/v2/search"
_LICENSE = "Public domain (U.S. federal government work)"


class NARASource:
    """U.S. National Archives adapter. Satisfies `StockSource`."""

    name = "nara"
    display_name = "U.S. National Archives"
    provider = "nara"
    priority = 35
    install_instructions = (
        "NARA works without an API key. "
        "Set NARA_API_KEY in .env for higher rate limits."
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        # NARA is always available (no key required)
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests

        kind = (filters.kind or "video").lower()

        params: dict[str, Any] = {
            "q": query,
            "rows": max(1, min(filters.per_page, 50)),
            "offset": (max(1, filters.page) - 1) * filters.per_page,
        }

        # Filter by type if possible
        if kind == "video":
            params["type"] = "moving-image"
        elif kind == "image":
            params["type"] = "still-image"

        headers: dict[str, str] = {}
        api_key = os.environ.get("NARA_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            r = requests.get(
                _SEARCH_URL,
                headers=headers,
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            _log.warning("NARA search failed: %s", e)
            return []

        results = data.get("results", []) or []
        out: list[Candidate] = []

        for item in results:
            candidates = self._extract_candidates(item, kind, filters)
            out.extend(candidates)

        return out

    def _extract_candidates(
        self, item: dict, kind: str, filters: SearchFilters
    ) -> list[Candidate]:
        """Extract downloadable candidates from a NARA catalog record."""
        naid = str(item.get("naId", "") or "")
        if not naid:
            return []

        title = item.get("title", "") or ""
        description = item.get("scopeAndContentNote", "") or ""
        source_tags = f"{title} {description}".strip()
        source_url = f"https://catalog.archives.gov/id/{naid}"

        # Look for digital objects
        objects = item.get("objects", []) or []
        if not objects:
            # Try alternate field names
            digital = item.get("digitalObjects", []) or []
            objects = digital

        out: list[Candidate] = []
        for obj in objects:
            file_url = obj.get("url") or obj.get("fileUrl") or ""
            if not file_url:
                continue

            # Determine kind from mime type or file extension
            mime = (obj.get("mimeType", "") or "").lower()
            ext = file_url.rsplit(".", 1)[-1].lower() if "." in file_url else ""

            is_video = (
                "video" in mime
                or ext in ("mp4", "mov", "avi", "wmv", "mkv", "webm")
            )
            is_image = (
                "image" in mime
                or ext in ("jpg", "jpeg", "png", "tif", "tiff", "gif")
            )

            if kind == "video" and not is_video:
                continue
            if kind == "image" and not is_image:
                continue
            if not is_video and not is_image:
                continue

            candidate_kind = "video" if is_video else "image"
            width = int(obj.get("width") or 0)
            height = int(obj.get("height") or 0)
            duration = float(obj.get("duration") or 0)

            # Duration filters (client-side)
            if candidate_kind == "video":
                if filters.min_duration and duration and duration < filters.min_duration:
                    continue
                if filters.max_duration and duration and duration > filters.max_duration:
                    continue

            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"{naid}_{obj.get('objectId', len(out))}",
                    source_url=source_url,
                    download_url=file_url,
                    kind=candidate_kind,
                    width=width,
                    height=height,
                    duration=duration,
                    creator="U.S. National Archives",
                    license=_LICENSE,
                    source_tags=source_tags,
                    thumbnail_url=obj.get("thumbnailUrl", "") or "",
                    extra={
                        "naId": naid,
                        "mime": mime,
                        "fileSize": obj.get("fileSize"),
                    },
                )
            )

        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            candidate.download_url, stream=True, timeout=180
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path
