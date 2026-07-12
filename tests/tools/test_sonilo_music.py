"""Tests for tools/audio/sonilo_music.py — SoniloMusic tool.

Network calls are stubbed with a fake ``requests`` module (the tool imports
``requests`` lazily inside ``_generate``), so the suite runs hermetically —
no API key, no network, no ffprobe required.
"""

from __future__ import annotations

import base64
import json
import sys
import types

import pytest

from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ToolRuntime,
    ToolStatus,
    ToolTier,
)
from tools.audio.sonilo_music import SoniloMusic
from tools.tool_registry import ToolRegistry


API_KEY = "test-key"


def _chunk(data: bytes, index: int = 0) -> str:
    return json.dumps(
        {
            "type": "audio_chunk",
            "stream_index": index,
            "num_streams": 1,
            "data": base64.b64encode(data).decode("ascii"),
        }
    )


_HAPPY_LINES = [
    '{"type": "stage_start", "stage": "analysis"}',
    _chunk(b"abc"),
    '{"type": "title", "title": "Rainy Commute"}',
    _chunk(b"def"),
    "not json at all",
    '{"type": "complete"}',
]


class _FakeStreamResponse:
    def __init__(self, lines=None, status_code: int = 200, text: str = "") -> None:
        self._lines = list(lines or [])
        self.status_code = status_code
        self.text = text

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def json(self):
        return json.loads(self.text)


def _install_fake_requests(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict,
    response: _FakeStreamResponse,
) -> types.ModuleType:
    """Install a stub ``requests`` module that records the outgoing call."""
    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, data=None, files=None, stream=False, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["files"] = files
        captured["stream"] = stream
        captured["timeout"] = timeout
        return response

    fake.post = fake_post
    monkeypatch.setitem(sys.modules, "requests", fake)
    return fake


@pytest.fixture
def tool(monkeypatch) -> SoniloMusic:
    monkeypatch.setenv("SONILO_API_KEY", API_KEY)
    # Keep tests hermetic: never shell out to ffprobe.
    monkeypatch.setattr(SoniloMusic, "_probe_duration", staticmethod(lambda path: None))
    return SoniloMusic()


class TestSoniloMusicDefinition:
    """Verify the tool class metadata matches project conventions."""

    def test_class_inherits_basetool(self):
        assert issubclass(SoniloMusic, BaseTool)

    def test_name(self):
        assert SoniloMusic.name == "sonilo_music"

    def test_tier(self):
        assert SoniloMusic.tier == ToolTier.GENERATE

    def test_capability(self):
        assert SoniloMusic.capability == "music_generation"

    def test_provider(self):
        assert SoniloMusic.provider == "sonilo"

    def test_runtime(self):
        assert SoniloMusic.runtime == ToolRuntime.API

    def test_execution_mode(self):
        assert SoniloMusic.execution_mode == ExecutionMode.SYNC

    def test_capabilities_list(self):
        assert "generate_background_music" in SoniloMusic.capabilities
        assert "generate_music_from_video" in SoniloMusic.capabilities

    def test_fallback_tools(self):
        assert "music_gen" in SoniloMusic.fallback_tools
        assert "pixabay_music" in SoniloMusic.fallback_tools
        assert "freesound_music" in SoniloMusic.fallback_tools

    def test_supports(self):
        assert SoniloMusic.supports["video_conditioning"] is True
        assert SoniloMusic.supports["native_duration_match"] is True

    def test_input_schema_fields(self):
        props = SoniloMusic.input_schema["properties"]
        assert "video_path" in props
        assert "video_url" in props
        assert "prompt" in props
        assert "output_path" in props

    def test_no_retries_on_generation(self):
        # Generation is non-idempotent — retries could double-charge.
        assert SoniloMusic.retry_policy.max_retries == 0

    def test_no_env_dependency_declared(self):
        # Availability is reported via get_status(), like music_gen/suno_music.
        assert SoniloMusic.dependencies == []


class TestSoniloMusicStatus:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("SONILO_API_KEY", raising=False)
        assert SoniloMusic().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("SONILO_API_KEY", API_KEY)
        assert SoniloMusic().get_status() == ToolStatus.AVAILABLE

    def test_execute_inert_without_key(self, monkeypatch):
        monkeypatch.delenv("SONILO_API_KEY", raising=False)
        result = SoniloMusic().execute({"video_url": "https://example.com/cut.mp4"})
        assert result.success is False
        assert "SONILO_API_KEY" in result.error

    def test_dry_run_returns_dict(self, tool):
        result = tool.dry_run({"video_url": "https://example.com/cut.mp4"})
        assert result["tool"] == "sonilo_music"
        assert result["would_execute"] is True


