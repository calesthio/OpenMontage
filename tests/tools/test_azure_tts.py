"""Focused tests for the Azure AI Speech neural TTS tool.

No live API calls: the network layer is monkeypatched. Covers the tool
contract, registry discovery, status behavior, voice resolution, SSML
construction, and execute() guardrails.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.audio.azure_tts import AzureTTS


FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 64


class _FakeResponse:
    def __init__(self, content=FAKE_MP3, status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text


@pytest.fixture
def azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.delenv("AZURE_TTS_ENDPOINT", raising=False)


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(AzureTTS, BaseTool)

    def test_identity(self):
        t = AzureTTS()
        assert t.name == "azure_tts"
        assert t.capability == "tts"
        assert t.provider == "azure"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.VOICE
        assert t.fallback == "piper_tts"
        assert "azure-text-to-speech" in t.agent_skills
        assert len(t.capabilities) > 0

    def test_get_info_valid(self):
        info = AzureTTS().get_info()
        assert info["name"] == "azure_tts"
        assert info["capability"] == "tts"
        assert "text" in info["input_schema"]["properties"]

    def test_estimate_cost_by_characters(self):
        t = AzureTTS()
        # Standard tier ≈ $16 per 1M characters.
        assert t.estimate_cost({"text": "x" * 1_000_000}) == pytest.approx(16.0)
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("azure_tts") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("tts")]
        assert "azure_tts" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_env(self, monkeypatch):
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.delenv("AZURE_TTS_ENDPOINT", raising=False)
        assert AzureTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key_and_region(self, azure_env):
        assert AzureTTS().get_status() == ToolStatus.AVAILABLE

    def test_available_with_key_and_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.setenv("AZURE_TTS_ENDPOINT", "https://custom.tts.example.com")
        assert AzureTTS().get_status() == ToolStatus.AVAILABLE

    def test_key_alone_is_not_enough(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.delenv("AZURE_TTS_ENDPOINT", raising=False)
        assert AzureTTS().get_status() == ToolStatus.UNAVAILABLE


# ---- Voice resolution + SSML construction (the risky logic) ----

class TestSSML:
    def test_voice_alias_resolution(self):
        t = AzureTTS()
        assert t._resolve_voice({"voice": "andrew"}) == "en-US-AndrewMultilingualNeural"
        assert t._resolve_voice({"voice": "JENNY"}) == "en-US-JennyNeural"
        # full short names pass through untouched
        assert t._resolve_voice({"voice": "de-DE-KatjaNeural"}) == "de-DE-KatjaNeural"
        # default when omitted or blank
        assert t._resolve_voice({}) == AzureTTS.DEFAULT_VOICE
        assert t._resolve_voice({"voice": "  "}) == AzureTTS.DEFAULT_VOICE

    def test_ssml_prosody_and_voice(self):
        t = AzureTTS()
        ssml = t._build_ssml(
            {"text": "Hello world", "rate": "-8%", "pitch": "+1st"},
            "en-US-AndrewMultilingualNeural",
        )
        assert '<voice name="en-US-AndrewMultilingualNeural">' in ssml
        assert '<prosody rate="-8%" pitch="+1st">Hello world</prosody>' in ssml
        assert 'xml:lang="en-US"' in ssml
        assert "<mstts:express-as" not in ssml  # no style requested

    def test_ssml_style_wrapping(self):
        t = AzureTTS()
        ssml = t._build_ssml(
            {"text": "Hi", "style": "narration-professional"}, "en-US-JennyNeural"
        )
        assert '<mstts:express-as style="narration-professional">' in ssml
        assert "</mstts:express-as>" in ssml

    def test_ssml_escapes_xml(self):
        t = AzureTTS()
        ssml = t._build_ssml({"text": "Bread & <butter>"}, "en-US-GuyNeural")
        assert "Bread &amp; &lt;butter&gt;" in ssml
        assert "<butter>" not in ssml

    def test_ssml_custom_locale(self):
        t = AzureTTS()
        ssml = t._build_ssml({"text": "Hallo", "locale": "de-DE"}, "de-DE-KatjaNeural")
        assert 'xml:lang="de-DE"' in ssml

    def test_host_prefers_explicit_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_TTS_ENDPOINT", "https://custom.tts.example.com/")
        assert AzureTTS()._host() == "https://custom.tts.example.com"
        monkeypatch.delenv("AZURE_TTS_ENDPOINT")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
        assert AzureTTS()._host() == "https://westeurope.tts.speech.microsoft.com"


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.delenv("AZURE_TTS_ENDPOINT", raising=False)
        res = AzureTTS().execute({"text": "hello"})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_success_path_mocked(self, azure_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = data
            return _FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)

        out = tmp_path / "narration.mp3"
        res = AzureTTS().execute(
            {"text": "Hello world", "voice": "andrew", "output_path": str(out)}
        )

        assert res.success
        assert res.model == "azure-neural-tts:en-US-AndrewMultilingualNeural"
        assert res.data["provider"] == "azure"
        assert res.data["voice"] == "en-US-AndrewMultilingualNeural"
        assert res.data["text_length"] == len("Hello world")
        # cost is rounded to 4 decimals by estimate_cost
        assert res.cost_usd == pytest.approx(round(11 * 16.0 / 1_000_000, 4))
        # audio bytes written to the requested path
        assert out.read_bytes() == FAKE_MP3
        assert res.artifacts == [str(out)]
        # correct endpoint, auth header, and output format used
        assert captured["url"] == "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
        assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "fake-key"
        assert captured["headers"]["X-Microsoft-OutputFormat"] == "audio-48khz-192kbitrate-mono-mp3"
        assert b"Hello world" in captured["body"]

    def test_wav_output_format(self, azure_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["headers"] = headers
            return _FakeResponse(content=b"RIFF....")

        monkeypatch.setattr(requests, "post", fake_post)

        out = tmp_path / "narration.wav"
        res = AzureTTS().execute(
            {"text": "Hi", "output_format": "wav", "output_path": str(out)}
        )
        assert res.success
        assert captured["headers"]["X-Microsoft-OutputFormat"] == "riff-48khz-16bit-mono-pcm"
        assert out.exists()

    def test_http_error_surfaced(self, azure_env, tmp_path, monkeypatch):
        import requests

        monkeypatch.setattr(
            requests, "post",
            lambda *a, **k: _FakeResponse(content=b"", status_code=401, text="Unauthorized"),
        )
        res = AzureTTS().execute(
            {"text": "hello", "output_path": str(tmp_path / "x.mp3")}
        )
        assert not res.success
        assert "401" in res.error

    def test_request_exception_surfaced(self, azure_env, tmp_path, monkeypatch):
        import requests

        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("no route to host")

        monkeypatch.setattr(requests, "post", boom)
        res = AzureTTS().execute(
            {"text": "hello", "output_path": str(tmp_path / "x.mp3")}
        )
        assert not res.success
        assert "no route to host" in res.error
