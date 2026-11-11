"""Mixkit (by Envato) stock video source adapter.

Scrapes the Mixkit website (``mixkit.co``) for stock video clips. No API
is available, so this adapter reads Mixkit's listing and detail pages.

Licensing — read before using footage
-------------------------------------
Mixkit publishes video under two different licences, chosen per clip:

- **Stock Video Free License** (``videoFree``): commercial and personal use,
  including YouTube, ads and broadcast; no attribution required.
- **Stock Video Restricted License** (``videoRestricted``): the free 720p file
  is for *personal projects only*. Commercial projects, advertising, company
  social media and YouTube videos are explicitly not allowed.

See https://mixkit.co/license/ . Because the licence varies per clip, this
adapter never assumes it:

1. ``search`` labels each candidate with the licence the listing page's
   schema.org data declares and, by default
   (``SearchFilters.require_commercial_use``), drops Restricted clips.
2. ``download`` re-reads the clip's detail page, which is authoritative.
   When commercial use is required it refuses Restricted clips and clips
   whose licence the page does not state. It downloads only files the page
   itself publishes — its download renditions (best first), then the
   JSON-LD ``contentUrl``, then the ``<video>`` source — never a guessed
   URL. The verified licence and its evidence are written back onto the
   candidate (``license`` and ``extra["license_evidence"]``).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .base import Candidate, SearchFilters

_log = logging.getLogger(__name__)

_BASE = "https://mixkit.co"
_SEARCH_URL = f"{_BASE}/free-stock-video/"
_UA = {"User-Agent": "OpenMontage/1.0"}

LICENSE_FREE = "videoFree"
LICENSE_RESTRICTED = "videoRestricted"
_LICENSE_LABELS = {
    LICENSE_FREE: "Mixkit Stock Video Free License (commercial and personal use, no attribution required)",
    LICENSE_RESTRICTED: "Mixkit Stock Video Restricted License (personal projects only; no commercial use, ads or YouTube)",
}
_UNRESOLVED = "Mixkit (licence not yet verified; resolved from the detail page at download)"
_RES_ORDER = {"2160p": 4, "4k": 4, "1080p": 3, "720p": 2, "480p": 1, "360p": 0}

_JSON_LD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


class MixkitLicenseError(RuntimeError):
    """The clip's published licence does not allow the required use."""


# ---------------------------------------------------------------------------
# JSON-LD helpers (string based, so they work without beautifulsoup4)
# ---------------------------------------------------------------------------

def _json_ld_nodes(html: str):
    """Yield every dict node in the page's JSON-LD blocks (any nesting shape)."""
    for block in _JSON_LD_RE.findall(html):
        try:
            payload = json.loads(block)
        except ValueError:
            # Third-party pages ship malformed or half-templated JSON-LD:
            # one bad block must not hide a good one later in the page
            continue
        pending: list[Any] = [payload]
        while pending:
            node = pending.pop(0)
            if isinstance(node, list):
                pending.extend(node)
            elif isinstance(node, dict):
                yield node
                pending.extend(v for v in node.values() if isinstance(v, (list, dict)))


def _is_video_object(node: dict) -> bool:
    types_ = node.get("@type", "")
    return "VideoObject" in (types_ if isinstance(types_, list) else [types_])


def _content_url_from_json_ld(html: str) -> str:
    """Return the ``VideoObject.contentUrl`` a Mixkit page declares, or ``""``.

    Mixkit ships schema.org metadata on every clip page and names a media
    file there directly, so this survives player and markup redesigns.
    """
    for node in _json_ld_nodes(html):
        if not _is_video_object(node):
            continue
        url = node.get("contentUrl", "")
        # Singular in schema.org, but pages do ship a list of renditions
        if isinstance(url, list):
            url = next((u for u in url if isinstance(u, str) and u.strip()), "")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return ""


