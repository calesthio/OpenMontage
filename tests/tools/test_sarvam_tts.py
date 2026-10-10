"""Focused tests for the Sarvam AI Bulbul TTS tool.

No live API calls: the network layer is monkeypatched. Covers the tool
contract, registry discovery, status behavior, model/speaker validation,
per-model payload shaping, sentence-boundary chunking, WAV joining, and
execute() guardrails.
"""

import base64
import io
import sys
import wave
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus, ToolTier
from tools.tool_registry import ToolRegistry
from tools.audio.sarvam_tts import SarvamTTS


def make_wav(seconds: float = 0.1, rate: int = 24000) -> bytes:
    """A real (silent) WAV payload so the joining path exercises `wave`."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


FAKE_WAV = make_wav()


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload if payload is not None else {
            "request_id": "req_1",
            "audios": [base64.b64encode(FAKE_WAV).decode()],
        }
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def sarvam_env(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "fake-key")
    monkeypatch.delenv("SARVAM_API_BASE_URL", raising=False)
    monkeypatch.delenv("SARVAM_INR_PER_USD", raising=False)


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(SarvamTTS, BaseTool)

    def test_identity(self):
        t = SarvamTTS()
        assert t.name == "sarvam_tts"
        assert t.capability == "tts"
        assert t.provider == "sarvam"
        assert t.runtime == ToolRuntime.API
        assert t.tier == ToolTier.VOICE
        assert t.fallback == "piper_tts"
        assert "sarvam-tts" in t.agent_skills
        assert len(t.capabilities) > 0

    def test_get_info_valid(self):
        info = SarvamTTS().get_info()
        assert info["name"] == "sarvam_tts"
        assert info["capability"] == "tts"
        assert "text" in info["input_schema"]["properties"]

    def test_estimate_cost_by_characters(self, monkeypatch):
        monkeypatch.delenv("SARVAM_INR_PER_USD", raising=False)
        t = SarvamTTS()
        # ₹30 per 10K characters, reported in USD at ₹88/USD.
        assert t.estimate_cost({"text": "x" * 10_000}) == pytest.approx(30 / 88, abs=1e-4)
        assert t.estimate_cost({}) == 0.0

    def test_cost_rate_override(self, monkeypatch):
        monkeypatch.setenv("SARVAM_INR_PER_USD", "100")
        assert SarvamTTS().estimate_cost({"text": "x" * 10_000}) == pytest.approx(0.3)

    def test_cost_rate_override_ignores_garbage(self, monkeypatch):
        monkeypatch.setenv("SARVAM_INR_PER_USD", "not-a-number")
        assert SarvamTTS().estimate_cost({"text": "x" * 10_000}) == pytest.approx(30 / 88, abs=1e-4)


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("sarvam_tts") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("tts")]
        assert "sarvam_tts" in names


# ---- Status behavior ----

class TestStatus:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        assert SarvamTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, sarvam_env):
        assert SarvamTTS().get_status() == ToolStatus.AVAILABLE


# ---- Model / speaker resolution ----

class TestResolution:
    def test_model_defaults_and_normalizes(self):
        t = SarvamTTS()
        assert t._resolve_model({}) == "bulbul:v3"
        assert t._resolve_model({"model": "BULBUL:V2"}) == "bulbul:v2"
        # unknown models fall back to the default rather than reaching the API
        assert t._resolve_model({"model": "bulbul:v9"}) == "bulbul:v3"

    def test_speaker_defaults_per_model(self):
        t = SarvamTTS()
        assert t._resolve_speaker({}, "bulbul:v3") == "shubh"
        assert t._resolve_speaker({}, "bulbul:v2") == "anushka"

    def test_speaker_case_insensitive(self):
        assert SarvamTTS()._resolve_speaker({"speaker": "RITU"}, "bulbul:v3") == "ritu"

    def test_cross_model_speaker_rejected(self):
        t = SarvamTTS()
        with pytest.raises(ValueError) as exc:
            t._resolve_speaker({"speaker": "anushka"}, "bulbul:v3")
        assert "bulbul:v3" in str(exc.value)
        with pytest.raises(ValueError):
            t._resolve_speaker({"speaker": "ritu"}, "bulbul:v2")


# ---- Payload shaping (per-model parameter filtering) ----

class TestPayload:
    def test_v3_drops_v2_only_fields(self):
        payload = SarvamTTS()._build_payload(
            {"pitch": 0.5, "loudness": 1.5, "enable_preprocessing": True,
             "temperature": 0.4, "pace": 0.9},
            "Hello", "bulbul:v3", "shubh", "wav",
        )
        assert "pitch" not in payload
        assert "loudness" not in payload
        assert "enable_preprocessing" not in payload
        assert payload["temperature"] == 0.4
        assert payload["pace"] == 0.9

    def test_v2_drops_v3_only_fields(self):
        payload = SarvamTTS()._build_payload(
            {"pitch": 0.5, "loudness": 1.5, "temperature": 0.4, "dict_id": "d1"},
            "Hello", "bulbul:v2", "anushka", "wav",
        )
        assert payload["pitch"] == 0.5
        assert payload["loudness"] == 1.5
        assert "temperature" not in payload
        assert "dict_id" not in payload
        assert payload["enable_preprocessing"] is False

    def test_language_and_codec_carried(self):
        payload = SarvamTTS()._build_payload(
            {"target_language_code": "hi-IN", "speech_sample_rate": 44100},
            "नमस्ते", "bulbul:v3", "ritu", "mp3",
        )
        assert payload["target_language_code"] == "hi-IN"
        assert payload["output_audio_codec"] == "mp3"
        assert payload["speech_sample_rate"] == 44100

    def test_base_url_override(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_BASE_URL", "https://proxy.example.com/")
        assert SarvamTTS()._base_url() == "https://proxy.example.com/text-to-speech"


# ---- Chunking + WAV joining (the risky logic) ----

class TestChunking:
    def test_short_text_is_one_chunk(self):
        assert SarvamTTS.chunk_text("Hello world.", 2500) == ["Hello world."]

    def test_empty_text_yields_no_chunks(self):
        assert SarvamTTS.chunk_text("   ", 2500) == []

    def test_splits_on_sentence_boundaries(self):
        text = " ".join(f"Sentence number {i} here." for i in range(40))
        chunks = SarvamTTS.chunk_text(text, 120)
        assert len(chunks) > 1
        assert all(len(c) <= 120 for c in chunks)
        # no words lost or duplicated in the split
        assert " ".join(chunks).split() == text.split()

    def test_splits_devanagari_danda(self):
        text = "यह पहला वाक्य है। यह दूसरा वाक्य है। यह तीसरा वाक्य है।"
        chunks = SarvamTTS.chunk_text(text, 30)
        assert len(chunks) > 1
        assert all(len(c) <= 30 for c in chunks)

    def test_oversized_single_sentence_splits_on_words(self):
        text = "word " * 200  # one run-on sentence, no terminal punctuation
        chunks = SarvamTTS.chunk_text(text.strip(), 100)
        assert all(len(c) <= 100 for c in chunks)
        assert " ".join(chunks).split() == text.split()

    def test_merge_wavs_sums_frames(self):
        clips = [make_wav(0.1), make_wav(0.2), make_wav(0.3)]
        merged = SarvamTTS.merge_wavs(clips)
        with wave.open(io.BytesIO(merged), "rb") as r:
            assert r.getframerate() == 24000
            assert r.getnchannels() == 1
            assert r.getnframes() == pytest.approx(24000 * 0.6, rel=0.01)

    def test_merge_single_clip_is_passthrough(self):
        clip = make_wav()
        assert SarvamTTS.merge_wavs([clip]) is clip


# ---- execute() guardrails + mocked success ----

class TestExecute:
    def test_missing_key(self, monkeypatch):
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        res = SarvamTTS().execute({"text": "hello"})
        assert not res.success
        assert "not configured" in res.error.lower()

    def test_empty_text_rejected(self, sarvam_env):
        res = SarvamTTS().execute({"text": "   "})
        assert not res.success
        assert "no text" in res.error.lower()

    def test_bad_speaker_rejected_before_call(self, sarvam_env, monkeypatch):
        import requests

        def boom(*a, **k):
            raise AssertionError("must not reach the API with an invalid speaker")

        monkeypatch.setattr(requests, "post", boom)
        res = SarvamTTS().execute({"text": "hi", "speaker": "anushka", "model": "bulbul:v3"})
        assert not res.success
        assert "not available on bulbul:v3" in res.error

    def test_success_path_mocked(self, sarvam_env, tmp_path, monkeypatch):
        import requests

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)

        out = tmp_path / "narration.wav"
        res = SarvamTTS().execute({
            "text": "Welcome to the future of learning.",
            "speaker": "ritu",
            "target_language_code": "hi-IN",
            "output_path": str(out),
        })

        assert res.success
        assert res.model == "bulbul:v3:ritu"
        assert res.data["provider"] == "sarvam"
        assert res.data["speaker"] == "ritu"
        assert res.data["language"] == "hi-IN"
        assert res.data["chunks"] == 1
        assert res.data["request_ids"] == ["req_1"]
        assert out.read_bytes() == FAKE_WAV
        assert res.artifacts == [str(out)]
        assert captured["url"] == "https://api.sarvam.ai/text-to-speech"
        assert captured["headers"]["api-subscription-key"] == "fake-key"
        assert captured["json"]["model"] == "bulbul:v3"

    def test_long_script_chunks_and_joins(self, sarvam_env, tmp_path, monkeypatch):
        import requests

        calls = []

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append(json)
            return _FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)

        text = " ".join(f"This is narration sentence number {i}." for i in range(200))
        out = tmp_path / "long.wav"
        res = SarvamTTS().execute({"text": text, "output_path": str(out)})

        assert res.success
        assert len(calls) > 1
        assert res.data["chunks"] == len(calls)
        # multi-chunk always pulls wav so the parts can be joined losslessly
        assert all(c["output_audio_codec"] == "wav" for c in calls)
        with wave.open(str(out), "rb") as r:
            assert r.getnframes() == pytest.approx(24000 * 0.1 * len(calls), rel=0.01)

    def test_retries_then_succeeds_on_429(self, sarvam_env, tmp_path, monkeypatch):
        import requests
        import time as time_mod

        responses = [_FakeResponse(payload={}, status_code=429, text="rate limited"),
                     _FakeResponse()]
        monkeypatch.setattr(requests, "post", lambda *a, **k: responses.pop(0))
        monkeypatch.setattr(time_mod, "sleep", lambda *_: None)

        res = SarvamTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.wav")})
        assert res.success
        assert responses == []

    def test_client_error_not_retried(self, sarvam_env, tmp_path, monkeypatch):
        import requests

        calls = []

        def fake_post(*a, **k):
            calls.append(1)
            return _FakeResponse(payload={}, status_code=403, text="Forbidden")

        monkeypatch.setattr(requests, "post", fake_post)
        res = SarvamTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.wav")})
        assert not res.success
        assert "403" in res.error
        assert len(calls) == 1

    def test_request_exception_surfaced(self, sarvam_env, tmp_path, monkeypatch):
        import requests
        import time as time_mod

        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("no route to host")

        monkeypatch.setattr(requests, "post", boom)
        monkeypatch.setattr(time_mod, "sleep", lambda *_: None)
        res = SarvamTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.wav")})
        assert not res.success
        assert "no route to host" in res.error

    def test_empty_audio_list_surfaced(self, sarvam_env, tmp_path, monkeypatch):
        import requests

        monkeypatch.setattr(
            requests, "post",
            lambda *a, **k: _FakeResponse(payload={"request_id": "r", "audios": []}),
        )
        res = SarvamTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.wav")})
        assert not res.success
        assert "no audio" in res.error.lower()

    def test_selector_adapts_shared_controls_for_sarvam(self, sarvam_env, tmp_path, monkeypatch):
        import requests
        from tools.audio.tts_selector import TTSSelector

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["json"] = json
            return _FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)
        monkeypatch.setattr(TTSSelector, "_providers", lambda self: [SarvamTTS()])

        result = TTSSelector().execute({
            "text": "Selector narration",
            "preferred_provider": "sarvam",
            "voice_id": "Ritu",
            "language_code": "hi",
            "speaking_rate": 0.95,
            "pitch": 12,          # selector scale — out of Bulbul's range, dropped
            "style": 0.8,         # ElevenLabs-only control, dropped
            "output_format": "mp3_44100_128",
            "output_path": str(tmp_path / "selector.mp3"),
        })

        assert result.success
        assert result.data["selected_tool"] == "sarvam_tts"
        assert captured["json"]["speaker"] == "ritu"
        assert captured["json"]["target_language_code"] == "hi-IN"
        assert captured["json"]["pace"] == 0.95
        assert "pitch" not in captured["json"]
        assert captured["json"]["output_audio_codec"] == "mp3"
