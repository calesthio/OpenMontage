#!/usr/bin/env python3
"""Red/green tests for the CONFIG-driven Kaggle runner (P1).

The kernel runner must work for a model it has never seen: the job payload
carries the model's contract (pipeline classes, install ladder, load config)
coming from config/image_engine.json. No network, no Kaggle, no GPU - only
the pure resolution logic is exercised.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.episode_batch import build_job, load_specs, plan_renders  # noqa: E402
from tools.illustration.model_registry import adapter_for, load_engine  # noqa: E402


def _runner():
    path = ROOT / "tools" / "kaggle_bridge" / "s7_bakeoff_run.py"
    spec = importlib.util.spec_from_file_location("om_s7_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CREATURE_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"
MODELS = ("klein", "sdxl-lightning", "dreamshaper-xl-lightning", "sdxl")


@pytest.mark.parametrize("key", MODELS)
def test_runner_resolves_every_configured_model_from_the_job(key):
    runner = _runner()
    engine = load_engine()
    adapter = adapter_for(engine, key)
    renders = plan_renders(load_specs(CREATURE_DIR)[:1], key, per_spec=1)
    job = build_job("t_runner", key, renders, width=320, height=180)

    plan = runner.resolve_model_plan(job)
    assert plan["candidates"] == list(adapter.pipeline_candidates)
    assert plan["ladder"] == list(adapter.install_ladder)
    assert plan["cfg"]["scheduler"]["class"] == adapter.scheduler.get("class")
    assert plan["cfg"]["guidance_override"] == adapter.guidance
    assert plan["cfg"]["offload"] == adapter.cpu_offload


def test_runner_needs_no_builtin_entry_for_a_configured_model():
    """A model that the runner's own tables never knew still resolves."""
    runner = _runner()
    engine = load_engine()
    adapter = adapter_for(engine, "dreamshaper-xl-lightning")
    assert "dreamshaper-xl-lightning" not in runner.DEFAULT_LADDERS
    assert "dreamshaper-xl-lightning" not in runner.PIPELINE_CANDIDATES
    plan = runner.resolve_model_plan({
        "model": "dreamshaper-xl-lightning",
        "model_config": adapter.job_model_config(),
    })
    assert plan["candidates"] == list(adapter.pipeline_candidates)
    assert plan["ladder"] == list(adapter.install_ladder)


def test_runner_fails_closed_without_candidates_or_ladder():
    runner = _runner()
    plan = runner.resolve_model_plan({"model": "totally-unknown-model"})
    assert plan["candidates"] == []
    assert plan["ladder"] == []


def test_job_payload_carries_the_full_model_contract():
    engine = load_engine()
    adapter = adapter_for(engine, "sdxl-lightning")
    renders = plan_renders(load_specs(CREATURE_DIR)[:1], "sdxl-lightning",
                            per_spec=1)
    job = build_job("t_runner", "sdxl-lightning", renders)
    assert job["model_config"]["pipeline_candidates"] == \
        list(adapter.pipeline_candidates)
    assert job["model_config"]["install_ladder"] == list(adapter.install_ladder)
    assert job["model_config"]["steps"] == adapter.steps
    assert job["model_config"]["guidance"] == adapter.guidance
    assert job["unet_checkpoint"]["repo"] == "ByteDance/SDXL-Lightning"
    assert job["load_config"]["scheduler"]["class"] == "EulerDiscreteScheduler"
    # the payload is JSON-serialisable (it is embedded into the kernel)
    json.dumps(job)
