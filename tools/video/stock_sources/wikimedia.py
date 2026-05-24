"""Wikimedia Commons stock media adapter.

Provides image and video search over Wikimedia Commons using the
MediaWiki API. Commons is a uniquely useful documentary source because
it mixes public-domain historical imagery, recent CC-licensed videos,
and educational media under one searchable catalogue.

Rate limiting: Wikimedia throttles anonymous clients aggressively
(post-April-2025 enforcement bump). All requests funnel through a shared
process-wide rate limiter (default ≥1.2s between calls; tune with
WIKIMEDIA_MIN_INTERVAL_SECONDS) and 429 responses honor the server's
Retry-After header. Failed responses surface their HTTP status code
instead of being silently swallowed.
"""
from __future__ import annotations

import html
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .base import Candidate, SearchFilters


_API_URL = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT = "OpenMontageBot/0.1 (https://github.com/calesthio/OpenMontage)"
_COMMONS_LICENSE = "Wikimedia Commons (verify per-file license)"
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Minimum spacing between Wikimedia requests, in seconds. Wikimedia's
# anonymous-client rate limits became aggressive post-April-2025; 1.2s
# is conservative and well-tolerated. Tune via env var if you have a
# token-authenticated client or a different rate budget.
_MIN_INTERVAL_SECONDS = float(os.environ.get("WIKIMEDIA_MIN_INTERVAL_SECONDS", "1.2"))
# How many times to retry on 429/5xx before giving up.
_MAX_RETRIES = int(os.environ.get("WIKIMEDIA_MAX_RETRIES", "3"))
# Hard ceiling on a single Retry-After sleep — beyond this we bail out
# rather than block the caller for minutes on a bad day.
_RETRY_AFTER_CAP_SECONDS = 60.0


class _RateLimiter:
    """Process-wide rate limiter — enforces min interval between requests.

    Wikimedia rate-limits per client IP, not per session, so all calls from
    this Python process share the budget. Thread-safe so concurrent search()
    callers serialize their request timing.
    """

    def __init__(self, min_interval: float = _MIN_INTERVAL_SECONDS) -> None:
        self.min_interval = min_interval
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()


_RATE_LIMITER = _RateLimiter()


def _parse_retry_after(value: str, default: float = 5.0) -> float:
    """Parse Retry-After. Wikimedia returns integer seconds; HTTP also
    allows an HTTP-date but we don't see those from this API.
    """
    if not value:
        return default
    try:
        seconds = float(value.strip())
        return min(max(seconds, 0.5), _RETRY_AFTER_CAP_SECONDS)
    except ValueError:
        return default


def _request_with_retry(
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    stream: bool = False,
    timeout: float = 30.0,
    max_retries: int = _MAX_RETRIES,
):
    """Rate-limited GET that honors Retry-After on 429 and backs off on 5xx.

    Caller owns the returned Response (close it or use as a context manager,
    especially with stream=True). On final failure, raises RuntimeError
    with the HTTP status code embedded so the cause is never silent.
    """
    import requests  # lazy

    attempt = 0
    last_status: Optional[int] = None
    last_error: Optional[str] = None

    while attempt <= max_retries:
        _RATE_LIMITER.wait()

        try:
            r = requests.get(
                url,
                params=params,
                stream=stream,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            )
        except requests.RequestException as exc:
            last_error = f"network: {exc}"
            attempt += 1
            if attempt > max_retries:
                break
            time.sleep(min(2 ** attempt, 30))
            continue

        last_status = r.status_code

        if r.status_code == 429:
            retry_after_header = r.headers.get("Retry-After", "")
            r.close()
            sleep_for = _parse_retry_after(retry_after_header)
            sys.stderr.write(
                f"[wikimedia] 429 Too Many Requests; honoring "
                f"Retry-After={retry_after_header!r} (sleeping {sleep_for:.1f}s)\n"
            )
            time.sleep(sleep_for)
            attempt += 1
            continue

        if 500 <= r.status_code < 600:
            r.close()
            backoff = min(2 ** attempt, 30)
            sys.stderr.write(
                f"[wikimedia] HTTP {r.status_code} {r.reason}; retrying in "
                f"{backoff}s (attempt {attempt + 1}/{max_retries + 1})\n"
            )
            time.sleep(backoff)
            attempt += 1
            continue

        if r.status_code >= 400:
            r.close()
            raise RuntimeError(
                f"Wikimedia request failed with HTTP {r.status_code} "
                f"{r.reason} for {url}"
            )

        return r

    raise RuntimeError(
        f"Wikimedia request failed after {max_retries + 1} attempts "
        f"(last_status={last_status}, last_error={last_error}) for {url}"
    )