def _ld_dimension(value: Any) -> int:
    """Pixel size from a schema.org width/height (number, "1920", "1920 px",
    or a QuantitativeValue). Returns 0 when absent or unparseable."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        match = re.match(r"\s*(\d+)", value)
        if match:
            return int(match.group(1))
    return 0


def license_key_from(value: Any) -> Optional[str]:
    """Map a Mixkit licence notice or URL to ``videoFree`` / ``videoRestricted``."""
    v = (value if isinstance(value, str) else "").lower()
    if "restricted" in v:
        return LICENSE_RESTRICTED
    if "videofree" in v or v.strip() == "free" or "free license" in v:
        return LICENSE_FREE
    return None


def _node_license(node: dict) -> Optional[str]:
    return license_key_from(node.get("copyrightNotice", "")) or license_key_from(node.get("license", ""))


def listing_licenses(html: str) -> dict[str, str]:
    """Return ``{detail_url: licence_key}`` from a page's schema.org VideoObjects."""
    out: dict[str, str] = {}
    for node in _json_ld_nodes(html):
        if not _is_video_object(node):
            continue
        key = _node_license(node)
        url = (node.get("@id") or node.get("url") or "").split("#", 1)[0]
        if key and url:
            out[url.rstrip("/") + "/"] = key
    return out


def page_license(html: str) -> Optional[str]:
    """The licence a clip detail page states for its own clip.

    The download block's ``data-license`` (what the free download is offered
    under) wins; the page's VideoObject ``copyrightNotice``/``license`` is the
    fallback. ``None`` means the page does not say.
    """
    for block in re.findall(r'class="download-video-options__download[^"]*"(.*?)</div>', html, re.S):
        m = re.search(r'data-license="([A-Za-z]+)"', block)
        if m and license_key_from(m.group(1)):
            return license_key_from(m.group(1))
    m = re.search(r'data-license="(video[A-Za-z]+)"', html)
    if m and license_key_from(m.group(1)):
        return license_key_from(m.group(1))
    for node in _json_ld_nodes(html):
        if _is_video_object(node) and _node_license(node):
            return _node_license(node)
    return None


def detail_renditions(html: str) -> list[dict[str, str]]:
    """Download renditions the detail page's download block publishes, best first.

    Free clips list radio options (``?type=720p`` / ``?type=1080p``); Restricted
    clips publish a single personal-use 720p link on a button.
    """
    out: list[dict[str, str]] = []
    for value in re.findall(r'name="download-option"[^>]*value="([^"]+)"', html) + \
            re.findall(r'value="([^"]+)"[^>]*name="download-option"', html):
        path = value.replace("&amp;", "&")
        m = re.search(r"type=([0-9a-zA-Z]+)", path)
        out.append({"label": m.group(1).lower() if m else "", "path": path})
    if not out:
        for path in re.findall(r'data-download--button-modal-url-value="([^"]+)"', html):
            title = re.search(r'download-title">([^<]*)<', html)
            m = re.search(r"(\d{3,4}p)", title.group(1)) if title else None
            out.append({"label": m.group(1).lower() if m else "", "path": path.replace("&amp;", "&")})
    seen, uniq = set(), []
    for r in out:
        if r["path"] not in seen:
            seen.add(r["path"])
            uniq.append(r)
    uniq.sort(key=lambda r: _RES_ORDER.get(r["label"], -1), reverse=True)
    return uniq


def parse_detail_offer(html: str) -> dict[str, Any]:
    """Licence plus published download renditions of a clip detail page.

    Returns ``{"license_key", "license_label", "renditions"}``; raises
    ``ValueError`` when the page states no licence or publishes no rendition.
    """
    key = page_license(html)
    if key is None:
        raise ValueError("detail page publishes no licence for this clip")
    renditions = detail_renditions(html)
    if not renditions:
        raise ValueError("detail page publishes no download rendition")
    return {"license_key": key, "license_label": _LICENSE_LABELS[key], "renditions": renditions}


