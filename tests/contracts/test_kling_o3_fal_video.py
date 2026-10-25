"""Offline contracts for Kling O3 image-reference video via fal.ai."""
import base64
import json

import pytest

from tools.video.kling_o3_fal_video import KlingO3FalVideo
from tools.video.kling_video import KlingVideo
from tools.tool_registry import ToolRegistry
from tools.video.video_selector import VideoSelector
from tools.base_tool import ToolResult, ToolStatus


@pytest.mark.parametrize("tier", ["standard", "pro", "4k"])
@pytest.mark.parametrize("operation,path", [
    ("text_to_video", "text-to-video"),
    ("image_to_video", "image-to-video"),
    ("reference_to_video", "reference-to-video"),
    ("video_to_video_edit", "video-to-video/edit"),
    ("video_to_video_reference", "video-to-video/reference"),
])
def test_all_o3_routes_are_discoverable(tier, operation, path):
    tool = KlingO3FalVideo()
    assert tool.routes[f"kling-o3-{tier}"][operation] == f"fal-ai/kling-video/o3/{tier}/{path}"
    assert operation in tool.capabilities


def test_catalog_reports_the_contract_snapshot_date():
    tool = KlingO3FalVideo()
    endpoint = tool.routes["kling-o3-4k"]["text_to_video"]
    from tools.fal_media import CONTRACTS
    assert tool.get_info()["model_catalog"]["kling-o3-4k"]["verified_on"] == CONTRACTS[endpoint]["verified_on"]


def test_registry_and_explicit_selector_route(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "offline-key")
    registry = ToolRegistry()
    registry.discover("tools.video")
    o3 = registry.get("kling_o3_fal_video")
    legacy = registry.get("kling_video")
    assert o3 is not None and legacy is not None
    assert o3.get_status() == ToolStatus.AVAILABLE
    candidates = VideoSelector()._filter_candidates({
        "preferred_tool": "kling_o3_fal_video", "hosting_provider": "fal.ai",
        "model": "kling-o3-4k", "operation": "video_to_video_reference",
    }, [o3, legacy])
    assert [candidate.name for candidate in candidates] == ["kling_o3_fal_video"]


@pytest.mark.parametrize("operation,expected", [
    ("video_edit", "video_to_video_edit"),
    ("video_to_video_reference", "video_to_video_reference"),
])
def test_video_selector_v2v_routes(operation, expected):
    tool = KlingO3FalVideo()
    assert operation in VideoSelector.input_schema["properties"]["operation"]["enum"]
    inputs = {"preferred_tool": tool.name, "hosting_provider": "fal.ai",
              "model": "kling-o3-pro", "operation": operation,
              "prompt": "Change the light", "video_url": "https://example.com/source.mp4"}
    assert VideoSelector()._filter_candidates(inputs, [tool]) == [tool]
    assert tool.build_request(inputs)[1] == expected


def test_video_selector_reference_images_are_not_discarded(tmp_path):
    path = tmp_path / "identity.png"
    path.write_bytes(b"identity")
    tool = KlingO3FalVideo()
    _, selected, _, payload = tool.build_request({
        "operation": "reference_to_video", "prompt": "@Image1 walks",
        "reference_image_path": str(path),
        "reference_image_urls": ["https://example.com/outfit.png"],
        "start_image_url": "https://example.com/first.png",
    })
    assert selected == "reference_to_video"
    assert payload["start_image_url"] == "https://example.com/first.png"
    assert payload["image_urls"] == [
        "https://example.com/outfit.png",
        "data:image/png;base64," + base64.b64encode(b"identity").decode(),
    ]


def test_selector_does_not_upload_first_frame_before_o3_validation(monkeypatch, tmp_path):
    first = tmp_path / "first.png"
    first.write_bytes(b"first")
    tool = KlingO3FalVideo()
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    monkeypatch.setattr(selector, "_select_best_tool", lambda *args: (tool, None))
    monkeypatch.setattr("tools.video._shared.upload_image_fal", lambda *_: pytest.fail("unexpected upload"))
    payloads = []
    def fake_execute(inputs):
        payloads.append(tool.build_request(inputs)[3])
        return ToolResult(success=True, data={})
    monkeypatch.setattr(tool, "execute", fake_execute)
    result = selector.execute({
        "preferred_tool": tool.name, "model": "kling-o3-pro", "operation": "image_to_video",
        "prompt": "A walk", "reference_image_path": str(first),
    })
    assert result.success, result.error
    assert payloads[0]["image_url"] == "data:image/png;base64," + base64.b64encode(b"first").decode()


def test_unsupported_selector_media_fails_before_paid_post():
    with pytest.raises(ValueError, match="reference_video_path"):
        KlingO3FalVideo().build_request({
            "operation": "reference_to_video", "prompt": "A walk",
            "reference_video_path": "/path/to/video.mp4",
        })


