"""Tests for scripts/s7_tally.py (S7-8). Written before the implementation.

Contract:
- input: the owner-filled CSV + the blind mapping (panel -> model)
- output per model: wins, losses, anatomy-ok count out of 10
- "TIE" when the best two models differ by <= 1 win
- the recommendation comes ONLY from the owner's CSV (never from the script's
  own judgement), and never when the CSV is incomplete
- "AGENT vs OWNER agree/disagree" compares the owner's winner with the
  agent's advisory pick; the agent's pick never overrides the owner
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s7_tally import (  # noqa: E402
    load_agent_pick,
    load_mapping,
    load_results,
    render_report,
    tally,
)

SCENES = ["s01", "s03", "s04", "s05", "s06", "s08", "s09", "s10", "s11", "s12"]
PANELS = {
    "s01": {"A": "sdxl", "B": "klein", "C": "zimage"},
    "s03": {"A": "zimage", "B": "sdxl", "C": "klein"},
    "s04": {"A": "klein", "B": "zimage", "C": "sdxl"},
    "s05": {"A": "sdxl", "B": "klein", "C": "zimage"},
    "s06": {"A": "zimage", "B": "klein", "C": "sdxl"},
    "s08": {"A": "klein", "B": "sdxl", "C": "zimage"},
    "s09": {"A": "sdxl", "B": "zimage", "C": "klein"},
    "s10": {"A": "zimage", "B": "sdxl", "C": "klein"},
    "s11": {"A": "klein", "B": "sdxl", "C": "zimage"},
    "s12": {"A": "sdxl", "B": "klein", "C": "zimage"},
}
CSV_HEADER = ("scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,"
              "anatomy_ok_C,comment")


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
        lines.append(
            f"{scene},{best},{worst},{anatomy['A']},{anatomy['B']},"
            f"{anatomy['C']},note")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_agent(tmp_path: Path, pick: str) -> Path:
    p = tmp_path / "agent.json"
    p.write_text(json.dumps({"agent_pick": pick, "confidence": "medium"}),
                 encoding="utf-8")
    return p


def fixed_rows(best_by_scene, worst_by_scene=None, anatomy=None):
    worst_by_scene = worst_by_scene or {}
    return [
        (s, best_by_scene[s], worst_by_scene.get(s, ""),
         anatomy.get(s) if anatomy else None)
        for s in SCENES if s in best_by_scene
    ]


def _mapping_dict():
    return {"model_metrics": {}, "scenes": PANELS}


def test_mapping_unblinds_panels_without_leaking_to_owner():
    m = load_mapping(_mapping_dict())
    assert m["panels_by_scene"]["s01"]["A"] == "sdxl"


def test_tally_counts_wins_losses_and_anatomy(tmp_path):
    # s01 A=sdxl  s03 C=klein  s04 A=klein  s05 A=sdxl  s06 C=sdxl
    # s08 A=klein  s09 A=sdxl  s10 A=zimage s11 A=klein s12 A=sdxl
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
    assert stats["sdxl"]["wins"] == 5
    assert stats["klein"]["wins"] == 4
    assert stats["zimage"]["wins"] == 1
    # anatomy-ok is per model, read from that model's own panel on every scene
    # (default "yes" for the 8 scenes not listed above):
    #   sdxl  -> no "no" on any scene            -> 10/10
    #   klein -> no on s01 (B) and s03 (C)       -> 8/10
    #   zimage-> no on s03 (A)                   -> 9/10
    assert stats["sdxl"]["anatomy_ok"] == 10
    assert stats["klein"]["anatomy_ok"] == 8
    assert stats["zimage"]["anatomy_ok"] == 9


def test_tie_when_top_two_differ_by_one_win(tmp_path):
    best = {s: "A" for s in SCENES}
    for s in ("s03", "s04", "s05", "s06"):
        best[s] = "B"
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "TIE" in report


def test_no_tie_when_clear_winner(tmp_path):
    # sdxl takes 8 scenes, klein 2 -> gap of 6
    best = {
        "s01": "A", "s03": "B", "s04": "A", "s05": "A", "s06": "C",
        "s08": "B", "s09": "A", "s10": "B", "s11": "A", "s12": "A",
    }
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict())
    assert "TIE" not in report
    assert "recommended model: sdxl" in report.lower()


def test_recommendation_comes_from_owner_csv_only(tmp_path):
    panels_for_klein = {
        scene: next(p for p, m in panels.items() if m == "klein")
        for scene, panels in PANELS.items()
    }
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
    rows = [("s01", "D", "", {"A": "yes", "B": "yes", "C": "yes"})]
    try:
        load_results(write_csv(tmp_path, rows))
    except ValueError as exc:
        assert "s01" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid panel must raise ValueError")


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


def test_agent_vs_owner_agree(tmp_path):
    # owner: sdxl 8 wins, klein 2 -> clear owner winner sdxl
    best = {
        "s01": "A", "s03": "B", "s04": "A", "s05": "A", "s06": "C",
        "s08": "B", "s09": "A", "s10": "B", "s11": "A", "s12": "A",
    }
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict(),
                           agent_pick="sdxl")
    assert "AGENT vs OWNER" in report
    assert "agree" in report.lower()
    assert "disagree" not in report.lower()


def test_agent_vs_owner_disagree(tmp_path):
    best = {
        "s01": "A", "s03": "B", "s04": "A", "s05": "A", "s06": "C",
        "s08": "B", "s09": "A", "s10": "B", "s11": "A", "s12": "A",
    }
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict(),
                           agent_pick="zimage")
    assert "AGENT vs OWNER" in report
    assert "disagree" in report.lower()


def test_agent_vs_owner_when_owner_is_a_tie(tmp_path):
    best = {s: "A" for s in SCENES}
    for s in ("s03", "s04", "s05", "s06"):
        best[s] = "B"
    rows = fixed_rows(best)
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict(),
                           agent_pick="klein")
    assert "TIE" in report
    assert "AGENT vs OWNER" in report


def test_missing_agent_assessment_is_not_checked_not_guessed(tmp_path):
    rows = fixed_rows({s: "A" for s in SCENES})
    report = render_report(load_results(write_csv(tmp_path, rows)), _mapping_dict(),
                           agent_pick=None)
    assert "NOT_CHECKED" in report


def test_load_agent_pick_reads_the_assessment_json(tmp_path):
    p = write_agent(tmp_path, "klein")
    assert load_agent_pick(p) == "klein"
    assert load_agent_pick(tmp_path / "missing.json") is None


def test_two_model_pack_tallies(tmp_path):
    """A blocked third model must not break the owner tally."""
    panels2 = {s: {"A": "sdxl", "B": "klein"} for s in SCENES}
    mapping = {"model_metrics": {}, "scenes": panels2}
    m = load_mapping(mapping)
    assert m["panels_by_scene"]["s01"]["B"] == "klein"
    rows = fixed_rows({s: "A" for s in SCENES})
    report = render_report(load_results(write_csv(tmp_path, rows)), mapping)
    assert "recommended model: sdxl" in report.lower()
    assert "zimage" not in report.lower()
