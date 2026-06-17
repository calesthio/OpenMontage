"""Unit coverage for the EvoLink video provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry
from tools.video.evolink_video import EvoLinkVideo
from tools.video.video_selector import VideoSelector


def test_evolink_video_identity():
    tool = EvoLinkVideo()
    info = tool.get_info()

    assert info["name"] == "evolink_video"
    assert info["tier"] == "generate"
    assert info["capability"] == "video_generation"
    assert info["provider"] == "evolink"
    assert "text_to_video" in info["capabilities"]
    assert "image_to_video" in info["capabilities"]


def test_evolink_video_status_uses_evolink_api_key(monkeypatch):
    monkeypatch.delenv("EVOLINK_API_KEY", raising=False)
    assert EvoLinkVideo().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("EVOLINK_API_KEY", "test-key")
    assert EvoLinkVideo().get_status() == ToolStatus.AVAILABLE


def test_evolink_text_payload_maps_to_current_api_fields():
    payload = EvoLinkVideo()._build_payload(
        {
            "prompt": "A cinematic product reveal",
            "duration": "4",
            "resolution": "480p",
            "aspect_ratio": "9:16",
            "generate_audio": False,
            "web_search": True,
        }
    )

    assert payload == {
        "model": "seedance-2.0-text-to-video",
        "prompt": "A cinematic product reveal",
        "duration": 4,
        "quality": "480p",
        "aspect_ratio": "9:16",
        "generate_audio": False,
        "content_filter": True,
        "model_params": {"web_search": True},
    }


def test_evolink_image_payload_accepts_selector_reference_alias():
    payload = EvoLinkVideo()._build_payload(
        {
            "prompt": "Animate this first frame",
            "operation": "image_to_video",
            "model_variant": "fast",
            "reference_image_url": "https://example.com/start.png",
            "end_image_url": "https://example.com/end.png",
        }
    )

    assert payload["model"] == "seedance-2.0-fast-image-to-video"
    assert payload["image_urls"] == [
        "https://example.com/start.png",
        "https://example.com/end.png",
    ]


def test_video_selector_discovers_evolink_provider():
    reg = ToolRegistry()
    reg.register(EvoLinkVideo())
    reg.register(VideoSelector())

    providers = {tool.provider for tool in reg.get_by_capability("video_generation")}
    assert "evolink" in providers


def test_evolink_execute_submits_polls_and_downloads(monkeypatch, tmp_path):
    monkeypatch.setenv("EVOLINK_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.evolink_video.time.sleep", lambda _: None)

    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class FakeResponse:
        def __init__(
            self,
            payload: dict[str, Any] | None = None,
            content: bytes = b"",
        ) -> None:
            self._payload = payload or {}
            self.content = content

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("post", url, kwargs.get("json")))
        return FakeResponse(
            {
                "id": "task-unified-123-test",
                "status": "pending",
                "model": "seedance-2.0-text-to-video",
            }
        )

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("get", url, None))
        if url.endswith("/v1/tasks/task-unified-123-test"):
            return FakeResponse(
                {
                    "id": "task-unified-123-test",
                    "status": "completed",
                    "results": ["https://cdn.example.com/video.mp4"],
                    "usage": {"credits_reserved": 1},
                }
            )
        return FakeResponse(content=b"fake mp4 bytes")

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    output_path = tmp_path / "evolink.mp4"
    result = EvoLinkVideo().execute(
        {
            "prompt": "A clean motion graphics title card",
            "duration": 4,
            "resolution": "480p",
            "generate_audio": False,
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert result.model == "seedance-2.0-text-to-video"
    assert result.data["provider"] == "evolink"
    assert result.data["task_id"] == "task-unified-123-test"
    assert result.artifacts == [str(output_path)]
    assert Path(output_path).read_bytes() == b"fake mp4 bytes"
    assert calls[0] == (
        "post",
        "https://api.evolink.ai/v1/videos/generations",
        {
            "model": "seedance-2.0-text-to-video",
            "prompt": "A clean motion graphics title card",
            "duration": 4,
            "quality": "480p",
            "aspect_ratio": "16:9",
            "generate_audio": False,
            "content_filter": True,
        },
    )
