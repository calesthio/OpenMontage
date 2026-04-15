"""Pexels stock media source adapter.

Wraps the Pexels video and image search APIs behind the unified
`StockSource` protocol. Pexels is the workhorse for the
documentary-montage pipeline: large catalogue, fast API, free, no
attribution required, and stable URLs for cacheable downloads.

Pexels exposes videos and images on two separate endpoints
(``/videos/search`` and ``/v1/search``), so this adapter fans out
internally and normalises both into the same `Candidate` shape. The
corpus builder never branches on kind.

Uses `PEXELS_API_KEY` from the environment. `.env` is loaded at process
start by `tools.base_tool._load_dotenv`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from .base import Candidate, SearchFilters


_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
_IMAGE_SEARCH_URL = "https://api.pexels.com/v1/search"
_PEXELS_LICENSE = "Pexels License (free, no attribution required)"


class PexelsSource:
    """Unified Pexels adapter for videos and images.

    Satisfies `StockSource`. Stateless — all config comes from the
    environment, so the corpus builder can instantiate one per run
    without caching the instance.
    """

    name = "pexels"
    display_name = "Pexels"
    provider = "pexels"
    priority = 10
    install_instructions = (
        "Set PEXELS_API_KEY in .env to enable Pexels stock search "
        "(free key at https://www.pexels.com/api/)."
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        return bool(os.environ.get("PEXELS_API_KEY"))

    # ------------------------------------------------------------------
    # Public protocol
    # ------------------------------------------------------------------

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        """Search Pexels, routing to video/image endpoints by `filters.kind`.

        `kind="video"` hits only the videos endpoint, `kind="image"`
        only the images endpoint, `kind="any"` queries both and
        concatenates the results (videos first). The caller decides
        ordering semantics downstream — this adapter does not re-rank.
        """
        kind = (filters.kind or "video").lower()
        out: list[Candidate] = []
        if kind in ("video", "any"):
            out.extend(self._search_videos(query, filters))
        if kind in ("image", "any"):
            out.extend(self._search_images(query, filters))
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Stream the candidate's file to `out_path`.

        Creates parent directories as needed. Uses streamed chunks so
        large 1080p clips don't blow RAM. No caching — the corpus
        builder is responsible for deciding whether to call this at
        all.
        """
        import requests  # lazy — avoid pulling requests at import time

        if not candidate.download_url:
            raise ValueError(
                f"Candidate {candidate.clip_id} has no download_url"
            )

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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("PEXELS_API_KEY")
        if not key:
            raise RuntimeError(
                "PEXELS_API_KEY not set. Get a free key at "
                "https://www.pexels.com/api/ and add it to .env."
            )
        return {"Authorization": key}

    def _search_videos(
        self, query: str, filters: SearchFilters
    ) -> list[Candidate]:
        import requests  # lazy

        params: dict[str, Any] = {
            "query": query,
            "per_page": max(1, min(filters.per_page, 80)),
            "page": max(1, filters.page),
        }
        if filters.orientation:
            params["orientation"] = filters.orientation

        r = requests.get(
            _VIDEO_SEARCH_URL,
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        videos = data.get("videos", []) or []

        out: list[Candidate] = []
        for v in videos:
            # Duration filter. Pexels doesn't expose this server-side,
            # so we filter client-side and accept that per_page may be
            # partially consumed by clips we throw away.
            duration = float(v.get("duration", 0) or 0)
            if filters.min_duration is not None and duration < filters.min_duration:
                continue
            if filters.max_duration is not None and duration > filters.max_duration:
                continue

            rend = _pick_video_rendition(
                v.get("video_files", []) or [],
                min_width=filters.min_width or 0,
                max_width=1920,
            )
            if rend is None:
                continue

            user = v.get("user") or {}
            tag_text = _slug_tags_from_url(v.get("url", "") or "")

            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(v.get("id")),
                    source_url=v.get("url", "") or "",
                    download_url=rend.get("link", "") or "",
                    kind="video",
                    width=int(rend.get("width") or v.get("width") or 0),
                    height=int(rend.get("height") or v.get("height") or 0),
                    duration=duration,
                    creator=user.get("name", "") or "",
                    license=_PEXELS_LICENSE,
                    source_tags=tag_text,
                    thumbnail_url=v.get("image", "") or "",
                    extra={
                        "fps": rend.get("fps"),
                        "rendition_quality": rend.get("quality"),
                        "user_url": user.get("url"),
                    },
                )
            )
        return out

    def _search_images(
        self, query: str, filters: SearchFilters
    ) -> list[Candidate]:
        import requests  # lazy

        params: dict[str, Any] = {
            "query": query,
            "per_page": max(1, min(filters.per_page, 80)),
            "page": max(1, filters.page),
        }
        if filters.orientation:
            params["orientation"] = filters.orientation

        r = requests.get(
            _IMAGE_SEARCH_URL,
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        photos = data.get("photos", []) or []

        out: list[Candidate] = []
        for p in photos:
            width = int(p.get("width", 0) or 0)
            height = int(p.get("height", 0) or 0)
            if filters.min_width is not None and width < filters.min_width:
                continue

            src = p.get("src") or {}
            # "large2x" is the sweet spot between detail and filesize
            # for montage use — usually 1.5-2 MP. Fall back to
            # "original" if the CDN gave us something weird.
            download_url = src.get("large2x") or src.get("original") or ""
            if not download_url:
                continue

            alt = (p.get("alt") or "").strip()

            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(p.get("id")),
                    source_url=p.get("url", "") or "",
                    download_url=download_url,
                    kind="image",
                    width=width,
                    height=height,
                    duration=0.0,
                    creator=p.get("photographer", "") or "",
                    license=_PEXELS_LICENSE,
                    source_tags=alt,
                    thumbnail_url=src.get("medium", "") or "",
                    extra={
                        "photographer_url": p.get("photographer_url"),
                        "avg_color": p.get("avg_color"),
                    },
                )
            )
        return out


# ----------------------------------------------------------------------
# Module-level helpers (also used by tests)
# ----------------------------------------------------------------------


def _pick_video_rendition(
    video_files: list[dict],
    min_width: int = 0,
    max_width: int = 1920,
) -> Optional[dict]:
    """Pick the largest mp4/mov rendition within [min_width, max_width].

    Pexels returns HLS, SD, HD, and sometimes UHD renditions per video.
    We want the biggest file that fits our cap — "biggest" as a quality
    proxy, "cap" so we don't waste bandwidth downloading 4K when we'll
    scale to 720p anyway.
    """
    candidates = [
        f for f in video_files
        if (f.get("file_type", "") or "").startswith("video/")
        and min_width <= int(f.get("width") or 0) <= max_width
        and f.get("link")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda f: int(f.get("width") or 0), reverse=True)
    return candidates[0]


def _slug_tags_from_url(url: str) -> str:
    """Extract a readable tag string from a Pexels video landing URL.

    Pexels video JSON does not expose tags or descriptions reliably,
    but the landing URL is a slug like::

        https://www.pexels.com/video/aerial-view-of-city-at-night-3571264/

    The slug is the closest thing to keywords the API gives us, and it
    matches what the uploader described the clip as. We strip the
    trailing numeric id and rejoin on spaces so the CLIP text encoder
    can work with it.

    Returns an empty string if the URL cannot be parsed — the caller
    should treat that as "no tag signal for this clip".
    """
    if not url:
        return ""
    tail = url.rstrip("/").rsplit("/", 1)
    if len(tail) != 2:
        return ""
    slug = tail[1]
    parts = slug.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        slug = parts[0]
    return slug.replace("-", " ").strip()
