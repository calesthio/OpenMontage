"""Openverse open-media image adapter.

Openverse (https://openverse.org) is a WordPress Foundation project that
federates openly licensed media from Flickr, Wikimedia Commons, museum
collections (Met, NYPL, ...), and dozens of smaller archives behind one
API. No account is required for anonymous use — the public endpoints
allow 20 requests/minute and 200/day per IP.

Scope note: Openverse indexes **images and audio only**. There is no
video endpoint (`/v1/video/` returns 404), so this adapter reports
``supports = {"video": False, "image": True}`` and returns an empty list
for video searches. Use ``wikimedia`` or ``archive_org`` for footage.

Licensing: Openverse holds works under many CC variants, including
non-commercial (NC) and no-derivatives (ND) licenses that cannot be used
in a monetised or edited video. This adapter therefore asks the API for
``commercial,modification`` by default so every returned candidate is
usable in a real edit. Override with ``OPENVERSE_LICENSE_TYPE`` if you
deliberately want a wider (or narrower) pool.

Optional credentials: set ``OPENVERSE_CLIENT_ID`` and
``OPENVERSE_CLIENT_SECRET`` (register an app at
https://api.openverse.org/v1/auth_tokens/register/) to authenticate and
lift the anonymous rate limits. Without them the adapter still works.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .base import Candidate, SearchFilters


_SEARCH_URL = "https://api.openverse.org/v1/images/"
_TOKEN_URL = "https://api.openverse.org/v1/auth_tokens/token/"
_USER_AGENT = "OpenMontage/0.1 (+https://github.com/calesthio/OpenMontage)"

# Some hosts behind Openverse (Flickr's CDN in particular) reject any
# User-Agent containing "Bot" and expect an image Accept header. Both are
# still honest identification — just not the string that trips the filter.
_DOWNLOAD_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "image/avif,image/webp,image/jpeg,image/png,*/*;q=0.8",
}

# Anonymous access is capped at 20/min and 200/day. Anything wider than
# this per call just wastes a request budget the corpus builder needs for
# several queries.
_MAX_PAGE_SIZE = 80

# Default to licenses that permit commercial use *and* derivative works —
# the two flags every edited video needs.
_DEFAULT_LICENSE_TYPE = "commercial,modification"

# Openverse "aspect_ratio" values differ from our filter vocabulary.
_ASPECT_RATIO = {
    "landscape": "wide",
    "portrait": "tall",
    "square": "square",
}

# Client-credentials tokens are valid for ~24h; refresh a minute early.
_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0.0}


class OpenverseSource:
    """Adapter for Openverse image search (keyless, CC-licensed)."""

    name = "openverse"
    display_name = "Openverse"
    provider = "openverse"
    priority = 21
    install_instructions = (
        "Works without an API key (anonymous: 20 req/min, 200 req/day). "
        "Optional: set OPENVERSE_CLIENT_ID and OPENVERSE_CLIENT_SECRET in "
        ".env to raise the rate limit. Images only — Openverse has no video "
        "endpoint."
    )
    supports = {"video": False, "image": True}

    def is_available(self) -> bool:
        # No key required; `requests` is a core dependency. Availability is
        # deliberately network-free so preflight stays fast and offline-safe.
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        import requests  # lazy

        kind = (filters.kind or "video").lower()
        if kind == "video":
            # Openverse has no video index. Returning [] keeps the fan-out
            # quiet instead of raising a "source cannot do that" error.
            return []

        params: dict[str, Any] = {
            "q": query,
            "page": max(1, filters.page),
            "page_size": max(1, min(filters.per_page, _MAX_PAGE_SIZE)),
            "license_type": _license_type(),
            "mature": "false",
        }
        aspect_ratio = _ASPECT_RATIO.get((filters.orientation or "").lower())
        if aspect_ratio:
            params["aspect_ratio"] = aspect_ratio
        if filters.min_width:
            # Coarse server-side hint; the precise width check happens in
            # `_result_to_candidate`.
            params["size"] = "large"

        r = requests.get(
            _SEARCH_URL,
            params=params,
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        out: list[Candidate] = []
        for result in data.get("results") or []:
            cand = _result_to_candidate(result, filters)
            if cand is not None:
                out.append(cand)
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        import requests  # lazy

        if not candidate.download_url:
            raise ValueError(f"Candidate {candidate.clip_id} has no download_url")

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Openverse proxies many hosts (Flickr's CDN especially), and some
        # of them answer 403/429 when several files are pulled back to back.
        # A short backoff turns those transient throttles into successes
        # instead of dropping otherwise usable candidates.
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with requests.get(
                    candidate.download_url,
                    stream=True,
                    timeout=180,
                    headers=_DOWNLOAD_HEADERS,
                ) as r:
                    if r.status_code in (403, 429) and attempt < 2:
                        raise requests.HTTPError(f"{r.status_code} throttled")
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1 << 16):
                            if chunk:
                                f.write(chunk)
                return out_path
            except Exception as e:  # noqa: BLE001 — re-raised below if final
                last_error = e
                if attempt < 2:
                    time.sleep(0.6 * (2**attempt))
        raise last_error if last_error else RuntimeError("download failed")

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        token = _access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


def _license_type() -> str:
    return (os.environ.get("OPENVERSE_LICENSE_TYPE") or _DEFAULT_LICENSE_TYPE).strip()


def _access_token() -> str | None:
    """Return a cached client-credentials token, or None when unconfigured.

    Failures are non-fatal: anonymous access still works, so a bad secret
    should degrade rather than break a corpus build.
    """
    client_id = os.environ.get("OPENVERSE_CLIENT_ID")
    client_secret = os.environ.get("OPENVERSE_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None

    now = time.monotonic()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]:
        return _TOKEN_CACHE["token"]

    import requests  # lazy

    try:
        r = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return None

    token = payload.get("access_token")
    if not token:
        return None
    expires_in = int(payload.get("expires_in") or 3600)
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + max(60, expires_in - 60)
    return token


def _result_to_candidate(
    result: dict[str, Any], filters: SearchFilters
) -> Candidate | None:
    download_url = (result.get("url") or "").strip()
    if not download_url:
        return None

    width = int(result.get("width") or 0)
    height = int(result.get("height") or 0)
    if filters.min_width is not None and width and width < filters.min_width:
        return None
    if filters.orientation and not _matches_orientation(
        filters.orientation, width, height
    ):
        return None

    title = (result.get("title") or "").strip()
    tag_names = " ".join(
        str(tag.get("name") or "")
        for tag in (result.get("tags") or [])
        if isinstance(tag, dict) and tag.get("name")
    )
    provider = (result.get("source") or result.get("provider") or "").strip()
    source_tags = " ".join(
        part for part in (title, tag_names, provider) if part
    ).strip()[:500]

    return Candidate(
        source=OpenverseSource.name,
        source_id=str(result.get("id") or ""),
        source_url=str(result.get("foreign_landing_url") or ""),
        download_url=download_url,
        kind="image",
        width=width,
        height=height,
        duration=0.0,
        creator=str(result.get("creator") or ""),
        license=_license_label(result),
        source_tags=source_tags,
        thumbnail_url=str(result.get("thumbnail") or download_url),
        extra={
            "provider": provider,
            "attribution": result.get("attribution") or "",
            "license_url": result.get("license_url") or "",
            "detail_url": result.get("detail_url") or "",
            "filesize": result.get("filesize"),
            "filetype": result.get("filetype"),
            "indexed_on": result.get("indexed_on"),
            "mature": result.get("mature"),
        },
    )


def _license_label(result: dict[str, Any]) -> str:
    """Human-readable licence string, e.g. ``CC BY-SA 4.0``.

    `Candidate.license` may hold either a label or a URL; a label plus the
    canonical URL in `extra` keeps attribution cheap for the agent.
    """
    code = str(result.get("license") or "").strip()
    version = str(result.get("license_version") or "").strip()
    if not code:
        return str(result.get("license_url") or "unknown")

    lowered = code.lower()
    if lowered == "cc0":
        return f"CC0 {version}".strip()
    if lowered in {"pdm", "public domain mark"}:
        return "Public Domain Mark"
    if lowered in {"by", "by-sa", "by-nd", "by-nc", "by-nc-sa", "by-nc-nd"}:
        return f"CC {code.upper()} {version}".strip()
    # Unknown code — prefer the canonical URL when the API supplied one.
    return str(result.get("license_url") or f"CC {code.upper()} {version}".strip())


def _matches_orientation(orientation: str, width: int, height: int) -> bool:
    if not width or not height:
        return True
    orientation = orientation.lower()
    if orientation == "landscape":
        return width >= height
    if orientation == "portrait":
        return height > width
    if orientation == "square":
        return abs(width - height) <= max(1, int(0.02 * max(width, height)))
    return True
