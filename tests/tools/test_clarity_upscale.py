"""Tests for the hero-tier Clarity image refiner (tools/enhancement/clarity_upscale.py).

Network-free: availability gating, cost, the low-denoise default that prevents
hallucination, the fal payload/response mapping, and that it's additive (RealESRGAN
`upscale` is untouched).
"""
from __future__ import annotations

import pytest

from tools.enhancement.clarity_upscale import ClarityUpscale
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return ClarityUpscale()


def test_unavailable_without_fal_key(tool, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    result = tool.execute({"input_path": "x.png"})
    assert result.success is False
    assert "unavailable" in result.error.lower()


def test_available_with_fal_key(tool, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_default_creativity_is_low_to_avoid_hallucination(tool):
    # The research-backed anti-hallucination setting: denoise stays low by default.
    payload = tool._build_payload("http://img", {})
    assert payload["creativity"] == 0.35
    assert payload["upscale_factor"] == 2
    assert payload["image_url"] == "http://img"


def test_payload_passes_through_overrides(tool):
    payload = tool._build_payload("http://img", {
        "upscale_factor": 4, "creativity": 0.6, "resemblance": 1.2, "seed": 7, "prompt": "film still",
    })
    assert payload["upscale_factor"] == 4
    assert payload["creativity"] == 0.6
    assert payload["resemblance"] == 1.2
    assert payload["seed"] == 7
    assert payload["prompt"] == "film still"


def test_extract_url_handles_both_fal_shapes(tool):
    assert tool._extract_url({"image": {"url": "a"}}) == "a"
    assert tool._extract_url({"images": [{"url": "b"}]}) == "b"
    with pytest.raises(RuntimeError):
        tool._extract_url({"nope": True})


def test_cost_is_hero_priced_not_free(tool):
    assert 0 < tool.estimate_cost({"input_path": "x"}) <= 0.10


def test_additive_realesrgan_upscale_untouched():
    # The existing local upscaler must still exist as a separate provider.
    from tools.enhancement.upscale import Upscale
    assert Upscale.provider == "realesrgan"
    assert ClarityUpscale.provider == "clarity"
    # Both are the 'enhancement' capability, so both show in the menu.
    assert Upscale.capability == ClarityUpscale.capability == "enhancement"
