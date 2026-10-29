#!/usr/bin/env python3
"""Tests for the S8 extension of the blind-pack tally (5 models, A-E panels)."""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "bakeoff_tally", REPO / "scripts/s7_tally.py")
tally_mod = importlib.util.module_from_spec(spec)
sys.modules["bakeoff_tally"] = tally_mod
spec.loader.exec_module(tally_mod)

SCENES = [f"s{n:02d}" for n in (1, 3, 4, 5, 6, 8, 9, 10, 11, 12)]
FIVE = ["sdxl", "klein", "sdxl-lightning", "dreamshaper-xl",
        "sana-sprint-1.6b"]
PANELS = ("A", "B", "C", "D", "E")


def mapping_doc(rotate: bool = False) -> dict:
    """Panel -> model per scene (rotated per scene when asked: a real pack
    randomises the order so the owner cannot learn the model from the layout).
    """
    scenes = {}
    for i, scene in enumerate(SCENES):
        models = list(FIVE)
        if rotate:
            models = models[i % 5:] + models[:i % 5]
        scenes[scene] = {p: m for p, m in zip(PANELS, models)}
    return {"model_metrics": {}, "scenes": scenes}


def write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "results.csv"
    header = ["scene", "best_panel", "second_best", "worst_panel"]
    header += [f"anatomy_ok_{x}" for x in PANELS] + ["comment"]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def row(scene: str, best: str, second: str, worst: str,
        anatomy: dict | None = None) -> dict:
    r = {"scene": scene, "best_panel": best, "second_best": second,
         "worst_panel": worst, "comment": ""}
    for x in PANELS:
        r[f"anatomy_ok_{x}"] = (anatomy or {}).get(x, "")
    return r


def test_five_panel_mapping_and_csv_load():
    mapping = tally_mod.load_mapping(mapping_doc())
    assert set(mapping["panels_by_scene"]) == set(SCENES)
    assert all(len(p) == 5 for p in mapping["panels_by_scene"].values())


def test_second_places_are_counted(tmp_path):
    rows = []
    for scene in SCENES:
        rows.append(row(scene, "A", "B", "E",
                        {"A": "yes", "B": "yes", "C": "no", "D": "yes",
                         "E": "no"}))
    p = write_csv(tmp_path, rows)
    results = tally_mod.load_results(p)
    stats = tally_mod.tally(results, mapping_doc())
    panel_to_model = mapping_doc()["scenes"][SCENES[0]]
    best_model = panel_to_model["A"]
    second_model = panel_to_model["B"]
    worst_model = panel_to_model["E"]
    assert stats[best_model]["wins"] == 10
    assert stats[second_model]["seconds"] == 10
    assert stats[worst_model]["losses"] == 10
    assert stats[best_model]["anatomy_ok"] == 10
    assert stats[best_model]["anatomy_out_of"] == 10
    # with a rotated pack the seconds are spread over the models
    rotated = tally_mod.tally(results, mapping_doc(rotate=True))
    assert sum(m["seconds"] for m in rotated.values()) == 10


def test_second_best_must_differ_from_best_and_worst(tmp_path):
    p = write_csv(tmp_path, [row(SCENES[0], "A", "A", "C")])
    try:
        tally_mod.load_results(p)
    except ValueError as exc:
        assert "second_best" in str(exc)
    else:
        raise AssertionError("expected a ValueError")


def test_panel_letters_come_from_the_csv_not_a_fixed_list(tmp_path):
    p = write_csv(tmp_path, [row(SCENES[0], "A", "B", "C")])
    results = tally_mod.load_results(p)
    assert set(results[0]["anatomy"]) == set(PANELS)


def test_tie_when_the_top_two_are_within_one_win(tmp_path):
    rows = [row(s, "A", "B", "E") for s in SCENES]
    rows[0] = row(SCENES[0], "B", "A", "E")
    p = write_csv(tmp_path, rows)
    report = tally_mod.render_report(tally_mod.load_results(p),
                                     mapping_doc(rotate=True))
    assert "TIE" in report


def test_agent_vs_owner_agree_and_disagree(tmp_path):
    rows = [row(s, "A", "B", "E") for s in SCENES]
    p = write_csv(tmp_path, rows)
    mapping = mapping_doc()
    winner = mapping["scenes"][SCENES[0]]["A"]
    report = tally_mod.render_report(tally_mod.load_results(p), mapping,
                                     agent_pick=winner)
    assert "AGREE" in report
    report2 = tally_mod.render_report(tally_mod.load_results(p), mapping,
                                      agent_pick="not-the-winner")
    assert "DISAGREE" in report2


def test_report_contains_the_speed_and_vram_table(tmp_path):
    doc = mapping_doc()
    doc["model_metrics"] = {
        m: {"steady_state_sec_per_image": 10.0, "usable_images_per_minute": 5.0,
            "peak_vram_mb": 8000.0, "black_count": 0, "nan_count": 0,
            "oom_count": 0, "load_seconds": 100.0}
        for m in FIVE
    }
    rows = [row(s, "A", "B", "E") for s in SCENES]
    p = write_csv(tmp_path, rows)
    report = tally_mod.render_report(tally_mod.load_results(p),
                                     tally_mod.load_mapping(doc))
    assert "s/image (steady)" in report
    assert "peak VRAM MB" in report
    for m in FIVE:
        assert f"| {m} |" in report
