"""ElevenLabs TTS: optional word-level timings via the /with-timestamps endpoint."""

from __future__ import annotations

import base64
import json
import wave
from unittest.mock import Mock

from tools.audio.elevenlabs_tts import ElevenLabsTTS


def _alignment(text: str, step: float = 0.1) -> dict:
    chars = list(text)
    return {
        "characters": chars,
        "character_start_times_seconds": [round(i * step, 3) for i in range(len(chars))],
        "character_end_times_seconds": [round((i + 1) * step, 3) for i in range(len(chars))],
    }


def _json_response(text: str, audio: bytes) -> Mock:
    body = {"audio_base64": base64.b64encode(audio).decode(), "alignment": _alignment(text)}
    return Mock(json=Mock(return_value=body), headers={"request-id": "r1"}, content=b"")


def test_with_timestamps_calls_endpoint_and_returns_words(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    text = "Много знакомств. А кому позвонить?"
    post = Mock(return_value=_json_response(text, b"ID3fake-mp3"))
    monkeypatch.setattr("requests.post", post)
    out = tmp_path / "para.mp3"

    result = ElevenLabsTTS().execute({"text": text, "with_timestamps": True, "output_path": str(out)})

    assert result.success, result.error
    assert post.call_args.args[0].endswith("/with-timestamps")
    assert post.call_args.kwargs["headers"]["Accept"] == "application/json"
    assert "with_timestamps" not in post.call_args.kwargs["json"]  # tool option, not an API field
    assert out.read_bytes() == b"ID3fake-mp3"

    words = result.data["word_timestamps"]
    assert [w["word"] for w in words] == text.split()
    assert words[0] == {"word": "Много", "start": 0.0, "end": 0.5}
    assert words[1]["start"] == 0.6 and words[1]["end"] == 1.6  # "знакомств." incl. punctuation
    assert result.data["alignment_matches_text"] is True

    saved = json.loads((tmp_path / "para.mp3.alignment.json").read_text(encoding="utf-8"))
    assert saved["text"] == text and saved["words"] == words
    assert str(tmp_path / "para.mp3.alignment.json") in result.artifacts


def test_with_timestamps_pcm_output_is_wrapped_as_wav(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    post = Mock(return_value=_json_response("Hi there", b"\x00\x00" * 50))
    monkeypatch.setattr("requests.post", post)
    out = tmp_path / "voice.wav"

    result = ElevenLabsTTS().execute(
        {"text": "Hi there", "with_timestamps": True, "output_format": "pcm_16000", "output_path": str(out)}
    )

    assert result.success, result.error
    with wave.open(str(out)) as wav:
        assert wav.getframerate() == 16000 and wav.getnframes() == 50
    assert [w["word"] for w in result.data["word_timestamps"]] == ["Hi", "there"]


def test_default_path_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    post = Mock(return_value=Mock(content=b"ID3audio", headers={"request-id": "r2"}))
    monkeypatch.setattr("requests.post", post)

    result = ElevenLabsTTS().execute({"text": "Hello", "output_path": str(tmp_path / "a.mp3")})

    assert result.success, result.error
    assert not post.call_args.args[0].endswith("/with-timestamps")
    assert post.call_args.kwargs["headers"]["Accept"] == "audio/mpeg"
    assert "word_timestamps" not in result.data
    assert result.artifacts == [str(tmp_path / "a.mp3")]


def test_missing_alignment_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    body = {"audio_base64": base64.b64encode(b"x").decode()}
    monkeypatch.setattr("requests.post", Mock(return_value=Mock(json=Mock(return_value=body), headers={})))

    result = ElevenLabsTTS().execute({"text": "Hello", "with_timestamps": True, "output_path": str(tmp_path / "a.mp3")})

    assert not result.success
    assert "alignment" in result.error


def test_words_from_alignment_handles_multichar_entries():
    alignment = {
        "characters": ["Hel", "lo", " ", "wo", "rld!"],
        "character_start_times_seconds": [0.0, 0.3, 0.5, 0.6, 0.8],
        "character_end_times_seconds": [0.3, 0.5, 0.6, 0.8, 1.1],
    }
    assert ElevenLabsTTS.words_from_alignment(alignment) == [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world!", "start": 0.6, "end": 1.1},
    ]


def test_with_timestamps_is_part_of_idempotency_key():
    assert "with_timestamps" in ElevenLabsTTS.idempotency_key_fields
    assert ElevenLabsTTS.input_schema["properties"]["with_timestamps"]["default"] is False
