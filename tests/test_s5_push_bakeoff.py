"""Guard the job payload actually executes as Python (S5-2).

The first two S5 SDXL kernels died before touching the GPU because the job was
embedded with plain json.dumps -> `null` in Python source. This test compiles
and execs the exact runner text that gets pushed, for every model.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s5_push_bakeoff import (  # noqa: E402
    KERNEL_SLUG,
    RUN_PY,
    build_job,
    embed_job,
)


def _load(model: str):
    src = embed_job(RUN_PY.read_text(encoding="utf-8"), build_job(model))
    ns: dict = {}
    exec(compile(src, f"runner_{model}", "exec"), ns)  # noqa: S102 - test only
    return src, ns


def test_every_model_job_executes_and_keeps_nulls_as_none():
    for model in ("sdxl", "zimage", "klein"):
        src, ns = _load(model)
        job = ns["JOB_EMBEDDED"]
        assert job["model"] == model
        assert job["width"] == job["height"] == 1024
        assert len(job["renders"]) == 13, f"{model}: expected 10 scenes + 3 neutral"
        assert any(r["negative_prompt"] is None for r in job["renders"]), \
            f"{model}: neutral renders must keep negative_prompt None"
        # guard the exact failure mode: bare JSON literals outside the string
        assert "JOB_EMBEDDED = {" not in src


def test_sdxl_keeps_negative_prompt_and_fp16_settings():
    _, ns = _load("sdxl")
    r = next(x for x in ns["JOB_EMBEDDED"]["renders"] if x["variant"] == "A")
    assert r["negative_prompt"] and r["guidance_scale"] == 7.5 and r["steps"] == 50
    assert ns["JOB_EMBEDDED"]["vae_model_id"] == "madebyollin/sdxl-vae-fp16-fix"


def test_zimage_and_klein_have_no_negative_prompt_on_main_variant():
    for model, variant in (("zimage", "B"), ("klein", "C")):
        _, ns = _load(model)
        r = next(x for x in ns["JOB_EMBEDDED"]["renders"] if x["variant"] == variant)
        assert r["negative_prompt"] is None


def test_s5_has_its_own_kernel_slug():
    # the shared runner slug belongs to other milestones; S5 must not overwrite it
    assert KERNEL_SLUG == "forts845/openmontage-s5-runner"
