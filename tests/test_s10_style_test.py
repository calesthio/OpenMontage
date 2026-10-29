#!/usr/bin/env python3
"""Tests for the S10 visual-style test (3 styles x 6 scenes x 3 seeds = 54).

Covers the four pieces of the milestone:
  * s10_build_testset   -> the frozen 54-render test set (same seeds per style)
  * s10_push_style_test -> ONE kernel job for the config-locked model
  * s10_blind_pack      -> 6 blind sheets + 6 captioned sheets + CSV + mapping
  * s10_checks          -> objective flags only (blur, duplicates, caption
                           contrast, colour spread)
  * s10_tally           -> owner-gated tally (refuses an incomplete CSV)
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from PIL import ImageFilter

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


build_set = _load("s10_build", REPO / "scripts/s10_build_testset.py")
push = _load("s10_push", REPO / "scripts/s10_push_style_test.py")
pack = _load("s10_pack", REPO / "scripts/s10_blind_pack.py")
checks = _load("s10_checks", REPO / "scripts/s10_checks.py")
tally = _load("s10_tally", REPO / "scripts/s10_tally.py")


# ----------------------------------------------------------------- test set
def test_test_set_is_54_renders_6_scenes_3_styles_3_seeds():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    assert len(doc["renders"]) == 54
    assert len(doc["scenes"]) == 6
    assert set(doc["styles"]) == {"S-A", "S-B", "S-C"}
    per = {}
    for r in doc["renders"]:
        per.setdefault((r["scene_id"], r["style"]), []).append(r)
    assert len(per) == 18
    for key, rows in per.items():
        assert len(rows) == 3, key
        assert len({r["seed"] for r in rows}) == 3
    for scene in doc["scenes"]:
        # same three seeds for every style of that scene
        seeds = {r["style"]: sorted(x["seed"] for x in doc["renders"]
                                    if x["scene_id"] == scene)
                 for _ in [0]}
        values = list(seeds.values())
        # recompute per style
        per_style = {}
        for r in doc["renders"]:
            if r["scene_id"] == scene:
                per_style.setdefault(r["style"], []).append(r["seed"])
        assert len({tuple(sorted(v)) for v in per_style.values()}) == 1


def test_kinds_are_two_creatures_two_habitats_plate_wide():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    kinds = [s["kind"] for s in doc["scene_specs"]]
    assert kinds.count("creature") == 2
    assert kinds.count("habitat") == 2
    assert kinds.count("food_web_plate") == 1
    assert kinds.count("wide_scene") == 1


def test_creature_prompts_carry_the_anatomy_counts():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    creatures = [s["scene_id"] for s in doc["scene_specs"]
                 if s["kind"] == "creature"]
    for r in doc["renders"]:
        if r["scene_id"] in creatures:
            spec = r["anatomy_counts"]
            line = (f"{spec['limbs']} limbs, {spec['eyes']} eyes, "
                    f"{spec['horns']} horns")
            assert line in r["prompt"], (r["render_id"], line)
    # and the counts are not zero for a creature
    assert any(r["anatomy_counts"]["limbs"] > 0 for r in doc["renders"]
               if r["scene_id"] in creatures)


def test_each_style_prompt_is_present_and_positive():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    for r in doc["renders"]:
        style = doc["style_specs"][r["style"]]
        for token in style["prompt_tokens"]:
            assert token in r["prompt"], (r["render_id"], token)
        low = r["prompt"].lower()
        assert "plain background" not in low
        assert "white background" not in low
        assert len(r["prompt"]) <= 1200
        assert r["negative_prompt"] is None  # klein: no negative prompt


def test_no_named_artist_channel_or_franchise_in_any_prompt():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    banned = ["studio ghibli", "ghibli", "disney", "pixar", "moebius", "miyazaki",
              "beeple", "greg rutkowski", "artstation", "kuvshinov",
              "in the style of", "national geographic", "bbc earth", "kurzgesagt",
              "hayao", "shinkai", "star wars", "marvel"]
    for r in doc["renders"]:
        low = r["prompt"].lower()
        for term in banned:
            assert term not in low, (r["render_id"], term)


def test_background_and_palette_vary_per_scene():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    palettes = [json.dumps(s["spec"]["palette"], sort_keys=True)
                for s in doc["scene_specs"]]
    assert len(set(palettes)) == 6
    backgrounds = [s["spec"]["environment"] for s in doc["scene_specs"]]
    assert len(set(backgrounds)) == 6


def test_test_set_uses_the_config_locked_model():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    cfg = json.loads((REPO / "config/image_engine.json")
                     .read_text(encoding="utf-8"))
    assert doc["model"] == cfg["model"]
    assert doc["dtype"] == "float16"
    assert doc["bitsandbytes"] is False
    for r in doc["renders"]:
        assert r["steps"] == cfg["steps"]
        assert r["dtype"] == "float16"


def test_seeds_come_from_the_reserved_range_and_are_unique_per_scene():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    seen = {}
    for r in doc["renders"]:
        assert 3000 <= r["seed"] <= 3999
        seen.setdefault(r["scene_id"], set()).add(r["seed"])
    all_seeds = [s for v in seen.values() for s in v]
    assert len(all_seeds) == len(set(all_seeds)) == 18


# --------------------------------------------------------------------- push
def test_push_job_carries_54_renders_and_the_config_lock():
    test_set = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                          .read_text(encoding="utf-8"))
    adapter = push.locked_adapter()
    job = push.build_job(test_set, adapter, attempt=1)
    assert job["job_id"] == "s10-style-test-1"
    assert job["output_dir"] == f"s10_bakeoff_{adapter.key}"
    assert len(job["renders"]) == 54
    assert job["dtype"] == "float16"
    assert job["model_config"]["dtype"] == "float16"
    assert all("git" not in rung.lower() for rung in job["install_ladder"])
    assert job["width"] == 1024 and job["height"] == 1024


def test_composed_runner_is_self_contained_and_syntactically_valid():
    test_set = json.loads((REPO / "docs/openmontage/image_gen/S10_TEST_SET.json")
                          .read_text(encoding="utf-8"))
    job = push.build_job(test_set, push.locked_adapter(), attempt=1)
    text = push.build_runner(job)
    compile(text, "run.py", "exec")
    assert text.count('if __name__ == "__main__":') == 1
    assert "JOB_EMBEDDED = None" not in text
    assert "s10-style-test-1" in text
    assert '\\"bitsandbytes\\": false' in text
    assert '\\"dtype\\": \\"float16\\"' in text


# --------------------------------------------------------------- blind pack
def _fake_images(tmp_path: Path, n_scenes: int = 2, n_styles: int = 3,
                 seeds: int = 3) -> Path:
    """Neutral render ids + manifest, like the kernel output."""
    images = tmp_path / "images"
    images.mkdir(parents=True)
    rows = []
    k = 0
    for scene in range(n_scenes):
        # the same seed per seed-index across styles (the real test set rule)
        scene_seeds = [3000 + scene * 10 + i for i in range(seeds)]
        for seed_index, seed in enumerate(scene_seeds):
            for style in range(n_styles):
                k += 1
                rid = f"p{k:03d}"
                rng = np.random.default_rng(1000 + k)
                arr = rng.integers(0, 60, size=(1024, 1024, 3), dtype=np.uint8)
                # bottom band dark so white captions are legible
                arr[-180:, :, :] = 12
                Image.fromarray(arr).save(images / f"{rid}.png")
                rows.append({"render_id": rid, "scene_id": f"s{scene + 1:02d}",
                             "style": f"S-{'ABC'[style]}", "seed": seed,
                             "file": f"{rid}.png", "width": 1024, "height": 1024,
                             "seed_index": seed_index})
    manifest = {"job_id": "s10-style-test-1", "model": "klein",
                "images": rows, "requested": len(rows)}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_blind_pack_builds_sheets_csv_and_separate_mapping(tmp_path):
    root = _fake_images(tmp_path)
    out = tmp_path / "blind"
    mapping = pack.run(root / "images", root / "manifest.json", out,
                       captions={"s01": "Caption one.", "s02": "Caption two."})
    sheets = sorted(p.name for p in out.glob("sheet_*.png"))
    assert sheets == ["sheet_s01.png", "sheet_s01_caption.png",
                      "sheet_s02.png", "sheet_s02_caption.png"]
    for p in out.glob("*.png"):
        with Image.open(p) as im:
            assert im.size[0] <= 1600, p.name
            assert im.size[1] > 0
    assert mapping["scenes"]["s01"] and len(mapping["scenes"]["s01"]) == 3
    assert set(mapping["scenes"]["s01"].values()) == {"S-A", "S-B", "S-C"}
    # the same panel letter must not always map to the same style
    orders = [tuple(sorted(v.items())) for v in mapping["scenes"].values()]
    assert len(set(orders)) >= 1
    assert (out / "results.csv").is_file()
    header = (out / "results.csv").read_text().splitlines()[0]
    assert header == ("scene,best_panel,worst_panel,"
                      "readable_with_captions_A,readable_with_captions_B,"
                      "readable_with_captions_C,comment")
    assert (out / "INSTRUCTIONS.txt").is_file()
    m = json.loads((out / "mapping.json").read_text(encoding="utf-8"))
    assert "unblinds" in m["note"].lower()


def test_blind_pack_caption_sheet_burns_white_text(tmp_path):
    root = _fake_images(tmp_path, n_scenes=1)
    out = tmp_path / "blind"
    pack.run(root / "images", root / "manifest.json", out,
             captions={"s01": "A caption for the phone."})
    with Image.open(out / "sheet_s01.png") as plain:
        plain_px = np.asarray(plain.convert("RGB"))
    with Image.open(out / "sheet_s01_caption.png") as cap:
        cap_px = np.asarray(cap.convert("RGB"))
    assert plain_px.shape == cap_px.shape
    # white pixels appear only in the captioned variant
    white_plain = int(((plain_px > 245).all(axis=2)).sum())
    white_cap = int(((cap_px > 245).all(axis=2)).sum())
    assert white_cap > white_plain + 100


# -------------------------------------------------------------------- checks
def test_checks_flag_monotone_blurry_and_duplicate_images(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    rng = np.random.default_rng(7)
    flat = np.full((1024, 1024, 3), 90, dtype=np.uint8)
    Image.fromarray(flat).save(images / "monotone.png")
    blurry = np.asarray(
        Image.fromarray(rng.integers(0, 255, (1024, 1024, 3), dtype=np.uint8))
        .filter(ImageFilter.GaussianBlur(12)), dtype=np.uint8)
    Image.fromarray(blurry).save(images / "blurry.png")
    colourful = rng.integers(0, 255, size=(1024, 1024, 3), dtype=np.uint8)
    Image.fromarray(colourful).save(images / "colourful.png")
    Image.fromarray(colourful).save(images / "duplicate.png")
    rows = [{"render_id": p.stem, "scene_id": "s01", "style": "S-A",
             "seed": 3000, "file": p.name} for p in sorted(images.glob("*.png"))]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"job_id": "j", "images": rows}),
                        encoding="utf-8")
    out = tmp_path / "checks.json"
    report = checks.run(images, manifest, out)
    by = {r["render_id"]: r for r in report["images"]}
    assert by["monotone"]["colour_spread_flag"] is True
    assert by["colourful"]["colour_spread_flag"] is False
    assert by["blurry"]["blur_flag_absolute"] is True
    assert any(d["a"].endswith("colourful") and d["b"].endswith("duplicate")
               for d in report["duplicates"])
    assert "caption_contrast_flag" in by["colourful"]
    assert out.is_file()


def test_caption_band_metric_separates_dark_and_bright_bands(tmp_path):
    dark = np.full((1024, 1024, 3), 10, dtype=np.uint8)
    bright = np.full((1024, 1024, 3), 245, dtype=np.uint8)
    d = tmp_path / "dark.png"
    b = tmp_path / "bright.png"
    Image.fromarray(dark).save(d)
    Image.fromarray(bright).save(b)
    md = checks.caption_band_metrics(d)
    mb = checks.caption_band_metrics(b)
    assert md["dark_fraction"] > 0.9
    assert mb["dark_fraction"] < 0.1
    assert md["white_text_contrast_flag"] is True
    assert mb["white_text_contrast_flag"] is False


# --------------------------------------------------------------------- tally
def _write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=pack.CSV_HEADER.split(","))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_tally_refuses_an_incomplete_csv(tmp_path):
    mapping = {"scenes": {"s01": {"A": "S-A", "B": "S-B", "C": "S-C"},
                          "s02": {"A": "S-B", "B": "S-C", "C": "S-A"}}}
    mp = tmp_path / "mapping.json"
    mp.write_text(json.dumps(mapping), encoding="utf-8")
    csv_path = tmp_path / "results.csv"
    _write_csv(csv_path, [
        {"scene": "s01", "best_panel": "A", "worst_panel": "C",
         "readable_with_captions_A": "yes", "readable_with_captions_B": "yes",
         "readable_with_captions_C": "yes", "comment": ""},
    ])
    out = tally.tally(csv_path, mp)
    assert out["status"] == "INCOMPLETE"
    assert out["filled"] == 1 and out["expected"] == 2
    assert out["wins"] == {}


def test_tally_counts_wins_and_caption_readability(tmp_path):
    mapping = {"scenes": {"s01": {"A": "S-A", "B": "S-B", "C": "S-C"},
                          "s02": {"A": "S-B", "B": "S-C", "C": "S-A"}}}
    mp = tmp_path / "mapping.json"
    mp.write_text(json.dumps(mapping), encoding="utf-8")
    csv_path = tmp_path / "results.csv"
    _write_csv(csv_path, [
        {"scene": "s01", "best_panel": "A", "worst_panel": "C",
         "readable_with_captions_A": "yes", "readable_with_captions_B": "no",
         "readable_with_captions_C": "yes", "comment": "clean"},
        {"scene": "s02", "best_panel": "C", "worst_panel": "B",
         "readable_with_captions_A": "no", "readable_with_captions_B": "yes",
         "readable_with_captions_C": "no", "comment": ""},
    ])
    out = tally.tally(csv_path, mp)
    assert out["status"] == "COMPLETE"
    assert out["wins"] == {"S-A": 2}
    assert out["losses"] == {"S-C": 2}
    assert out["caption_readable"] == {"S-A": 1, "S-C": 2}
    assert out["caption_scored"] == {"S-A": 2, "S-B": 2, "S-C": 2}
    assert out["n_scenes"] == 2
