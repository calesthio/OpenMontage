#!/usr/bin/env python3
"""Red-then-green tests for tools/analytics/analytics_import.py (M8).

Parses YouTube Studio CSV exports (recorded fixtures only, no OAuth, no network)
into docs/openmontage/analytics/ and computes retention drop points per chapter.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.analytics.analytics_import import (  # noqa: E402
    parse_studio_csv,
    retention_drop_points,
    import_analytics,
)

TMP = Path("/tmp/kilo_analytics")
TMP.mkdir(parents=True, exist_ok=True)


def test_parse_studio_csv_flexible_columns():
    csv = TMP / "studio.csv"
    csv.write_text(
        "Video title,Video publish time,Views,Average view duration %\n"
        "ISS Earth View,2026-01-01,1234,85\n"
        "ISS Earth View,2026-01-02,5678,72\n"
    )
    rows = parse_studio_csv(csv)
    assert len(rows) == 2
    assert rows[0]["views"] == "1234"


def test_retention_drop_points():
    rows = [
        {"relative_audience_retention": "90"},
        {"relative_audience_retention": "88"},
        {"relative_audience_retention": "60"},  # big drop
        {"relative_audience_retention": "59"},
        {"relative_audience_retention": "40"},  # big drop
    ]
    drops = retention_drop_points(rows, threshold=0.10)
    assert len(drops) == 2
    assert drops[0]["from"] == 88 and drops[0]["to"] == 60
    assert drops[1]["from"] == 59 and drops[1]["to"] == 40


def test_import_analytics_writes_json():
    csv = TMP / "studio2.csv"
    csv.write_text(
        "Video title,Views,Relative audience retention (%)\n"
        "Demo,100,90\nDemo,200,50\nDemo,300,45\n"
    )
    import json
    out_dir = TMP / "analytics"
    res = import_analytics(csv, out_dir)
    assert res["ok"] is True
    assert (out_dir / "analytics.json").is_file()
    data = json.loads((out_dir / "analytics.json").read_text())
    assert "drop_points" in data
