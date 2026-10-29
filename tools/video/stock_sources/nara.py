"""U.S. National Archives (NARA) stock source adapter.

Wraps the NARA Catalog API (``catalog.archives.gov/api/v2``) behind the
unified `StockSource` protocol. NARA holds billions of records including
significant film and video holdings — all U.S. federal government work
and therefore public domain.

An API key IS required: without an ``x-api-key`` header the catalog serves
its HTML single-page app instead of JSON, so every search fails to parse.
Request one from Catalog_API@nara.gov and set ``NARA_API_KEY``. Rate limit
is ~10,000 queries per month per key.

Fetch pattern
-------------
Two-stage like NASA. ``/records/search`` returns metadata records under
``body.hits.hits[]._source.record``; each record may carry ``digitalObjects``
(files), which is what we follow to find downloadable media.

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

_SEARCH_URL = "https://catalog.archives.gov/api/v2/records/search"
_LICENSE = "Public domain (U.S. federal government work)"

# The catalog's own facet values (aggregation "typeOfMaterials"), used to
# push the video/image split server-side instead of over-fetching and
# discarding. Anything else is left unfiltered.
_MATERIAL_FILTER = {
    "video": "Moving Images",
    "image": "Photographs and other Graphic Materials",
}

_VIDEO_EXT = ("mp4", "mov", "avi", "wmv", "mkv", "webm", "m4v", "mpg", "mpeg")
_IMAGE_EXT = ("jpg", "jpeg", "png", "tif", "tiff", "gif", "bmp")


class NARASource:
    """U.S. National Archives adapter. Satisfies `StockSource`."""

    name = "nara"
    display_name = "U.S. National Archives"
    provider = "nara"
    priority = 35
    install_instructions = (
        "NARA requires an API key: without one the catalog returns HTML, not JSON.\n"
        "Request a key from Catalog_API@nara.gov, then set NARA_API_KEY in .env."
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        return bool(os.environ.get("NARA_API_KEY"))

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests

        api_key = os.environ.get("NARA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "NARA_API_KEY is not set. " + self.install_instructions
            )

        kind = (filters.kind or "video").lower()

        params: dict[str, Any] = {
            "q": query,
            "limit": max(1, min(filters.per_page, 50)),
            # 1-based. The v2 API ignores offset/from/start entirely.
            #
            # Ordering is not stable: identical requests come back with
            # relevance ties shuffled, so consecutive pages can overlap or
            # skip a record. Nothing to fix here — de-dup downstream on
            # `source_id` if a caller walks several pages.
            "page": max(1, filters.page),
            # Records with no digitised file can never yield a candidate.
            "availableOnline": "true",
        }
        material = _MATERIAL_FILTER.get(kind)
        if material:
            params["typeOfMaterials"] = material

        try:
            r = requests.get(
                _SEARCH_URL,
                headers={"x-api-key": api_key},
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            # Contract: an empty list means "nothing matched", so a
            # transport failure has to propagate. See `base.StockSource`.
            _log.warning("NARA search failed: %s", e)
            raise

        hits = (
            (data.get("body") or {})
            .get("hits", {})
            .get("hits", [])
        ) or []

        out: list[Candidate] = []
        for hit in hits:
            record = ((hit.get("_source") or {}).get("record")) or {}
            out.extend(self._extract_candidates(record, kind, filters))
        return out

    @staticmethod
    def _describe(record: dict) -> str:
        """Flatten the record's prose fields into one searchable tag blob.

        v2 dropped ``scopeAndContentNote``; what description exists is spread
        across ``generalNotes`` (list of str), ``shotList`` (str) and
        ``subjects`` (list of dicts with a ``heading``).
        """
        parts: list[str] = [str(record.get("title") or "")]

        notes = record.get("generalNotes")
        if isinstance(notes, list):
            parts += [str(n) for n in notes if isinstance(n, str)]

        shot_list = record.get("shotList")
        if isinstance(shot_list, str):
            parts.append(shot_list)

        subjects = record.get("subjects")
        if isinstance(subjects, list):
            parts += [
                str(s.get("heading"))
                for s in subjects
                if isinstance(s, dict) and s.get("heading")
            ]

        return " ".join(p for p in parts if p).strip()

    def _extract_candidates(
        self, record: dict, kind: str, filters: SearchFilters
    ) -> list[Candidate]:
        """Extract downloadable candidates from a NARA catalog record."""
        naid = str(record.get("naId", "") or "")
        if not naid:
            return []

        source_tags = self._describe(record)
        source_url = f"https://catalog.archives.gov/id/{naid}"

        out: list[Candidate] = []
        for obj in record.get("digitalObjects") or []:
            file_url = obj.get("objectUrl") or ""
            if not file_url:
                continue

            # v2 has no mime type; it labels files like "Audio/Visual File (MP4)"
            # or "Image (JPG)". The extension is the reliable signal, with the
            # label as a fallback for the odd extensionless URL.
            label = str(obj.get("objectType") or "").lower()
            name = str(obj.get("objectFilename") or file_url)
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

            is_video = ext in _VIDEO_EXT or (not ext and "audio/visual" in label)
            is_image = ext in _IMAGE_EXT or (not ext and "image" in label)

            if kind == "video" and not is_video:
                continue
            if kind == "image" and not is_image:
                continue
            if not is_video and not is_image:
                continue

            # v2 reports no dimensions or duration, so duration filters can only
            # be applied downstream once the file is probed. Leaving these at 0
            # keeps the Candidate honest rather than inventing values.
            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"{naid}_{obj.get('objectId', len(out))}",
                    source_url=source_url,
                    download_url=file_url,
                    kind="video" if is_video else "image",
                    width=0,
                    height=0,
                    duration=0.0,
                    creator="U.S. National Archives",
                    license=_LICENSE,
                    source_tags=source_tags,
                    thumbnail_url="",
                    extra={
                        "naId": naid,
                        "objectType": obj.get("objectType"),
                        "fileSize": obj.get("objectFileSize"),
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
