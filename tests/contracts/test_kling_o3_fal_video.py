"""Offline contracts for Kling O3 image-reference video via fal.ai."""
import base64
import json

import pytest

from tools.video.kling_o3_fal_video import KlingO3FalVideo
from tools.video.kling_video import KlingVideo


def test_reference_route_keeps_first_frame_separate_from_identity_images(tmp_path):
    face = tmp_path / "face.png"
    face.write_bytes(b"face")
    tool = KlingO3FalVideo()
    model, operation, endpoint, payload = tool.build_request({
        "model": "kling-o3-standard", "operation": "reference_to_video",
        "prompt": "@Image1 walks through the garden", "image_paths": [str(face)],
        "start_image_url": "https://example.com/first.png", "duration": "5",
        "aspect_ratio": "9:16", "generate_audio": False,
    })
    assert (model, operation, endpoint) == (
        "kling-o3-standard", "reference_to_video",
        "fal-ai/kling-video/o3/standard/reference-to-video",
    )
    assert payload["start_image_url"] == "https://example.com/first.png"
    assert payload["image_urls"] == ["data:image/png;base64," + base64.b64encode(b"face").decode()]
    assert payload["generate_audio"] is False
    assert payload["duration"] == "5"
    assert payload["aspect_ratio"] == "9:16"


def test_pro_route_and_invalid_duration_are_checked_before_submission():
    tool = KlingO3FalVideo()
    model, operation, endpoint, payload = tool.build_request({
        "model": "kling-o3-pro", "prompt": "A cinematic walk",
        "image_urls": ["https://example.com/subject.png"], "duration": "12",
    })
    assert (model, operation, endpoint) == (
        "kling-o3-pro", "reference_to_video", "fal-ai/kling-video/o3/pro/reference-to-video",
    )
    assert payload["image_urls"] == ["https://example.com/subject.png"]
    with pytest.raises(Exception):
        tool.build_request({"prompt": "A walk", "duration": "20"})


def test_legacy_adapter_is_not_replaced():
    assert KlingVideo.name == "kling_video"
    assert KlingVideo.input_schema["properties"]["model_variant"]["default"] == "v3/standard"
    assert "reference_to_video" not in KlingVideo.input_schema["properties"]["operation"]["enum"]


def test_submit_once_checkpoint_and_resume_without_duplicate_charge(monkeypatch, tmp_path):
    calls = []
    endpoint = "fal-ai/kling-video/o3/standard/reference-to-video"
    base = f"https://queue.fal.run/{endpoint}/requests/owned-123"

    def fake_request(method, url, *, headers, **kwargs):
        calls.append((method, url))
        if method == "POST":
            assert kwargs["json"]["generate_audio"] is False
            return {"request_id": "owned-123", "status_url": base + "/status", "response_url": base}
        if url.endswith("/status"):
            return {"status": "COMPLETED", "request_id": "owned-123"}
        return {"video": {"url": "https://example.com/master.mp4"}}

    def fake_download(url, path):
        path.write_bytes(b"offline-video")
        return str(path)

    monkeypatch.setenv("FAL_KEY", "offline-key")
    monkeypatch.setattr("tools.fal_media.request_json", fake_request)
    monkeypatch.setattr("tools.fal_media.download", fake_download)
    output = tmp_path / "master.mp4"
    checkpoint = tmp_path / "job.json"
    tool = KlingO3FalVideo()
    result = tool.execute({
        "prompt": "A walk", "image_urls": ["https://example.com/ref.png"],
        "generate_audio": False, "job_path": str(checkpoint), "output_path": str(output),
        "poll_interval": 0.01,
    })
    assert result.success, result.error
    assert json.loads(checkpoint.read_text())["request_id"] == "owned-123"
    resumed = tool.execute({"resume_job": result.data["resume_job"], "output_path": str(output), "poll_interval": 0.01})
    assert resumed.success, resumed.error
    assert calls.count(("POST", f"https://queue.fal.run/{endpoint}")) == 1
    assert output.read_bytes() == b"offline-video"
