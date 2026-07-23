"""Contract tests for the Kling official video provider."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools._kling.account import reset_account_usage_cache
from tools._kling.errors import KlingAPIError
from tools.video.kling_official_video import KlingOfficialVideo


def test_registry_discovers_kling_official_video(monkeypatch, isolated_tool_registry):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    isolated_tool_registry.discover("tools")
    tool = isolated_tool_registry.get("kling_official_video")
    assert tool is not None
    assert tool.capability == "video_generation"
    assert tool.provider == "kling_official"


def test_video_schema_has_no_top_level_image_url_and_has_skill():
    tool = KlingOfficialVideo()
    props = tool.input_schema["properties"]
    assert "image_url" not in props
    assert "reference_image_url" in props
    assert "kling-official" in tool.agent_skills
    assert "ai-video-gen" in tool.agent_skills


def test_classic_text_to_video_payload():
    tool = KlingOfficialVideo()
    request = tool._build_request(
        {
            "prompt": "cinematic robot walking through rain",
            "api_family": "classic",
            "operation": "text_to_video",
            "duration": "5",
            "aspect_ratio": "9:16",
            "watermark": False,
        }
    )
    assert request["path"] == "/v1/videos/text2video"
    assert request["protocol"] == "classic"
    assert request["payload"]["model_name"] == "kling-v3"
    assert request["payload"]["prompt"].startswith("cinematic")
    assert request["payload"]["aspect_ratio"] == "9:16"
    assert request["payload"]["watermark_info"] == {"enabled": False}


def test_classic_image_to_video_uses_reference_image_path(tmp_path):
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"fake-image")
    tool = KlingOfficialVideo()
    request = tool._build_request(
        {
            "prompt": "animate the frame",
            "api_family": "classic",
            "operation": "image_to_video",
            "reference_image_path": str(image_path),
        }
    )
    assert request["path"] == "/v1/videos/image2video"
    assert request["payload"]["image"] == base64.b64encode(b"fake-image").decode("ascii")
    assert "aspect_ratio" not in request["payload"]


def test_turbo_payloads():
    tool = KlingOfficialVideo()
    text_request = tool._build_request(
        {
            "prompt": "fast product reveal",
            "api_family": "turbo",
            "operation": "text_to_video",
            "duration": "6",
            "resolution": "1080p",
        }
    )
    assert text_request["path"] == "/text-to-video/kling-3.0-turbo"
    assert text_request["payload"]["settings"] == {
        "resolution": "1080p",
        "duration": 6,
        "aspect_ratio": "16:9",
    }

    image_request = tool._build_request(
        {
            "prompt": "animate the product",
            "api_family": "turbo",
            "operation": "image_to_video",
            "reference_image_url": "https://example.com/ref.png",
        }
    )
    assert image_request["path"] == "/image-to-video/kling-3.0-turbo"
    assert image_request["payload"]["contents"] == [
        {"type": "prompt", "text": "animate the product"},
        {"type": "first_frame", "url": "https://example.com/ref.png"},
    ]


def test_omni_reference_payload():
    tool = KlingOfficialVideo()
    request = tool._build_request(
        {
            "prompt": "match the motion and mood",
            "api_family": "omni",
            "operation": "reference_to_video",
            "video_list": [{"video_url": "https://example.com/ref.mp4", "refer_type": "base"}],
        }
    )
    assert request["path"] == "/v1/videos/omni-video"
    assert request["payload"]["model_name"] == "kling-video-o1"
    assert request["payload"]["video_list"][0]["video_url"].endswith("ref.mp4")


def test_video_omni_payload_supports_multi_refs_elements_and_multi_prompt(tmp_path):
    image_path = tmp_path / "local.png"
    image_path.write_bytes(b"local-ref")
    tool = KlingOfficialVideo()
    request = tool._build_request(
        {
            "prompt": "two-shot brand reveal",
            "api_family": "omni",
            "operation": "reference_to_video",
            "image_list": [{"image_url": "https://example.com/start.png", "type": "first_frame"}],
            "reference_tail_image_path": str(image_path),
            "video_list": [
                {
                    "video_url": "https://example.com/motion.mp4",
                    "refer_type": "feature",
                    "keep_original_sound": True,
                }
            ],
            "element_list": [123, {"element_id": "456"}],
            "multi_shot": True,
            "shot_type": "customize",
            "multi_prompt": [
                {"prompt": "wide product intro", "duration": "5"},
                {"prompt": "close detail pass", "camera_control": {"type": "simple"}},
            ],
        }
    )
    payload = request["payload"]
    assert payload["image_list"][0] == {"image_url": "https://example.com/start.png", "type": "first_frame"}
    assert payload["image_list"][1] == {
        "image_url": base64.b64encode(b"local-ref").decode("ascii"),
        "type": "end_frame",
    }
    assert payload["video_list"] == [
        {
            "video_url": "https://example.com/motion.mp4",
            "refer_type": "feature",
            "keep_original_sound": "yes",
        }
    ]
    assert payload["element_list"] == [{"element_id": 123}, {"element_id": 456}]
    assert payload["multi_shot"] is True
    assert payload["multi_prompt"][1]["camera_control"] == {"type": "simple"}
    assert request["element_ids"] == [123, 456]
    assert any(item["kind"] == "element" for item in request["references_used"])


def test_video_omni_requires_reference_input_and_rejects_local_video_paths():
    tool = KlingOfficialVideo()
    try:
        tool._build_request(
            {
                "prompt": "needs a reference",
                "api_family": "omni",
                "operation": "reference_to_video",
            }
        )
    except ValueError as exc:
        assert "requires image_list, video_list, element_list" in str(exc)
    else:
        raise AssertionError("reference_to_video must require at least one Omni reference")

    try:
        tool._build_request(
            {
                "prompt": "local video",
                "api_family": "omni",
                "operation": "reference_to_video",
                "reference_video_path": "/tmp/ref.mp4",
            }
        )
    except ValueError as exc:
        assert "local video paths cannot be silently uploaded" in str(exc)
    else:
        raise AssertionError("Video Omni must not silently upload local videos")


def test_video_callback_payloads_and_validation():
    tool = KlingOfficialVideo()
    classic = tool._build_request(
        {
            "prompt": "callback classic",
            "api_family": "classic",
            "operation": "text_to_video",
            "callback_url": "https://example.com/kling/callback",
        }
    )
    assert classic["payload"]["callback_url"] == "https://example.com/kling/callback"

    turbo = tool._build_request(
        {
            "prompt": "callback turbo",
            "api_family": "turbo",
            "operation": "text_to_video",
            "callback_url": "https://example.com/kling/callback",
        }
    )
    assert turbo["payload"]["options"]["callback_url"] == "https://example.com/kling/callback"

    omni = tool._build_request(
        {
            "prompt": "callback omni",
            "api_family": "omni",
            "operation": "reference_to_video",
            "video_list": [{"video_url": "https://example.com/ref.mp4"}],
            "callback_url": "https://example.com/kling/callback",
        }
    )
    assert omni["payload"]["callback_url"] == "https://example.com/kling/callback"

    try:
        tool._build_request(
            {
                "prompt": "bad callback",
                "api_family": "classic",
                "operation": "text_to_video",
                "callback_url": "not-a-url",
            }
        )
    except ValueError as exc:
        assert "callback_url" in str(exc)
    else:
        raise AssertionError("callback_url must be validated before sending")


def test_video_model_must_match_api_family():
    tool = KlingOfficialVideo()
    try:
        tool._build_request(
            {
                "prompt": "classic request with omni model",
                "api_family": "classic",
                "operation": "text_to_video",
                "model_name": "kling-video-o1",
            }
        )
    except ValueError as exc:
        assert "api_family=classic" in str(exc)
    else:
        raise AssertionError("classic requests must reject omni video models")

    try:
        tool._build_request(
            {
                "prompt": "omni request with classic model",
                "api_family": "omni",
                "operation": "reference_to_video",
                "model_name": "kling-v3",
                "video_list": [{"video_url": "https://example.com/ref.mp4"}],
            }
        )
    except ValueError as exc:
        assert "api_family=omni" in str(exc)
    else:
        raise AssertionError("omni requests must reject classic video models")


def test_execute_downloads_video_and_returns_artifact(monkeypatch, tmp_path):
    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [{"url": "https://example.com/out.mp4"}]

        def download(self, url, output_path):
            output_path.write_bytes(b"video")
            return output_path

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.kling_official_video.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.video.kling_official_video.probe_output", lambda path: {"duration_seconds": 5.0})
    output_path = tmp_path / "out.mp4"
    result = KlingOfficialVideo().execute({"prompt": "x", "output_path": str(output_path)})
    assert result.success
    assert result.data["provider"] == "kling_official"
    assert result.data["task_id"] == "task-1"
    assert result.artifacts == [str(output_path)]
    assert output_path.read_bytes() == b"video"
    assert result.cost_usd > 0


def test_execute_downloads_all_omni_video_outputs_and_records_metadata(monkeypatch, tmp_path):
    reset_account_usage_cache()

    class FakeClient:
        def create_classic_task(self, path, payload):
            self.path = path
            self.payload = payload
            return "omni-task-1"

        def poll_classic(self, path, task_id, result_key, timeout_seconds, poll_interval):
            return [
                {"url": "https://example.com/a.mp4"},
                {"url": "https://example.com/b.mp4"},
            ]

        def download(self, url, output_path):
            output_path.write_bytes(url.encode("utf-8"))
            return output_path

        def get(self, path, params=None):
            assert path == "/account/costs"
            return {"code": 0, "data": {"resource_pack_subscribe_infos": [{"name": "pack-a"}]}}

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.kling_official_video.KlingClient", lambda: FakeClient())
    monkeypatch.setattr("tools.video.kling_official_video.probe_output", lambda path: {"duration_seconds": 5.0})
    result = KlingOfficialVideo().execute(
        {
            "prompt": "omni",
            "api_family": "omni",
            "operation": "reference_to_video",
            "video_list": [{"video_url": "https://example.com/ref.mp4", "refer_type": "base"}],
            "element_list": [789],
            "callback_url": "https://example.com/callback",
            "include_account_usage": True,
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert result.success
    assert result.data["api_family"] == "omni"
    assert result.data["remote_outputs"][1]["url"].endswith("b.mp4")
    assert result.data["element_ids"] == [789]
    assert result.data["callback_requested"] is True
    assert result.data["polling_used"] is True
    assert result.data["account_usage"]["resource_pack_subscribe_infos"][0]["name"] == "pack-a"
    assert result.data["cost_source"] == "estimate_with_account_usage_context"
    assert result.cost_usd > 0
    assert len(result.artifacts) == 2
    assert Path(result.artifacts[1]).name == "out_2.mp4"


def test_video_selector_prefers_official_provider_without_fal_upload(
    monkeypatch, tmp_path, isolated_tool_registry
):
    monkeypatch.setenv("KLING_API_KEY", "test-key")
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"fake")
    isolated_tool_registry.discover("tools")

    seen = {}

    def fake_execute(self, inputs):
        seen.update(inputs)
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={"output_path": "out.mp4"}, artifacts=["out.mp4"])

    def fail_upload(path):
        raise AssertionError("fal.ai upload should not be called for kling_official_video")

    monkeypatch.setattr(KlingOfficialVideo, "execute", fake_execute)
    monkeypatch.setattr("tools.video._shared.upload_image_fal", fail_upload)
    result = isolated_tool_registry.get("video_selector").execute(
        {
            "prompt": "animate",
            "operation": "image_to_video",
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "reference_image_path": str(image_path),
        }
    )
    assert result.success
    assert result.data["selected_provider"] == "kling_official"
    assert seen["reference_image_path"] == str(image_path)


def test_video_cost_estimate_is_not_zero():
    tool = KlingOfficialVideo()
    assert tool.estimate_cost({"prompt": "x"}) > 0
    base = tool.estimate_cost({"prompt": "x", "api_family": "omni"})
    expensive = tool.estimate_cost(
        {
            "prompt": "x",
            "api_family": "omni",
            "mode": "4k",
            "sound": "on",
            "video_list": [{"video_url": "https://example.com/ref.mp4"}],
            "element_list": [1, 2],
            "multi_prompt": [{"prompt": "a"}, {"prompt": "b"}],
        }
    )
    assert expensive > base
    dry_run = tool.dry_run({"prompt": "x"})
    assert dry_run["cost_estimate_confidence"] == "low"


def test_video_account_resource_error_includes_diagnostic(monkeypatch):
    class FakeClient:
        def create_classic_task(self, path, payload):
            raise KlingAPIError("resource pack exhausted", code=1102, request_id="req-1")

    monkeypatch.setenv("KLING_API_KEY", "test-key")
    monkeypatch.setattr("tools.video.kling_official_video.KlingClient", lambda: FakeClient())
    result = KlingOfficialVideo().execute({"prompt": "x"})
    assert not result.success
    assert result.data["account_usage_diagnostic"]["reason"] == "account_balance_or_resource_pack"