# Stop words stripped from multi-term queries before the cascade runs.
# Commons' CirrusSearch defaults to AND semantics across multi-word
# queries, so each extra common token shrinks the result set fast.
_STOP_WORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into",
    "its", "their", "about", "over", "under", "while", "during",
    "your", "you", "our", "are", "was", "were", "have", "has",
})

# Tokens that refer to other stock archives — useless on Commons and
# will poison the cascade if they end up in top2_or because Commons
# file names don't reference Prelinger or other archives. Keeps the
# cascade parallel to ``archive_org.py``'s own source-hint stripping.
_SOURCE_HINT_TOKENS = frozenset({
    "prelinger", "archive", "archives", "stock", "footage",
})


class WikimediaSource:
    """Adapter for Wikimedia Commons media search."""

    name = "wikimedia"
    display_name = "Wikimedia Commons"
    provider = "wikimedia"
    priority = 25
    install_instructions = (
        "No setup required. Wikimedia Commons media search works without API keys."
    )
    supports = {"video": True, "image": True}

    def is_available(self) -> bool:
        return True

    def search(self, query: str, filters: SearchFilters) -> list[Candidate]:
        """Search Commons via CirrusSearch, cascading from precise to broad.

        Commons' search defaults to AND across multi-word queries, so
        our first diagnostic pass against the P2 query set returned 0
        video results for 10/10 queries — every query was too specific
        to intersect Commons' relatively sparse video holdings.

        The cascade (see ``_build_search_queries``) tries strict first,
        then narrows to 2 distinctive tokens, then to 1 — returning the
        first non-empty video result set.
        """
        for _label, search_text in _build_search_queries(query, filters.kind):
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": search_text,
                "gsrnamespace": 6,
                "gsrlimit": max(1, min(filters.per_page, 50)),
                "gsroffset": max(0, (max(filters.page, 1) - 1) * max(1, min(filters.per_page, 50))),
                "prop": "imageinfo|info",
                "iiprop": "url|size|mime|extmetadata|mediatype",
                "iiurlwidth": 640,
                "inprop": "url",
            }

            try:
                with _request_with_retry(_API_URL, params=params, timeout=30) as r:
                    data = r.json()
            except Exception as exc:
                # Surface the cause — used to be silently swallowed, which
                # made post-April-2025 429s look like "no results found".
                sys.stderr.write(
                    f"[wikimedia] search failed for {search_text!r}: {exc}\n"
                )
                continue
            pages = list(((data.get("query") or {}).get("pages") or {}).values())
            if not pages:
                continue
            pages.sort(key=lambda page: int(page.get("index", 0)))

            out: list[Candidate] = []
            for page in pages:
                cand = _page_to_candidate(page, filters)
                if cand is not None:
                    out.append(cand)
            if out:
                return out

        return []

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        if not candidate.download_url:
            raise ValueError(f"Candidate {candidate.clip_id} has no download_url")

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with _request_with_retry(
            candidate.download_url,
            stream=True,
            timeout=300,
        ) as r:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path


