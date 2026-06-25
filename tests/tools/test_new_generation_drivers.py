"""Contract tests for new generation drivers added in PR #174.

Covers:
- tools/audio/stepfun_tts.py
- tools/audio/xiaomi_tts.py
- tools/graphics/qwen_image.py
- tools/graphics/stepfun_image.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolTier
from tools.audio.stepfun_tts import StepFunTTS
from tools.audio.xiaomi_tts import XiaomiTTS
from tools.graphics.qwen_image import QwenImage
from tools.graphics.stepfun_image import StepFunImage


# ---- Tool registry ----

NEW_TOOLS = [
    StepFunTTS,
    XiaomiTTS,
    QwenImage,
    StepFunImage,
]

TTS_TOOLS = [StepFunTTS, XiaomiTTS]
IMAGE_TOOLS = [QwenImage, StepFunImage]


# ---- Base contract tests (replicate phase1 pattern) ----

class TestNewToolContracts:
    """Verify all new tools satisfy the ToolContract."""

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_inherits_base_tool(self, tool_cls):
        assert issubclass(tool_cls, BaseTool)

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_has_required_identity(self, tool_cls):
        tool = tool_cls()
        assert tool.name, f"{tool_cls.__name__} must have a non-empty name"
        assert tool.version, f"{tool_cls.__name__} must have a version"
        assert tool.tier in ToolTier
        assert len(tool.capabilities) > 0, f"{tool_cls.__name__} must declare capabilities"

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_has_input_schema(self, tool_cls):
        tool = tool_cls()
        assert isinstance(tool.input_schema, dict)
        assert "type" in tool.input_schema
        assert "properties" in tool.input_schema

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_execute_is_implemented(self, tool_cls):
        tool = tool_cls()
        assert callable(tool.execute)

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_dry_run_returns_dict(self, tool_cls):
        tool = tool_cls()
        result = tool.dry_run({})
        assert isinstance(result, dict)


# ---- TTS-specific tests ----

class TestTTSContracts:
    """TTS tools must require 'text' input and have audio output format options."""

    @pytest.mark.parametrize("tool_cls", TTS_TOOLS)
    def test_requires_text_input(self, tool_cls):
        tool = tool_cls()
        schema = tool.input_schema
        assert "text" in schema.get("required", [])

    @pytest.mark.parametrize("tool_cls", TTS_TOOLS)
    def test_supports_common_formats(self, tool_cls):
        tool = tool_cls()
        fmt_prop = tool.input_schema["properties"].get("format", {})
        assert "enum" in fmt_prop
        assert "mp3" in fmt_prop["enum"]

    @pytest.mark.parametrize("tool_cls", TTS_TOOLS)
    def test_has_speed_control(self, tool_cls):
        tool = tool_cls()
        assert "speed" in tool.input_schema["properties"]

    @pytest.mark.parametrize("tool_cls", TTS_TOOLS)
    def test_has_output_path_option(self, tool_cls):
        tool = tool_cls()
        assert "output_path" in tool.input_schema["properties"]


# ---- Image tool-specific tests ----

class TestImageContracts:
    """Image tools must require prompt or image_path and support output_path."""

    @pytest.mark.parametrize("tool_cls", IMAGE_TOOLS)
    def test_has_output_path(self, tool_cls):
        tool = tool_cls()
        assert "output_path" in tool.input_schema["properties"]

    def test_qwen_requires_prompt(self):
        tool = QwenImage()
        assert "prompt" in tool.input_schema["required"]

    def test_stepfun_image_requires_prompt_and_image(self):
        tool = StepFunImage()
        required = tool.input_schema["required"]
        assert "prompt" in required
        assert "image_path" in required

    def test_qwen_supports_multiple_outputs(self):
        tool = QwenImage()
        n_prop = tool.input_schema["properties"].get("n", {})
        assert n_prop.get("maximum", 1) >= 2


# ---- Error handling tests ----

class TestErrorHandling:
    """All tools must fail gracefully when API key is missing."""

    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_missing_api_key_returns_failure(self, tool_cls, monkeypatch):
        monkeypatch.delenv(tool_cls()._get_api_key.__func__(tool_cls()) or "", raising=False)
        # Ensure the relevant env var is unset
        env_var = tool_cls()._get_api_key()
        if env_var:
            monkeypatch.delenv(env_var, raising=False)
        tool = tool_cls()
        result = tool.execute({}, None)
        assert result.success is False
        assert "not set" in result.error.lower() or "API key" in result.error.lower()

    def test_stepfun_tts_missing_key_message(self, monkeypatch):
        monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
        tool = StepFunTTS()
        result = tool.execute({"text": "hello"}, None)
        assert result.success is False
        assert "STEPFUN_API_KEY" in result.error

    def test_xiaomi_tts_missing_key_message(self, monkeypatch):
        monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
        tool = XiaomiTTS()
        result = tool.execute({"text": "hello"}, None)
        assert result.success is False
        assert "XIAOMI_API_KEY" in result.error

    def test_qwen_missing_key_message(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        tool = QwenImage()
        result = tool.execute({"prompt": "a cat"}, None)
        assert result.success is False
        assert "DASHSCOPE_API_KEY" in result.error

    def test_stepfun_image_missing_key_message(self, monkeypatch):
        monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
        tool = StepFunImage()
        result = tool.execute({"prompt": "make it red", "image_path": "/tmp/test.png"}, None)
        assert result.success is False
        assert "STEPFUN_API_KEY" in result.error


# ---- Tool registry tests ----

class TestToolRegistry:
    """Verify new tools are discoverable through the registry."""


    @pytest.mark.parametrize("tool_cls", NEW_TOOLS)
    def test_tool_info_callable(self, tool_cls):
        tool = tool_cls()
        info = tool.get_info()
        assert info["name"] == tool.name
        assert "version" in info
        assert "tier" in info
