"""Tests for the modern local image tool (tools/graphics/local_diffusion_xl.py).

Weight-free: exercises availability gating, free cost, and the per-model call-kwarg
logic (the FLUX-vs-SDXL knob) without loading any diffusion model. Also asserts the
tool is purely additive — it does not touch the existing SD-2.1 local_diffusion.
"""
from __future__ import annotations

import pytest

from tools.graphics.local_diffusion_xl import (
    COMMERCIAL_SAFE_MODELS,
    LocalDiffusionXL,
    _DEFAULT_MODEL,
    _is_flux_schnell,
)


@pytest.fixture
def tool():
    return LocalDiffusionXL()


def test_default_model_is_commercial_safe_sdxl():
    assert _DEFAULT_MODEL == "stabilityai/stable-diffusion-xl-base-1.0"
    assert _DEFAULT_MODEL in COMMERCIAL_SAFE_MODELS
    # The non-commercial FLUX-dev must never be a suggested default.
    assert not any("dev" in m.lower() for m in COMMERCIAL_SAFE_MODELS)


def test_free_cost(tool):
    assert tool.estimate_cost({"prompt": "a fox"}) == 0.0


def test_flux_detection():
    assert _is_flux_schnell("black-forest-labs/FLUX.1-schnell")
    assert not _is_flux_schnell("black-forest-labs/FLUX.1-dev")  # dev is not schnell
    assert not _is_flux_schnell("stabilityai/stable-diffusion-xl-base-1.0")


def test_sdxl_call_kwargs_include_negative_and_full_steps(tool):
    kw = tool._build_call_kwargs(_DEFAULT_MODEL, {"prompt": "castle", "negative_prompt": "blurry"})
    assert kw["negative_prompt"] == "blurry"
    assert kw["num_inference_steps"] == 30
    assert kw["guidance_scale"] == 7.0
    assert kw["width"] == 1024 and kw["height"] == 1024


def test_flux_call_kwargs_omit_negative_and_use_distilled_defaults(tool):
    # FLUX-schnell has no negative_prompt and wants guidance 0 / ~4 steps.
    kw = tool._build_call_kwargs("black-forest-labs/FLUX.1-schnell",
                                 {"prompt": "castle", "negative_prompt": "blurry"})
    assert "negative_prompt" not in kw
    assert kw["num_inference_steps"] == 4
    assert kw["guidance_scale"] == 0.0


def test_explicit_overrides_win_over_model_defaults(tool):
    kw = tool._build_call_kwargs("black-forest-labs/FLUX.1-schnell",
                                 {"prompt": "x", "num_inference_steps": 8, "guidance_scale": 1.5})
    assert kw["num_inference_steps"] == 8
    assert kw["guidance_scale"] == 1.5


def test_additive_does_not_replace_sd21_local_diffusion():
    # The original SD-2.1 tool must still exist, untouched, as a separate provider.
    from tools.graphics.local_diffusion import LocalDiffusion
    assert LocalDiffusion.provider == "local_diffusion"
    assert LocalDiffusionXL.provider == "local_diffusion_xl"
    assert LocalDiffusion().input_schema["properties"]["model"]["default"] == (
        "stabilityai/stable-diffusion-2-1-base"
    )
