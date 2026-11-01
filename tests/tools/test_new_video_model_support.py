"""Contracts for the August 2026 video-model provider refresh."""

from __future__ import annotations

import requests


class _Response:
    def __init__(self, payload=None, content=b"video", status_code=200):
        self.payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = str(self.payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _queue_mocks(monkeypatch):
    calls = {"posts": []}

    def post(url, headers=None, json=None, timeout=None):
        calls["posts"].append((url, json))
        return _Response(
            {"status_url": "https://status", "response_url": "https://result"}
        )

    def get(url, headers=None, timeout=None, params=None):
        if url == "https://status":
            return _Response({"status": "COMPLETED"})
        if url == "https://result":
            return _Response({"video": {"url": "https://video"}, "seed": 9})
        return _Response(content=b"fake mp4")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("time.sleep", lambda _: None)
    return calls


def test_fal_seedance_25_uses_current_endpoint_and_reference_fields(
    monkeypatch, tmp_path
):
    from tools.video.seedance_video import SeedanceVideo

    monkeypatch.setenv("FAL_KEY", "test")
    calls = _queue_mocks(monkeypatch)
    result = SeedanceVideo().execute(
        {
            "prompt": "Use @Image1 as the hero",
            "model_version": "2.5",
            "operation": "reference_to_video",
            "duration": "30",
            "reference_image_urls": ["https://image"],
            "reference_video_urls": ["https://motion"],
            "reference_audio_urls": ["https://voice"],
            "output_path": str(tmp_path / "seedance25.mp4"),
        }
    )
    assert result.success, result.error
    url, payload = calls["posts"][0]
    assert url.endswith("/bytedance/seedance-2.5/reference-to-video")
    assert payload["image_urls"] == ["https://image"]
    assert payload["video_urls"] == ["https://motion"]
    assert payload["audio_urls"] == ["https://voice"]
    assert payload["duration"] == "30"


def test_fal_seedance_20_reference_to_video_uses_fal_reference_fields(
    monkeypatch, tmp_path
):
    # fal's 2.0 reference-to-video endpoint reads image_urls / video_urls / audio_urls,
    # same as 2.5; reference_*_urls is ignored and the request 422s with
    # "At least one reference image or video is required."
    from tools.video.seedance_video import SeedanceVideo

    monkeypatch.setenv("FAL_KEY", "test")
    calls = _queue_mocks(monkeypatch)
    result = SeedanceVideo().execute(
        {
            "prompt": "Macro shot of the ball on this court",
            "model_version": "2.0",
            "operation": "reference_to_video",
            "reference_image_urls": ["https://image"],
            "reference_video_urls": ["https://motion"],
            "reference_audio_urls": ["https://voice"],
            "output_path": str(tmp_path / "seedance20.mp4"),
        }
    )
    assert result.success, result.error
    url, payload = calls["posts"][0]
    assert url.endswith("/bytedance/seedance-2.0/reference-to-video")
    assert payload["image_urls"] == ["https://image"]
    assert payload["video_urls"] == ["https://motion"]
    assert payload["audio_urls"] == ["https://voice"]
    for stale in ("reference_image_urls", "reference_video_urls", "reference_audio_urls"):
        assert stale not in payload


def test_fal_gemini_omni_and_minimax_h3_are_discovered_and_submit(
    monkeypatch, tmp_path
):
    from tools.tool_registry import ToolRegistry
    from tools.video.gemini_omni_fal import GeminiOmniFalVideo
    from tools.video.minimax_fal_video import MiniMaxFalVideo

    monkeypatch.setenv("FAL_KEY", "test")
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("gemini_omni_fal") is not None
    assert registry.get("minimax_fal_video") is not None

    calls = _queue_mocks(monkeypatch)
    gemini = GeminiOmniFalVideo().execute(
        {
            "prompt": "Animate <IMAGE_REF_0>",
            "operation": "image_to_video",
            "image_url": "https://image",
            "output_path": str(tmp_path / "omni.mp4"),
        }
    )
    assert gemini.success, gemini.error
    assert calls["posts"][0][0].endswith("/google/gemini-omni-flash/image-to-video")

    calls = _queue_mocks(monkeypatch)
    edited = GeminiOmniFalVideo().execute(
        {
            "prompt": "Remove the sign",
            "operation": "edit_video",
            "video_url": "https://video-input",
            "output_path": str(tmp_path / "omni-edit.mp4"),
        }
    )
    assert edited.success, edited.error
    assert calls["posts"][0][0].endswith("/google/gemini-omni-flash/edit")
    assert calls["posts"][0][1] == {
        "prompt": "Remove the sign",
        "video_url": "https://video-input",
    }

    calls = _queue_mocks(monkeypatch)
    minimax = MiniMaxFalVideo().execute(
        {
            "prompt": "A dolly shot",
            "duration": 15,
            "output_path": str(tmp_path / "h3.mp4"),
        }
    )
    assert minimax.success, minimax.error
    assert calls["posts"][0][0].endswith("/fal-ai/minimax/hailuo-03/text-to-video")


def test_runway_supports_all_three_current_model_identifiers(monkeypatch, tmp_path):
    from tools.video.runway_video import RunwayVideo

    monkeypatch.setenv("RUNWAY_API_KEY", "test")
    calls = {"posts": []}

    def post(url, headers=None, json=None, timeout=None):
        calls["posts"].append((url, json))
        return _Response({"id": "task"})

    def get(url, headers=None, timeout=None, params=None):
        if url.endswith("/tasks/task"):
            return _Response({"status": "SUCCEEDED", "output": ["https://video"]})
        return _Response(content=b"fake mp4")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("time.sleep", lambda _: None)
    for model, duration in (
        ("seedance2_5", 30),
        ("gemini_omni_flash", 10),
        ("hailuo3", 15),
    ):
        result = RunwayVideo().execute(
            {
                "prompt": "A cinematic shot",
                "model": model,
                "duration": duration,
                "output_path": str(tmp_path / f"{model}.mp4"),
            }
        )
        assert result.success, result.error
        assert calls["posts"][-1][1]["model"] == model


def test_runway_uses_each_models_official_request_shape(monkeypatch, tmp_path):
    from tools.video.runway_video import RunwayVideo

    monkeypatch.setenv("RUNWAY_API_KEY", "test")
    calls = {"posts": []}

    def post(url, headers=None, json=None, timeout=None):
        calls["posts"].append((url, json))
        return _Response({"id": "task"})

    def get(url, headers=None, timeout=None, params=None):
        if url.endswith("/tasks/task"):
            return _Response({"status": "SUCCEEDED", "output": ["https://video"]})
        return _Response(content=b"fake mp4")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("time.sleep", lambda _: None)
    tool = RunwayVideo()

    result = tool.execute(
        {
            "prompt": "Use the references",
            "model": "seedance2_5",
            "duration": 12,
            "resolution": "480p",
            "ratio": "9:16",
            "generate_audio": True,
            "reference_image_urls": ["https://image"],
            "reference_video_urls": ["https://motion"],
            "reference_audio_urls": ["https://audio"],
            "output_path": str(tmp_path / "seedance.mp4"),
        }
    )
    assert result.success, result.error
    payload = calls["posts"][-1][1]
    assert payload["ratio"] == "480:854"
    assert payload["audio"] is True
    assert payload["references"] == [{"uri": "https://image"}]
    assert payload["referenceVideos"] == [{"type": "video", "uri": "https://motion"}]
    assert payload["referenceAudio"] == [{"type": "audio", "uri": "https://audio"}]
    assert "resolution" not in payload

    result = tool.execute(
        {
            "prompt": "Restyle the motion",
            "model": "hailuo3",
            "operation": "video_to_video",
            "duration": 8,
            "resolution": "768P",
            "video_url": "https://source",
            "reference_image_urls": ["https://image"],
            "output_path": str(tmp_path / "hailuo.mp4"),
        }
    )
    assert result.success, result.error
    payload = calls["posts"][-1][1]
    assert payload["promptVideo"] == "https://source"
    assert payload["resolution"] == "768P"
    assert payload["references"] == [{"uri": "https://image"}]
    assert "videoUri" not in payload

    result = tool.execute(
        {
            "prompt": "Remove the sign",
            "model": "gemini_omni_flash",
            "operation": "video_to_video",
            "video_url": "https://source",
            "reference_image_urls": ["https://image"],
            "output_path": str(tmp_path / "gemini.mp4"),
        }
    )
    assert result.success, result.error
    payload = calls["posts"][-1][1]
    assert payload["videoUri"] == "https://source"
    assert payload["references"] == [{"uri": "https://image"}]
    assert "duration" not in payload
    assert "ratio" not in payload


def test_comfyui_partner_workflows_and_local_h3_metadata():
    from tools.video.comfyui_video import ComfyUIVideo

    tool = ComfyUIVideo()
    for family, node_class in (
        ("gemini_omni_flash", "GeminiVideoOmni"),
        ("seedance_2.5", "ByteDance2TextToVideoNode"),
        ("minimax_h3_api", "MinimaxHailuo03TextToVideoNode"),
    ):
        workflow, output_node = tool._build_partner_t2v(
            {"prompt": "A product reveal", "duration": 5},
            42,
            __import__("pathlib").Path("clip.mp4"),
            family,
        )
        assert workflow["1"]["class_type"] == node_class
        assert workflow["2"]["class_type"] == "SaveVideo"
        assert output_node == "2"

    local = tool.execute({"prompt": "x", "model_family": "minimax_h3_local"})
    assert not local.success
    assert local.data["model"] == "MiniMax-H3"
    assert len(local.data["model_stack"]) == 4