@pytest.mark.parametrize("operation,payload", [
    ("text_to_video", {"prompt": "A person walks", "duration": "5"}),
    ("image_to_video", {"prompt": "A person walks", "image_url": "https://example.com/start.png"}),
    ("reference_to_video", {"prompt": "@Image1 walks", "image_urls": ["https://example.com/ref.png"]}),
    ("video_to_video_edit", {"prompt": "Change the weather", "video_url": "https://example.com/input.mp4"}),
    ("video_to_video_reference", {"prompt": "Keep camera movement", "video_url": "https://example.com/input.mp4"}),
])
def test_native_request_for_every_mode(operation, payload):
    tool = KlingO3FalVideo()
    _, selected, _, native = tool.build_request({"model": "kling-o3-pro", "operation": operation, **payload})
    assert selected == operation
    assert native == payload


def test_ref_mode_rejects_ambiguous_image_url():
    with pytest.raises(ValueError, match="start_image_url"):
        KlingO3FalVideo().build_request({
            "operation": "reference_to_video", "prompt": "A person walks",
            "image_url": "https://example.com/first.png",
        })


@pytest.mark.parametrize("operation", [
    "text_to_video", "image_to_video", "reference_to_video",
    "video_to_video_edit", "video_to_video_reference",
])
def test_each_mode_rejects_invalid_native_fields_before_paid_submit(monkeypatch, operation):
    monkeypatch.setenv("FAL_KEY", "offline-key")
    def forbidden_request(*args, **kwargs):
        pytest.fail("invalid input reached the paid fal queue")
    monkeypatch.setattr("tools.fal_media.request_json", forbidden_request)
    result = KlingO3FalVideo().execute({
        "model": "kling-o3-4k", "operation": operation,
        "prompt": "A person walks", "video_url": "https://example.com/video.mp4",
        "image_url": "https://example.com/start.png", "duration": "90",
    })
    assert not result.success


def test_local_first_frame_for_image_to_video(tmp_path):
    first = tmp_path / "first.png"
    first.write_bytes(b"first")
    _, _, _, payload = KlingO3FalVideo().build_request({
        "operation": "image_to_video", "prompt": "Walk", "image_path": str(first),
    })
    assert payload["image_url"] == "data:image/png;base64," + base64.b64encode(b"first").decode()


@pytest.mark.parametrize("operation", ["text_to_video", "image_to_video", "reference_to_video"])
def test_generation_rejects_prompt_and_multi_prompt_together(operation):
    inputs = {"operation": operation, "prompt": "A walk", "multi_prompt": [{"prompt": "A run"}]}
    if operation == "image_to_video":
        inputs["image_url"] = "https://example.com/start.png"
    with pytest.raises(ValueError, match="prompt or multi_prompt"):
        KlingO3FalVideo().build_request(inputs)


def test_multishot_native_payload_passes_contract():
    _, _, _, payload = KlingO3FalVideo().build_request({
        "operation": "text_to_video", "multi_prompt": [
            {"prompt": "A walk", "duration": "3"},
            {"prompt": "A run", "duration": "2"},
        ], "duration": "5", "shot_type": "customize",
    })
    assert len(payload["multi_prompt"]) == 2


def test_text_and_image_defaults_are_not_reference_route():
    tool = KlingO3FalVideo()
    assert tool.build_request({"prompt": "A walk"})[1] == "text_to_video"
    assert tool.build_request({"prompt": "A walk", "image_url": "https://example.com/first.png"})[1] == "image_to_video"
    assert tool.build_request({"prompt": "@Image1 walks", "image_urls": ["https://example.com/ref.png"]})[1] == "reference_to_video"


def test_ambiguous_post_failure_is_not_retried_and_warns_about_resubmission(monkeypatch):
    calls = []
    monkeypatch.setenv("FAL_KEY", "offline-key")

    def timeout(method, url, **kwargs):
        calls.append((method, url))
        raise TimeoutError("transport timed out after sending")

    monkeypatch.setattr("tools.fal_media.request_json", timeout)
    result = KlingO3FalVideo().execute({"operation": "text_to_video", "prompt": "A walk"})
    assert not result.success
    assert len(calls) == 1
    assert "do not resubmit" in result.error.lower()
    assert result.data == {}  # no checkpoint is fabricated without request_id


def test_incomplete_submission_response_is_not_resubmitted(monkeypatch):
    calls = []
    monkeypatch.setenv("FAL_KEY", "offline-key")
    def incomplete(method, url, **kwargs):
        calls.append(method)
        return {"request_id": "job-id-but-no-status-url"}
    monkeypatch.setattr("tools.fal_media.request_json", incomplete)
    result = KlingO3FalVideo().execute({"operation": "text_to_video", "prompt": "A walk"})
    assert not result.success
    assert calls == ["POST"]
    assert "do not resubmit" in result.error.lower()


def test_resume_rejects_foreign_endpoint_without_network(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "offline-key")
    monkeypatch.setattr("tools.fal_media.request_json", lambda *args, **kwargs: pytest.fail("network"))
    result = KlingO3FalVideo().execute({"resume_job": {
        "model": "kling-o3-standard", "operation": "text_to_video",
        "endpoint": "fal-ai/kling-video/o3/pro/text-to-video",
        "tool": "kling_o3_fal_video", "status_url": "https://queue.fal.run/anything",
        "response_url": "https://queue.fal.run/anything",
    }})
    assert not result.success
    assert "different tool or endpoint" in result.error


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
