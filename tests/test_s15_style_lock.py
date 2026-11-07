#!/usr/bin/env python3
"""S15: the recipe file, the push script and the frozen prompt contract agree.

These tests do not touch the network, Kaggle or any model. They exist so the
frozen recipe cannot drift silently: if someone edits a style string, a step
count or the anatomy sentence in the push script without updating the recipe
JSON, this fails.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RECIPE = REPO / "docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json"
PUSH = REPO / "scripts/s15_push_style_lock.py"


def _push_module():
    spec = importlib.util.spec_from_file_location("s15_push_style_lock", PUSH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _recipe():
    return json.loads(RECIPE.read_text(encoding="utf-8"))


def test_recipe_is_frozen():
    r = _recipe()
    assert r["model"]["model_id"] == "Lykon/dreamshaper-xl-1-0"
    assert len(r["model"]["revision"]) == 40
    rec = r["recipe"]
    assert rec["dtype"] == "float16"
    assert rec["bf16"] is False
    assert rec["bitsandbytes"] is False
    assert rec["steps"] == 25
    assert rec["guidance_scale"] == 5.5
    assert rec["scheduler"]["class"] == "DEISMultistepScheduler"
    assert "stock" in rec["vae"]
    assert rec["seeds"] == [1001, 2027]


def test_recipe_matches_push_script():
    r = _recipe()
    m = _push_module()
    assert r["model"]["model_id"] == m.MODEL_ID
    assert r["model"]["revision"] == m.REVISION
    assert r["recipe"]["steps"] == m.STEPS
    assert r["recipe"]["guidance_scale"] == m.CFG
    assert r["recipe"]["seeds"] == m.SEEDS
    assert r["recipe"]["negative_prompt"] == m.NEGATIVE
    assert r["recipe"]["prompt_rule"].endswith('no text"')
    assert m.TAIL in r["recipe"]["prompt_rule"]
    assert r["s15_style_lock_test"]["styles"] == list(m.STYLES)


def test_style_strings_are_frozen():
    r = _recipe()
    m = _push_module()
    # the three style strings must be identical in both places, byte for byte
    assert set(m.STYLES) == {"paper-cut", "field-guide", "graphic-novel-ink"}
    for key, text in m.STYLES.items():
        assert text == text.strip()
        assert "  " not in text
        assert len(text) > 80
    assert r["s15_style_lock_test"]["styles"] == list(m.STYLES)


def test_job_shape_and_prompt_contract():
    m = _push_module()
    job = m.build_job(1)
    assert len(job["renders"]) == 36
    assert len(job["wide_scenes"]) == 6
    assert job["bf16"] is False and job["bitsandbytes"] is False
    seen = set()
    for render in job["renders"]:
        assert render["prompt"].endswith(m.TAIL)
        assert render["negative_prompt"] == m.NEGATIVE
        assert render["steps"] == 25
        assert render["guidance_scale"] == 5.5
        seen.add((render["scene_id"], render["style"], render["seed"]))
        # style string appears verbatim and only one style per prompt
        present = [k for k, v in m.STYLES.items() if v in render["prompt"]]
        assert present == [render["style"]], (render["render_id"], present)
    assert len(seen) == 36


def test_anatomy_sentence_only_on_limbed_creatures():
    m = _push_module()
    job = m.build_job(1)
    by_scene = {}
    for render in job["renders"]:
        by_scene.setdefault(render["scene_id"], set()).add(
            m.ANATOMY_CREATURE in render["prompt"])
    assert by_scene["s01"] == {True}
    assert by_scene["s10"] == {True}
    assert by_scene["s03"] == {False}      # S10 says the drifter is limbless
    for habitat in ("s05", "s06", "s12"):
        assert by_scene[habitat] == {False}
    s03 = next(r for r in job["renders"] if r["scene_id"] == "s03")
    assert "limbless" in s03["prompt"]


def test_no_wide_duplicates_of_square_renders():
    m = _push_module()
    job = m.build_job(1)
    ids = [r["render_id"] for r in job["renders"]]
    assert len(ids) == len(set(ids))
    assert sorted(job["wide_scenes"]) == ["s01", "s03", "s05", "s06", "s10", "s12"]
