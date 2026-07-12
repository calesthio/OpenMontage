"""Regression: maas_video's ToolResult.data must reflect what actually
happened, not just what the caller asked for.

- leapfast/wan2.2 ignores the resolution enum entirely and substitutes its
  own fixed size grid (see _build_payload) — the result must report the
  size actually used, not the ignored input value.
- Seedance's native-passthrough content array for image_to_video/
  reference_to_video has no audio field at all — if a caller explicitly
  requests an audio setting there, it can't be honored and must surface as
  a warning instead of being silently dropped.
"""

from __future__ import annotations

import pytest

from tools.video.maas_video import MaasVideo


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("MAAS_API_KEY", "sk-dlp-test-key")


class _FakeResponse:
    def __init__(self, json_data=None, content=b"fake-mp4-bytes"):
        self._json = json_data or {}
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def iter_content(self, chunk_size=8192):
        yield self._content


@pytest.fixture
def _stub_success_flow(monkeypatch):
    job_id = "job-abc123"

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/v1/video/generations")
        return _FakeResponse({"job_id": job_id})

    def fake_get(url, headers=None, timeout=None, stream=None):
        if url.endswith(f"/v1/video/jobs/{job_id}"):
            return _FakeResponse({"status": "succeeded"})
        if url.endswith(f"/v1/video/jobs/{job_id}/result"):
            return _FakeResponse(content=b"fake-mp4-bytes")
        raise AssertionError(f"unexpected GET {url}")

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda *_: None)


def test_wan22_reports_actual_size_grid_not_requested_resolution(_stub_success_flow, tmp_path):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "waves",
        "model": "leapfast/wan2.2",
        "operation": "text_to_video",
        "resolution": "1080p",  # this model has no resolution enum at all
        "aspect_ratio": "9:16",
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True
    assert result.data["resolution"] == "704*1280"


def test_non_wan22_model_reports_requested_resolution_unchanged(_stub_success_flow, tmp_path):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a cat",
        "model": "volcengine/doubao-seedance-2.0",
        "operation": "text_to_video",
        "resolution": "480p",
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True
    assert result.data["resolution"] == "480p"


def test_seedance_i2v_explicit_audio_request_surfaces_warning(_stub_success_flow, tmp_path):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a cat",
        "model": "volcengine/doubao-seedance-2.0",
        "operation": "image_to_video",
        "image_url": "https://example.com/cat.png",
        "audio": False,
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True
    assert any("audio" in w for w in result.data["warnings"])


def test_seedance_t2v_audio_request_does_not_warn(_stub_success_flow, tmp_path):
    # Seedance t2v uses the standard DTO, which does have an audio field —
    # only the i2v/r2v native-passthrough path drops it.
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a cat",
        "model": "volcengine/doubao-seedance-2.0",
        "operation": "text_to_video",
        "audio": False,
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True
    assert result.data["warnings"] == []


def test_no_warning_when_audio_not_explicitly_requested(_stub_success_flow, tmp_path):
    tool = MaasVideo()
    result = tool.execute({
        "prompt": "a cat",
        "model": "volcengine/doubao-seedance-2.0",
        "operation": "image_to_video",
        "image_url": "https://example.com/cat.png",
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True
    assert result.data["warnings"] == []
