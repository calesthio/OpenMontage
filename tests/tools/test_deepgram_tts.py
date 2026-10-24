"""Focused tests for the Deepgram Aura TTS tool.

No live API calls: the network layer is monkeypatched. Covers the tool
contract, registry discovery, status behavior, voice/param resolution,
selector routing, and execute() guardrails.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.audio.deepgram_tts import DeepgramTTS


FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 64


class _FakeResponse:
    def __init__(self, content=FAKE_MP3, status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text


@pytest.fixture
def deepgram_env(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")


def _capture_post(monkeypatch, response=None):
    import requests

    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured.update(url=url, params=params, headers=headers, json=json)
        return response or _FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    return captured


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(DeepgramTTS, BaseTool)

    def test_identity(self):
        t = DeepgramTTS()
        assert t.name == "deepgram_tts"
        assert t.capability == "tts"
        assert t.provider == "deepgram"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.VOICE
        assert t.fallback == "piper_tts"
        assert "deepgram-text-to-speech" in t.agent_skills
        assert len(t.capabilities) > 0

    def test_get_info_valid(self):
        info = DeepgramTTS().get_info()
        assert info["name"] == "deepgram_tts"
        assert info["capability"] == "tts"
        assert "text" in info["input_schema"]["properties"]

    def test_estimate_cost_by_characters(self):
        t = DeepgramTTS()
        # Aura-2 pay-as-you-go ≈ $0.030 per 1k characters.
        assert t.estimate_cost({"text": "x" * 1_000}) == pytest.approx(0.03)
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("deepgram_tts") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("tts")]
        assert "deepgram_tts" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_env(self, monkeypatch):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        assert DeepgramTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, deepgram_env):
        assert DeepgramTTS().get_status() == ToolStatus.AVAILABLE


# ---- Voice + request params (the risky logic) ----

class TestParams:
    def test_voice_alias_resolution(self):
        t = DeepgramTTS()
        assert t._resolve_voice({"voice": "antonia"}) == "aura-2-antonia-es"
        assert t._resolve_voice({"voice": "ANTONIA"}) == "aura-2-antonia-es"
        assert t._resolve_voice({"voice": "aura-2-luna-en"}) == "aura-2-luna-en"
        assert t._resolve_voice({"voice_id": "selena"}) == "aura-2-selena-es"
        assert t._resolve_voice({}) == DeepgramTTS.DEFAULT_VOICE

    def test_mp3_params_default(self):
        params = DeepgramTTS()._build_params({"text": "hola", "voice": "antonia"})
        assert params == {"model": "aura-2-antonia-es", "encoding": "mp3"}

    def test_wav_params(self):
        params = DeepgramTTS()._build_params({"text": "hola", "output_format": "wav"})
        assert params["encoding"] == "linear16"
        assert params["container"] == "wav"
        assert params["sample_rate"] == 48000

    def test_selector_style_format_normalized(self):
        t = DeepgramTTS()
        assert t._resolve_container({"output_format": "mp3_44100_128"}) == "mp3"
        assert t._resolve_container({"output_format": "pcm_24000"}) == "wav"

    def test_speed_clamped_and_aliased(self):
        t = DeepgramTTS()
        assert t._build_params({"text": "x", "speed": 0.9})["speed"] == 0.9
        assert t._build_params({"text": "x", "speaking_rate": 3})["speed"] == 1.5
        assert t._build_params({"text": "x", "speed": 0.1})["speed"] == 0.7
        assert "speed" not in t._build_params({"text": "x", "speed": 1.0})


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        res = DeepgramTTS().execute({"text": "hola"})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_success_path_mocked(self, deepgram_env, tmp_path, monkeypatch):
        captured = _capture_post(monkeypatch)
        out = tmp_path / "seg.mp3"

        res = DeepgramTTS().execute(
            {"text": "Hola mundo", "voice": "antonia", "output_path": str(out)}
        )

        assert res.success
        assert res.model == "deepgram-aura:aura-2-antonia-es"
        assert res.data["provider"] == "deepgram"
        assert res.data["voice"] == "aura-2-antonia-es"
        assert res.data["format"] == "mp3"
        assert res.cost_usd == pytest.approx(round(10 * 0.030 / 1_000, 4))
        assert out.read_bytes() == FAKE_MP3
        assert res.artifacts == [str(out)]
        assert captured["url"] == "https://api.deepgram.com/v1/speak"
        assert captured["headers"]["Authorization"] == "Token fake-key"
        assert captured["json"] == {"text": "Hola mundo"}
        assert captured["params"]["model"] == "aura-2-antonia-es"

    def test_selector_routes_shared_controls(self, deepgram_env, tmp_path, monkeypatch):
        from tools.audio.tts_selector import TTSSelector

        captured = _capture_post(monkeypatch)
        monkeypatch.setattr(TTSSelector, "_providers", lambda self: [DeepgramTTS()])

        result = TTSSelector().execute(
            {
                "text": "Narración desde el selector",
                "preferred_provider": "deepgram",
                "voice_id": "antonia",
                "speaking_rate": 0.9,
                "style": 0.8,
                "output_format": "mp3_44100_128",
                "output_path": str(tmp_path / "selector.mp3"),
            }
        )

        assert result.success
        assert result.data["selected_tool"] == "deepgram_tts"
        assert captured["params"]["model"] == "aura-2-antonia-es"
        assert captured["params"]["speed"] == 0.9
        assert captured["params"]["encoding"] == "mp3"

    def test_http_error_surfaced(self, deepgram_env, tmp_path, monkeypatch):
        _capture_post(monkeypatch, _FakeResponse(content=b"", status_code=401, text="INVALID_AUTH"))
        res = DeepgramTTS().execute({"text": "hola", "output_path": str(tmp_path / "x.mp3")})
        assert not res.success
        assert "401" in res.error
        assert "INVALID_AUTH" in res.error
        assert res.cost_usd is None or res.cost_usd == 0

    def test_request_exception_surfaced(self, deepgram_env, tmp_path, monkeypatch):
        import requests

        def boom(*args, **kwargs):
            raise requests.ConnectionError("network down")

        monkeypatch.setattr(requests, "post", boom)
        res = DeepgramTTS().execute({"text": "hola", "output_path": str(tmp_path / "x.mp3")})
        assert not res.success
        assert "network down" in res.error
