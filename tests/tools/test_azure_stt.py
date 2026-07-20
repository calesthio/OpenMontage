"""Focused tests for the Azure AI Speech (Fast Transcription) STT tool.

No live API calls: the network layer is monkeypatched. Covers the tool
contract, registry discovery, status behavior, the response→transcript
mapping, execute() guardrails, and downstream subtitle compatibility.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.analysis.azure_stt import AzureSpeechToText
from tools.subtitle.subtitle_gen import SubtitleGen


# A representative Fast Transcription response payload.
SAMPLE_PAYLOAD = {
    "durationMilliseconds": 2400,
    "combinedPhrases": [{"text": "Hello world this is a test"}],
    "phrases": [
        {
            "offsetMilliseconds": 0,
            "durationMilliseconds": 1200,
            "text": "Hello world",
            "locale": "en-US",
            "confidence": 0.97,
            "speaker": 1,
            "words": [
                {"text": "Hello", "offsetMilliseconds": 0, "durationMilliseconds": 500},
                {"text": "world", "offsetMilliseconds": 500, "durationMilliseconds": 700},
            ],
        },
        {
            "offsetMilliseconds": 1200,
            "durationMilliseconds": 1200,
            "text": "this is a test",
            "locale": "en-US",
            "confidence": 0.95,
            "words": [
                {"text": "this", "offsetMilliseconds": 1200, "durationMilliseconds": 300},
                {"text": "is", "offsetMilliseconds": 1500, "durationMilliseconds": 200},
                {"text": "a", "offsetMilliseconds": 1700, "durationMilliseconds": 200},
                {"text": "test", "offsetMilliseconds": 1900, "durationMilliseconds": 500},
            ],
        },
    ],
}


class _FakeResponse:
    def __init__(self, payload, status_code=200, text="ok"):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(AzureSpeechToText, BaseTool)

    def test_identity(self):
        t = AzureSpeechToText()
        assert t.name == "azure_stt"
        assert t.capability == "analysis"
        assert t.provider == "azure"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.CORE
        assert t.fallback == "transcriber"
        assert "azure-speech-to-text" in t.agent_skills
        assert len(t.capabilities) > 0

    def test_get_info_valid(self):
        info = AzureSpeechToText().get_info()
        assert info["name"] == "azure_stt"
        assert info["capability"] == "analysis"
        assert "input_path" in info["input_schema"]["properties"]

    def test_estimate_cost_by_duration(self):
        t = AzureSpeechToText()
        assert t.estimate_cost({"duration_seconds": 3600}) == pytest.approx(1.0)
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("azure_stt") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("analysis")]
        assert "azure_stt" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_env(self, monkeypatch):
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
        assert AzureSpeechToText().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key_and_region(self, azure_env):
        assert AzureSpeechToText().get_status() == ToolStatus.AVAILABLE

    def test_available_with_key_and_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://custom.example.com")
        assert AzureSpeechToText().get_status() == ToolStatus.AVAILABLE

    def test_key_alone_is_not_enough(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
        assert AzureSpeechToText().get_status() == ToolStatus.UNAVAILABLE


# ---- Response → transcript mapping (the risky logic) ----

class TestParsePayload:
    def test_maps_segments_words_and_timestamps(self):
        data = AzureSpeechToText._parse_payload(SAMPLE_PAYLOAD, ["en-US"])
        assert data["language"] == "en-US"
        assert data["duration_seconds"] == 2.4
        assert len(data["segments"]) == 2

        seg0 = data["segments"][0]
        assert seg0["text"] == "Hello world"
        assert seg0["start"] == 0.0 and seg0["end"] == 1.2
        assert seg0["speaker"] == 1
        # ms → seconds conversion on words
        assert seg0["words"][0] == {
            "word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.97,
        }
        # flat word stream aggregates every phrase
        assert len(data["word_timestamps"]) == 6

    def test_locale_resolution(self):
        r = AzureSpeechToText._resolve_locales
        assert r({"language": "en"}) == ["en-US"]        # ISO → default locale
        assert r({"language": "en-GB"}) == ["en-GB"]     # explicit locale kept
        assert r({"candidate_locales": ["fr-FR"]}) == ["fr-FR"]
        assert len(r({})) > 1                             # falls back to a shortlist

    def test_duration_falls_back_to_last_segment(self):
        payload = {k: v for k, v in SAMPLE_PAYLOAD.items() if k != "durationMilliseconds"}
        data = AzureSpeechToText._parse_payload(payload, ["en-US"])
        assert data["duration_seconds"] == pytest.approx(2.4)

    def test_output_feeds_subtitle_gen(self, tmp_path):
        """Parsed segments must be a drop-in for the subtitle generator."""
        data = AzureSpeechToText._parse_payload(SAMPLE_PAYLOAD, ["en-US"])
        out = tmp_path / "captions.srt"
        res = SubtitleGen().execute(
            {"segments": data["segments"], "format": "srt", "output_path": str(out)}
        )
        assert res.success
        assert out.exists()
        assert "Hello world" in out.read_text()


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_file(self, azure_env, tmp_path):
        res = AzureSpeechToText().execute({"input_path": str(tmp_path / "nope.wav")})
        assert not res.success
        assert "not found" in res.error.lower()

    def test_missing_credentials(self, monkeypatch, tmp_path):
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = AzureSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_success_path_mocked(self, azure_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, headers=None, files=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            return _FakeResponse(SAMPLE_PAYLOAD)

        monkeypatch.setattr(requests, "post", fake_post)

        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = AzureSpeechToText().execute(
            {"input_path": str(audio), "language": "en", "output_dir": str(tmp_path)}
        )

        assert res.success
        assert res.model == "azure-fast-transcription"
        assert res.cost_usd == pytest.approx(0.0007, abs=1e-4)  # 2.4s at $1/hr
        assert res.data["provider"] == "azure"
        assert len(res.data["segments"]) == 2
        # transcript JSON artifact was written
        assert res.artifacts and Path(res.artifacts[0]).exists()
        # correct endpoint + auth header used
        assert "transcriptions:transcribe" in captured["url"]
        assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "fake-key"

    def test_http_error_surfaced(self, azure_env, tmp_path, monkeypatch):
        import requests

        monkeypatch.setattr(
            requests, "post",
            lambda *a, **k: _FakeResponse(None, status_code=401, text="Unauthorized"),
        )
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = AzureSpeechToText().execute({"input_path": str(audio), "output_dir": str(tmp_path)})
        assert not res.success
        assert "401" in res.error
