"""Tests for scripts/s7_push_bakeoff.py (S7-2).

Contract:
  * the pushed runner text exec's cleanly for every model, with the embedded
    job parsed as a dict (the S5 lesson: a JSON-null payload must never
    reach Kaggle);
  * the job carries exactly this model's renders, the shared per-scene seed
    and the fixed resolution;
  * attempt N never repeats an install-ladder rung already used by attempt N-1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s7_push_bakeoff import (  # noqa: E402
    MODEL_CONFIG,
    build_job,
    embed_job,
    ladder_for,
)
from tools.kaggle_bridge.s7_bakeoff_run import DEFAULT_LADDERS  # noqa: E402

RUN_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
TEST_SET = REPO / "docs/openmontage/image_gen/S7_TEST_SET.json"


def _runner_text():
    return RUN_PY.read_text(encoding="utf-8")


def test_embedded_job_executes_as_a_dict_for_every_model():
    for model in MODEL_CONFIG:
        job = build_job(model, 1, 1024, 1024, "attempt 1")
        text = embed_job(_runner_text(), job)
        ns: dict = {"__name__": "s7_runner_not_main"}
        exec(compile(text, "s7_runner_embedded.py", "exec"), ns)  # noqa: S102
        embedded = ns["JOB_EMBEDDED"]
        assert isinstance(embedded, dict), f"{model}: embedded job is not a dict"
        assert embedded["model"] == model
        assert embedded["job_id"] == f"s7-{model}-1"
        assert embedded["renders"], f"{model}: no renders embedded"
        assert all(isinstance(r["prompt"], str) and r["prompt"] for r in embedded["renders"])


def test_job_has_only_this_model_and_fixed_resolution():
    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    for model in MODEL_CONFIG:
        job = build_job(model, 1, 1024, 1024, "attempt 1")
        assert len(job["renders"]) == 10
        assert {r["model"] for r in job["renders"]} == {model}
        assert job["width"] == 1024 and job["height"] == 1024
        seeds = {r["scene_id"]: r["seed"] for r in job["renders"]}
        assert seeds == ts["seeds"], "seed per scene must match the fixed test set"


def test_attempts_do_not_repeat_an_install_rung():
    for model in MODEL_CONFIG:
        used: list[str] = []
        for attempt in (1, 2, 3, 4):
            rung = ladder_for(model, attempt)
            assert rung, f"{model} attempt {attempt}: empty ladder"
            assert rung[0] not in used, (
                f"{model} attempt {attempt} repeats rung {rung[0]}")
            used.append(rung[0])
        assert len(DEFAULT_LADDERS[model]) >= 4


def test_sdxl_job_keeps_the_fp16_vae():
    job = build_job("sdxl", 1, 1024, 1024, "attempt 1")
    assert job["vae_model_id"] == "madebyollin/sdxl-vae-fp16-fix"
    assert job["model_id"] == "stabilityai/stable-diffusion-xl-base-1.0"


def test_klein_job_uses_the_vendor_card_class():
    job = build_job("klein", 1, 1024, 1024, "attempt 1")
    assert job["pipeline_class"] == "Flux2KleinPipeline"
    assert job["model_id"] == "black-forest-labs/FLUX.2-klein-4B"
    assert all(r["negative_prompt"] is None for r in job["renders"])


def test_load_config_override_is_embedded():
    job = build_job("zimage", 2, 1024, 1024, "attempt 2",
                    load_config={"offload": True, "low_cpu_mem_usage": True})
    assert job["load_config"] == {"offload": True, "low_cpu_mem_usage": True}
    text = embed_job(_runner_text(), job)
    ns: dict = {"__name__": "s7_runner_not_main"}
    exec(compile(text, "s7_runner_embedded.py", "exec"), ns)  # noqa: S102
    assert ns["JOB_EMBEDDED"]["load_config"]["offload"] is True


def test_ladder_override_replaces_the_attempt_ladder():
    job = build_job("zimage", 2, 1024, 1024, "attempt 2",
                    ladder_override=["released_037_x4", "released_037_x5"])
    assert job["install_ladder"] == ["released_037_x4", "released_037_x5"]


def test_no_load_config_key_when_not_requested():
    job = build_job("sdxl", 1, 1024, 1024, "attempt 1")
    assert "load_config" not in job
