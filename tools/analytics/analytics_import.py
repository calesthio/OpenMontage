#!/usr/bin/env python3
"""tools/analytics/analytics_import.py — YouTube Studio analytics import (M8).

Parses YouTube Studio CSV exports into docs/openmontage/analytics/ and computes
retention drop points per chapter. No OAuth, no network, local files only.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", col.lower())


def _find_col(fields: List[str], candidates: List[str]) -> Optional[str]:
    norm = {_norm(f): f for f in fields}
    for c in candidates:
        nc = _norm(c)
        if nc in norm:
            return norm[nc]
    # substring fallback
    for c in candidates:
        nc = _norm(c)
        for f in fields:
            if nc in _norm(f):
                return f
    return None


def parse_studio_csv(path) -> List[Dict[str, str]]:
    """Parse a YouTube Studio CSV export. Flexible column names via fuzzy match.

    Returns list of row dicts keyed by normalized semantic names:
      video_title, publish_time, views, watch_time_minutes, subscribers,
      average_view_duration, relative_audience_retention, rpm_usd, cpm_usd.
    """
    path = Path(path)
    rows_out: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        colmap = {
            "video_title": _find_col(fields, ["video title", "title"]),
            "publish_time": _find_col(fields, ["video publish time", "publish time", "date"]),
            "views": _find_col(fields, ["views"]),
            "watch_time_minutes": _find_col(fields, ["watch time (minutes)", "watch time"]),
            "subscribers": _find_col(fields, ["subscribers"]),
            "average_view_duration": _find_col(fields, ["average view duration"]),
            "relative_audience_retention": _find_col(fields, ["relative audience retention (%)", "relative audience retention", "audience retention %"]),
            "rpm_usd": _find_col(fields, ["rpm (usd)", "rpm"]),
            "cpm_usd": _find_col(fields, ["cpm (usd)", "cpm"]),
        }
        for row in reader:
            out: Dict[str, str] = {}
            for key, col in colmap.items():
                out[key] = (row.get(col) or "").strip() if col else ""
            rows_out.append(out)
    return rows_out


def _to_float(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def retention_drop_points(rows: List[Dict[str, str]],
                          threshold: float = 0.10) -> List[Dict[str, Any]]:
    """Find points where relative audience retention drops by > threshold.

    threshold is a fraction (0.10 = 10 percentage points). Returns list of
    {index, from, to, drop, retention_before, retention_after}.
    """
    drops: List[Dict[str, Any]] = []
    prev: Optional[float] = None
    prev_idx: Optional[int] = None
    for i, row in enumerate(rows):
        cur = _to_float(row.get("relative_audience_retention", ""))
        if cur is None:
            continue
        if prev is not None and prev_idx is not None:
            drop = (prev - cur) / 100.0  # fraction of 100%
            if drop > threshold:
                drops.append({
                    "index": i,
                    "from_index": prev_idx,
                    "from": prev,
                    "to": cur,
                    "drop": round(drop, 4),
                })
        prev = cur
        prev_idx = i
    return drops


def import_analytics(csv_path, out_dir) -> Dict[str, Any]:
    """Parse a Studio CSV, compute retention drop points, write analytics.json.

    Returns {ok, output, rows, drop_points}.
    """
    csv_path = Path(csv_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = parse_studio_csv(csv_path)
    drops = retention_drop_points(rows)
    analytics = {
        "source": str(csv_path),
        "imported_utc": now_utc(),
        "rows": len(rows),
        "drop_points": drops,
        "rows_sample": rows[:5],
    }
    out_path = out_dir / "analytics.json"
    out_path.write_text(json.dumps(analytics, indent=2), encoding="utf-8")
    return {"ok": True, "output": str(out_path), "rows": len(rows),
            "drop_points": drops}
