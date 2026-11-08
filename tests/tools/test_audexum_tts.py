"""Unit tests for the Audexum TTS provider (tools/audio/audexum_tts.py).

The real API is never called: requests.post is patched. The fake response
mirrors the documented contract (https://audexum.com/docs): raw audio body,
an audio Content-Type and the X-Audio-Duration-S header.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.audio.audexum_tts import AudexumTTS
from tools.base_tool import ToolStatus
from tools.provider_pricing import PriceQuoteRequired


def _ok(content: bytes = b"ID3fake-audio", content_type: str = "audio/mpeg") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.headers = {"Content-Type": content_type, "X-Audio-Duration-S": "1.25", "X-Format": "mp3"}
    return resp


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    monkeypatch.delenv("AUDEXUM_BASE_URL", raising=False)
    return "sk_live_x"


def test_status_follows_api_key(monkeypatch):
    monkeypatch.delenv("AUDEXUM_API_KEY", raising=False)
    assert AudexumTTS().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    assert AudexumTTS().get_status() == ToolStatus.AVAILABLE


def test_execute_without_key_fails(monkeypatch):
    monkeypatch.delenv("AUDEXUM_API_KEY", raising=False)
    result = AudexumTTS().execute({"text": "hello"})
    assert result.success is False
    assert "AUDEXUM_API_KEY" in result.error


# ---- Documented request contract ----


def test_request_matches_documented_contract(api_key, tmp_path):
    out = tmp_path / "a.mp3"
    with patch("requests.post", return_value=_ok(b"AUDIO")) as post:
        result = AudexumTTS().execute(
            {"text": "hello", "voice_id": "Reid", "language_code": "bg", "output_path": str(out)}
        )
    assert result.success is True
    assert out.read_bytes() == b"AUDIO"
    args, kwargs = post.call_args
    assert args[0] == "https://audexum.com/api/synthesize"
    assert kwargs["headers"]["Authorization"] == "Bearer sk_live_x"
    assert "xi-api-key" not in kwargs["headers"]
    assert "params" not in kwargs
    assert kwargs["json"] == {
        "text": "hello",
        "voice": "Reid",
        "lang": "bg",
        "format": "mp3",
        "backend": "v3",
    }
    assert result.data["audio_duration_seconds"] == 1.25


def test_defaults(api_key, tmp_path):
    with patch("requests.post", return_value=_ok()) as post:
        result = AudexumTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.mp3")})
    assert result.success is True
    body = post.call_args.kwargs["json"]
    assert (body["voice"], body["lang"], body["format"], body["backend"]) == ("Atlas", "en", "mp3", "v3")


@pytest.mark.parametrize("code,lang", [("en-US", "en"), ("pt_BR", "pt"), ("BG", "bg"), ("", "en")])
def test_region_suffix_is_dropped(api_key, tmp_path, code, lang):
    with patch("requests.post", return_value=_ok()) as post:
        AudexumTTS().execute(
            {"text": "hi", "language_code": code, "output_path": str(tmp_path / "a.mp3")}
        )
    assert post.call_args.kwargs["json"]["lang"] == lang


@pytest.mark.parametrize(
    "requested,sent",
    [("mp3_44100_128", "mp3"), ("wav", "wav"), ("wav_44100", "wav"), ("ogg", "ogg"), ("opus", "opus")],
)
def test_output_format_mapping(api_key, tmp_path, monkeypatch, requested, sent):
    monkeypatch.chdir(tmp_path)  # no output_path: the default file lands here
    with patch("requests.post", return_value=_ok()) as post:
        result = AudexumTTS().execute({"text": "hi", "output_format": requested})
    assert post.call_args.kwargs["json"]["format"] == sent
    assert result.data["output"].endswith(f".{sent}")


def test_unsupported_format_is_rejected_before_any_request(api_key, tmp_path):
    with patch("requests.post") as post:
        result = AudexumTTS().execute(
            {"text": "hi", "output_format": "pcm_16000", "output_path": str(tmp_path / "a.pcm")}
        )
    assert result.success is False
    post.assert_not_called()


@pytest.mark.parametrize(
    "inputs,engine",
    [({"voice_id": "M1"}, "v2"), ({"voice_id": "F5"}, "v2"), ({"voice_id": "Nova"}, "v3"),
     ({"voice_id": "M1", "engine": "v1"}, "v1"), ({"engine": "V2"}, "v2")],
)
def test_engine_selection(api_key, tmp_path, inputs, engine):
    with patch("requests.post", return_value=_ok()) as post:
        AudexumTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.mp3"), **inputs})
    assert post.call_args.kwargs["json"]["backend"] == engine


# ---- Cost reporting (budget-facing) ----


@pytest.mark.parametrize("engine,credits", [("v1", 5000), ("v2", 7500), ("v3", 10000)])
def test_estimate_cost_requires_a_quote_and_names_the_credits(engine, credits):
    tool = AudexumTTS()
    inputs = {"text": "x" * 5000, "engine": engine}
    assert tool.estimate_credits(inputs) == credits
    with pytest.raises(PriceQuoteRequired, match=str(credits)):
        tool.estimate_cost(inputs)


def test_dry_run_reports_quote_required_not_free():
    plan = AudexumTTS().dry_run({"text": "x" * 5000})
    assert plan["estimated_cost_usd"] is None
    assert plan["cost_status"] == "quote_required"


def test_successful_call_reports_cost_as_unknown(api_key, tmp_path):
    with patch("requests.post", return_value=_ok()):
        result = AudexumTTS().execute(
            {"text": "abc", "voice_id": "M2", "output_path": str(tmp_path / "a.mp3")}
        )
    assert result.success is True
    assert result.cost_usd is None
    assert result.data["cost_status"] == "unquoted"
    assert result.data["estimated_credits"] == 5  # ceil(3 chars * 1.5, V2)


def test_scoring_treats_unquoted_cost_as_unknown(api_key):
    from lib.scoring import score_provider

    score = score_provider(AudexumTTS(), {"text": "hello", "budget_remaining_usd": 1.0})
    assert score.cost_efficiency == 0.0


# ---- Validation and errors ----


@pytest.mark.parametrize("text", ["", "   ", "x" * 5001])
def test_rejects_bad_text(api_key, tmp_path, text):
    with patch("requests.post") as post:
        result = AudexumTTS().execute({"text": text, "output_path": str(tmp_path / "a.mp3")})
    assert result.success is False
    post.assert_not_called()


def test_http_error_is_reported(api_key, tmp_path):
    resp = _ok()
    resp.raise_for_status.side_effect = RuntimeError("402 insufficient_credits")
    with patch("requests.post", return_value=resp):
        result = AudexumTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.mp3")})
    assert result.success is False
    assert "402" in result.error


# ---- Selector routing and discovery ----


def test_selector_routes_to_audexum_with_documented_body(api_key, tmp_path):
    from tools.audio.tts_selector import TTSSelector

    out = tmp_path / "selector.mp3"
    with patch("requests.post", return_value=_ok(b"SELECTED")) as post:
        result = TTSSelector().execute(
            {
                "text": "routed through the selector",
                "preferred_provider": "audexum",
                "voice_id": "Sage",
                "language_code": "de-DE",
                "output_format": "mp3_44100_128",
                "output_path": str(out),
            }
        )
    assert result.success is True
    assert result.data["selected_provider"] == "audexum"
    assert out.read_bytes() == b"SELECTED"
    assert post.call_args.kwargs["json"] == {
        "text": "routed through the selector",
        "voice": "Sage",
        "lang": "de",
        "format": "mp3",
        "backend": "v3",
    }


def test_unknown_engine_is_rejected_before_any_request(api_key, tmp_path):
    with patch("requests.post") as post:
        result = AudexumTTS().execute(
            {"text": "hi", "engine": "v9", "output_path": str(tmp_path / "a.mp3")}
        )
    assert result.success is False
    post.assert_not_called()
