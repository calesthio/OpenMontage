#!/usr/bin/env python3
"""Red/green tests for the reference-image (img2img) path of the runner (P2).

The locked model's official card (FLUX.2-klein-4B, accessed 2026-10-22)
documents multi-reference image-to-image editing, so the runner may hand a
reference image to the pipeline. The tests below cover the pure call builder
only - no GPU, no Kaggle, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.creature_sheet import (  # noqa: E402
    build_creature_sheet,
    build_sheet_job,
    load_creature_specs,
)
from tools.illustration.model_registry import (  # noqa: E402
    active_adapter,
    load_engine,
)
from tools.illustration.style_kit import load_style  # noqa: E402


def _runner():
    path = ROOT / "tools/kaggle_bridge" / "s7_bakeoff_run.py"
    spec = importlib.util.spec_from_file_location("om_s7_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CREATURE_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"


def test_call_without_a_reference_has_no_image():
    runner = _runner()
    render = {"render_id": "r0001", "prompt": "p", "steps": 4,
              "guidance_scale": 1.0, "seed": 3000}
    call = runner.build_generation_call(render, {"guidance_override": None},
                                        1024, 1024)
    assert "image" not in call
    assert call["num_inference_steps"] == 4
    assert call["guidance_scale"] == 1.0


def test_call_with_a_reference_passes_the_image(tmp_path):
    runner = _runner()
    from PIL import Image
    ref = tmp_path / "r0001.png"
    Image.new("RGB", (16, 16), (10, 20, 30)).save(ref)
    render = {"render_id": "r0002", "prompt": "p", "steps": 4,
              "guidance_scale": 1.0, "seed": 3001}
    call = runner.build_generation_call(render, {}, 1024, 1024, str(ref))
    assert "image" in call
    assert call["image"].size == (16, 16)


def test_the_sheet_job_points_the_other_views_at_the_front_view():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    job = build_sheet_job("speculative_evolution", creature,
                          build_creature_sheet(creature, style, adapter), adapter)
    front = job["renders"][0]["render_id"]
    assert job["renders"][0].get("reference_render_id") is None
    for render in job["renders"][1:]:
        assert render["reference_render_id"] == front
    assert job["reference_policy"]["supported"] is True
    assert job["reference_policy"]["card"].startswith("http")


def test_the_runner_keeps_working_without_the_reference_feature():
    """A job without reference declarations behaves exactly as before."""
    runner = _runner()
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    renders = build_creature_sheet(creature, style, adapter)
    for render in renders:
        render.pop("reference_render_id", None)
    job = build_sheet_job("speculative_evolution", creature, renders, adapter)
    plan = runner.resolve_model_plan(job)
    assert plan["candidates"] == list(adapter.pipeline_candidates)
    assert plan["ladder"] == list(adapter.install_ladder)
