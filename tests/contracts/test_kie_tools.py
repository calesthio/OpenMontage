"""Contract tests for the KIE AI multi-model gateway (kie_video, kie_image, kie_tts, kie_music)."""

import pytest

from tools import kie_client
from tools.audio.kie_music import KieMusic
from tools.audio.kie_tts import KieTTS
from tools.base_tool import BaseTool, ExecutionMode, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.graphics.kie_image import KieImage
from tools.video.kie_video import KieVideo

TOOLS = [KieVideo, KieImage, KieTTS, KieMusic]


@pytest.fixture(autouse=True)
def _clear_kie_env(monkeypatch):
    for key in kie_client.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("cls", TOOLS, ids=lambda cls: cls.name)
class TestContract:
    def test_contract_identity(self, cls):
        tool = cls()
        assert issubclass(cls, BaseTool)
        assert tool.provider == "kie"
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API
        assert tool.execution_mode == ExecutionMode.SYNC
        assert "env:KIE_API_KEY" in tool.dependencies

    def test_status_and_key_aliases(self, cls, monkeypatch):
        assert cls().get_status() == ToolStatus.UNAVAILABLE
        for key in kie_client.ENV_KEYS:
            monkeypatch.setenv(key, "test")
            assert cls().get_status() == ToolStatus.AVAILABLE
            monkeypatch.delenv(key)

    def test_no_key_fails_before_network(self, cls):
        inputs = {"prompt": "test"} if cls is not KieTTS else {"text": "test"}
        if cls is KieMusic:
            inputs = {"style": "test", "duration_seconds": 30}
        result = cls().execute(inputs)
        assert not result.success
        assert "KIE_API_KEY" in result.error

    def test_resume_task_id_is_a_declared_input(self, cls):
        assert "resume_task_id" in cls().input_schema["properties"]

    def test_timeout_is_not_retryable(self, cls):
        """createTask is not idempotent -- see docs/PROVIDERS.md 'KIE AI'."""
        assert "timeout" not in cls().retry_policy.retryable_errors


def test_registry_discovers_kie_tools(isolated_tool_registry):
    isolated_tool_registry.discover()
    assert isolated_tool_registry.get("kie_video") is not None
    assert isolated_tool_registry.get("kie_image") is not None
    assert isolated_tool_registry.get("kie_tts") is not None
    assert isolated_tool_registry.get("kie_music") is not None


def test_image_selector_discovers_kie_image(isolated_tool_registry, monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "test")
    isolated_tool_registry.discover()
    providers = [t.name for t in isolated_tool_registry.get_by_capability("image_generation")]
    assert "kie_image" in providers


def test_video_selector_discovers_kie_video(isolated_tool_registry, monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "test")
    isolated_tool_registry.discover()
    providers = [t.name for t in isolated_tool_registry.get_by_capability("video_generation")]
    assert "kie_video" in providers


def test_tts_selector_discovers_kie_tts(isolated_tool_registry, monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "test")
    isolated_tool_registry.discover()
    providers = [t.name for t in isolated_tool_registry.get_by_capability("tts")]
    assert "kie_tts" in providers


def test_music_capability_discovers_kie_music(isolated_tool_registry, monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "test")
    isolated_tool_registry.discover()
    providers = [t.name for t in isolated_tool_registry.get_by_capability("music_generation")]
    assert "kie_music" in providers
