"""Contract coverage for the first-party MiniMax video provider.

These tests patch the live ``requests`` module so the shared import remains
available to the rest of the test suite.
"""

from __future__ import annotations

import pytest
import requests

from tools.base_tool import ToolStatus


class _FakeResponse:
    def __init__(self, *, json_data=None, content=b""):
        self._json = json_data or {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _isolate_minimax_environment(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_REGION", raising=False)
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)


def _h3_success_task(task_id="task-h3"):
    return {
        "task": {
            "id": task_id,
            "model": "MiniMax-H3",
            "status": "succeeded",
            "error": None,
            "content": {"url": "https://cdn.example/h3.mp4"},
            "resolution": "2K",
            "duration": 5,
            "usage": {
                "total_seconds": 5,
                "input_seconds": 0,
                "output_seconds": 5,
                "image_count": 0,
            },
            "ratio": "16:9",
            "task_type": "video_generation",
            "modality": "text_to_video",
        }
    }


def test_minimax_video_is_discovered_as_direct_provider():
    from tools.tool_registry import ToolRegistry
    from tools.video.minimax_video import DEFAULT_MODEL, MODELS

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("minimax_video")
    assert tool is not None
    assert tool.provider == "minimax"
    assert tool.capability == "video_generation"
    assert tool.dependencies == ["env:MINIMAX_API_KEY"]
    assert DEFAULT_MODEL == "MiniMax-H3"
    assert MODELS == [
        "MiniMax-H3",
        "MiniMax-Hailuo-2.3",
        "MiniMax-Hailuo-2.3-Fast",
        "MiniMax-Hailuo-02",
        "T2V-01-Director",
        "T2V-01",
        "I2V-01-Director",
        "I2V-01-live",
        "I2V-01",
    ]


def test_minimax_video_unavailable_without_key(monkeypatch):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert MiniMaxVideo().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    assert MiniMaxVideo().get_status() == ToolStatus.AVAILABLE


def test_minimax_video_region_routing(monkeypatch):
    from tools.video.minimax_video import MiniMaxVideo

    tool = MiniMaxVideo()
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
    monkeypatch.delenv("MINIMAX_REGION", raising=False)
    assert tool._base_url() == "https://api.minimax.io"

    monkeypatch.setenv("MINIMAX_REGION", "global_en")
    assert tool._base_url() == "https://api.minimax.io"

    monkeypatch.setenv("MINIMAX_REGION", "cn_zh")
    assert tool._base_url() == "https://api.minimaxi.com"

    monkeypatch.setenv("MINIMAX_BASE_URL", "https://proxy.example.com/")
    assert tool._base_url() == "https://proxy.example.com"


def test_minimax_h3_text_to_video_v2_contract(monkeypatch, tmp_path):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setenv("MINIMAX_REGION", "global")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post_url"] = url
        calls["post_headers"] = headers
        calls["post_payload"] = json
        return _FakeResponse(json_data={"task_id": "task-h3"})

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.setdefault("get_urls", []).append(url)
        if url.endswith("/v2/query/video_generation/task-h3"):
            return _FakeResponse(json_data=_h3_success_task())
        return _FakeResponse(content=b"h3 video bytes")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    output_path = tmp_path / "h3.mp4"
    result = MiniMaxVideo().execute(
        {
            "prompt": "A calm product shot, slow dolly-in",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert calls["post_url"] == "https://api.minimax.io/v2/video_generation"
    assert calls["post_headers"]["Authorization"] == "Bearer test-minimax-key"
    assert calls["post_payload"] == {
        "model": "MiniMax-H3",
        "content": [
            {"type": "text", "text": "A calm product shot, slow dolly-in"},
        ],
        "resolution": "2K",
        "duration": 5,
        "ratio": "16:9",
    }
    assert (
        "https://api.minimax.io/v2/query/video_generation/task-h3" in calls["get_urls"]
    )
    assert output_path.read_bytes() == b"h3 video bytes"
    assert result.data["api_version"] == "v2"
    assert result.data["task"]["status"] == "succeeded"
    assert result.model == "MiniMax-H3"


def test_minimax_h3_reference_content_and_cn_watermark(monkeypatch, tmp_path):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setenv("MINIMAX_REGION", "cn")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["payload"] = json
        return _FakeResponse(json_data={"task_id": "task-reference"})

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/v2/query/video_generation/task-reference"):
            task = _h3_success_task("task-reference")
            task["task"]["ratio"] = "adaptive"
            task["task"]["modality"] = "reference_to_video"
            return _FakeResponse(json_data=task)
        return _FakeResponse(content=b"reference video bytes")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    result = MiniMaxVideo().execute(
        {
            "prompt": "Keep the character and camera rhythm consistent",
            "operation": "reference_to_video",
            "reference_image_urls": ["https://cdn.example/reference.png"],
            "reference_video_url": "https://cdn.example/reference.mp4",
            "reference_audio_urls": ["https://cdn.example/reference.wav"],
            "aigc_watermark": True,
            "output_path": str(tmp_path / "reference.mp4"),
        }
    )

    assert result.success, result.error
    assert calls["url"] == "https://api.minimaxi.com/v2/video_generation"
    assert calls["payload"]["aigc_watermark"] is True
    assert calls["payload"]["ratio"] == "adaptive"
    assert [
        (item["type"], item.get("role")) for item in calls["payload"]["content"]
    ] == [
        ("text", None),
        ("image_url", "reference_image"),
        ("video_url", "reference_video"),
        ("audio_url", "reference_audio"),
    ]


def test_minimax_h3_validates_frame_and_audio_rules(monkeypatch):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    tool = MiniMaxVideo()

    missing_last = tool.execute(
        {
            "prompt": "Transition between these frames",
            "operation": "first_last_frame_to_video",
            "first_frame_image": "https://cdn.example/first.png",
        }
    )
    assert not missing_last.success
    assert "last_frame_image" in missing_last.error

    audio_only = tool.execute(
        {
            "prompt": "Follow this rhythm",
            "operation": "reference_to_video",
            "reference_audio_urls": ["https://cdn.example/reference.wav"],
        }
    )
    assert not audio_only.success
    assert "requires at least one reference image or video" in audio_only.error


def test_minimax_h3_normalizes_selector_duration_and_first_last_frames(monkeypatch):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    tool = MiniMaxVideo()
    payload, error = tool._build_v2_payload(
        {
            "prompt": "Move smoothly between these frames",
            "operation": "first_last_frame_to_video",
            "first_frame_image": "https://cdn.example/first.png",
            "last_frame_image": "https://cdn.example/last.png",
            "duration": "10",
            "aspect_ratio": "9:16",
        },
        "https://api.minimax.io",
    )

    assert error is None
    assert payload["duration"] == 10
    assert payload["ratio"] == "9:16"
    assert [item.get("role") for item in payload["content"]] == [
        None,
        "first_frame",
        "last_frame",
    ]
    assert (
        tool.estimate_cost(
            {
                "duration": "10",
                "reference_image_urls": [
                    f"https://cdn.example/{index}.png" for index in range(6)
                ],
            }
        )
        == 1.33
    )


def test_minimax_hailuo_text_to_video_v1_contract(monkeypatch, tmp_path):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setenv("MINIMAX_REGION", "global")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post_url"] = url
        calls["post_payload"] = json
        return _FakeResponse(
            json_data={"task_id": "task-v1", "base_resp": {"status_code": 0}}
        )

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.setdefault("get", []).append((url, params))
        if url.endswith("/v1/query/video_generation"):
            return _FakeResponse(
                json_data={
                    "status": "Success",
                    "file_id": "file-v1",
                    "base_resp": {"status_code": 0},
                }
            )
        if url.endswith("/v1/files/retrieve"):
            return _FakeResponse(
                json_data={
                    "file": {"download_url": "https://cdn.example/v1.mp4"},
                    "base_resp": {"status_code": 0},
                }
            )
        return _FakeResponse(content=b"v1 video bytes")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    output_path = tmp_path / "v1.mp4"
    result = MiniMaxVideo().execute(
        {
            "prompt": "A calm product shot",
            "model": "MiniMax-Hailuo-2.3",
            "duration": 6,
            "resolution": "1080P",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert calls["post_url"] == "https://api.minimax.io/v1/video_generation"
    assert calls["post_payload"] == {
        "model": "MiniMax-Hailuo-2.3",
        "prompt": "A calm product shot",
        "duration": 6,
        "resolution": "1080P",
    }
    get_urls = [url for url, _params in calls["get"]]
    assert "https://api.minimax.io/v1/query/video_generation" in get_urls
    assert "https://api.minimax.io/v1/files/retrieve" in get_urls
    assert output_path.read_bytes() == b"v1 video bytes"
    assert result.data["api_version"] == "v1"
    assert result.data["file_id"] == "file-v1"


def test_minimax_hailuo_image_to_video_prompt_is_optional(monkeypatch, tmp_path):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["payload"] = json
        return _FakeResponse(
            json_data={"task_id": "task-v1-image", "base_resp": {"status_code": 0}}
        )

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/v1/query/video_generation"):
            return _FakeResponse(
                json_data={
                    "status": "Success",
                    "file_id": "file-v1-image",
                    "base_resp": {"status_code": 0},
                }
            )
        if url.endswith("/v1/files/retrieve"):
            return _FakeResponse(
                json_data={
                    "file": {"download_url": "https://cdn.example/v1-image.mp4"},
                    "base_resp": {"status_code": 0},
                }
            )
        return _FakeResponse(content=b"v1 image video bytes")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    result = MiniMaxVideo().execute(
        {
            "operation": "image_to_video",
            "model": "I2V-01",
            "first_frame_image": "https://cdn.example/first.png",
            "output_path": str(tmp_path / "v1-image.mp4"),
        }
    )

    assert result.success, result.error
    assert calls["payload"] == {
        "model": "I2V-01",
        "first_frame_image": "https://cdn.example/first.png",
    }


def test_video_selector_routes_reference_image_to_minimax_h3(monkeypatch, tmp_path):
    from tools.video import _shared
    from tools.video.minimax_video import MiniMaxVideo
    from tools.video.video_selector import VideoSelector

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        _shared,
        "upload_image_fal",
        lambda _path: "https://cdn.example/reference.png",
    )
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["payload"] = json
        return _FakeResponse(json_data={"task_id": "task-selector"})

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/v2/query/video_generation/task-selector"):
            return _FakeResponse(json_data=_h3_success_task("task-selector"))
        return _FakeResponse(content=b"selector video bytes")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    tool = MiniMaxVideo()
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    monkeypatch.setattr(
        selector,
        "_select_best_tool",
        lambda _inputs, _candidates, _context: (tool, None),
    )

    result = selector.execute(
        {
            "prompt": "A calm product shot",
            "operation": "image_to_video",
            "reference_image_path": str(tmp_path / "reference.png"),
            "output_path": str(tmp_path / "selector.mp4"),
        }
    )

    assert result.success, result.error
    first_frame = calls["payload"]["content"][1]
    assert first_frame == {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example/reference.png"},
        "role": "first_frame",
    }
    assert result.data["selected_tool"] == "minimax_video"


def test_minimax_video_surfaces_v1_base_resp_error(monkeypatch):
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            json_data={"base_resp": {"status_code": 1004, "status_msg": "auth failed"}}
        )

    monkeypatch.setattr(requests, "post", fake_post)

    result = MiniMaxVideo().execute({"prompt": "hi", "model": "MiniMax-Hailuo-2.3"})
    assert not result.success
    assert "1004" in result.error


@pytest.mark.parametrize("model", ["MiniMax-H3", "MiniMax-Hailuo-2.3"])
def test_polling_timeout_is_bounded_and_preserves_task_id(monkeypatch, model):
    import tools.video.minimax_video as minimax_module
    from tools.video.minimax_video import MiniMaxVideo

    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            json_data={"task_id": "recoverable-task", "base_resp": {"status_code": 0}}
        ),
    )
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("deadline must stop polling"),
    )

    class _ExpiredClock:
        def __init__(self):
            self._ticks = iter([0.0, 2.0])

        @staticmethod
        def time():
            return 0.0

        def monotonic(self):
            return next(self._ticks)

        @staticmethod
        def sleep(_seconds):
            return None

    monkeypatch.setattr(minimax_module, "time", _ExpiredClock())

    result = MiniMaxVideo().execute(
        {"prompt": "A camera move", "model": model, "timeout_seconds": 1}
    )

    assert not result.success
    assert "timed out" in (result.error or "")
    assert result.data["task_id"] == "recoverable-task"
    assert result.data["status"] == "timed_out"
