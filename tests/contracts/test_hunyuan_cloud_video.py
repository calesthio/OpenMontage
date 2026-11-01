"""Contract tests for the Tencent Hunyuan cloud video provider tool (TokenHub API).

These tests verify that the tool satisfies the BaseTool contract without
requiring real Tencent Cloud credentials or making any API calls.

Run: pytest tests/contracts/test_hunyuan_cloud_video.py -v
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.video.hunyuan_cloud_video import HunyuanCloudVideo


# ------------------------------------------------------------------
# Fake HTTP infrastructure (used by execute-path tests)
# ------------------------------------------------------------------

class FakeResponse:
    def __init__(self, json_data=None, content=b"", ok=True, status_code=200, headers=None, text=""):
        self._json = json_data
        self.content = content
        self.ok = ok
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text or (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _install_fake_requests(monkeypatch, post_responses, get_responses):
    """Inject a fake requests module; returns the recorded calls."""
    calls = {"post": [], "get": []}
    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, data=None, timeout=None, params=None):
        calls["post"].append({"url": url, "headers": headers, "json": json, "data": data})
        return post_responses.pop(0)

    def fake_get(url, headers=None, timeout=None, params=None):
        calls["get"].append({"url": url, "headers": headers, "params": params})
        return get_responses.pop(0)

    fake.post = fake_post
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def hunyuan_env(monkeypatch):
    """Set fake TokenHub API credentials."""
    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "thub-fake-test-key")


@pytest.fixture()
def no_hunyuan_env(monkeypatch):
    """Ensure no TokenHub credentials are set."""
    monkeypatch.delenv("TENCENT_TOKENHUB_API_KEY", raising=False)


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------

class TestContract:

    def test_inherits_base_tool(self):
        assert issubclass(HunyuanCloudVideo, BaseTool)

    def test_has_required_identity(self):
        tool = HunyuanCloudVideo()
        assert tool.name == "hunyuan_cloud_video"
        assert tool.version == "0.1.0"
        assert tool.provider == "hunyuan_cloud"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.API

    def test_execution_mode_is_async(self):
        assert HunyuanCloudVideo().execution_mode == ExecutionMode.ASYNC

    def test_has_input_schema(self):
        schema = HunyuanCloudVideo().input_schema
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        required = schema.get("required", [])
        assert required == ["prompt"]
        for field in required:
            assert field in props

    def test_has_capabilities(self):
        tool = HunyuanCloudVideo()
        assert "text_to_video" in tool.capabilities
        assert "image_to_video" in tool.capabilities

    def test_has_agent_skills(self):
        assert "ai-video-gen" in HunyuanCloudVideo().agent_skills

    def test_has_fallbacks(self):
        tool = HunyuanCloudVideo()
        assert "jimeng_video" in tool.fallback_tools
        assert "kling_official_video" in tool.fallback_tools
        assert "minimax_video" in tool.fallback_tools

    def test_has_install_instructions(self):
        tool = HunyuanCloudVideo()
        assert "TENCENT_TOKENHUB_API_KEY" in tool.install_instructions

    def test_get_info_returns_dict(self):
        info = HunyuanCloudVideo().get_info()
        assert isinstance(info, dict)
        assert info["name"] == "hunyuan_cloud_video"
        assert info["provider"] == "hunyuan_cloud"
        assert info["runtime"] == "api"
        assert info["capability"] == "video_generation"

    def test_status_unavailable_without_keys(self, no_hunyuan_env):
        assert HunyuanCloudVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_status_available_with_keys(self, hunyuan_env):
        assert HunyuanCloudVideo().get_status() == ToolStatus.AVAILABLE

    def test_has_resource_profile(self):
        rp = HunyuanCloudVideo().resource_profile
        assert rp.network_required is True
        assert rp.vram_mb == 0

    def test_has_retry_policy(self):
        assert HunyuanCloudVideo().retry_policy.max_retries >= 0

    def test_has_side_effects(self):
        side = HunyuanCloudVideo().side_effects
        assert len(side) > 0
        assert any("API" in s for s in side) or any("TokenHub" in s for s in side)

    def test_has_user_visible_verification(self):
        assert len(HunyuanCloudVideo().user_visible_verification) > 0

    def test_estimate_cost_returns_float(self):
        cost = HunyuanCloudVideo().estimate_cost({"prompt": "x"})
        assert isinstance(cost, float)
        assert cost > 0.0

    def test_dry_run_returns_dict(self):
        result = HunyuanCloudVideo().dry_run({"prompt": "test"})
        assert isinstance(result, dict)
        assert result["tool"] == "hunyuan_cloud_video"


# ------------------------------------------------------------------
# Supports flags
# ------------------------------------------------------------------

class TestSupports:

    def test_text_to_video_supported(self):
        assert HunyuanCloudVideo().supports["text_to_video"] is True

    def test_image_to_video_supported(self):
        assert HunyuanCloudVideo().supports["image_to_video"] is True

    def test_native_audio_not_supported(self):
        assert HunyuanCloudVideo().supports["native_audio"] is False

    def test_seed_not_supported(self):
        assert HunyuanCloudVideo().supports["seed"] is False


# ------------------------------------------------------------------
# Idempotency keys
# ------------------------------------------------------------------

class TestIdempotencyKeys:

    def test_includes_all_output_affecting_fields(self):
        fields = HunyuanCloudVideo().idempotency_key_fields
        for field in (
            "prompt", "operation", "model", "image_url", "image_path",
            "resolution", "logo_add",
        ):
            assert field in fields, f"missing idempotency field: {field}"

    def test_excludes_execution_only_fields(self):
        fields = HunyuanCloudVideo().idempotency_key_fields
        for field in ("output_path", "poll_interval_seconds", "timeout_seconds"):
            assert field not in fields

    def test_differs_on_operation(self):
        tool = HunyuanCloudVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "operation": "image_to_video"}
        )

    def test_differs_on_model(self):
        tool = HunyuanCloudVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "model": "yt-video-2.0"}
        )

    def test_differs_on_image_url(self):
        tool = HunyuanCloudVideo()
        base = {"prompt": "x", "operation": "image_to_video"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "image_url": "https://example.com/img.png"}
        )

    def test_ignores_execution_params(self):
        tool = HunyuanCloudVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key(base) == tool.idempotency_key(
            {**base, "output_path": "/tmp/out.mp4", "timeout_seconds": 999}
        )


# ------------------------------------------------------------------
# Tool-specific behavior
# ------------------------------------------------------------------

class TestToolSpecific:

    def test_default_operation_is_text_to_video(self):
        tool = HunyuanCloudVideo()
        assert tool.input_schema["properties"]["operation"]["default"] == "text_to_video"

    def test_default_resolution_is_720p(self):
        tool = HunyuanCloudVideo()
        assert tool.input_schema["properties"]["resolution"]["default"] == "720p"

    def test_default_logo_add_is_1(self):
        tool = HunyuanCloudVideo()
        assert tool.input_schema["properties"]["logo_add"]["default"] == 1

    def test_default_poll_interval_is_5(self):
        tool = HunyuanCloudVideo()
        assert tool.input_schema["properties"]["poll_interval_seconds"]["default"] == 5.0

    def test_default_timeout_is_600(self):
        tool = HunyuanCloudVideo()
        assert tool.input_schema["properties"]["timeout_seconds"]["default"] == 600

    # -- _resolve_model --

    def test_resolve_model_defaults_t2v(self):
        model = HunyuanCloudVideo._resolve_model({"prompt": "test"})
        assert model == "hy-video-1.5"

    def test_resolve_model_defaults_i2v(self):
        model = HunyuanCloudVideo._resolve_model({
            "prompt": "test", "operation": "image_to_video",
        })
        assert model == "yt-video-2.0"

    def test_resolve_model_explicit_input(self):
        model = HunyuanCloudVideo._resolve_model({
            "prompt": "test", "model": "yt-video-2.0",
        })
        assert model == "yt-video-2.0"

    # -- _build_payload --

    def test_build_payload_t2v_minimal(self):
        """Minimal T2V payload — only prompt is required by TokenHub."""
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({"prompt": "一只猫"})
        assert payload["prompt"] == "一只猫"
        # resolution and logo_add are optional in TokenHub; only included when
        # explicitly passed in inputs
        assert "resolution" not in payload
        assert "logo_add" not in payload

    def test_build_payload_t2v_with_resolution_and_logo(self):
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({
            "prompt": "test", "resolution": "720p", "logo_add": 0,
        })
        assert payload["prompt"] == "test"
        assert payload["resolution"] == "720p"
        assert payload["logo_add"] == 0

    def test_build_payload_t2v_custom_logo_add(self):
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({"prompt": "test", "logo_add": 0})
        assert payload["logo_add"] == 0

    def test_build_payload_i2v_includes_image_url(self):
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({
            "prompt": "motion",
            "operation": "image_to_video",
            "image_url": "https://example.com/frame.png",
        })
        assert payload["image_url"] == "https://example.com/frame.png"

    def test_build_payload_t2v_omits_image(self):
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({"prompt": "a cat", "operation": "text_to_video"})
        assert "image_url" not in payload
        assert "image" not in payload

    def test_build_payload_i2v_base64_from_path(self, tmp_path):
        """image_path should be base64-encoded into the image field."""
        img = tmp_path / "frame.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0test-jpeg-data")
        tool = HunyuanCloudVideo()
        payload = tool._build_payload({
            "prompt": "test",
            "operation": "image_to_video",
            "image_path": str(img),
        })
        assert payload["image"].startswith("/9j/")

    def test_encode_image_returns_base64(self, tmp_path):
        img = tmp_path / "ref.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
        encoded = HunyuanCloudVideo._encode_image(str(img))
        assert isinstance(encoded, str)
        assert encoded.startswith("/9j/")

    def test_encode_image_raises_on_missing(self):
        with pytest.raises(FileNotFoundError):
            HunyuanCloudVideo._encode_image("/nonexistent/file.jpg")

    # -- Error paths --

    def test_no_keys_returns_error(self, no_hunyuan_env):
        result = HunyuanCloudVideo().execute({"prompt": "test"})
        assert result.success is False
        assert "TENCENT_TOKENHUB_API_KEY" in result.error

    def test_i2v_without_image_fails(self, hunyuan_env):
        result = HunyuanCloudVideo().execute(
            {"prompt": "test", "operation": "image_to_video"}
        )
        assert result.success is False
        assert "image_url" in result.error or "image_path" in result.error

    @pytest.mark.parametrize(
        ("operation", "model", "expected"),
        [
            ("text_to_video", "yt-video-2.0", "hy-video-1.5"),
            ("image_to_video", "hy-video-1.5", "yt-video-2.0"),
        ],
    )
    def test_incompatible_model_operation_fails_before_submit(
        self, hunyuan_env, monkeypatch, operation, model, expected
    ):
        monkeypatch.setattr(
            HunyuanCloudVideo,
            "_generate",
            lambda *args, **kwargs: pytest.fail("must not submit a paid task"),
        )
        inputs = {"prompt": "test", "operation": operation, "model": model}
        if operation == "image_to_video":
            inputs["image_url"] = "https://example.com/frame.png"
        result = HunyuanCloudVideo().execute(inputs)
        assert not result.success
        assert expected in (result.error or "")

    def test_i2v_both_url_and_path_fails(self, hunyuan_env, tmp_path):
        img = tmp_path / "ref.jpg"
        img.write_bytes(b"fake-jpeg")
        result = HunyuanCloudVideo().execute({
            "prompt": "test",
            "operation": "image_to_video",
            "image_url": "https://example.com/img.jpg",
            "image_path": str(img),
        })
        assert result.success is False
        assert "not both" in result.error.lower()

    def test_safe_error_redacts_keys(self, monkeypatch):
        monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "thub-secret-key")
        redacted = HunyuanCloudVideo._safe_error(
            Exception("failed with thub-secret-key in message")
        )
        assert "thub-secret-key" not in redacted
        assert "[redacted]" in redacted

    def test_safe_error_no_empty_string_bug(self, no_hunyuan_env):
        msg = HunyuanCloudVideo._safe_error(Exception("abc"))
        assert msg == "abc"


# ------------------------------------------------------------------
# TokenHub auth headers
# ------------------------------------------------------------------

class TestAuthHeaders:

    def test_auth_headers_includes_bearer(self):
        headers = HunyuanCloudVideo._auth_headers("test-api-key")
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"


# ------------------------------------------------------------------
# Error handling helpers
# ------------------------------------------------------------------

class TestErrorHelpers:

    def test_json_or_raise_returns_dict(self):
        class FakeResp:
            status_code = 200
            def json(self):
                return {"id": "task-123", "status": "queued"}
        result = HunyuanCloudVideo._json_or_raise(FakeResp())
        assert result == {"id": "task-123", "status": "queued"}

    def test_json_or_raise_raises_on_non_json(self):
        class FakeResp:
            status_code = 500
            def json(self):
                raise ValueError("not JSON")
        with pytest.raises(RuntimeError, match="Non-JSON"):
            HunyuanCloudVideo._json_or_raise(FakeResp())

    def test_check_response_passes_on_success(self):
        HunyuanCloudVideo._check_response(
            {"id": "task-123", "status": "completed"}
        )

    def test_check_response_passes_without_error_field(self):
        HunyuanCloudVideo._check_response(
            {"id": "task-456", "status": "running", "progress": 50}
        )

    def test_check_response_raises_on_api_error(self):
        with pytest.raises(RuntimeError, match="Prompt too long"):
            HunyuanCloudVideo._check_response({
                "error": {"code": "invalid_parameter", "message": "Prompt too long"},
            })

    def test_check_response_raises_on_auth_failure(self):
        with pytest.raises(RuntimeError, match="Invalid API key"):
            HunyuanCloudVideo._check_response({
                "error": {
                    "type": "authentication_error",
                    "message": "Invalid API key",
                },
            })


# ------------------------------------------------------------------
# Execute with mocked HTTP
# ------------------------------------------------------------------

class TestExecuteWithMocks:

    def test_text_to_video_success(self, hunyuan_env, tmp_path, monkeypatch):
        """Full T2V flow: submit -> poll -> download -> write output."""
        task_id = "143-test-task-12345"
        calls = _install_fake_requests(
            monkeypatch,
            post_responses=[
                # Submit response
                FakeResponse({
                    "id": task_id,
                    "request_id": "req-sub-001",
                    "object": "video",
                    "created_at": 1700000000,
                    "status": "queued",
                }),
                # Poll response (completed)
                FakeResponse({
                    "request_id": "req-poll-001",
                    "object": "video",
                    "created_at": 1700000000,
                    "completed_at": 1700000120,
                    "status": "completed",
                    "progress": 100,
                    "data": {"url": "https://example.com/output.mp4"},
                }),
            ],
            get_responses=[
                # Download response
                FakeResponse(content=b"fake-hunyuan-mp4-data"),
            ],
        )

        output_path = tmp_path / "hunyuan_out.mp4"
        result = HunyuanCloudVideo().execute({
            "prompt": "一只猫在草原上奔跑",
            "output_path": str(output_path),
        })

        assert result.success, result.error
        assert output_path.read_bytes() == b"fake-hunyuan-mp4-data"
        assert result.data["provider"] == "hunyuan_cloud"
        assert result.data["route"] == "tokenhub"
        assert result.data["model"] == "hy-video-1.5"
        assert result.data["task_id"] == task_id
        assert result.data["operation"] == "text_to_video"
        assert result.cost_usd == pytest.approx(0.25)
        assert len(result.artifacts) == 1
        assert result.artifacts[0] == str(output_path)

        # Verify submit was called to the correct TokenHub endpoint
        submit_call = calls["post"][0]
        assert "tokenhub.tencentmaas.com" in submit_call["url"]
        assert submit_call["url"].endswith("/v1/api/video/submit")
        assert submit_call["headers"]["Authorization"] == "Bearer thub-fake-test-key"
        assert submit_call["json"]["model"] == "hy-video-1.5"
        assert submit_call["json"]["prompt"] == "一只猫在草原上奔跑"

        # Verify poll was called
        poll_call = calls["post"][1]
        assert poll_call["url"].endswith("/v1/api/video/query")
        assert poll_call["json"]["model"] == "hy-video-1.5"
        assert poll_call["json"]["id"] == task_id

        # Verify download was called
        assert len(calls["get"]) == 1
        assert calls["get"][0]["url"] == "https://example.com/output.mp4"

    def test_image_to_video_with_url_success(self, hunyuan_env, tmp_path, monkeypatch):
        """Full I2V flow with an image URL."""
        task_id = "i2v-task-999"
        _install_fake_requests(
            monkeypatch,
            post_responses=[
                FakeResponse({
                    "id": task_id, "request_id": "req-sub", "object": "video",
                    "created_at": 1700000000, "status": "queued",
                }),
                FakeResponse({
                    "request_id": "req-poll", "object": "video",
                    "created_at": 1700000000, "completed_at": 1700000120,
                    "status": "completed", "progress": 100,
                    "data": {"url": "https://example.com/i2v_out.mp4"},
                }),
            ],
            get_responses=[
                FakeResponse(content=b"fake-i2v-video"),
            ],
        )

        output_path = tmp_path / "i2v_out.mp4"
        result = HunyuanCloudVideo().execute({
            "prompt": "让画面动起来",
            "operation": "image_to_video",
            "image_url": "https://example.com/frame.jpg",
            "output_path": str(output_path),
        })

        assert result.success, result.error
        assert output_path.read_bytes() == b"fake-i2v-video"
        assert result.data["operation"] == "image_to_video"
        assert result.data["model"] == "yt-video-2.0"
        assert result.data["task_id"] == task_id

    def test_i2v_with_local_image_path(self, hunyuan_env, tmp_path, monkeypatch):
        """Full I2V flow with a local image path -> base64 encoding."""
        img = tmp_path / "frame.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0test-jpeg-image-data")

        task_id = "i2v-local-task"
        _install_fake_requests(
            monkeypatch,
            post_responses=[
                FakeResponse({
                    "id": task_id, "request_id": "req-sub", "object": "video",
                    "created_at": 1700000000, "status": "queued",
                }),
                FakeResponse({
                    "request_id": "req-poll", "object": "video",
                    "created_at": 1700000000, "completed_at": 1700000120,
                    "status": "completed", "progress": 100,
                    "data": {"url": "https://example.com/i2v_local.mp4"},
                }),
            ],
            get_responses=[
                FakeResponse(content=b"fake-i2v-local-video"),
            ],
        )

        output_path = tmp_path / "i2v_local.mp4"
        result = HunyuanCloudVideo().execute({
            "prompt": "animate this frame",
            "operation": "image_to_video",
            "image_path": str(img),
            "output_path": str(output_path),
        })

        assert result.success, result.error
        assert output_path.read_bytes() == b"fake-i2v-local-video"

    def test_explicit_incompatible_model_is_rejected(self, hunyuan_env):
        result = HunyuanCloudVideo().execute({
            "prompt": "test",
            "operation": "image_to_video",
            "model": "hy-video-1.5",
            "image_url": "https://example.com/frame.jpg",
        })

        assert not result.success
        assert "yt-video-2.0" in (result.error or "")

    def test_polling_retries_until_success(self, hunyuan_env, tmp_path, monkeypatch):
        """Polling should retry when status is queued/running, then succeed."""
        task_id = "poll-retry-task"
        _install_fake_requests(
            monkeypatch,
            post_responses=[
                FakeResponse({
                    "id": task_id, "request_id": "req-sub", "object": "video",
                    "created_at": 1700000000, "status": "queued",
                }),
                FakeResponse({
                    "request_id": "r1", "object": "video",
                    "status": "queued", "progress": 0,
                }),
                FakeResponse({
                    "request_id": "r2", "object": "video",
                    "status": "running", "progress": 45,
                }),
                FakeResponse({
                    "request_id": "r3", "object": "video",
                    "status": "completed", "progress": 100,
                    "data": {"url": "https://example.com/final.mp4"},
                }),
            ],
            get_responses=[
                FakeResponse(content=b"final-video-data"),
            ],
        )

        result = HunyuanCloudVideo().execute({
            "prompt": "test polling",
            "poll_interval_seconds": 0.1,
            "output_path": str(tmp_path / "polled.mp4"),
        })

        assert result.success, result.error
        assert result.data["task_id"] == task_id

    def test_polling_fails_on_task_failed(self, hunyuan_env, tmp_path, monkeypatch):
        """When the API returns status=failed, execute should return error."""
        task_id = "failed-task"
        _install_fake_requests(
            monkeypatch,
            post_responses=[
                FakeResponse({
                    "id": task_id, "request_id": "req-sub", "object": "video",
                    "created_at": 1700000000, "status": "queued",
                }),
                FakeResponse({
                    "request_id": "req-fail", "object": "video",
                    "status": "failed",
                    "error": {"code": "internal_error", "message": "Service unavailable"},
                }),
            ],
            get_responses=[],
        )

        result = HunyuanCloudVideo().execute({
            "prompt": "this will fail",
            "poll_interval_seconds": 0.1,
            "output_path": str(tmp_path / "failed.mp4"),
        })

        assert result.success is False
        assert "failed" in result.error.lower()
        assert "Service unavailable" in result.error

    def test_submit_error_returns_failure(self, hunyuan_env, tmp_path, monkeypatch):
        """API-level error on submit should be returned as ToolResult error."""
        _install_fake_requests(
            monkeypatch,
            post_responses=[
                FakeResponse({
                    "error": {"code": "invalid_parameter", "message": "Prompt exceeds limit"},
                }),
            ],
            get_responses=[],
        )

        result = HunyuanCloudVideo().execute({
            "prompt": "test",
            "output_path": str(tmp_path / "err.mp4"),
        })

        assert result.success is False
        assert "Prompt exceeds limit" in result.error


# ------------------------------------------------------------------
# Registry discovery
# ------------------------------------------------------------------

class TestRegistryDiscovery:

    def test_discoverable(self, isolated_tool_registry):
        isolated_tool_registry.discover()
        tool = isolated_tool_registry.get("hunyuan_cloud_video")
        assert tool is not None
        assert tool.provider == "hunyuan_cloud"
        assert tool.capability == "video_generation"

    def test_distinct_from_local_hunyuan_tool(self, isolated_tool_registry):
        isolated_tool_registry.discover()
        cloud = isolated_tool_registry.get("hunyuan_cloud_video")
        local = isolated_tool_registry.get("hunyuan_video")
        assert cloud is not None
        assert local is not None
        assert cloud.provider == "hunyuan_cloud"
        assert local.provider == "hunyuan"
        assert cloud.runtime == ToolRuntime.API
        assert local.runtime == ToolRuntime.LOCAL_GPU

    def test_video_selector_routes_to_hunyuan_cloud(self, hunyuan_env, monkeypatch):
        from tools.base_tool import ToolResult
        from tools.video.video_selector import VideoSelector

        tool = HunyuanCloudVideo()
        selector = VideoSelector()
        monkeypatch.setattr(selector, "_providers", lambda: [tool])
        monkeypatch.setattr(
            selector,
            "_select_best_tool",
            lambda _inputs, _candidates, _context: (tool, None),
        )
        monkeypatch.setattr(
            tool,
            "execute",
            lambda inputs: ToolResult(
                success=True,
                data={"received": inputs},
                artifacts=[inputs["output_path"]],
            ),
        )

        result = selector.execute(
            {
                "prompt": "test",
                "preferred_provider": "hunyuan_cloud",
                "output_path": "out.mp4",
            }
        )
        assert result.success
        assert result.data["selected_tool"] == "hunyuan_cloud_video"
        assert result.data["selected_provider"] == "hunyuan_cloud"


# ------------------------------------------------------------------
# Schema validation
# ------------------------------------------------------------------

class TestSchemaValidation:

    def test_prompt_max_length_200(self):
        schema = HunyuanCloudVideo().input_schema
        assert schema["properties"]["prompt"]["maxLength"] == 200

    def test_prompt_rejects_over_200_chars(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        instance = {"prompt": "x" * 201}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance, schema)

    def test_prompt_accepts_200_chars(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        instance = {"prompt": "x" * 200}
        jsonschema.validate(instance, schema)

    def test_operation_accepts_valid_values(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        for op in ["text_to_video", "image_to_video"]:
            jsonschema.validate({"prompt": "test", "operation": op}, schema)

    def test_operation_rejects_invalid_values(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        for invalid in ["video_to_video", "", "TEXT_TO_VIDEO"]:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate({"prompt": "test", "operation": invalid}, schema)

    def test_model_accepts_valid_values(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        for m in ["hy-video-1.5", "yt-video-2.0"]:
            jsonschema.validate({"prompt": "test", "model": m}, schema)

    def test_model_rejects_invalid_values(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"prompt": "test", "model": "invalid-model"}, schema)

    def test_logo_add_accepts_0_and_1(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        for val in [0, 1]:
            jsonschema.validate({"prompt": "test", "logo_add": val}, schema)

    def test_logo_add_rejects_other_values(self):
        import jsonschema
        schema = HunyuanCloudVideo().input_schema
        for invalid in [2, -1, 99]:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate({"prompt": "test", "logo_add": invalid}, schema)

    def test_poll_interval_minimum_2(self):
        schema = HunyuanCloudVideo().input_schema
        assert schema["properties"]["poll_interval_seconds"]["minimum"] == 2

    def test_timeout_minimum_60(self):
        schema = HunyuanCloudVideo().input_schema
        assert schema["properties"]["timeout_seconds"]["minimum"] == 60

    def test_resolution_only_720p(self):
        schema = HunyuanCloudVideo().input_schema
        assert schema["properties"]["resolution"]["enum"] == ["720p", "1080p"]
