"""Unsplash stock photo adapter.

Unsplash is image-only in this pipeline. It widens the corpus for
modern, polished, lifestyle, and product-adjacent scenes where a
high-quality still can still be valuable to the edit.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .base import Candidate, SearchFilters


_SEARCH_URL = "https://api.unsplash.com/search/photos"
_UNSPLASH_LICENSE = "Unsplash License (use returned hotlinked image URLs)"
_USER_AGENT = "OpenMontageBot/0.1 (https://github.com/calesthio/OpenMontage)"


class UnsplashSource:
    """Adapter for Unsplash photo search."""

    name = "unsplash"
    display_name = "Unsplash"
    provider = "unsplash"
    priority = 18
    install_instructions = (
        "Set UNSPLASH_ACCESS_KEY in .env to enable Unsplash image search "
        "(see https://unsplash.com/documentation)."
    )
    supports = {"video": False, "image": True}

    def is_available(self) -> bool:
        return bool(os.environ.get("UNSPLASH_ACCESS_KEY"))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests  # lazy

        kind = (filters.kind or "video").lower()
        if kind == "video":
            return []

        params: dict[str, Any] = {
            "query": query,
            "page": max(1, filters.page),
            "per_page": max(1, min(filters.per_page, 30)),
            "content_filter": "high",
        }
        orientation = _orientation_for_unsplash(filters.orientation)
        if orientation:
            params["orientation"] = orientation

        r = requests.get(
            _SEARCH_URL,
            params=params,
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []

        out: list[Candidate] = []
        for photo in results:
            cand = _photo_to_candidate(photo, filters)
            if cand is not None:
                out.append(cand)
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests  # lazy

        if not candidate.download_url:
            raise ValueError(f"Candidate {candidate.clip_id} has no download_url")

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            candidate.download_url,
            stream=True,
            timeout=180,
            headers={"User-Agent": _USER_AGENT},
        ) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("UNSPLASH_ACCESS_KEY")
        if not key:
            raise RuntimeError(
                "UNSPLASH_ACCESS_KEY not set. Create an app at "
                "https://unsplash.com/documentation and add the access key to .env."
            )
        return {
            "Authorization": f"Client-ID {key}",
            "Accept-Version": "v1",
            "User-Agent": _USER_AGENT,
        }


def _photo_to_candidate(photo: dict[str, Any], filters: SearchFilters) -> Candidate | None:
    width = int(photo.get("width") or 0)
    height = int(photo.get("height") or 0)
    if filters.min_width is not None and width and width < filters.min_width:
        return None
    if filters.orientation and not _matches_orientation(filters.orientation, width, height):
        return None

    user = photo.get("user") or {}
    links = photo.get("links") or {}
    urls = photo.get("urls") or {}
    raw_url = urls.get("raw") or urls.get("regular") or ""
    if not raw_url:
        return None

    description_parts = [
        photo.get("description") or "",
        photo.get("alt_description") or "",
        photo.get("slug") or "",
    ]
    source_tags = " ".join(part.strip() for part in description_parts if part).strip()
    if len(source_tags) > 500:
        source_tags = source_tags[:500]

    return Candidate(
        source=UnsplashSource.name,
        source_id=str(photo.get("id") or ""),
        source_url=links.get("html", "") or "",
        download_url=_build_download_url(raw_url, target_width=max(filters.min_width or 0, 1920)),
        kind="image",
        width=width,
        height=height,
        duration=0.0,
        creator=user.get("name", "") or "",
        license=_UNSPLASH_LICENSE,
        source_tags=source_tags,
        thumbnail_url=urls.get("small", "") or urls.get("thumb", "") or raw_url,
        extra={
            "color": photo.get("color"),
            "blur_hash": photo.get("blur_hash"),
            "download_location": links.get("download_location"),
            "photographer_url": user.get("links", {}).get("html"),
        },
    )


def _orientation_for_unsplash(orientation: str | None) -> str | None:
    if orientation == "landscape":
        return "landscape"
    if orientation == "portrait":
        return "portrait"
    if orientation == "square":
        return "squarish"
    return None


def _matches_orientation(orientation: str, width: int, height: int) -> bool:
    if not width or not height:
        return True
    if orientation == "landscape":
        return width >= height
    if orientation == "portrait":
        return height > width
    if orientation == "square":
        return width == height
    return True


def _build_download_url(raw_url: str, target_width: int) -> str:
    parts = urlparse(raw_url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params.setdefault("fm", "jpg")
    params.setdefault("q", "80")
    if target_width > 0:
        params["w"] = str(target_width)
        params.setdefault("fit", "max")
    return urlunparse(parts._replace(query=urlencode(params)))
