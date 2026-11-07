"""Free footage sourcing with provenance.

Supports NASA Image and Video Library, Archive.org, Wikimedia Commons,
and optional Pexels/Pixabay (API keys via env). Every downloaded asset
gets a manifest entry with source, license, url and usage terms.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

NASA_SEARCH = "https://images-api.nasa.gov/search"
ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"


def _get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_nasa(query: str, media_type: str = "image", page: int = 1) -> list[dict[str, Any]]:
    params = {"q": query, "media_type": media_type, "page": page}
    url = NASA_SEARCH + "?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    items = data.get("collection", {}).get("items", [])
    out = []
    for it in items:
        meta = (it.get("data") or [{}])[0]
        links = it.get("links") or [{}]
        out.append({
            "source": "nasa",
            "title": meta.get("title"),
            "description": meta.get("description"),
            "nasa_id": meta.get("nasa_id"),
            "media_type": meta.get("media_type"),
            "license": "Public Domain (US Government work; verify third-party credits)",
            "usage_terms": "Free to use; verify third-party credits and restrictions.",
            "preview_url": links[0].get("href") if links else None,
            "page_url": f"https://images.nasa.gov/details/{meta.get('nasa_id')}" if meta.get("nasa_id") else None,
        })
    return out


def search_archive_org(query: str, rows: int = 20) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "output": "json",
        "rows": rows,
        "fl[]": ["identifier", "title", "licenseurl", "mediatype"],
    }
    url = ARCHIVE_SEARCH + "?" + urllib.parse.urlencode(params, doseq=True)
    data = _get_json(url)
    docs = data.get("response", {}).get("docs", [])
    out = []
    for d in docs:
        ident = d.get("identifier")
        out.append({
            "source": "archive_org",
            "title": d.get("title"),
            "identifier": ident,
            "media_type": d.get("mediatype"),
            "license": d.get("licenseurl") or "Check collection license",
            "usage_terms": "Verify collection/item license before use.",
            "page_url": f"https://archive.org/details/{ident}" if ident else None,
        })
    return out


def search_wikimedia(query: str, limit: int = 20) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    url = WIKIMEDIA_API + "?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    out = []
    for r in data.get("query", {}).get("search", []):
        out.append({
            "source": "wikimedia_commons",
            "title": r.get("title"),
            "page_url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(r.get('title','').replace(' ', '_'))}",
            "license": "Check file page (CC varies)",
            "usage_terms": "Verify per-file license and attribution requirements.",
        })
    return out


def search_pexels(query: str, api_key: str | None = None) -> list[dict[str, Any]]:
    key = api_key or os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    url = PEXELS_SEARCH + "?" + urllib.parse.urlencode({"query": query, "per_page": 15})
    data = _get_json(url, headers={"Authorization": key})
    out = []
    for v in data.get("videos", []):
        files = v.get("video_files") or [{}]
        out.append({
            "source": "pexels",
            "title": f"pexels_{v.get('id')}",
            "license": "Pexels License (free use, attribution not required)",
            "usage_terms": "Free for commercial use; cannot sell unmodified.",
            "preview_url": (files[0].get("link") if files else None),
            "page_url": v.get("url"),
        })
    return out


def search_pixabay(query: str, api_key: str | None = None) -> list[dict[str, Any]]:
    key = api_key or os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    url = PIXABAY_SEARCH + "?" + urllib.parse.urlencode({"key": key, "q": query, "per_page": 15})
    data = _get_json(url)
    out = []
    for v in data.get("hits", []):
        out.append({
            "source": "pixabay",
            "title": f"pixabay_{v.get('id')}",
            "license": "Pixabay Content License (free use)",
            "usage_terms": "Free for commercial use; cannot sell unmodified or redistribute as stock.",
            "preview_url": v.get("videos", {}).get("medium", {}).get("url"),
            "page_url": v.get("pageURL"),
        })
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return {"path": str(dest), "sha256": sha256_file(dest), "size_bytes": dest.stat().st_size}


def write_manifest(entries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
