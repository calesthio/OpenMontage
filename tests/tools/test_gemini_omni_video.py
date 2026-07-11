"""Regression coverage for first-class Gemini Omni provider discovery and execution."""

from __future__ import annotations

import base64
import json
import sys
import types
from pathlib import Path

import pytest

from tools.base_tool import ToolStatus


class FakeResponse:
    def __init__(self, json_data=None, content=b"", ok=True, status_code=200, headers=None, text=""):
        self._json = json_data
        self.content = content
        self.ok = ok
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text or (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _install_fake_requests(monkeypatch, post_responses, get_responses):
    """Inject a fake requests module; returns the recorded calls."""
    calls = {"post": [], "get": []}

    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, data=None, timeout=None, params=None):
        calls["post"].append({"url": url, "headers": headers, "json": json, "data": data})
        return post_responses.pop(0)

    def fake_get(url, headers=None, timeout=None, params=None):
        calls["get"].append({"url": url, "headers": headers, "params": params})
        return get_responses.pop(0)

    fake.post = fake_post
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


@pytest.fixture()
def gemini_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


def test_gemini_omni_is_discovered_as_video_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("gemini_omni_video")
    assert tool is not None
    assert tool.provider == "gemini_omni"
    assert tool.capability == "video_generation"
    # Ranking + selector-filter contract: without these the scorer buries the
    # editing capability and the selector drops it from image_to_video routing.
    assert tool.quality_score == 0.85
    assert tool.supports["image_to_video"] is True
    assert tool.supports["reference_to_video"] is True
    assert tool.supports["conversational_editing"] is True
    assert "gemini-omni" in tool.agent_skills


def test_gemini_omni_is_routed_by_video_selector():
    from tools.video.video_selector import VideoSelector

    provider_names = [t.name for t in VideoSelector()._providers()]
    assert "gemini_omni_video" in provider_names


def test_gemini_omni_status_tracks_google_api_keys(monkeypatch):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GeminiOmniVideo().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    assert GeminiOmniVideo().get_status() == ToolStatus.AVAILABLE


def test_gemini_omni_cost_estimate_clamps_duration_hint(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    tool = GeminiOmniVideo()
    assert tool.estimate_cost({"prompt": "x"}) == pytest.approx(0.80)
    assert tool.estimate_cost({"prompt": "x", "duration": "5s"}) == pytest.approx(0.50)
    assert tool.estimate_cost({"prompt": "x", "duration": "30"}) == pytest.approx(1.00)


def test_gemini_omni_text_to_video_via_uri_delivery(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse({"id": "int_123", "output_video": {"uri": "files/vid-123"}}),
        ],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"fake omni mp4"),
        ],
    )

    output_path = tmp_path / "clip.mp4"
    result = GeminiOmniVideo().execute(
        {
            "prompt": "A marble rolling on a track, single continuous shot.",
            "aspect_ratio": "9:16",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert output_path.read_bytes() == b"fake omni mp4"
    assert result.data["interaction_id"] == "int_123"
    assert result.data["editable"] is True

    payload = calls["post"][0]["json"]
    assert payload["model"] == "gemini-omni-flash-preview"
    assert payload["input"] == "A marble rolling on a track, single continuous shot."
    assert payload["response_format"] == {"type": "video", "aspect_ratio": "9:16", "delivery": "uri"}
    assert calls["post"][0]["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert calls["get"][1]["url"].endswith("files/vid-123:download")
    assert calls["get"][1]["params"] == {"alt": "media"}


def test_gemini_omni_uri_delivery_handles_full_download_url(monkeypatch, tmp_path, gemini_env):
    """The API may return a full .../files/<id>:download?alt=media URL, not just files/<id>."""
    from tools.video.gemini_omni_video import GeminiOmniVideo

    full_url = (
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456:download?alt=media"
    )
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_5", "output_video": {"uri": full_url}})],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"full url mp4"),
        ],
    )

    output_path = tmp_path / "full.mp4"
    result = GeminiOmniVideo().execute({"prompt": "A sunset.", "output_path": str(output_path)})

    assert result.success, result.error
    assert output_path.read_bytes() == b"full url mp4"
    assert calls["get"][0]["url"].endswith("/files/vid-456")
    assert calls["get"][1]["url"].endswith("/files/vid-456:download")


@pytest.mark.parametrize(
    "uri",
    [
        "files/vid-456",
        "files/vid-456/",
        "v1beta/files/vid-456",
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456",
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456:download?alt=media",
    ],
)
def test_gemini_omni_file_id_extraction_covers_documented_uri_shapes(uri):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    assert GeminiOmniVideo._file_id_from_uri(uri) == "vid-456"


def test_gemini_omni_inline_data_response_is_handled(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"inline mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_9", "output_video": {"data": inline}})],
        get_responses=[],
    )

    output_path = tmp_path / "inline.mp4"
    result = GeminiOmniVideo().execute({"prompt": "A sunset.", "output_path": str(output_path)})

    assert result.success, result.error
    assert output_path.read_bytes() == b"inline mp4"
    assert calls["get"] == []


def test_gemini_omni_edit_turn_sends_previous_interaction_id(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"edited mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_2", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "Make the violin invisible. Keep everything else the same.",
            "operation": "edit_video",
            "previous_interaction_id": "int_1",
            "output_path": str(tmp_path / "edit.mp4"),
        }
    )

    assert result.success, result.error
    assert calls["post"][0]["json"]["previous_interaction_id"] == "int_1"


def test_gemini_omni_edit_without_source_is_rejected(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    result = GeminiOmniVideo().execute({"prompt": "Make it anime", "operation": "edit_video"})
    assert not result.success
    assert "previous_interaction_id" in result.error


def test_gemini_omni_image_to_video_sends_typed_parts(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    ref = tmp_path / "cat.png"
    ref.write_bytes(b"png bytes")
    inline = base64.b64encode(b"cat mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_3", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "A cat <IMAGE_REF_0> playfully batting at yarn.",
            "operation": "image_to_video",
            "reference_image_path": str(ref),
            "output_path": str(tmp_path / "cat.mp4"),
        }
    )

    assert result.success, result.error
    parts = calls["post"][0]["json"]["input"]
    assert parts[0]["type"] == "image"
    assert parts[0]["mime_type"] == "image/png"
    assert parts[0]["data"] == base64.b64encode(b"png bytes").decode("ascii")
    assert parts[-1] == {"type": "text", "text": "A cat <IMAGE_REF_0> playfully batting at yarn."}


def test_gemini_omni_image_to_video_requires_reference(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    result = GeminiOmniVideo().execute({"prompt": "x", "operation": "image_to_video"})
    assert not result.success
    assert "reference_image_path" in result.error


def test_gemini_omni_store_false_marks_result_not_editable(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"oneshot mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_4", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "store": False, "output_path": str(tmp_path / "s.mp4")}
    )

    assert result.success, result.error
    assert result.data["editable"] is False
    assert calls["post"][0]["json"]["store"] is False