class TestSoniloMusicValidation:
    def test_rejects_both_inputs(self, tool):
        result = tool.execute(
            {"video_path": "cut.mp4", "video_url": "https://example.com/cut.mp4"}
        )
        assert result.success is False
        assert "exactly one" in result.error

    def test_rejects_neither_input(self, tool):
        result = tool.execute({})
        assert result.success is False
        assert "exactly one" in result.error

    def test_rejects_non_http_url(self, tool):
        result = tool.execute({"video_url": "file:///etc/passwd"})
        assert result.success is False
        assert "http" in result.error

    def test_rejects_missing_local_file(self, tool, tmp_path):
        result = tool.execute({"video_path": str(tmp_path / "missing.mp4")})
        assert result.success is False
        assert "not found" in result.error

    def test_rejects_video_over_duration_limit(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SONILO_API_KEY", API_KEY)
        monkeypatch.setattr(
            SoniloMusic, "_probe_duration", staticmethod(lambda path: 400.0)
        )
        video = tmp_path / "long.mp4"
        video.write_bytes(b"fake video")
        result = SoniloMusic().execute({"video_path": str(video)})
        assert result.success is False
        assert "6 minutes" in result.error


class TestSoniloMusicGenerate:
    def test_url_mode_request_shape(self, tool, monkeypatch, tmp_path):
        captured: dict = {}
        _install_fake_requests(monkeypatch, captured, _FakeStreamResponse(_HAPPY_LINES))
        out = tmp_path / "track.m4a"
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "prompt": "warm analog synths",
                "output_path": str(out),
            }
        )

        assert result.success is True
        assert captured["url"] == "https://api.sonilo.com/v1/video-to-music"
        assert captured["headers"]["Authorization"] == f"Bearer {API_KEY}"
        assert captured["data"]["video_url"] == "https://example.com/cut.mp4"
        assert captured["data"]["prompt"] == "warm analog synths"
        assert captured["files"] is None
        assert captured["stream"] is True

    def test_file_mode_uploads_multipart(self, tool, monkeypatch, tmp_path):
        captured: dict = {}
        _install_fake_requests(monkeypatch, captured, _FakeStreamResponse(_HAPPY_LINES))
        video = tmp_path / "final_cut.mp4"
        video.write_bytes(b"fake video bytes")
        out = tmp_path / "track.m4a"
        result = tool.execute({"video_path": str(video), "output_path": str(out)})

        assert result.success is True
        name, _fh, mime = captured["files"]["video"]
        assert name == "final_cut.mp4"
        assert mime == "video/mp4"
        # No prompt given — no stray form fields.
        assert captured["data"] is None

    def test_audio_chunks_are_concatenated(self, tool, monkeypatch, tmp_path):
        captured: dict = {}
        _install_fake_requests(monkeypatch, captured, _FakeStreamResponse(_HAPPY_LINES))
        out = tmp_path / "track.m4a"
        result = tool.execute(
            {"video_url": "https://example.com/cut.mp4", "output_path": str(out)}
        )

        assert result.success is True
        assert out.read_bytes() == b"abcdef"
        assert result.artifacts == [str(out)]
        assert result.data["title"] == "Rainy Commute"
        assert result.data["format"] == "m4a"
        assert result.data["provider"] == "sonilo"

    def test_lowest_stream_index_is_returned(self, tool, monkeypatch, tmp_path):
        lines = [_chunk(b"second", 1), _chunk(b"first", 0), '{"type": "complete"}']
        _install_fake_requests(monkeypatch, {}, _FakeStreamResponse(lines))
        out = tmp_path / "track.m4a"
        result = tool.execute(
            {"video_url": "https://example.com/cut.mp4", "output_path": str(out)}
        )
        assert result.success is True
        assert out.read_bytes() == b"first"

    def test_error_event_fails(self, tool, monkeypatch, tmp_path):
        lines = [_chunk(b"abc"), '{"type": "error", "message": "generation failed"}']
        _install_fake_requests(monkeypatch, {}, _FakeStreamResponse(lines))
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert result.success is False
        assert "generation failed" in result.error

    def test_stream_without_complete_fails(self, tool, monkeypatch, tmp_path):
        lines = [_chunk(b"abc")]
        _install_fake_requests(monkeypatch, {}, _FakeStreamResponse(lines))
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert result.success is False
        assert "before completing" in result.error

    def test_http_401_reports_rejected_key(self, tool, monkeypatch, tmp_path):
        response = _FakeStreamResponse(
            status_code=401, text='{"detail": "invalid key"}'
        )
        _install_fake_requests(monkeypatch, {}, response)
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert result.success is False
        assert "rejected" in result.error

    def test_http_402_reports_credits(self, tool, monkeypatch, tmp_path):
        response = _FakeStreamResponse(
            status_code=402, text='{"detail": "no credits left"}'
        )
        _install_fake_requests(monkeypatch, {}, response)
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert result.success is False
        assert "no credits left" in result.error

    def test_api_key_never_leaks_into_result(self, tool, monkeypatch, tmp_path):
        response = _FakeStreamResponse(status_code=401, text='{"detail": "bad"}')
        _install_fake_requests(monkeypatch, {}, response)
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert API_KEY not in (result.error or "")
        assert API_KEY not in json.dumps(result.data)

    def test_cost_and_model_are_reported(self, tool, monkeypatch, tmp_path):
        _install_fake_requests(monkeypatch, {}, _FakeStreamResponse(_HAPPY_LINES))
        result = tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert result.success is True
        assert result.cost_usd == tool.estimate_cost({})
        assert result.model == "video-to-music"

    def test_base_url_override(self, tool, monkeypatch, tmp_path):
        monkeypatch.setenv("SONILO_API_URL", "https://staging.sonilo.test/")
        captured: dict = {}
        _install_fake_requests(monkeypatch, captured, _FakeStreamResponse(_HAPPY_LINES))
        tool.execute(
            {
                "video_url": "https://example.com/cut.mp4",
                "output_path": str(tmp_path / "track.m4a"),
            }
        )
        assert captured["url"] == "https://staging.sonilo.test/v1/video-to-music"


class TestSoniloMusicRegistry:
    """Verify the tool is discoverable via the registry."""

    def test_registry_registers_tool(self):
        reg = ToolRegistry()
        reg.register(SoniloMusic())
        found = reg.get("sonilo_music")
        assert found is not None
        assert found.name == "sonilo_music"

    def test_registry_finds_by_capability(self):
        reg = ToolRegistry()
        reg.register(SoniloMusic())
        matches = reg.get_by_capability("music_generation")
        assert any(t.name == "sonilo_music" for t in matches)

    def test_registry_discovers_tool(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("sonilo_music") is not None
