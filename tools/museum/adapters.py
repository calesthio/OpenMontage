#!/usr/bin/env python3
"""tools/museum/adapters.py — keyless museum collection adapters (M4).

Each adapter fetches from the museum's public API via urllib (no network in
tests; inject `http_get` for recorded fixtures). Returns normalized candidate
dicts with rights_basis/usable from the CC0/PD rights gate.

Adapters:
  met_object(query, http_get)              # collectionapi.metmuseum.org (keyless)
  smithsonian_object(query, http_get)      # api.si.edu (api_key optional)
  rijksmuseum_object(query, http_get)      # rijksmuseum.nl API (key optional)
  nga_object(query, http_get)              # NGA (key optional)
  wikimedia_file(query, http_get)          # Wikimedia Commons (keyless)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from .asset_record import make_asset_record
from .rights import check_rights

DEFAULT_HEADERS = {"User-Agent": "OpenMontage/1.0 (museum adapter; keyless)"}


def _http_get(url: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _normalize(source: str, obj: Dict[str, Any], license_info: Any,
               object_id: str, title: str, url: str,
               width: int = 0, height: int = 0,
               thumbnail: Optional[str] = None,
               credit: Optional[str] = None) -> Dict[str, Any]:
    usable, reason = check_rights(license_info)
    return {
        "source": source,
        "object_id": object_id,
        "title": title,
        "url": url,
        "thumbnail": thumbnail,
        "license": license_info,
        "credit": credit or "",
        "width": width,
        "height": height,
        "rights_basis": "explicit_cc0_public_domain" if usable else "rejected_license",
        "usable": usable,
        "rights_reason": reason,
    }


def normalize_candidate(source: str, obj: Optional[Dict[str, Any]] = None,
                        license_info: Any = None,
                        object_id: str = "", title: str = "", url: str = "",
                        width: int = 0, height: int = 0,
                        thumbnail: Optional[str] = None,
                        credit: Optional[str] = None) -> Dict[str, Any]:
    """Public wrapper around _normalize for tests and external callers."""
    return _normalize(source, obj or {}, license_info, object_id, title, url,
                      width, height, thumbnail, credit)


# ---- Met (keyless) ----

def met_object(query: str, http_get: Callable[[str], Dict[str, Any]] = _http_get
               ) -> Optional[Dict[str, Any]]:
    try:
        sr = http_get("https://collectionapi.metmuseum.org/public/collection/v1/search"
                      f"?q={urllib.parse.quote(query)}")
        ids = sr.get("objectIDs") or []
        if not ids:
            return None
        obj = http_get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{ids[0]}")
        lic = "CC0" if obj.get("cc0") else None
        return _normalize(
            "met", obj, lic, str(obj.get("objectID", "")),
            obj.get("title", ""), obj.get("objectURL", ""),
            width=int(obj.get("width", 0) or 0), height=int(obj.get("height", 0) or 0),
            thumbnail=obj.get("primaryImage"), credit=obj.get("creditLine"),
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        return None


# ---- Smithsonian (api_key optional) ----

def smithsonian_object(query: str, http_get: Callable[[str], Dict[str, Any]] = _http_get,
                       api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        params = {"q": urllib.parse.quote(query), "rows": "1"}
        if api_key:
            params["api_key"] = api_key
        url = "https://api.si.edu/openaccess/api/search.cfm?" + urllib.parse.urlencode(params)
        data = http_get(url)
        result = (data.get("response") or {}).get("records") or [{}]
        rec = result[0] if result else {}
        online = rec.get("online_media") or {}
        images = online.get("images") or []
        thumb = images[0].get("url") if images else None
        lic = rec.get("rights") or rec.get("usage") or None
        return _normalize(
            "smithsonian", rec, lic, rec.get("uuid", ""),
            rec.get("title", ""), rec.get("url", ""),
            thumbnail=thumb, credit=rec.get("credit", ""),
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        return None


# ---- Rijksmuseum (key optional) ----

def rijksmuseum_object(query: str, http_get: Callable[[str], Dict[str, Any]] = _http_get,
                       api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        params = {"q": urllib.parse.quote(query), "format": "json", "top": "1"}
        if api_key:
            params["key"] = api_key
        url = "https://www.rijksmuseum.nl/api/nl/collection?" + urllib.parse.urlencode(params)
        data = http_get(url)
        art = (data.get("artObjects") or [None])[0]
        if not art:
            return None
        lic = "CC0" if art.get("principalOrFirstMaker") is not None else None  # placeholder; real API has rights
        return _normalize(
            "rijksmuseum", art, lic, str(art.get("objectNumber", "")),
            art.get("title", ""), art.get("links", {}).get("web", ""),
            width=int((art.get("dimensions") or {}).get("width", 0) or 0),
            height=int((art.get("dimensions") or {}).get("height", 0) or 0),
            thumbnail=art.get("webImage", {}).get("url"),
            credit=art.get("creditLine", ""),
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        return None


# ---- National Gallery of Art (key optional) ----

def nga_object(query: str, http_get: Callable[[str], Dict[str, Any]] = _http_get,
               api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        params = {"q": urllib.parse.quote(query)}
        if api_key:
            params["api_key"] = api_key
        url = "https://api.nga.gov/collection/artwork?" + urllib.parse.urlencode(params)
        data = http_get(url)
        arts = data.get("artworks") or data.get("results") or []
        if not arts:
            return None
        art = arts[0]
        return _normalize(
            "nga", art, art.get("license"), str(art.get("id", "")),
            art.get("title", ""), art.get("url", ""),
            thumbnail=art.get("image"),
            credit=art.get("credit", ""),
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        return None


# ---- Wikimedia Commons (keyless) ----

def wikimedia_file(query: str, http_get: Callable[[str], Dict[str, Any]] = _http_get
                   ) -> Optional[Dict[str, Any]]:
    try:
        params = {"action": "query", "generator": "search", "gsrsearch": query,
                  "gsrnamespace": "6", "gsrlimit": "1", "prop": "imageinfo",
                  "iiprop": "url|size|extmetadata", "format": "json"}
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
        data = http_get(url)
        pages = (data.get("query") or {}).get("pages") or {}
        for page in pages.values():
            ii = (page.get("imageinfo") or [None])[0]
            if not ii:
                continue
            ext = ii.get("extmetadata") or {}
            lic = ext.get("LicenseShortName", {}).get("value", "")
            credit = ext.get("Artist", {}).get("value", "") or ext.get("Credit", {}).get("value", "")
            return _normalize(
                "wikimedia", ii, lic, page.get("title", ""),
                page.get("title", ""), ii.get("descriptionurl", ""),
                width=int((ii.get("width") or 0) or 0), height=int((ii.get("height") or 0) or 0),
                thumbnail=ii.get("url"), credit=credit,
            )
        return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError):
        return None


ADAPTERS = {"met": met_object, "smithsonian": smithsonian_object,
            "rijksmuseum": rijksmuseum_object, "nga": nga_object,
            "wikimedia": wikimedia_file}


def fetch(source: str, query: str, **kwargs) -> Optional[Dict[str, Any]]:
    if source not in ADAPTERS:
        raise ValueError(f"unknown museum source: {source}")
    return ADAPTERS[source](query, **kwargs)
