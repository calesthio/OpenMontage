"""Coverage for the OpenRouter vision tool.

No network: the endpoint call is exercised through a fake urlopen, and the
ffmpeg calls through a fake subprocess.run. tests/conftest.py blocks sockets at
the socket layer anyway, so a regression that reintroduces a real request fails
loudly rather than billing someone.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from tools.analysis.openrouter_vision import OpenRouterVision
from tools.base_tool import ToolStatus


class FakeHTTPResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(monkeypatch, payload):
    """Capture the outgoing request and answer it with payload."""
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode())
        return FakeHTTPResponse(payload)

    monkeypatch.setattr("tools.analysis.openrouter_vision.urllib.request.urlopen", fake)
    return captured


def _ok(text="a description"):
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture()
def keyed(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


@pytest.fixture()
def image(tmp_path):
    # A real PNG header matters: the tool picks the mime type off the magic bytes.
    path = tmp_path / "frame.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return path


def test_discovered_by_the_registry():
    from tools.tool_registry import ToolRegistry
    import tools.analysis.openrouter_vision as module

    assert "openrouter_vision" in ToolRegistry().register_module(module)


def test_status_follows_the_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert OpenRouterVision().get_status() is ToolStatus.UNAVAILABLE
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert OpenRouterVision().get_status() is ToolStatus.AVAILABLE


def test_missing_key_is_reported_not_posted(monkeypatch, image):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = OpenRouterVision().execute({"input_path": str(image)})
    assert not result.success
    assert "OPENROUTER_API_KEY" in result.error


@pytest.mark.parametrize(
    "inputs, expected",
    [
        ({"input_path": "/nope/missing.png"}, "not found"),
        ({"input_path": "notes.txt"}, "Unsupported file type"),
        ({"input_path": "frame.png", "mode": "qa"}, "Query is required"),
        ({"input_path": "frame.png", "mode": "interpretive-dance"}, "Unknown mode"),
    ],
)
def test_input_guards(keyed, tmp_path, image, inputs, expected):
    if inputs["input_path"] in ("frame.png", "notes.txt"):
        target = tmp_path / inputs["input_path"]
        if not target.exists():
            target.write_bytes(b"x")
        inputs = {**inputs, "input_path": str(target)}
    result = OpenRouterVision().execute(inputs)
    assert not result.success
    assert expected in result.error


def test_image_is_sent_inline_with_a_bearer_header(keyed, monkeypatch, image):
    captured = _fake_urlopen(monkeypatch, _ok("a red square"))

    result = OpenRouterVision().execute(
        {"input_path": str(image), "mode": "qa", "query": "what colour?"}
    )

    assert result.success
    assert result.data["summary"] == "a red square"
    assert result.data["frame_count"] == 1
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"

    content = captured["body"]["messages"][0]["content"]
    assert "what colour?" in content[0]["text"]
    images = [part for part in content if part["type"] == "image_url"]
    assert len(images) == 1
    # PNG magic bytes must produce a PNG mime type, not the JPEG default.
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_upstream_error_inside_a_200_is_a_failure(keyed, monkeypatch, image):
    # OpenRouter reports routed-provider failures as HTTP 200 with an error
    # member. Treating that as success returns an empty summary and no reason.
    _fake_urlopen(monkeypatch, {"error": {"message": "upstream is down"}})
    result = OpenRouterVision().execute({"input_path": str(image)})
    assert not result.success
    assert "upstream is down" in result.error


def test_empty_content_is_a_failure(keyed, monkeypatch, image):
    _fake_urlopen(monkeypatch, {"choices": [{"message": {"content": ""}}]})
    result = OpenRouterVision().execute({"input_path": str(image)})
    assert not result.success


def test_model_comes_from_input_then_env_then_default(keyed, monkeypatch):
    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)
    assert OpenRouterVision._model({}) == "stealth/ox-alpha"
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "vendor/from-env")
    assert OpenRouterVision._model({}) == "vendor/from-env"
    assert OpenRouterVision._model({"model": "vendor/explicit"}) == "vendor/explicit"


def test_frames_are_sampled_across_the_whole_clip(monkeypatch, tmp_path):
    """Regression: sampling must not cluster at the start of the video.

    The obvious ffmpeg spelling for this — `-vf thumbnail=N -frames:v N` —
    selects the most representative frame out of each consecutive N-frame
    BATCH, so it never looks past the opening seconds. A four-second clip that
    is red for 2s then blue for 2s came back as four red frames and a confident
    "nothing changes across the sequence".
    """
    seek_positions: list[float] = []

    def fake_run(cmd, **kwargs):
        assert "thumbnail=" not in " ".join(cmd), "thumbnail= reintroduces the batching bug"
        if "-ss" in cmd:
            seek_positions.append(float(cmd[cmd.index("-ss") + 1]))
            Path(cmd[-4]).write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("tools.analysis.openrouter_vision.subprocess.run", fake_run)
    monkeypatch.setattr(OpenRouterVision, "_duration_seconds", staticmethod(lambda _p: 100.0))

    frames = OpenRouterVision._sample_video(tmp_path / "clip.mp4", 4, 720)

    assert len(frames) == 4
    assert seek_positions == [12.5, 37.5, 62.5, 87.5]
    # Every sample sits inside its own quarter, and the last is near the end —
    # the property the batching bug violated.
    assert seek_positions[-1] > 75.0


def test_sampling_falls_back_when_duration_is_unknown(monkeypatch, tmp_path):
    """A stream or a missing ffprobe must still yield frames, not zero."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "-frames:v" in cmd:
            for index in range(2):
                Path(str(cmd[-4]).replace("%04d", f"{index:04d}")).write_bytes(b"\xff\xd8\xff")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("tools.analysis.openrouter_vision.subprocess.run", fake_run)
    monkeypatch.setattr(OpenRouterVision, "_duration_seconds", staticmethod(lambda _p: None))

    frames = OpenRouterVision._sample_video(tmp_path / "stream.mp4", 2, 720)

    assert frames, "fallback path must still produce frames"
    assert not any("-ss" in cmd for cmd in calls), "no duration means no seek positions"


def test_max_frames_is_capped(keyed, monkeypatch, tmp_path):
    """The cap is a transfer-cost guard: frames go base64-encoded in the body."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 16)
    requested: dict = {}

    def fake_sample(path, max_frames, height):
        requested["max_frames"] = max_frames
        return [b"\xff\xd8\xff"]

    monkeypatch.setattr(OpenRouterVision, "_sample_video", staticmethod(fake_sample))
    _fake_urlopen(monkeypatch, _ok())

    OpenRouterVision().execute({"input_path": str(video), "max_frames": 500})
    assert requested["max_frames"] == 24
