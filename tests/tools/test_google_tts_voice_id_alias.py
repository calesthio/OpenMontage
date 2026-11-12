"""Regression tests for google_tts voice_id alias + language_code derivation.

Covers the selector-compatibility fix: tts_selector passes its
provider-agnostic 'voice_id' through unchanged, so google_tts must accept
it as an alias for 'voice' and derive languageCode from the voice name's
BCP-47 locale prefix. No live API calls: requests.post is monkeypatched
and the captured payload is asserted directly.
"""

import base64
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.google_tts import GoogleTTS


FAKE_AUDIO = b"fake-mp3-bytes"


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"audioContent": base64.b64encode(FAKE_AUDIO).decode()}

    def raise_for_status(self):
        return None


@pytest.fixture
def captured_synthesize(monkeypatch):
    """Route requests.post to a fake and capture the synthesize call."""
    calls = []

    def fake_post(url, headers=None, params=None, json=None, timeout=None):
        calls.append({"url": url, "params": params, "payload": json})
        return _FakeResponse()

    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("requests.post", fake_post)
    return calls


def _execute(tmp_path, **inputs):
    inputs.setdefault("text", "こんにちは")
    inputs.setdefault("output_path", str(tmp_path / "out.mp3"))
    return GoogleTTS().execute(inputs)


# ---- voice_id alias → request payload ----


class TestVoiceIdAlias:
    def test_voice_id_sets_voice_name_and_derived_language(
        self, tmp_path, captured_synthesize
    ):
        result = _execute(tmp_path, voice_id="ja-JP-Chirp3-HD-Kore")

        assert result.success, result.error
        voice_payload = captured_synthesize[0]["payload"]["voice"]
        assert voice_payload["name"] == "ja-JP-Chirp3-HD-Kore"
        assert voice_payload["languageCode"] == "ja-JP"
        assert result.data["voice"] == "ja-JP-Chirp3-HD-Kore"
        assert result.data["language_code"] == "ja-JP"

    def test_explicit_voice_wins_over_voice_id(self, tmp_path, captured_synthesize):
        result = _execute(
            tmp_path,
            voice="es-ES-Neural2-A",
            voice_id="ja-JP-Chirp3-HD-Kore",
        )

        assert result.success, result.error
        voice_payload = captured_synthesize[0]["payload"]["voice"]
        assert voice_payload["name"] == "es-ES-Neural2-A"
        assert voice_payload["languageCode"] == "es-ES"

    def test_explicit_language_code_wins_over_derived(
        self, tmp_path, captured_synthesize
    ):
        result = _execute(
            tmp_path,
            voice_id="ja-JP-Chirp3-HD-Kore",
            language_code="en-US",
        )

        assert result.success, result.error
        voice_payload = captured_synthesize[0]["payload"]["voice"]
        assert voice_payload["name"] == "ja-JP-Chirp3-HD-Kore"
        assert voice_payload["languageCode"] == "en-US"

    def test_default_voice_when_neither_field_set(self, tmp_path, captured_synthesize):
        result = _execute(tmp_path)

        assert result.success, result.error
        voice_payload = captured_synthesize[0]["payload"]["voice"]
        assert voice_payload["name"] == "en-US-Chirp3-HD-Orus"
        assert voice_payload["languageCode"] == "en-US"

    def test_chirp_voice_id_routes_to_beta_endpoint(
        self, tmp_path, captured_synthesize
    ):
        # Endpoint selection must see the resolved alias, not just 'voice'.
        _execute(tmp_path, voice_id="ja-JP-Chirp3-HD-Kore")
        assert "/v1beta1/" in captured_synthesize[0]["url"]

        _execute(tmp_path, voice_id="ja-JP-Neural2-B")
        assert "/v1/" in captured_synthesize[1]["url"]


# ---- locale derivation ----


class TestLocaleDerivation:
    def test_two_letter_prefix(self):
        assert GoogleTTS._locale_from_voice("ja-JP-Chirp3-HD-Kore") == "ja-JP"

    def test_three_letter_prefix(self):
        assert GoogleTTS._locale_from_voice("fil-PH-Standard-A") == "fil-PH"

    def test_unparseable_name_falls_back_to_en_us(self):
        assert GoogleTTS._locale_from_voice("Kore") == "en-US"


# ---- cost & idempotency (no API call) ----


class TestCostAndIdempotency:
    def test_voice_id_selects_pricing_tier(self):
        tool = GoogleTTS()
        text = "a" * 1000
        chirp_cost = tool.estimate_cost(
            {"text": text, "voice_id": "ja-JP-Chirp3-HD-Kore"}
        )
        standard_cost = tool.estimate_cost(
            {"text": text, "voice_id": "ja-JP-Standard-B"}
        )
        # Chirp 3 HD ($30/1M chars) vs Standard ($4/1M chars)
        assert chirp_cost == pytest.approx(0.03)
        assert standard_cost == pytest.approx(0.004)

    def test_voice_id_matches_equivalent_voice_pricing(self):
        tool = GoogleTTS()
        inputs_alias = {"text": "hello", "voice_id": "en-US-Studio-O"}
        inputs_direct = {"text": "hello", "voice": "en-US-Studio-O"}
        assert tool.estimate_cost(inputs_alias) == tool.estimate_cost(inputs_direct)

    def test_voice_id_changes_idempotency_key(self):
        tool = GoogleTTS()
        assert "voice_id" in tool.idempotency_key_fields
        key_kore = tool.idempotency_key(
            {"text": "hello", "voice_id": "ja-JP-Chirp3-HD-Kore"}
        )
        key_orus = tool.idempotency_key(
            {"text": "hello", "voice_id": "en-US-Chirp3-HD-Orus"}
        )
        assert key_kore != key_orus
