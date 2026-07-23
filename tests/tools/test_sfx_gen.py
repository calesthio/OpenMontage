"""Focused tests for the ElevenLabs sound-effect generation tool.

No live API calls: the network layer is monkeypatched. Covers the tool
contract, registry discovery, status gating, payload construction, and
execute() guardrails.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.audio.sfx_gen import SfxGen
from tools.audio.music_gen import MusicGen


FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 32


class _FakeResponse:
    def __init__(self, content=FAKE_MP3, status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text


@pytest.fixture
def eleven_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(SfxGen, BaseTool)

    def test_identity(self):
        t = SfxGen()
        assert t.name == "sfx_gen"
        assert t.capability == "sfx_generation"
        assert t.provider == "elevenlabs"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.GENERATE
        assert "sound-effects" in t.agent_skills
        assert "generate_sfx" in t.capabilities

    def test_music_gen_no_longer_claims_sfx(self):
        """generate_sfx moved here — music_gen must not double-claim it."""
        assert "generate_sfx" not in MusicGen.capabilities

    def test_cost_is_flat_per_effect(self):
        assert SfxGen().estimate_cost({"prompt": "tick"}) == pytest.approx(0.03)


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("sfx_gen") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("sfx_generation")]
        assert names == ["sfx_gen"]


# ---- Status ----

class TestStatus:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        assert SfxGen().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, eleven_env):
        assert SfxGen().get_status() == ToolStatus.AVAILABLE


# ---- execute() ----

class TestExecute:
    def test_missing_key(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        res = SfxGen().execute({"prompt": "soft glass tick"})
        assert not res.success
        assert "API key" in res.error

    def test_success_path_mocked(self, eleven_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return _FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)

        out = tmp_path / "sfx" / "tick.mp3"
        res = SfxGen().execute({
            "prompt": "single soft glass tick, short",
            "duration_seconds": 0.5,
            "prompt_influence": 0.6,
            "output_path": str(out),
        })

        assert res.success
        assert res.model == "elevenlabs-sound-generation"
        assert res.cost_usd == pytest.approx(0.03)
        assert out.read_bytes() == FAKE_MP3
        assert res.artifacts == [str(out)]
        assert captured["url"] == "https://api.elevenlabs.io/v1/sound-generation"
        assert captured["headers"]["xi-api-key"] == "fake-key"
        assert captured["payload"] == {
            "text": "single soft glass tick, short",
            "prompt_influence": 0.6,
            "duration_seconds": 0.5,
        }

    def test_loop_and_auto_duration(self, eleven_env, tmp_path, monkeypatch):
        import requests

        captured = {}
        monkeypatch.setattr(
            requests, "post",
            lambda url, headers=None, json=None, timeout=None: (
                captured.update(payload=json), _FakeResponse())[1],
        )
        res = SfxGen().execute({
            "prompt": "airy ambient hum",
            "loop": True,
            "output_path": str(tmp_path / "hum.mp3"),
        })
        assert res.success
        # no duration key when omitted (API auto-calculates); loop passed through
        assert "duration_seconds" not in captured["payload"]
        assert captured["payload"]["loop"] is True

    def test_http_error_surfaced(self, eleven_env, tmp_path, monkeypatch):
        import requests

        monkeypatch.setattr(
            requests, "post",
            lambda *a, **k: _FakeResponse(content=b"", status_code=422,
                                          text="duration out of range"),
        )
        res = SfxGen().execute(
            {"prompt": "tick", "output_path": str(tmp_path / "x.mp3")}
        )
        assert not res.success
        assert "422" in res.error
        assert "duration out of range" in res.error

    def test_request_exception_surfaced(self, eleven_env, tmp_path, monkeypatch):
        import requests

        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("no route to host")

        monkeypatch.setattr(requests, "post", boom)
        res = SfxGen().execute(
            {"prompt": "tick", "output_path": str(tmp_path / "x.mp3")}
        )
        assert not res.success
        assert "no route to host" in res.error
