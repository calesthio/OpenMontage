"""Tests for scripts/s5_tally.py (S5-5). Written before the implementation.

Contract:
- input: the owner-filled CSV + the blind mapping (render panel -> model)
- output per model: wins, losses, anatomy-ok count out of 10
- "TIE" when the best two models differ by <= 1 win
- the recommendation comes ONLY from the owner's CSV (never from the script's
  own judgement), and never when the CSV is incomplete
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s5_tally import (  # noqa: E402
    load_mapping,
    load_results,
    render_report,
    tally,
)

SCENES = ["s01", "s03", "s04", "s05", "s06", "s08", "s09", "s10", "s11", "s12"]
# per-scene panel -> model (the blind mapping the owner never sees)
PANELS = {
    "s01": {"A": "sdxl", "B": "zimage", "C": "klein"},
    "s03": {"A": "zimage", "B": "klein", "C": "sdxl"},
    "s04": {"A": "klein", "B": "sdxl", "C": "zimage"},
    "s05": {"A": "sdxl", "B": "zimage", "C": "klein"},
    "s06": {"A": "zimage", "B": "klein", "C": "sdxl"},
    "s08": {"A": "klein", "B": "sdxl", "C": "zimage"},
    "s09": {"A": "sdxl", "B": "zimage", "C": "klein"},
    "s10": {"A": "zimage", "B": "klein", "C": "sdxl"},
    "s11": {"A": "klein", "B": "sdxl", "C": "zimage"},
    "s12": {"A": "sdxl", "B": "zimage", "C": "klein"},
}
CSV_HEADER = ("scene,best_panel,worst_panel,comment,"
              "anatomy_ok_A,anatomy_ok_B,anatomy_ok_C")


def write_mapping(tmp_path: Path) -> Path:
    p = tmp_path / "mapping.json"
    p.write_text(json.dumps({"model_metrics": {}, "scenes": PANELS}), encoding="utf-8")
    return p


def write_csv(tmp_path: Path, rows) -> Path:
    """rows: list of (scene, best, worst, anatomy_ok dict or None)."""
    p = tmp_path / "results.csv"
    lines = [CSV_HEADER]
    for row in rows:
        scene, best, worst, anatomy = row[0], row[1], row[2], row[3]
        anatomy = anatomy or {"A": "yes", "B": "yes", "C": "yes"}
        lines.append(f"{scene},{best},{worst},,{anatomy['A']},{anatomy['B']},{anatomy['C']}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def fixed_rows(best_by_scene, worst_by_scene=None, anatomy=None):
    worst_by_scene = worst_by_scene or {}
    return [
        (s, best_by_scene[s], worst_by_scene.get(s, ""), anatomy.get(s) if anatomy else None)
        for s in SCENES if s in best_by_scene
    ]


def test_mapping_unblinds_panels_without_leaking_to_owner():
    m = load_mapping(_mapping_dict())
    assert m["panels_by_scene"]["s01"]["A"] == "sdxl"


def _mapping_dict():
    return {"model_metrics": {}, "scenes": PANELS}


def test_tally_counts_wins_losses_and_anatomy(tmp_path):
    # sdxl wins 6 (A on s01,s05,s09,s12; C on s03,s06),
    # zimage wins 3 (B on s01? no -> keep it simple), klein wins 1
    best = {
        "s01": "A", "s03": "C", "s04": "A", "s05": "A", "s06": "C",
        "s08": "A", "s09": "A", "s10": "A", "s11": "A", "s12": "A",
    }
    rows = fixed_rows(best, anatomy={
        "s01": {"A": "yes", "B": "no", "C": "yes"},
        "s03": {"A": "no", "B": "yes", "C": "no"},
    })
    results = load_results(write_csv(tmp_path, rows))
    stats = tally(results, PANELS)
    # s01 A = sdxl, s03 C = sdxl, s04 A = klein, s05 A = sdxl, s06 C = sdxl,
    # s08 A = klein, s09 A = sdxl, s10 A = zimage, s11 A = klein, s12 A = sdxl
    assert stats["sdxl"]["wins"] == 6
    assert stats["klein"]["wins"] == 3
    assert stats["zimage"]["wins"] == 1
    # anatomy-ok is per model, read from that model's own panel on every scene
    # (default "yes" for the 8 scenes not listed above):
    #   sdxl fails s03 (its panel C = no)                  -> 9/10
    #   zimage fails s01 (panel B) and s03 (panel A)       -> 8/10
    #   klein's panel B has no "no" on any scene           -> 10/10
    assert stats["sdxl"]["anatomy_ok"] == 9
    assert stats["zimage"]["anatomy_ok"] == 8
    assert stats["klein"]["anatomy_ok"] == 10


def test_tie_when_top_two_differ_by_one_win(tmp_path):
    best = {s: "A" for s in SCENES}
    best["s03"] = "B"
    best["s04"] = "B"
    best["s05"] = "B"
    best["s06"] = "B"
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "TIE" in report


def test_no_tie_when_clear_winner(tmp_path):
    # sdxl wins 6 scenes (A on s01/s05/s09/s12, C on s03/s06) -> gap of 3
    best = {s: "A" for s in SCENES}
    best["s03"] = "C"
    best["s06"] = "C"
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "TIE" not in report


def test_recommendation_comes_from_owner_csv_only(tmp_path):
    # owner prefers klein on 9 of 10 scenes -> klein must be recommended even
    # though klein is not the fastest model in the metrics table
    panels_for_klein = {}
    for scene, panels in PANELS.items():
        panels_for_klein[scene] = next(p for p, m in panels.items() if m == "klein")
    rows = fixed_rows(panels_for_klein)
    mapping = {
        "model_metrics": {
            "sdxl": {"steady_state_sec_per_image": 3.0, "peak_vram_mb": 6000},
            "zimage": {"steady_state_sec_per_image": 1.0, "peak_vram_mb": 5000},
            "klein": {"steady_state_sec_per_image": 9.0, "peak_vram_mb": 12000},
        },
        "scenes": PANELS,
    }
    report = render_report(load_results(write_csv(tmp_path, rows)), mapping)
    assert "recommended model: klein" in report.lower()


def test_incomplete_csv_blocks_recommendation(tmp_path):
    rows = fixed_rows({s: "A" for s in SCENES[:4]})
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "recommended model" not in report.lower()
    assert "PARTIAL" in report


def test_invalid_panel_is_reported_not_guessed(tmp_path):
    rows = [("s01", "D", "", "", "yes", "yes", "yes")]
    try:
        load_results(write_csv(tmp_path, rows))
    except ValueError as exc:
        assert "s01" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid panel must raise ValueError")


def test_missing_metrics_renders_na(tmp_path):
    rows = fixed_rows({s: "A" for s in SCENES})
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "n/a" in report


def test_metrics_table_includes_speed_and_vram(tmp_path):
    rows = fixed_rows({s: "A" for s in SCENES})
    mapping = {
        "model_metrics": {
            "sdxl": {"steady_state_sec_per_image": 3.2, "peak_vram_mb": 7100},
            "zimage": {"steady_state_sec_per_image": 0.9, "peak_vram_mb": 6100},
            "klein": {"steady_state_sec_per_image": 7.5, "peak_vram_mb": 12800},
        },
        "scenes": PANELS,
    }
    report = render_report(load_results(write_csv(tmp_path, rows)), mapping)
    assert "0.9" in report and "12800" in report
