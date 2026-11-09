"""Contract tests for the DreamAPI provider tools."""

from pathlib import Path

import pytest

from tools.audio.dreamapi_tts import DreamApiTts
from tools.avatar.dreamapi_avatar import DreamApiAvatar
from tools.base_tool import BaseTool, ToolStatus
from tools.dreamapi_client import DreamApiError, run_task
from tools.dreamapi_models import MODELS, build_body
from tools.graphics.dreamapi_image import DreamApiImage
from tools.video.dreamapi_video import DreamApiVideo

TOOLS = [DreamApiImage, DreamApiVideo, DreamApiAvatar, DreamApiTts]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _clear_key(monkeypatch):
    monkeypatch.delenv("DREAMAPI_API_KEY", raising=False)


@pytest.mark.parametrize("cls", TOOLS, ids=lambda cls: cls.name)
class TestContract:
    def test_identity(self, cls):
        tool = cls()
        assert issubclass(cls, BaseTool)
        assert tool.provider == "dreamapi"
        assert "env:DREAMAPI_API_KEY" in tool.dependencies
        assert "dreamapi" in tool.agent_skills
        assert tool.input_schema["required"] == ["model"]

    def test_missing_key_fails_before_network(self, cls):
        result = cls().execute({"model": tool_model(cls)})
        assert not result.success
        assert "DREAMAPI_API_KEY" in result.error

    def test_status_and_catalog(self, cls, monkeypatch):
        assert cls().get_status() == ToolStatus.UNAVAILABLE
        monkeypatch.setenv("DREAMAPI_API_KEY", "local-test-key")
        tool = cls()
        assert tool.get_status() == ToolStatus.AVAILABLE
        catalog = tool.get_info()["model_catalog"]
        assert catalog
        assert set(catalog) <= set(MODELS)


def tool_model(cls) -> str:
    return cls().input_schema["properties"]["model"]["enum"][0]


def test_catalog_covers_every_public_dreamapi_tool():
    assert len(MODELS) >= 36
    assert len({spec["capability"] for spec in MODELS.values()}) == 4


def test_model_id_is_not_sent_as_a_body_field():
    _spec, body = build_body("wan-2.1-text", {"model": "wan-2.1-text", "prompt": "city", "output_path": "out.mp4"}, "video_generation")
    assert body["prompt"] == "city"
    assert "model" not in body
    with pytest.raises(ValueError, match="duration"):
        build_body("dreamvideo-3-text", {"prompt": "city", "duration": 2}, "video_generation")
    with pytest.raises(ValueError, match="image"):
        build_body("dreamimage-2", {"prompt": "edit"}, "image_generation")
    with pytest.raises(ValueError, match="upper"):
        build_body("try-on", {"model_image": "https://example.com/m.png"}, "image_generation")


def test_resume_does_not_submit(monkeypatch):
    calls = []

    def fake_post(path, body, api_key, timeout=60):
        calls.append(path)
        if path == "/api/getAsyncResult":
            return {"task": {"status": 3, "taskId": body["taskId"]}, "videos": [{"videoUrl": "https://cdn.example/out.mp4"}]}
        raise AssertionError(path)

    monkeypatch.setattr("tools.dreamapi_client.post_json", fake_post)
    result = run_task("/api/async/wan/text_to_video/2.1", {"prompt": "city"}, "k", task_id="task-1", interval=0, timeout=5)
    assert calls == ["/api/getAsyncResult"]
    assert result["task_id"] == "task-1"


def test_registry_discovers_dreamapi(isolated_tool_registry):
    isolated_tool_registry.discover()
    for name in ("dreamapi_image", "dreamapi_video", "dreamapi_avatar", "dreamapi_tts"):
        assert isolated_tool_registry.get(name) is not None


def test_skill_mentions_key():
    text = (PROJECT_ROOT / ".agents" / "skills" / "dreamapi" / "SKILL.md").read_text(encoding="utf-8")
    assert "DREAMAPI_API_KEY" in text


def test_provider_error_is_a_failed_result(monkeypatch):
    monkeypatch.setenv("DREAMAPI_API_KEY", "local-test-key")
    monkeypatch.setattr("tools.dreamapi_tool.execute_catalog", lambda *args, **kwargs: (_ for _ in ()).throw(DreamApiError("boom")))
    result = DreamApiVideo().execute({"model": "wan-2.1-text", "prompt": "city"})
    assert not result.success
    assert "boom" in result.error
