"""Regression coverage for Inworld TTS controls and cache identity."""

from __future__ import annotations

import base64

from tools.audio.inworld_tts import InworldTTS
from tools.base_tool import ToolResult


def test_selector_can_choose_inworld(monkeypatch, isolated_tool_registry):
    monkeypatch.setenv("INWORLD_API_KEY", "test-key")
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("inworld_tts")
    monkeypatch.setattr(
        tool,
        "execute",
        lambda inputs: ToolResult(success=True, data={}, artifacts=["speech.mp3"]),
    )

    result = isolated_tool_registry.get("tts_selector").execute(
        {
            "text": "Inworld narration",
            "preferred_provider": "inworld",
            "allowed_providers": ["inworld"],
        }
    )

    assert result.success
    assert result.data["selected_provider"] == "inworld"


def test_wav_language_delivery_and_timestamps_reach_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("INWORLD_API_KEY", "test-key")
    captured = {}

    def fake_request(method, url, *, headers, **kwargs):
        captured.update(method=method, url=url, headers=headers, kwargs=kwargs)
        return {
            "audioContent": base64.b64encode(b"fake-wav").decode("ascii"),
            "timestampInfo": {"wordAlignment": []},
        }

    monkeypatch.setattr("tools.audio.inworld_tts.request_json", fake_request)
    output = tmp_path / "speech.wav"
    result = InworldTTS().execute(
        {
            "text": "Bonjour",
            "voice": "Dennis",
            "model": "inworld-tts-2",
            "language_code": "fr-FR",
            "delivery_mode": "CREATIVE",
            "timestamps": True,
            "apply_text_normalization": "auto",
            "output_path": str(output),
        }
    )

    payload = captured["kwargs"]["json"]
    assert result.success
    assert output.read_bytes() == b"fake-wav"
    assert payload["voiceId"] == "Dennis"
    assert payload["language"] == "fr-FR"
    assert payload["deliveryMode"] == "CREATIVE"
    assert payload["timestampType"] == "WORD"
    assert payload["applyTextNormalization"] == (
        "APPLY_TEXT_NORMALIZATION_UNSPECIFIED"
    )
    assert payload["audioConfig"] == {
        "audioEncoding": "LINEAR16",
        "sampleRateHertz": 48000,
    }


def test_timestamp_false_disables_alignment(monkeypatch, tmp_path):
    monkeypatch.setenv("INWORLD_API_KEY", "test-key")
    captured = {}

    def fake_request(method, url, *, headers, **kwargs):
        captured.update(kwargs)
        return {"audioContent": base64.b64encode(b"fake-mp3").decode("ascii")}

    monkeypatch.setattr("tools.audio.inworld_tts.request_json", fake_request)
    result = InworldTTS().execute(
        {
            "text": "Hello",
            "voice_id": "Dennis",
            "timestamps": False,
            "output_path": str(tmp_path / "speech.mp3"),
        }
    )

    assert result.success
    assert captured["json"]["timestampType"] == "TIMESTAMP_TYPE_UNSPECIFIED"


def test_normalization_schema_matches_selector_contract():
    schema = InworldTTS.input_schema["properties"]["apply_text_normalization"]
    assert schema["default"] == "auto"
    assert schema["enum"] == ["auto", "on", "off"]


def test_idempotency_key_covers_audio_affecting_inputs():
    tool = InworldTTS()
    baseline = {"text": "Hello"}
    variants = {
        "voice_id": "Alex",
        "model_id": "inworld-tts-2-flash",
        "format": "wav",
        "sample_rate_hertz": 24000,
        "language": "fr-FR",
        "delivery_mode": "CREATIVE",
        "timestamp_type": "CHARACTER",
        "apply_text_normalization": "off",
    }

    for field, value in variants.items():
        assert tool.idempotency_key(baseline) != tool.idempotency_key(
            {**baseline, field: value}
        ), field


def test_idempotency_key_canonicalizes_aliases_and_defaults():
    tool = InworldTTS()
    canonical = {
        "text": "Bonjour",
        "voice_id": "Alex",
        "model_id": "inworld-tts-2",
        "language": "fr-FR",
        "format": "mp3",
        "sample_rate_hertz": 48000,
        "delivery_mode": "BALANCED",
        "timestamp_type": "WORD",
        "apply_text_normalization": "auto",
    }
    aliases = {
        "text": "Bonjour",
        "voice": "Alex",
        "model": "inworld-tts-2",
        "language_code": "fr-FR",
        "timestamps": True,
        "apply_text_normalization": "AUTO",
    }

    assert tool.idempotency_key(canonical) == tool.idempotency_key(aliases)
    assert tool.idempotency_key({"text": "Hello"}) == tool.idempotency_key(
        {
            "text": "Hello",
            "voice_id": "Dennis",
            "model_id": "inworld-tts-2",
            "format": "mp3",
            "sample_rate_hertz": 48000,
            "delivery_mode": "BALANCED",
            "timestamp_type": "WORD",
            "apply_text_normalization": "auto",
        }
    )


def test_utf16_limit_is_checked_before_submission(monkeypatch, tmp_path):
    monkeypatch.setenv("INWORLD_API_KEY", "test-key")
    monkeypatch.setattr(
        "tools.audio.inworld_tts.request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("must not submit oversized text")
        ),
    )

    result = InworldTTS().execute(
        {
            "text": "😀" * 1001,
            "voice_id": "Dennis",
            "output_path": str(tmp_path / "speech.mp3"),
        }
    )

    assert not result.success
    assert "2000 UTF-16" in result.error
