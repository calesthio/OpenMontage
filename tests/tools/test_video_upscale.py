"""Tests for hero-tier video super-resolution (tools/enhancement/video_upscale.py).

Network-free: FAL gating, the input requirement, payload mapping (incl. opt-in
interpolation off by default), fal response shapes, hero pricing, and additivity
(RealESRGAN `upscale` untouched).
"""
from __future__ import annotations

import pytest

from tools.enhancement.video_upscale import VideoUpscale
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return VideoUpscale()


def test_unavailable_without_fal_key(tool, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    result = tool.execute({"video_url": "http://v"})
    assert result.success is False and "unavailable" in result.error.lower()


def test_requires_input(tool, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    result = tool.execute({})
    assert result.success is False and "input_path or a video_url" in result.error


def test_payload_defaults_no_interpolation(tool):
    # Interpolation must be OFF unless explicitly requested (soap-opera risk).
    payload = tool._build_payload("http://v", {})
    assert payload["video_url"] == "http://v"
    assert payload["upscale_factor"] == 2
    assert "target_fps" not in payload


def test_payload_opt_in_interpolation(tool):
    payload = tool._build_payload("http://v", {"upscale_factor": 4, "target_fps": 60})
    assert payload["upscale_factor"] == 4
    assert payload["target_fps"] == 60


def test_extract_url_handles_both_shapes(tool):
    assert tool._extract_url({"video": {"url": "a"}}) == "a"
    assert tool._extract_url({"videos": [{"url": "b"}]}) == "b"
    with pytest.raises(RuntimeError):
        tool._extract_url({"nothing": True})


def test_cost_is_hero_priced(tool):
    assert tool.estimate_cost({}) >= 0.25  # video upscale is a pricey hero-only op


def test_additive_realesrgan_upscale_untouched():
    from tools.enhancement.upscale import Upscale
    assert Upscale.provider == "realesrgan"
    assert VideoUpscale.provider == "topaz"
    assert Upscale.capability == VideoUpscale.capability == "enhancement"
