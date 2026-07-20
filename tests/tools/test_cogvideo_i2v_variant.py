"""Regression for cogvideo-2b i2v mismatch (REVIEW §8 #4).

COGVIDEO_VARIANTS declares the 2B variant i2v=False (t2v-only), but
cogvideo_video advertised image_to_video + reference_image unconditionally
and never consulted the variant flag — so an image_to_video brief against
cogvideo-2b reached the diffusion pipeline and failed opaquely.

This pins:
- is_operation_available() derives capability from the variant table
  (default 5b: t2v + i2v both True), not an unconditional True.
- execute() fails fast with a clear error when the caller's chosen variant
  lacks the requested mode (2b + image_to_video).
"""

from __future__ import annotations

import pytest

from tools.base_tool import ToolStatus
from tools.video._shared import COGVIDEO_VARIANTS
from tools.video.cogvideo_video import CogVideoVideo


def test_2b_variant_is_t2v_only():
    """The premise: the 2B variant really does declare i2v=False."""
    assert COGVIDEO_VARIANTS["cogvideo-2b"]["i2v"] is False
    assert COGVIDEO_VARIANTS["cogvideo-2b"]["t2v"] is True


def test_5b_variant_supports_i2v():
    assert COGVIDEO_VARIANTS["cogvideo-5b"]["i2v"] is True


def test_is_operation_available_reflects_default_variant():
    tool = CogVideoVideo()
    # Default variant (5b) supports both modes.
    assert tool.is_operation_available("text_to_video") is True
    assert tool.is_operation_available("image_to_video") is True


def test_execute_rejects_i2v_for_2b_variant(monkeypatch):
    """Selecting the 2B variant for image_to_video fails fast, not at the pipeline."""
    monkeypatch.setattr(
        CogVideoVideo, "get_status", lambda self: ToolStatus.AVAILABLE
    )
    # Guard against the local-generation path actually running.
    monkeypatch.setattr(
        "tools.video.cogvideo_video.generate_local_video",
        lambda **kw: pytest.fail("generate_local_video must not run for an unsupported variant"),
    )

    result = CogVideoVideo().execute(
        {"prompt": "x", "operation": "image_to_video", "model_variant": "cogvideo-2b"}
    )
    assert result.success is False
    assert "cogvideo-2b" in result.error
    assert "image_to_video" in result.error


def test_execute_allows_i2v_for_5b_variant(monkeypatch):
    """The default 5B variant still routes to generation for image_to_video."""
    from tools.base_tool import ToolResult

    monkeypatch.setattr(
        CogVideoVideo, "get_status", lambda self: ToolStatus.AVAILABLE
    )

    sentinel = ToolResult(success=True, data={"output": "out.mp4"})

    def fake_generate(**kw):
        return sentinel

    monkeypatch.setattr("tools.video.cogvideo_video.generate_local_video", fake_generate)

    result = CogVideoVideo().execute(
        {"prompt": "x", "operation": "image_to_video", "model_variant": "cogvideo-5b"}
    )
    assert result.success is True
