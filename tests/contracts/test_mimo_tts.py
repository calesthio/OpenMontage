"""Contract tests for Xiaomi MiMo TTS.

Verifies BaseTool contract, input validation, request shaping, and a mocked
API call path — no real MIMO_API_KEY or network required.

Run: pytest tests/contracts/test_mimo_tts.py -v
"""

from __future__ import annotations

import base64
import json
import sys
from unittest.mock import MagicMock

import pytest

from tools.audio.mimo_tts import BUILTIN_VOICES, DEFAULT_MODEL, MiMoTTS
from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# Minimal valid WAV (44-byte header + empty data chunk size 0)
_MINIMAL_WAV = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    b"\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00"
    b"\x02\x00\x10\x00data\x00\x00\x00\x00"
)


@pytest.fixture
def tool() -> MiMoTTS:
    return MiMoTTS()


class TestMiMoContract:
    def test_inherits_base_tool(self):
        assert issubclass(MiMoTTS, BaseTool)

    def test_identity(self, tool):
        assert tool.name == "mimo_tts"
        assert tool.provider == "mimo"
        assert tool.capability == "tts"
        assert tool.tier == ToolTier.VOICE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.API
        assert tool.execution_mode == ExecutionMode.SYNC

    def test_input_schema_requires_text(self, tool):
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "text" in schema["required"]
        props = schema["properties"]
        assert "voice" in props
        assert "model" in props
        assert "style_instruction" in props
        assert "voice_description" not in props
        assert "reference_audio" not in props
        assert props["model"]["enum"] == [DEFAULT_MODEL]

    def test_fallbacks_include_offline(self, tool):
        assert tool.fallback == "piper_tts"
        assert "piper_tts" in tool.fallback_tools

    def test_agent_skills(self, tool):
        assert "text-to-speech" in tool.agent_skills

    def test_install_instructions_mention_key(self, tool):
        assert "MIMO_API_KEY" in tool.install_instructions

    def test_get_info(self, tool):
        info = tool.get_info()
        assert info["name"] == "mimo_tts"
        assert info["provider"] == "mimo"
        assert info["capability"] == "tts"

    def test_status_unavailable_without_key(self, tool, monkeypatch):
        monkeypatch.delenv("MIMO_API_KEY", raising=False)
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_status_available_with_key(self, tool, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "fake-key-for-testing")
        assert tool.get_status() == ToolStatus.AVAILABLE

    def test_estimate_cost_is_promotional_zero(self, tool):
        assert tool.estimate_cost({"text": "hello world"}) == 0.0

    def test_does_not_support_voice_cloning(self, tool):
        assert tool.supports.get("voice_cloning") is False

    def test_not_good_for_voice_clone_matching(self, tool):
        assert "voice clone matching" in tool.not_good_for


class TestMiMoValidation:
    def test_rejects_unknown_preset_voice(self, tool):
        err = tool._validate_inputs({"text": "hi", "voice": "not-a-voice"})
        assert err and "Unknown preset voice" in err

    def test_accepts_builtin_voices(self, tool):
        for voice in BUILTIN_VOICES:
            assert tool._validate_inputs({"text": "hi", "voice": voice}) is None

    def test_rejects_unsupported_model(self, tool):
        err = tool._validate_inputs(
            {"text": "hi", "model": "mimo-v2.5-tts-voiceclone"}
        )
        assert err and "Unsupported model" in err

    def test_execute_without_key(self, tool, monkeypatch):
        monkeypatch.delenv("MIMO_API_KEY", raising=False)
        result = tool.execute({"text": "hello"})
        assert result.success is False
        assert "MIMO_API_KEY" in result.error


class TestMiMoRequestBuilding:
    def test_preset_payload(self, tool):
        msgs, audio = tool._build_request("你好", "冰糖", "温柔沉稳")
        assert msgs == [
            {"role": "user", "content": "温柔沉稳"},
            {"role": "assistant", "content": "你好"},
        ]
        assert audio == {"format": "wav", "voice": "冰糖"}

    def test_preset_without_style_omits_user_message(self, tool):
        msgs, audio = tool._build_request("hello", "Chloe", "")
        assert msgs == [{"role": "assistant", "content": "hello"}]
        assert audio["voice"] == "Chloe"

    def test_safe_error_redacts_key(self, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "secret-key-12345")
        redacted = MiMoTTS._safe_error(
            Exception("failed with key secret-key-12345")
        )
        assert "secret-key-12345" not in redacted
        assert "[redacted]" in redacted

    def test_idempotency_differs_on_style_instruction(self, tool):
        base = {"text": "hi", "voice": "Mia"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "style_instruction": "calm narrator"}
        )


class TestMiMoExecuteMocked:
    def test_successful_preset_generation(self, tool, monkeypatch, tmp_path):
        monkeypatch.setenv("MIMO_API_KEY", "fake-key-for-testing")
        output = tmp_path / "out.wav"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "audio": {
                            "data": base64.b64encode(_MINIMAL_WAV).decode("ascii")
                        }
                    }
                }
            ]
        }

        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp
        monkeypatch.setitem(sys.modules, "requests", mock_requests)
        monkeypatch.setattr(
            "tools.analysis.audio_probe.probe_duration",
            lambda _path: 1.25,
        )

        result = tool.execute(
            {
                "text": "你好世界",
                "voice": "冰糖",
                "style_instruction": "温柔",
                "output_path": str(output),
            }
        )

        assert result.success is True
        assert output.exists()
        assert output.read_bytes()[:4] == b"RIFF"
        assert result.data["provider"] == "mimo"
        assert result.data["voice"] == "冰糖"
        assert result.data["audio_duration_seconds"] == 1.25
        assert result.cost_usd == 0.0
        assert str(output) in result.artifacts

        call_kwargs = mock_requests.post.call_args
        assert call_kwargs.kwargs["headers"]["api-key"] == "fake-key-for-testing"
        payload = call_kwargs.kwargs["json"]
        assert payload["model"] == DEFAULT_MODEL
        assert payload["audio"]["voice"] == "冰糖"
        assert json.dumps(payload["messages"])

    def test_api_error_surface(self, tool, monkeypatch, tmp_path):
        monkeypatch.setenv("MIMO_API_KEY", "fake-key-for-testing")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "unauthorized"

        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp
        monkeypatch.setitem(sys.modules, "requests", mock_requests)

        result = tool.execute(
            {"text": "hi", "output_path": str(tmp_path / "x.wav")}
        )
        assert result.success is False
        assert "401" in result.error


class TestMiMoRegistryDiscovery:
    def test_discoverable_by_registry(self):
        from tools.tool_registry import ToolRegistry

        registry = ToolRegistry()
        registry.discover()
        tool = registry.get("mimo_tts")
        assert tool is not None
        assert tool.provider == "mimo"
        assert tool.capability == "tts"

    def test_tts_capability_matches_selector(self, tool):
        from tools.audio.tts_selector import TTSSelector

        assert tool.capability == "tts"
        assert TTSSelector().capability == "tts"