def parse_modal_file_url(html: str) -> str:
    """Read the file URL a Mixkit download modal publishes."""
    m = re.search(r'data-download--modal-url-value="([^"]+)"', html)
    if not m:
        raise ValueError("download modal publishes no file URL")
    return m.group(1)


class MixkitSource:
    """Mixkit video adapter. Satisfies `StockSource`."""

    name = "mixkit"
    display_name = "Mixkit"
    provider = "envato"
    priority = 19
    install_instructions = (
        "Mixkit works without an API key. Scrapes the Mixkit website. "
        "Requires beautifulsoup4: pip install beautifulsoup4. "
        "Licence varies per clip (Free vs Restricted = personal use only); "
        "Restricted or unstated-licence clips are excluded unless "
        "SearchFilters.require_commercial_use=False."
    )
    supports = {"video": True, "image": False}

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
        if kind == "image":
            return []
        require_commercial = getattr(filters, "require_commercial_use", True)

        slug = query.lower().replace(" ", "-")
        search_url = f"{_SEARCH_URL}{slug}/"
        try:
            r = requests.get(search_url, timeout=30, headers=_UA)
            r.raise_for_status()
        except Exception as e:
            # Contract: an empty list means "nothing matched", so a
            # transport failure has to propagate. See `base.StockSource`.
            _log.warning("Mixkit search failed: %s", e)
            raise

        declared = listing_licenses(r.text)
        soup = BeautifulSoup(r.text, "html.parser")
        out: list[Candidate] = []

        cards = soup.select(".item-grid-card, .item-grid__item, .video-item, article, [class*='VideoCard']")
        for card in cards:
            if len(out) >= filters.per_page:
                break
            link_el = card.select_one("a[href]")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = f"{_BASE}{href}"
            if "/free-stock-video/" not in href and "/video/" not in href:
                continue

            licence_key = declared.get(href.rstrip("/") + "/")
            if licence_key == LICENSE_RESTRICTED and require_commercial:
                continue

            title = ""
            title_el = card.select_one("h3, h2, .title, [class*='title']")
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                title = link_el.get_text(strip=True)

            thumb = ""
            img_el = card.select_one("img")
            if img_el:
                thumb = img_el.get("src", "") or img_el.get("data-src", "") or ""

            video_el = card.select_one("video source[src], video[src]")
            preview_url = video_el.get("src", "") if video_el else ""

            clip_id = href.rstrip("/").rsplit("/", 1)[-1]
            out.append(self._candidate(href, clip_id, f"{title} {query}", licence_key, require_commercial,
                                       thumb=thumb, preview_url=preview_url))

        if not out:
            out = self._parse_json_ld(r.text, query, filters, require_commercial)
        return out

    def _parse_json_ld(self, html: str, query: str, filters: SearchFilters,
                       require_commercial: bool) -> list[Candidate]:
        """Read results from the page's schema.org VideoObject entries.

        Used when the listing exposes no result cards. Licence filtering and
        labelling match the card path; the file is still resolved (and the
        licence re-verified) from the detail page at download time.
        """
        out: list[Candidate] = []
        for node in _json_ld_nodes(html):
            if not _is_video_object(node):
                continue
            content_url = node.get("contentUrl") or ""
            if not isinstance(content_url, str) or not content_url.lower().endswith(".mp4"):
                continue
            licence_key = _node_license(node)
            if licence_key == LICENSE_RESTRICTED and require_commercial:
                continue
            href = (node.get("@id") or "").split("#", 1)[0]
            clip_id = href.rstrip("/").rsplit("-", 1)[-1] if href else content_url
            out.append(self._candidate(
                href or content_url, clip_id,
                f"{node.get('name', '')} {node.get('description', '')} {query}".strip(),
                licence_key, require_commercial,
                thumb=node.get("thumbnailUrl", ""), preview_url=node.get("embedUrl", ""),
                # Only trust declared dimensions; the "-1080" filename suffix
                # says nothing about orientation. 0 = unknown until probed.
                width=_ld_dimension(node.get("width")), height=_ld_dimension(node.get("height")),
            ))
            if len(out) >= filters.per_page:
                break
        return out

    def _candidate(self, href: str, clip_id: str, tags: str, licence_key: Optional[str],
                   require_commercial: bool, *, thumb: str = "", preview_url: str = "",
                   width: int = 0, height: int = 0) -> Candidate:
        return Candidate(
            source=self.name,
            source_id=f"mixkit_{clip_id}",
            source_url=href,
            download_url=href,  # resolved from the detail page in download()
            kind="video",
            width=width,
            height=height,
            creator="Mixkit",
            license=_LICENSE_LABELS.get(licence_key, _UNRESOLVED),
            source_tags=tags,
            thumbnail_url=thumb,
            extra={
                "detail_url": href,
                "preview_url": preview_url,
                "listing_license": licence_key,
                "require_commercial_use": require_commercial,
            },
        )

    def _published_files(self, detail_html: str) -> list[dict[str, str]]:
        """Files the detail page publishes, best first: download renditions (via
        their modal), then the JSON-LD contentUrl, then the <video> source."""
        from bs4 import BeautifulSoup

        files = [{"label": r["label"], "modal": r["path"]} for r in detail_renditions(detail_html)]
        content_url = _content_url_from_json_ld(detail_html)
        if content_url:
            files.append({"label": "json-ld contentUrl", "url": content_url})
        soup = BeautifulSoup(detail_html, "html.parser")
        for el in soup.select("video source[src], video[src]"):
            src = el.get("src", "")
            if src and any(ext in src.lower() for ext in (".mp4", ".mov")):
                files.append({"label": "video src", "url": src if src.startswith("http") else f"{_BASE}{src}"})
                break
        return files

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Verify the clip's licence on its detail page, then fetch a file it publishes."""
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        detail_url = candidate.extra.get("detail_url") or candidate.source_url
        require_commercial = candidate.extra.get("require_commercial_use", True)

        r = requests.get(detail_url, timeout=30, headers=_UA)
        r.raise_for_status()
        html = r.text

        files = self._published_files(html)
        if not files:
            raise RuntimeError(f"Mixkit download failed for {detail_url}: Could not find download URL on Mixkit page")

        licence_key = page_license(html)
        if require_commercial and licence_key != LICENSE_FREE:
            why = ("is published under the Mixkit Restricted License (personal use only)"
                   if licence_key == LICENSE_RESTRICTED else "does not state its licence")
            raise MixkitLicenseError(f"{detail_url} {why}; excluded because commercial use is required")

        errors: list[str] = []
        for item in files:
            try:
                file_url = item.get("url")
                if not file_url:
                    modal = item["modal"] if item["modal"].startswith("http") else f"{_BASE}{item['modal']}"
                    m = requests.get(modal, timeout=30, headers=_UA)
                    m.raise_for_status()
                    file_url = parse_modal_file_url(m.text)
                self._stream_download(file_url, out_path)
            except Exception as e:  # try the next file the page publishes
                errors.append(f"{item['label'] or '?'}: {e}")
                continue
            label = _LICENSE_LABELS.get(licence_key, _UNRESOLVED)
            candidate.download_url = file_url
            candidate.license = label
            candidate.extra["license_evidence"] = {
                "license_key": licence_key,
                "license_label": label,
                "detail_url": detail_url,
                "rendition": item["label"],
                "file_url": file_url,
                "license_terms_url": f"{_BASE}/license/#{licence_key}" if licence_key else f"{_BASE}/license/",
                "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            return out_path
        raise RuntimeError(f"Mixkit download failed for {detail_url}: " + "; ".join(errors))

    def _stream_download(self, url: str, out_path: Path) -> Path:
        import requests

        with requests.get(url, stream=True, timeout=120, headers=_UA) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        return out_path
