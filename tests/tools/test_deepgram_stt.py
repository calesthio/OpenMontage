"""Focused tests for the Deepgram (pre-recorded /v1/listen) STT tool.

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
from tools.analysis.deepgram_stt import DeepgramSpeechToText
from tools.subtitle.subtitle_gen import SubtitleGen


def _w(word, start, end, punct=None, conf=0.9, speaker=None):
    entry = {"word": word, "start": start, "end": end, "confidence": conf}
    if punct:
        entry["punctuated_word"] = punct
    if speaker is not None:
        entry["speaker"] = speaker
    return entry


# A representative /v1/listen response with utterances=true.
SAMPLE_PAYLOAD = {
    "metadata": {"duration": 2.6, "channels": 1},
    "results": {
        "channels": [
            {
                "detected_language": "es",
                "alternatives": [
                    {
                        "transcript": "Hola mundo. Esto es una prueba.",
                        "confidence": 0.97,
                        "words": [
                            _w("hola", 0.0, 0.4, "Hola"),
                            _w("mundo", 0.4, 1.0, "mundo."),
                            _w("esto", 1.3, 1.6, "Esto"),
                            _w("es", 1.6, 1.8),
                            _w("una", 1.8, 2.0),
                            _w("prueba", 2.0, 2.5, "prueba."),
                        ],
                    }
                ],
            }
        ],
        "utterances": [
            {
                "start": 0.0,
                "end": 1.0,
                "transcript": "Hola mundo.",
                "speaker": 0,
                "words": [_w("hola", 0.0, 0.4, "Hola"), _w("mundo", 0.4, 1.0, "mundo.")],
            },
            {
                "start": 1.3,
                "end": 2.5,
                "transcript": "Esto es una prueba.",
                "words": [
                    _w("esto", 1.3, 1.6, "Esto"),
                    _w("es", 1.6, 1.8),
                    _w("una", 1.8, 2.0),
                    _w("prueba", 2.0, 2.5, "prueba."),
                ],
            },
        ],
    },
}


class _FakeResponse:
    def __init__(self, payload, status_code=200, text="ok"):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def deepgram_env(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(DeepgramSpeechToText, BaseTool)

    def test_identity(self):
        t = DeepgramSpeechToText()
        assert t.name == "deepgram_stt"
        assert t.capability == "analysis"
        assert t.provider == "deepgram"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.CORE
        assert t.fallback == "transcriber"
        assert "deepgram-speech-to-text" in t.agent_skills
        assert "word_timestamps" in t.capabilities

    def test_get_info_valid(self):
        info = DeepgramSpeechToText().get_info()
        assert info["name"] == "deepgram_stt"
        assert "input_path" in info["input_schema"]["properties"]

    def test_estimate_cost_by_duration(self):
        t = DeepgramSpeechToText()
        # Nova-3: $0.0048/min monolingual, $0.0058/min multilingual.
        assert t.estimate_cost({"duration_seconds": 600}) == pytest.approx(0.048)
        assert t.estimate_cost(
            {"duration_seconds": 600, "language": "multi"}
        ) == pytest.approx(0.058)
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("deepgram_stt") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("analysis")]
        assert "deepgram_stt" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_env(self, monkeypatch):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        assert DeepgramSpeechToText().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, deepgram_env):
        assert DeepgramSpeechToText().get_status() == ToolStatus.AVAILABLE


# ---- Request params ----

class TestParams:
    def test_language_pinned(self):
        params = dict(DeepgramSpeechToText._build_params({"language": "es"}))
        assert params["model"] == "nova-3"
        assert params["language"] == "es"
        assert params["smart_format"] == "true"
        assert params["utterances"] == "true"
        assert "detect_language" not in params

    def test_auto_detect_when_no_language(self):
        params = dict(DeepgramSpeechToText._build_params({}))
        assert params["detect_language"] == "true"
        assert "language" not in params

    def test_diarize_and_keyterms(self):
        params = DeepgramSpeechToText._build_params(
            {"diarize": True, "keyterms": ["Saporito", "Dunken"]}
        )
        assert ("diarize_model", "latest") in params
        assert ("keyterm", "Saporito") in params
        assert ("keyterm", "Dunken") in params


# ---- Response → transcript mapping (the risky logic) ----

class TestParsePayload:
    def test_maps_utterances_words_and_timestamps(self):
        data = DeepgramSpeechToText._parse_payload(SAMPLE_PAYLOAD, None)
        assert data["language"] == "es"
        assert data["duration_seconds"] == 2.6
        assert len(data["segments"]) == 2

        seg0 = data["segments"][0]
        assert seg0["text"] == "Hola mundo."
        assert seg0["start"] == 0.0 and seg0["end"] == 1.0
        assert seg0["speaker"] == 0
        # smart-formatted word preferred over the raw lowercase token
        assert seg0["words"][0] == {
            "word": "Hola", "start": 0.0, "end": 0.4, "probability": 0.9,
        }
        assert seg0["words"][1]["word"] == "mundo."
        assert len(data["word_timestamps"]) == 6

    def test_falls_back_to_alternative_without_utterances(self):
        payload = {
            "metadata": {"duration": 2.6},
            "results": {"channels": SAMPLE_PAYLOAD["results"]["channels"]},
        }
        data = DeepgramSpeechToText._parse_payload(payload, "es")
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Hola mundo. Esto es una prueba."
        assert data["segments"][0]["end"] == 2.5
        assert len(data["word_timestamps"]) == 6

    def test_duration_falls_back_to_last_segment(self):
        payload = {"results": SAMPLE_PAYLOAD["results"]}
        data = DeepgramSpeechToText._parse_payload(payload, "es")
        assert data["duration_seconds"] == pytest.approx(2.5)

    def test_requested_language_used_when_not_detected(self):
        payload = {
            "metadata": {"duration": 1.0},
            "results": {"channels": [{"alternatives": [{"transcript": "", "words": []}]}]},
        }
        data = DeepgramSpeechToText._parse_payload(payload, "es-419")
        assert data["language"] == "es-419"
        assert data["segments"] == []

    def test_output_feeds_subtitle_gen(self, tmp_path):
        """Parsed segments must be a drop-in for the subtitle generator."""
        data = DeepgramSpeechToText._parse_payload(SAMPLE_PAYLOAD, None)
        out = tmp_path / "captions.srt"
        res = SubtitleGen().execute(
            {"segments": data["segments"], "format": "srt", "output_path": str(out)}
        )
        assert res.success
        assert out.exists()
        assert "Hola mundo." in out.read_text(encoding="utf-8")


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_file(self, deepgram_env, tmp_path):
        res = DeepgramSpeechToText().execute({"input_path": str(tmp_path / "nope.wav")})
        assert not res.success
        assert "not found" in res.error.lower()

    def test_missing_credentials(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = DeepgramSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_success_path_mocked(self, deepgram_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, params=None, headers=None, data=None, timeout=None):
            captured.update(url=url, params=params, headers=headers, body=data.read())
            return _FakeResponse(SAMPLE_PAYLOAD)

        monkeypatch.setattr(requests, "post", fake_post)
        audio = tmp_path / "clip.wav"
        audio.write_bytes(b"RIFF....")

        res = DeepgramSpeechToText().execute(
            {"input_path": str(audio), "language": "es", "output_dir": str(tmp_path / "out")}
        )

        assert res.success
        assert res.model == "deepgram-nova-3"
        assert res.data["provider"] == "deepgram"
        assert res.cost_usd == pytest.approx(round(2.6 / 60 * 0.0048, 4))
        transcript = Path(res.artifacts[0])
        assert transcript.name == "clip_transcript.json"
        assert "Hola mundo." in transcript.read_text(encoding="utf-8")
        assert captured["url"] == "https://api.deepgram.com/v1/listen"
        assert captured["headers"]["Authorization"] == "Token fake-key"
        assert captured["headers"]["Content-Type"] == "audio/x-wav" or captured["headers"][
            "Content-Type"
        ].startswith("audio/")
        assert captured["body"] == b"RIFF...."
        assert ("language", "es") in captured["params"]

    def test_http_error_surfaced(self, deepgram_env, tmp_path, monkeypatch):
        import requests

        monkeypatch.setattr(
            requests,
            "post",
            lambda *a, **k: _FakeResponse({}, status_code=400, text="Bad Request: unsupported"),
        )
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = DeepgramSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "400" in res.error
