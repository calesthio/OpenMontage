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

1. ``search`` labels each candidate with the licence declared in the listing
   page's schema.org data and, by default (``SearchFilters.require_commercial_use``),
   drops Restricted clips.
2. ``download`` re-reads the clip's detail page, which is authoritative,
   refuses Restricted clips when commercial use is required, and downloads
   only a rendition that page actually publishes (never a guessed URL). The
   verified licence and its evidence are written back onto the candidate
   (``license`` and ``extra["license_evidence"]``).
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
_UA = {"User-Agent": "OpenMontage/1.0"}

LICENSE_FREE = "videoFree"
LICENSE_RESTRICTED = "videoRestricted"
_LICENSE_LABELS = {
    LICENSE_FREE: "Mixkit Stock Video Free License (commercial and personal use, no attribution required)",
    LICENSE_RESTRICTED: "Mixkit Stock Video Restricted License (personal projects only; no commercial use, ads or YouTube)",
}
_UNRESOLVED = "Mixkit (licence not yet verified; resolved from the detail page at download)"
_LD_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_RES_ORDER = {"2160p": 4, "4k": 4, "1080p": 3, "720p": 2, "480p": 1, "360p": 0}


class MixkitLicenseError(RuntimeError):
    """The clip's published licence does not allow the required use."""


def license_key_from(value: str) -> Optional[str]:
    """Map a Mixkit licence notice or URL to ``videoFree`` / ``videoRestricted``."""
    v = (value or "").lower()
    if "restricted" in v:
        return LICENSE_RESTRICTED
    if "videofree" in v or v.strip() == "free" or "free license" in v:
        return LICENSE_FREE
    return None


def listing_licenses(html: str) -> dict[str, str]:
    """Return ``{detail_url: licence_key}`` from a listing page's schema.org VideoObjects."""
    out: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("@type") == "VideoObject":
                key = license_key_from(node.get("copyrightNotice", "")) or license_key_from(node.get("license", ""))
                url = (node.get("@id") or node.get("url") or "").split("#", 1)[0]
                if key and url:
                    out[url.rstrip("/") + "/"] = key
            for value in node.values():
                walk(value)

    for block in _LD_RE.findall(html):
        try:
            walk(json.loads(block))
        except ValueError:
            continue
    return out


def parse_detail_offer(html: str) -> dict[str, Any]:
    """Read the licence and published renditions from a Mixkit clip detail page.

    Returns ``{"license_key", "license_label", "renditions": [{"label", "path"}]}``
    with renditions ordered best-first. Raises ``ValueError`` when the page does
    not publish a licence or any download rendition.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".download-video-options__download")
    licence_el = None
    for block in blocks:
        licence_el = block.select_one("[data-license]")
        if licence_el:
            break
    if not licence_el:
        raise ValueError("detail page publishes no licence for this clip")
    key = license_key_from(licence_el.get("data-license", ""))
    if key is None:
        raise ValueError(f"unrecognised Mixkit licence {licence_el.get('data-license')!r}")

    renditions: list[dict[str, str]] = []
    block = licence_el.find_parent(class_="download-video-options__download")
    for radio in block.select("input[name='download-option'][value]"):
        m = re.search(r"type=([0-9a-zA-Z]+)", radio["value"])
        renditions.append({"label": m.group(1).lower() if m else radio.get("data-label", ""), "path": radio["value"]})
    if not renditions:
        for btn in block.select("[data-download--button-modal-url-value]"):
            title = block.get_text(" ", strip=True)
            m = re.search(r"(\d{3,4}p)", title)
            renditions.append({"label": m.group(1).lower() if m else "", "path": btn["data-download--button-modal-url-value"]})
    if not renditions:
        raise ValueError("detail page publishes no download rendition")
    renditions.sort(key=lambda r: _RES_ORDER.get(r["label"], -1), reverse=True)
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
        "Restricted clips are excluded unless SearchFilters.require_commercial_use=False."
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
        search_url = f"{_BASE}/free-stock-video/{slug}/"
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
            out.append(
                Candidate(
                    source=self.name,
                    source_id=f"mixkit_{clip_id}",
                    source_url=href,
                    download_url=href,  # resolved from the detail page in download()
                    kind="video",
                    creator="Mixkit",
                    license=_LICENSE_LABELS.get(licence_key, _UNRESOLVED),
                    source_tags=f"{title} {query}",
                    thumbnail_url=thumb,
                    extra={
                        "detail_url": href,
                        "preview_url": preview_url,
                        "listing_license": licence_key,
                        "require_commercial_use": require_commercial,
                    },
                )
            )
        return out

    def download(self, candidate: Candidate, out_path: Path) -> Path:
        """Verify the clip's licence on its detail page, then fetch a published rendition."""
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        detail_url = candidate.extra.get("detail_url") or candidate.source_url
        require_commercial = candidate.extra.get("require_commercial_use", True)

        r = requests.get(detail_url, timeout=30, headers=_UA)
        r.raise_for_status()
        offer = parse_detail_offer(r.text)
        if offer["license_key"] == LICENSE_RESTRICTED and require_commercial:
            raise MixkitLicenseError(
                f"{detail_url} is published under the Mixkit Restricted License "
                "(personal use only); excluded because commercial use is required"
            )

        errors: list[str] = []
        for rendition in offer["renditions"]:
            try:
                modal_url = rendition["path"] if rendition["path"].startswith("http") else f"{_BASE}{rendition['path']}"
                m = requests.get(modal_url, timeout=30, headers=_UA)
                m.raise_for_status()
                file_url = parse_modal_file_url(m.text)
                self._stream_download(file_url, out_path)
            except Exception as e:  # try the next rendition the page publishes
                errors.append(f"{rendition['label'] or '?'}: {e}")
                continue
            candidate.download_url = file_url
            candidate.license = offer["license_label"]
            candidate.extra["license_evidence"] = {
                "license_key": offer["license_key"],
                "license_label": offer["license_label"],
                "detail_url": detail_url,
                "rendition": rendition["label"],
                "file_url": file_url,
                "license_terms_url": f"{_BASE}/license/#{offer['license_key']}",
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