def _build_search_queries(query: str, kind: str) -> list[tuple[str, str]]:
    """Return a cascade of search queries to try in preference order.

    Commons' CirrusSearch defaults to AND semantics for multi-word
    queries, so a 4-word descriptive query like
    "1950s family watching television" intersects to 0 video hits.
    We walk from specific to loose:

    1. **full** — ``filetype:video <full query>``. Works when Commons
       has a file whose name/description contains all the tokens
       (e.g. "atomic bomb test civil defense" finds
       "Operation Cue 1955").
    2. **top2_or** — ``filetype:video <token1> <token2>`` using the
       two longest non-year tokens. AND-combines at the query level
       but with only 2 terms, it's loose enough to hit most
       documentary queries.
    3. **single_best** — ``filetype:video <longest_token>``.
       Last-resort single-token search. Noisy but non-empty.

    Year tokens are excluded from the distinctive-token picks — they
    rarely correlate with file name matches on Commons.
    """
    user_query = query.strip()
    kind_l = (kind or "video").lower()

    prefix = "filetype:video" if kind_l == "video" else (
        "filetype:image" if kind_l == "image" else ""
    )

    def _wrap(text: str) -> str:
        return f"{prefix} {text}".strip() if prefix else text

    if not user_query:
        return [("default", _wrap(""))]

    tokens = [
        t for t in user_query.split()
        if len(t) >= 3
        and t.lower() not in _STOP_WORDS
        and t.lower() not in _SOURCE_HINT_TOKENS
    ]
    non_year = [t for t in tokens if not _looks_like_year(t)]

    queries: list[tuple[str, str]] = [("full", _wrap(user_query))]

    if len(non_year) >= 2:
        top2 = sorted(non_year, key=lambda t: -len(t))[:2]
        queries.append(("top2_or", _wrap(f"{top2[0]} {top2[1]}")))

    if non_year:
        best = max(non_year, key=len)
        queries.append(("single_best", _wrap(best)))

    return queries


def _looks_like_year(token: str) -> bool:
    bare = token.rstrip("s")
    return bare.isdigit() and len(bare) == 4


def _page_to_candidate(page: dict[str, Any], filters: SearchFilters) -> Candidate | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    mime = (info.get("mime") or "").lower()
    kind = _kind_from_mime(mime, page.get("title", ""))

    requested_kind = (filters.kind or "video").lower()
    if requested_kind == "video" and kind != "video":
        return None
    if requested_kind == "image" and kind != "image":
        return None

    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    duration = float(info.get("duration") or 0.0)

    if filters.min_width is not None and width and width < filters.min_width:
        return None
    if filters.min_duration is not None and duration and duration < filters.min_duration:
        return None
    if filters.max_duration is not None and duration and duration > filters.max_duration:
        return None
    if filters.orientation and not _matches_orientation(filters.orientation, width, height):
        return None

    meta = info.get("extmetadata") or {}
    object_name = _meta_value(meta, "ObjectName")
    description = _meta_value(meta, "ImageDescription")
    categories = _meta_value(meta, "Categories")
    creator = _meta_value(meta, "Artist")
    license_name = _meta_value(meta, "LicenseShortName")
    usage_terms = _meta_value(meta, "UsageTerms")
    source_tags = " ".join(part for part in (object_name, description, categories) if part).strip()
    if len(source_tags) > 500:
        source_tags = source_tags[:500]

    title = page.get("title", "")
    page_id = str(page.get("pageid") or title.replace("File:", "", 1))
    source_url = info.get("descriptionurl") or page.get("canonicalurl") or ""

    return Candidate(
        source=WikimediaSource.name,
        source_id=page_id,
        source_url=source_url,
        download_url=info.get("url", "") or "",
        kind=kind,
        width=width,
        height=height,
        duration=duration,
        creator=creator,
        license=license_name or usage_terms or _COMMONS_LICENSE,
        source_tags=source_tags,
        thumbnail_url=info.get("thumburl", "") or info.get("url", "") or "",
        extra={
            "mime": mime,
            "title": title,
            "mediatype": info.get("mediatype"),
            "descriptionshorturl": info.get("descriptionshorturl"),
        },
    )


def _kind_from_mime(mime: str, title: str) -> str:
    if mime.startswith("video/") or title.lower().endswith((".webm", ".ogv", ".ogg")):
        return "video"
    return "image"


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


def _meta_value(meta: dict[str, Any], key: str) -> str:
    raw = ((meta.get(key) or {}).get("value")) or ""
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
