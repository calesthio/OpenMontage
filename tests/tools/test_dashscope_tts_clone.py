"""Tests for cloned-voice synthesis through dashscope_tts.

The pre-existing qwen3-tts path must stay byte-for-byte identical; these tests
cover the new native SpeechSynthesizer branch: model inference from a cloned
voice_id, endpoint routing, model-binding errors, and tts_selector pass-through.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.audio.dashscope_tts import DashscopeTTS
from tools.audio.tts_selector import TTSSelector

VOICE_ID = "qwen-audio-3.1-tts-flash-femtest-cd3af4b0d06a44449d58934877dfb8ba"
MULTIMODAL = "multimodal-generation/generation"
NATIVE = "services/audio/tts/SpeechSynthesizer"


class _FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        status_code: int = 200,
        content: bytes = b"WAVAUDIO",
    ):
        self._payload = payload if payload is not None else {
            "output": {"audio": {"url": "https://example.com/a.wav"}},
            "usage": {"characters": 12},
        }
        self.status_code = status_code
        self.content = content

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dashscope-secret")
    return "sk-dashscope-secret"


@pytest.fixture(autouse=True)
def no_probe(monkeypatch):
    monkeypatch.setattr("tools.analysis.audio_probe.probe_duration", lambda _p: 3.2)


def _run(inputs, responses=None, tmp_path=None):
    out = (tmp_path or __import__("pathlib").Path(".")) / "out.wav"
    payload = dict(inputs)
    payload.setdefault("output_path", str(out))
    responses = responses or [_FakeResponse()]
    with patch("requests.post", side_effect=responses) as mock_post, patch(
        "requests.get", return_value=_FakeResponse(content=b"WAVAUDIO")
    ):
        result = DashscopeTTS().execute(payload)
    return result, mock_post, out


class TestQwen3PathUnchanged:
    def test_default_call_uses_multimodal_endpoint(self, api_key, tmp_path):
        result, mock_post, out = _run({"text": "你好"}, tmp_path=tmp_path)

        assert result.success is True, result.error
        assert mock_post.call_args.args[0].endswith(MULTIMODAL)
        body = mock_post.call_args.kwargs["json"]
        assert body == {
            "model": "qwen3-tts-flash",
            "input": {"text": "你好", "voice": "Cherry", "language_type": "Auto"},
        }
        assert result.data["endpoint"] == "multimodal_generation"
        assert "voice_id" not in result.data
        assert out.read_bytes() == b"WAVAUDIO"

    def test_instructions_only_for_instruct_model(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {
                "text": "hi",
                "model": "qwen3-tts-instruct-flash",
                "instructions": "warm, slow",
            },
            tmp_path=tmp_path,
        )
        assert result.success is True
        body = mock_post.call_args.kwargs["json"]
        assert body["input"]["instructions"] == "warm, slow"
        assert body["input"]["optimize_instructions"] is True


class TestClonedVoicePath:
    def test_voice_id_infers_model_and_uses_native_endpoint(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {"text": "你好", "voice_id": VOICE_ID}, tmp_path=tmp_path
        )

        assert result.success is True, result.error
        assert mock_post.call_args.args[0].endswith(NATIVE)
        body = mock_post.call_args.kwargs["json"]
        assert body["model"] == "qwen-audio-3.1-tts-flash"
        assert body["input"] == {
            "text": "你好",
            "voice": VOICE_ID,
            "format": "wav",
            "sample_rate": 24000,
        }
        assert result.data["endpoint"] == "native_tts"
        assert result.data["voice_id"] == VOICE_ID
        assert result.data["model_inferred_from_voice_id"] is True
        assert result.data["format"] == "wav"
        assert result.data["sample_rate"] == 24000

    def test_explicit_format_and_sample_rate(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {
                "text": "你好",
                "voice_id": VOICE_ID,
                "format": "mp3",
                "sample_rate": 48000,
            },
            tmp_path=tmp_path,
        )
        assert result.success is True, result.error
        assert mock_post.call_args.kwargs["json"]["input"]["format"] == "mp3"
        assert mock_post.call_args.kwargs["json"]["input"]["sample_rate"] == 48000

    def test_voice_id_beats_voice_name(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {"text": "x", "voice": "Cherry", "voice_id": VOICE_ID},
            tmp_path=tmp_path,
        )
        assert result.success is True, result.error
        assert mock_post.call_args.kwargs["json"]["input"]["voice"] == VOICE_ID

    def test_model_id_alias_from_selector_is_accepted(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {
                "text": "x",
                "voice_id": VOICE_ID,
                "model_id": "qwen-audio-3.1-tts-flash",
            },
            tmp_path=tmp_path,
        )
        assert result.success is True, result.error
        assert mock_post.call_args.args[0].endswith(NATIVE)
        assert result.data["model"] == "qwen-audio-3.1-tts-flash"
        assert result.data["model_inferred_from_voice_id"] is False


class TestModelBindingErrors:
    def test_conflicting_model_is_rejected_without_a_call(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {
                "text": "x",
                "voice_id": "qwen-audio-3.0-tts-flash-narr-abc",
                "model": "qwen-audio-3.1-tts-flash",
            },
            tmp_path=tmp_path,
        )
        assert result.success is False
        assert "bound to their enrollment model" in result.error
        mock_post.assert_not_called()

    def test_voice_id_with_qwen3_model_is_rejected(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {"text": "x", "voice_id": VOICE_ID, "model": "qwen3-tts-flash"},
            tmp_path=tmp_path,
        )
        assert result.success is False
        assert "cloned voice" in result.error
        mock_post.assert_not_called()

    def test_unrecognized_voice_id_requires_explicit_model(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {"text": "x", "voice_id": "custom-voice-1"}, tmp_path=tmp_path
        )
        assert result.success is False
        assert "Could not infer the target model" in result.error
        mock_post.assert_not_called()

    def test_native_model_requires_a_voice(self, api_key, tmp_path):
        result, mock_post, _ = _run(
            {"text": "x", "model": "qwen-audio-3.1-tts-flash"}, tmp_path=tmp_path
        )
        assert result.success is False
        assert "needs a voice" in result.error
        mock_post.assert_not_called()


class TestErrors:
    def test_api_error_code_surfaces(self, api_key, tmp_path):
        error = _FakeResponse(
            {"code": "InvalidParameter", "message": "voice not found"},
            status_code=400,
        )
        result, _, _ = _run({"text": "x", "voice_id": VOICE_ID}, [error], tmp_path)
        assert result.success is False
        assert "InvalidParameter" in result.error
        assert "voice not found" in result.error

    def test_missing_audio_url_surfaces_reason(self, api_key, tmp_path):
        empty = _FakeResponse({"output": {}, "request_id": "req-1"})
        result, _, _ = _run({"text": "x"}, [empty], tmp_path)
        assert result.success is False
        assert "no audio URL" in result.error
        assert "req-1" in result.error

    def test_key_is_redacted(self, api_key, tmp_path):
        def _boom(*args, **kwargs):
            raise RuntimeError("failed with sk-dashscope-secret")

        with patch("requests.post", side_effect=_boom):
            result = DashscopeTTS().execute(
                {"text": "x", "output_path": str(tmp_path / "o.wav")}
            )
        assert result.success is False
        assert "sk-dashscope-secret" not in result.error


class TestSelectorRouting:
    def test_selector_routes_clone_to_dashscope_native_path(self, api_key, tmp_path):
        out = tmp_path / "selector.wav"
        with patch("requests.post", return_value=_FakeResponse()) as mock_post, patch(
            "requests.get", return_value=_FakeResponse(content=b"X")
        ):
            result = TTSSelector().execute(
                {
                    "text": "选择器路由测试",
                    "preferred_provider": "dashscope",
                    "voice_id": VOICE_ID,
                    "model_id": "qwen-audio-3.1-tts-flash",
                    "output_path": str(out),
                }
            )

        assert result.success is True, result.error
        assert result.data["selected_provider"] == "dashscope"
        assert mock_post.call_args.args[0].endswith(NATIVE)
        assert mock_post.call_args.kwargs["json"]["input"]["voice"] == VOICE_ID
        assert out.read_bytes() == b"X"


class TestSchema:
    def test_clone_models_are_offered(self):
        enum = DashscopeTTS.input_schema["properties"]["model"]["enum"]
        assert "qwen-audio-3.1-tts-flash" in enum
        assert "cosyvoice-v3.5-plus" in enum
        assert DashscopeTTS.input_schema["properties"]["model"]["default"] == (
            "qwen3-tts-flash"
        )

    def test_voice_id_field_exists(self):
        props = DashscopeTTS.input_schema["properties"]
        assert "voice_id" in props
        assert "model_id" in props

    def test_declares_voice_cloning_support(self):
        assert DashscopeTTS.supports["voice_cloning"] is True
        assert "voice_id_synthesis" in DashscopeTTS.capabilities

    def test_infer_model_handles_longest_prefix(self):
        assert (
            DashscopeTTS.infer_model_from_voice_id(
                "cosyvoice-v3.5-flash-narr-abc"
            )
            == "cosyvoice-v3.5-flash"
        )
        assert DashscopeTTS.infer_model_from_voice_id("not-a-clone") is None
        assert DashscopeTTS.infer_model_from_voice_id(None) is None
