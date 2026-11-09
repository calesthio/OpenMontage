"""Contract tests for the Dreamina (即梦) CLI video provider tool.

Verifies BaseTool compliance, painless discovery/status checks, and execution contract.
Run: pytest tests/contracts/test_dreamina_cli_video.py -v
"""

from unittest.mock import MagicMock, patch
import pytest

from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.video.dreamina_cli_video import DreaminaCliVideo


class TestContract:

    def test_inherits_base_tool(self):
        assert issubclass(DreaminaCliVideo, BaseTool)

    def test_has_required_identity(self):
        tool = DreaminaCliVideo()
        assert tool.name == "dreamina_cli_video"
        assert tool.version == "0.1.0"
        assert tool.provider == "dreamina_cli"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.LOCAL

    def test_execution_mode_is_async(self):
        assert DreaminaCliVideo().execution_mode == ExecutionMode.ASYNC

    def test_has_input_schema(self):
        schema = DreaminaCliVideo().input_schema
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        required = schema.get("required", [])
        assert required == ["prompt"]
        assert "operation" in props
        assert "aspect_ratio" in props
        assert "model_version" in props

    def test_has_capabilities(self):
        tool = DreaminaCliVideo()
        assert "text_to_video" in tool.capabilities
        assert "image_to_video" in tool.capabilities
        assert "first_last_frame" in tool.capabilities
        assert "multimodal_reference" in tool.capabilities

    def test_painless_status_when_cli_missing(self):
        """When dreamina CLI is missing, get_status() returns ToolStatus.UNAVAILABLE

        without throwing exceptions or running subprocesses.
        """
        tool = DreaminaCliVideo()
        with patch.object(tool, "_resolve_cli_path", return_value=None):
            status = tool.get_status()
            assert status == ToolStatus.UNAVAILABLE

    def test_painless_status_when_cli_exists_and_logged_in(self):
        """When dreamina CLI exists and user_credit succeeds, get_status() returns AVAILABLE."""
        tool = DreaminaCliVideo()
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch.object(tool, "_resolve_cli_path", return_value="/usr/bin/dreamina"):
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                status = tool.get_status()
                assert status == ToolStatus.AVAILABLE
                mock_run.assert_called_once()

    def test_painless_status_when_cli_not_logged_in(self):
        """When dreamina CLI exists but user is not logged in, get_status() returns UNAVAILABLE."""
        tool = DreaminaCliVideo()
        mock_proc = MagicMock()
        mock_proc.returncode = 1

        with patch.object(tool, "_resolve_cli_path", return_value="/usr/bin/dreamina"):
            with patch("subprocess.run", return_value=mock_proc):
                status = tool.get_status()
                assert status == ToolStatus.UNAVAILABLE

    def test_estimate_cost_is_zero(self):
        tool = DreaminaCliVideo()
        assert tool.estimate_cost({"prompt": "test"}) == 0.0
