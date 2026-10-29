#!/usr/bin/env python3
"""tools/museum/asset_record.py — immutable asset record (M4).

Each downloaded museum asset gets a record: sha256, credit, URL, source,
rights_basis, usable flag. Written next to the asset; never committed (media is
gitignored).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .rights import check_rights, rights_basis


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_asset_record(url: str, credit: str, sha256: str,
                      source: str = "", object_id: str = "",
                      width: int = 0, height: int = 0,
                      license_info: Any = None) -> Dict[str, Any]:
    usable, reason = check_rights(license_info)
    return {
        "url": url,
        "credit": credit,
        "sha256": sha256,
        "source": source,
        "object_id": object_id,
        "width": width,
        "height": height,
        "license": license_info,
        "rights_basis": rights_basis(usable, reason),
        "usable": usable,
        "rights_reason": reason,
        "recorded_utc": now_utc(),
    }


def write_asset_record(asset_path, record: Dict[str, Any]) -> str:
    rec_path = Path(str(asset_path) + ".record.json")
    rec_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return str(rec_path)
