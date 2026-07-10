"""Regression: maas_video.execute() must reject an operation the chosen
model doesn't support BEFORE making the paid API call, not silently drop
the image_url/reference and return a normal-looking text-to-video clip.

Found live: several models are declared "ops": ["t2v"] only (e.g.
happyhorse-1.0-t2v), but a multi-shot character-consistency pass could
request image_to_video/reference_to_video against one with no error — the
reference is silently ignored, and the mismatch only surfaces as visibly
inconsistent output across shots after paying for all of them.

leapfast/ltx-2.3 was originally in that same t2v-only bucket per the
2026-06-28 model catalogue, but a live test on 2026-07-10 confirmed
image_to_video actually works through this gateway route (submit ->
succeeded, output correctly conditioned on the reference frame) — MODELS
was corrected to ["t2v", "i2v"] accordingly. reference_to_video is still
genuinely unsupported for this model, so that rejection case still uses it.
"""

from __future__ import annotations

import pytest

from tools.video.maas_video import MaasVideo


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    # These checks must reject before any network call, but execute()
    # checks for an API key first — set one so the operation/model check
    # is actually what's being exercised.
    monkeypatch.setenv("MAAS_API_KEY", "sk-dlp-test-key")


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {}  # no job_id — execute() reports this as a clean ToolResult


@pytest.fixture
def _no_network(monkeypatch):
    """Requests that pass the operation/model check must not hit the network —
    stub requests.post so a bug that removes/weakens the validation shows up
    as a real network call (and likely a test failure/hang) instead of
    silently passing."""
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse())


def test_image_to_video_rejected_for_t2v_only_model():
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "happyhorse-1.0-t2v",
        "operation": "image_to_video",
        "image_url": "https://example.com/ref.png",
    })
    assert result.success is False
    assert "happyhorse-1.0-t2v" in result.error
    assert "image_to_video" in result.error


def test_image_to_video_allowed_for_ltx(_no_network):
    # Confirmed live 2026-07-10 — see module docstring.
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "leapfast/ltx-2.3",
        "operation": "image_to_video",
        "image_url": "https://example.com/ref.png",
    })
    assert "does not support operation" not in (result.error or "")


def test_reference_to_video_rejected_for_t2v_only_model():
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "leapfast/ltx-2.3",
        "operation": "reference_to_video",
        "image_url": "https://example.com/ref.png",
    })
    assert result.success is False
    assert "reference_to_video" in result.error
    # Error should point toward a model that actually supports it.
    assert "happyhorse-1.0-r2v" in result.error


def test_text_to_video_still_allowed_for_ltx(_no_network):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "leapfast/ltx-2.3",
        "operation": "text_to_video",
    })
    # Should proceed past the validation check to the (stubbed) API call,
    # not fail on model/operation compatibility.
    assert result.error == "No job_id in gateway response: {}"


def test_image_to_video_allowed_for_seedance(_no_network):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "volcengine/doubao-seedance-2.0",
        "operation": "image_to_video",
        "image_url": "https://example.com/ref.png",
    })
    assert result.error == "No job_id in gateway response: {}"


def test_unknown_model_rejected():
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a robot vacuum",
        "model": "not-a-real-model",
    })
    assert result.success is False
    assert "Unknown model" in result.error
