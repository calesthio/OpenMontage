"""Focused tests for the Gemini (gemini-3.5-transcribe) STT tool.

No live API calls: the google-genai client is replaced by a fake. Covers the
tool contract, registry discovery, status behavior, request building, the
word_info → transcript mapping, execute() guardrails, and downstream subtitle
compatibility.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.analysis.gemini_stt import GeminiSpeechToText, _seconds
from tools.subtitle.subtitle_gen import SubtitleGen


def _w(text, start, end, speaker=None):
    ann = {"type": "word_info", "text": text, "start_offset": f"{start}s", "end_offset": f"{end}s"}
    if speaker:
        ann["speaker"] = speaker
    return ann


# A representative interaction response (dict form, as in the REST docs).
SAMPLE_INTERACTION = {
    "id": "interactions/abc123",
    "status": "completed",
    "steps": [
        {
            "type": "model_output",
            "content": [
                {
                    "type": "text",
                    "text": "Hola mundo. Esto es una prueba.",
                    "annotations": [
                        _w("Hola", 0.1, 0.45, "spk_1"),
                        _w("mundo.", 0.5, 0.95, "spk_1"),
                        _w("Esto", 1.3, 1.55, "spk_1"),
                        _w("es", 1.6, 1.7, "spk_1"),
                        _w("una", 1.75, 1.9, "spk_1"),
                        _w("prueba.", 1.95, 2.5, "spk_1"),
                    ],
                }
            ],
        }
    ],
}


class _FakeFiles:
    def __init__(self, captured):
        self.captured = captured

    def upload(self, file=None, config=None):
        self.captured["upload"] = {"file": file, "config": config}
        return SimpleNamespace(uri="files/xyz", mime_type="audio/wav")


class _FakeInteractions:
    def __init__(self, captured, response):
        self.captured = captured
        self.response = response

    def create(self, **request):
        self.captured["request"] = request
        return self.response


class _FakeClient:
    def __init__(self, captured, response=SAMPLE_INTERACTION):
        self.files = _FakeFiles(captured)
        self.interactions = _FakeInteractions(captured, response)


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(GeminiSpeechToText, BaseTool)

    def test_identity(self):
        t = GeminiSpeechToText()
        assert t.name == "gemini_stt"
        assert t.capability == "analysis"
        assert t.provider == "google"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.CORE
        assert t.fallback == "transcriber"
        assert "gemini-speech-to-text" in t.agent_skills
        assert "word_timestamps" in t.capabilities

    def test_get_info_valid(self):
        info = GeminiSpeechToText().get_info()
        assert info["name"] == "gemini_stt"
        assert "input_path" in info["input_schema"]["properties"]

    def test_estimate_cost_by_duration(self):
        t = GeminiSpeechToText()
        assert t.estimate_cost({"duration_seconds": 600}) == pytest.approx(0.05)
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("gemini_stt") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("analysis")]
        assert "gemini_stt" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_credentials(self, monkeypatch):
        for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("tools.google_credentials.service_account_configured", lambda: False)
        assert GeminiSpeechToText().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_google_key(self, gemini_env):
        assert GeminiSpeechToText().get_status() == ToolStatus.AVAILABLE

    def test_available_with_gemini_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        assert GeminiSpeechToText().get_status() == ToolStatus.AVAILABLE


# ---- Request building ----

class TestRequest:
    def test_word_timestamps_and_language(self):
        req = GeminiSpeechToText.build_request({"language": "es-AR"}, "files/x", "audio/wav")
        assert req["model"] == "gemini-3.5-transcribe"
        assert req["input"] == [{"type": "audio", "uri": "files/x", "mime_type": "audio/wav"}]
        tc = req["generation_config"]["transcription_config"]
        assert tc["mode"]["type"] == "verbatim"
        assert tc["mode"]["timestamp_granularities"] == ["word"]
        assert tc["language_codes"] == ["es-AR"]
        assert "diarization_mode" not in tc["mode"]

    def test_auto_detect_and_diarization(self):
        req = GeminiSpeechToText.build_request({"diarize": True}, "files/x", "audio/wav")
        tc = req["generation_config"]["transcription_config"]
        assert tc["language_codes"] == []
        assert tc["mode"]["diarization_mode"] == "speaker"


# ---- Response → transcript mapping (the risky logic) ----

class TestParse:
    def test_duration_strings(self):
        assert _seconds("1.250s") == 1.25
        assert _seconds(2) == 2.0
        assert _seconds(None) == 0.0

    def test_maps_words_and_sentence_segments(self):
        data = GeminiSpeechToText._parse_interaction(SAMPLE_INTERACTION, "es-AR")
        assert data["language"] == "es-AR"
        assert len(data["word_timestamps"]) == 6
        assert data["word_timestamps"][0] == {
            "word": "Hola", "start": 0.1, "end": 0.45, "probability": None, "speaker": "spk_1",
        }
        assert [s["text"] for s in data["segments"]] == ["Hola mundo.", "Esto es una prueba."]
        assert data["segments"][1]["start"] == 1.3
        assert data["duration_seconds"] == 2.5

    def test_object_style_response(self):
        # The SDK returns attribute objects rather than dicts.
        def ns(d):
            if isinstance(d, dict):
                return SimpleNamespace(**{k: ns(v) for k, v in d.items()})
            if isinstance(d, list):
                return [ns(x) for x in d]
            return d

        data = GeminiSpeechToText._parse_interaction(ns(SAMPLE_INTERACTION), None)
        assert len(data["word_timestamps"]) == 6
        assert data["segments"][0]["text"] == "Hola mundo."

    def test_long_pause_splits_segment(self):
        interaction = {"steps": [{"content": [{"type": "text", "annotations": [
            _w("uno", 0.0, 0.3), _w("dos", 2.0, 2.3)]}]}]}
        data = GeminiSpeechToText._parse_interaction(interaction, None)
        assert [s["text"] for s in data["segments"]] == ["uno", "dos"]

    def test_text_only_fallback(self):
        interaction = {"output_text": "Sin marcas de tiempo.", "steps": []}
        data = GeminiSpeechToText._parse_interaction(interaction, None)
        assert data["segments"][0]["text"] == "Sin marcas de tiempo."
        assert data["word_timestamps"] == []

    def test_output_feeds_subtitle_gen(self, tmp_path):
        data = GeminiSpeechToText._parse_interaction(SAMPLE_INTERACTION, None)
        out = tmp_path / "captions.srt"
        res = SubtitleGen().execute({"segments": data["segments"], "format": "srt", "output_path": str(out)})
        assert res.success
        assert "Hola mundo." in out.read_text(encoding="utf-8")


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_file(self, gemini_env, tmp_path):
        res = GeminiSpeechToText().execute({"input_path": str(tmp_path / "nope.wav")})
        assert not res.success
        assert "not found" in res.error.lower()

    def test_missing_credentials(self, monkeypatch, tmp_path):
        for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("tools.google_credentials.service_account_configured", lambda: False)
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = GeminiSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_success_path_mocked(self, gemini_env, tmp_path, monkeypatch):
        captured = {}
        monkeypatch.setattr("tools.google_credentials.get_genai_client", lambda *a, **k: _FakeClient(captured))
        audio = tmp_path / "clip.wav"
        audio.write_bytes(b"RIFF....")

        res = GeminiSpeechToText().execute(
            {"input_path": str(audio), "language": "es-AR", "output_dir": str(tmp_path / "out")}
        )

        assert res.success, res.error
        assert res.model == "gemini-3.5-transcribe"
        assert res.data["provider"] == "google"
        assert Path(res.artifacts[0]).name == "clip_transcript.json"
        assert captured["upload"]["file"] == str(audio)
        assert captured["request"]["input"][0]["uri"] == "files/xyz"
        assert captured["request"]["generation_config"]["transcription_config"]["language_codes"] == ["es-AR"]

    def test_api_error_surfaced(self, gemini_env, tmp_path, monkeypatch):
        class Boom(_FakeClient):
            def __init__(self):
                super().__init__({})
                self.interactions.create = lambda **k: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED"))

        monkeypatch.setattr("tools.google_credentials.get_genai_client", lambda *a, **k: Boom())
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = GeminiSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "429" in res.error


class TestRobustness:
    def test_empty_transcript_is_failure(self, gemini_env, tmp_path, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            "tools.google_credentials.get_genai_client",
            lambda *a, **k: _FakeClient(captured, response={"steps": []}),
        )
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF....")
        res = GeminiSpeechToText().execute({"input_path": str(audio)})
        assert not res.success
        assert "empty transcript" in res.error

    def test_video_input_uploads_extracted_audio(self, gemini_env, tmp_path, monkeypatch):
        import subprocess

        captured = {}
        monkeypatch.setattr("tools.google_credentials.get_genai_client", lambda *a, **k: _FakeClient(captured))
        calls = []

        def fake_run(cmd, check=True):
            calls.append(cmd)
            Path(cmd[-1]).write_bytes(b"RIFF....")

        monkeypatch.setattr(subprocess, "run", fake_run)
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        res = GeminiSpeechToText().execute({"input_path": str(video), "output_dir": str(tmp_path / "out")})
        assert res.success, res.error
        assert calls and calls[0][0] == "ffmpeg" and "-vn" in calls[0]
        assert captured["upload"]["file"].endswith("clip.wav")
        assert captured["upload"]["config"] == {"mime_type": "audio/wav"}
