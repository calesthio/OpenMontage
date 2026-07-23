"""Contract tests for the Volcengine Jimeng video provider tool.

These tests verify that the tool satisfies the BaseTool contract without
requiring real Volcengine AK/SK credentials or making any API calls.

Run: pytest tests/contracts/test_jimeng_video.py -v
"""

import pytest

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.video.jimeng_video import JimengVideo


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------

class TestContract:

    def test_inherits_base_tool(self):
        assert issubclass(JimengVideo, BaseTool)

    def test_has_required_identity(self):
        tool = JimengVideo()
        assert tool.name == "jimeng_video"
        assert tool.version
        assert tool.provider == "volcengine"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.API

    def test_execution_mode_is_async(self):
        assert JimengVideo().execution_mode == ExecutionMode.ASYNC

    def test_has_input_schema(self):
        schema = JimengVideo().input_schema
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        required = schema.get("required", [])
        assert required == ["prompt"]
        for field in required:
            assert field in props

    def test_has_capabilities(self):
        tool = JimengVideo()
        assert "text_to_video" in tool.capabilities
        assert "image_to_video" in tool.capabilities

    def test_has_agent_skills(self):
        assert "ai-video-gen" in JimengVideo().agent_skills

    def test_has_fallbacks(self):
        tool = JimengVideo()
        assert "minimax_video" in tool.fallback_tools
        assert "kling_video" in tool.fallback_tools

    def test_has_install_instructions(self):
        tool = JimengVideo()
        assert "VOLC_ACCESSKEY" in tool.install_instructions
        assert "VOLC_SECRETKEY" in tool.install_instructions

    def test_get_info_returns_dict(self):
        info = JimengVideo().get_info()
        assert isinstance(info, dict)
        assert info["name"] == "jimeng_video"
        assert info["provider"] == "volcengine"
        assert info["runtime"] == "api"

    def test_status_unavailable_without_keys(self, monkeypatch):
        monkeypatch.delenv("VOLC_ACCESSKEY", raising=False)
        monkeypatch.delenv("VOLC_SECRETKEY", raising=False)
        assert JimengVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_status_available_with_keys(self, monkeypatch):
        monkeypatch.setenv("VOLC_ACCESSKEY", "fake-ak")
        monkeypatch.setenv("VOLC_SECRETKEY", "fake-sk")
        assert JimengVideo().get_status() == ToolStatus.AVAILABLE

    def test_status_unavailable_with_only_ak(self, monkeypatch):
        monkeypatch.setenv("VOLC_ACCESSKEY", "fake-ak")
        monkeypatch.delenv("VOLC_SECRETKEY", raising=False)
        assert JimengVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_has_resource_profile(self):
        rp = JimengVideo().resource_profile
        assert rp.network_required is True
        assert rp.vram_mb == 0

    def test_has_retry_policy(self):
        assert JimengVideo().retry_policy.max_retries >= 0

    def test_has_side_effects(self):
        side = JimengVideo().side_effects
        assert len(side) > 0
        assert any("API" in s for s in side)

    def test_has_user_visible_verification(self):
        assert len(JimengVideo().user_visible_verification) > 0

    def test_lazy_imports_requests(self, monkeypatch):
        import importlib
        import sys
        mod_name = "tools.video.jimeng_video"
        if "requests" in sys.modules:
            monkeypatch.delitem(sys.modules, "requests")
        importlib.reload(sys.modules[mod_name])

    def test_estimate_cost_returns_float(self):
        cost = JimengVideo().estimate_cost({"prompt": "x", "frames": 121})
        assert isinstance(cost, float)
        assert cost > 0.0

    def test_dry_run_returns_dict(self):
        result = JimengVideo().dry_run({"prompt": "test"})
        assert isinstance(result, dict)
        assert result["tool"] == "jimeng_video"


# ------------------------------------------------------------------
# Idempotency keys
# ------------------------------------------------------------------

class TestIdempotencyKeys:

    def test_includes_all_output_affecting_fields(self):
        fields = JimengVideo().idempotency_key_fields
        for field in ("prompt", "operation", "image_url", "frames", "aspect_ratio", "seed"):
            assert field in fields, f"missing idempotency field: {field}"

    def test_excludes_execution_only_fields(self):
        fields = JimengVideo().idempotency_key_fields
        for field in ("output_path", "poll_interval_seconds", "timeout_seconds"):
            assert field not in fields

    def test_differs_on_frames(self):
        tool = JimengVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key(base) != tool.idempotency_key({**base, "frames": 241})

    def test_differs_on_aspect_ratio(self):
        tool = JimengVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key({**base, "aspect_ratio": "16:9"}) != tool.idempotency_key(
            {**base, "aspect_ratio": "9:16"}
        )

    def test_differs_on_seed(self):
        tool = JimengVideo()
        base = {"prompt": "x"}
        assert tool.idempotency_key({**base, "seed": -1}) != tool.idempotency_key(
            {**base, "seed": 42}
        )

    def test_differs_on_image_url(self):
        tool = JimengVideo()
        base = {"prompt": "x", "operation": "image_to_video"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "image_url": "https://example.com/img.png"}
        )


# ------------------------------------------------------------------
# Tool-specific behavior
# ------------------------------------------------------------------

class TestToolSpecific:

    def test_default_frames_is_121(self):
        tool = JimengVideo()
        assert tool.input_schema["properties"]["frames"]["default"] == 121

    def test_default_aspect_ratio_is_16_9(self):
        tool = JimengVideo()
        assert tool.input_schema["properties"]["aspect_ratio"]["default"] == "16:9"

    def test_default_seed_is_negative_one(self):
        tool = JimengVideo()
        assert tool.input_schema["properties"]["seed"]["default"] == -1

    def test_cost_scales_with_frames(self):
        tool = JimengVideo()
        cost_5s = tool.estimate_cost({"prompt": "x", "frames": 121})
        cost_10s = tool.estimate_cost({"prompt": "x", "frames": 241})
        assert cost_10s > cost_5s

    def test_build_payload_t2v(self):
        tool = JimengVideo()
        payload = tool._build_payload({"prompt": "a cat"})
        assert payload["req_key"] == "jimeng_ti2v_v30_pro"
        assert payload["prompt"] == "a cat"
        assert payload["frames"] == 121
        assert payload["aspect_ratio"] == "16:9"
        assert payload["seed"] == -1
        assert "image_urls" not in payload

    def test_build_payload_i2v_includes_image(self):
        tool = JimengVideo()
        payload = tool._build_payload({
            "prompt": "motion",
            "operation": "image_to_video",
            "image_url": "https://example.com/img.png",
        })
        assert payload["image_urls"] == ["https://example.com/img.png"]

    def test_build_payload_t2v_omits_image(self):
        tool = JimengVideo()
        payload = tool._build_payload({"prompt": "a cat", "operation": "text_to_video"})
        assert "image_urls" not in payload

    def test_i2v_without_image_fails(self, monkeypatch):
        monkeypatch.setenv("VOLC_ACCESSKEY", "fake-ak")
        monkeypatch.setenv("VOLC_SECRETKEY", "fake-sk")
        result = JimengVideo().execute({"prompt": "test", "operation": "image_to_video"})
        assert result.success is False
        assert "image_url" in result.error

    def test_no_keys_returns_error(self, monkeypatch):
        monkeypatch.delenv("VOLC_ACCESSKEY", raising=False)
        monkeypatch.delenv("VOLC_SECRETKEY", raising=False)
        result = JimengVideo().execute({"prompt": "test"})
        assert result.success is False
        assert "VOLC_ACCESSKEY" in result.error
        assert "VOLC_SECRETKEY" in result.error

    def test_safe_error_redacts_keys(self, monkeypatch):
        monkeypatch.setenv("VOLC_ACCESSKEY", "my-ak-secret")
        monkeypatch.setenv("VOLC_SECRETKEY", "my-sk-secret")
        redacted = JimengVideo._safe_error(
            Exception("failed with ak=my-ak-secret sk=my-sk-secret")
        )
        assert "my-ak-secret" not in redacted
        assert "my-sk-secret" not in redacted
        assert "[redacted]" in redacted

    def test_safe_error_no_empty_string_bug(self, monkeypatch):
        """Regression: when no keys are set, _safe_error must not mangle."""
        monkeypatch.delenv("VOLC_ACCESSKEY", raising=False)
        monkeypatch.delenv("VOLC_SECRETKEY", raising=False)
        msg = JimengVideo._safe_error(Exception("abc"))
        assert msg == "abc"

    def test_sign_returns_authorization_header(self):
        headers = JimengVideo._sign(
            "POST", "/",
            {"Action": "CVSync2AsyncSubmitTask", "Version": "2022-08-31"},
            {}, b'{"prompt":"test"}',
            "fake-ak", "fake-sk",
        )
        assert "Authorization" in headers
        assert "HMAC-SHA256" in headers["Authorization"]
        assert "fake-ak" in headers["Authorization"]
        assert "Host" in headers
        assert "X-Date" in headers
        assert "X-Content-Sha256" in headers

    def test_sign_includes_content_type(self):
        headers = JimengVideo._sign("POST", "/", {}, {}, b"{}", "ak", "sk")
        assert headers["Content-Type"] == "application/json"

    def test_json_or_raise_returns_dict(self):
        class FakeResp:
            status_code = 200
            def json(self):
                return {"code": 10000, "data": {"task_id": "123"}}
        assert JimengVideo._json_or_raise(FakeResp()) == {"code": 10000, "data": {"task_id": "123"}}

    def test_json_or_raise_raises_on_non_json(self):
        class FakeResp:
            status_code = 500
            def json(self):
                raise ValueError("not JSON")
        with pytest.raises(RuntimeError, match="Non-JSON"):
            JimengVideo._json_or_raise(FakeResp())

    def test_check_code_passes_on_success(self):
        JimengVideo._check_code(200, {"code": 10000, "message": "Success"})

    def test_check_code_raises_on_api_error(self):
        with pytest.raises(RuntimeError, match="code=10008"):
            JimengVideo._check_code(200, {"code": 10008, "message": "Insufficient balance"})

    def test_check_code_raises_on_http_error(self):
        with pytest.raises(RuntimeError, match="HTTP 401"):
            JimengVideo._check_code(401, {"code": 10004, "message": "Auth failed"})

    def test_check_code_defaults_to_success_when_code_missing(self):
        """If code field is absent on HTTP 2xx, default to 10000 (success)."""
        JimengVideo._check_code(200, {"data": {"task_id": "123"}})


# ------------------------------------------------------------------
# Registry discovery
# ------------------------------------------------------------------

class TestRegistryDiscovery:

    def test_discoverable(self):
        from tools.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover()
        names = {t.name for t in registry._tools.values()}
        assert "jimeng_video" in names

    def test_distinct_from_other_minimax_tools(self):
        from tools.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover()
        jimeng = [t for t in registry._tools.values() if t.name == "jimeng_video"]
        assert len(jimeng) == 1
        assert jimeng[0].provider == "volcengine"


# ------------------------------------------------------------------
# Schema validation — reject invalid inputs before paid API call
# ------------------------------------------------------------------

class TestSchemaValidation:

    def test_frames_accepts_121(self):
        schema = JimengVideo().input_schema
        valid = schema["properties"]["frames"]
        assert valid["enum"] == [121, 241]

    def test_frames_rejects_non_enum(self):
        import jsonschema
        schema = JimengVideo().input_schema
        for invalid in [1, 100, 200, 500, 0, -1]:
            instance = {"prompt": "test", "frames": invalid}
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(instance, schema)

    def test_prompt_max_length_800(self):
        schema = JimengVideo().input_schema
        assert schema["properties"]["prompt"]["maxLength"] == 800

    def test_prompt_rejects_over_800_chars(self):
        import jsonschema
        schema = JimengVideo().input_schema
        instance = {"prompt": "x" * 801}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance, schema)

    def test_prompt_accepts_800_chars(self):
        import jsonschema
        schema = JimengVideo().input_schema
        instance = {"prompt": "x" * 800}
        jsonschema.validate(instance, schema)

    def test_seed_minimum_is_negative_one(self):
        schema = JimengVideo().input_schema
        assert schema["properties"]["seed"]["minimum"] == -1

    def test_seed_rejects_below_negative_one(self):
        import jsonschema
        schema = JimengVideo().input_schema
        for invalid in [-2, -10, -100]:
            instance = {"prompt": "test", "seed": invalid}
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(instance, schema)

    def test_seed_accepts_negative_one(self):
        import jsonschema
        schema = JimengVideo().input_schema
        jsonschema.validate({"prompt": "test", "seed": -1}, schema)

    def test_seed_accepts_zero_and_positive(self):
        import jsonschema
        schema = JimengVideo().input_schema
        for valid in [0, 1, 42, 999999]:
            jsonschema.validate({"prompt": "test", "seed": valid}, schema)


# ------------------------------------------------------------------
# Selector duration → frames mapping
# ------------------------------------------------------------------

class TestSelectorDurationMapping:

    def test_duration_5_maps_to_121_frames(self):
        payload = JimengVideo._build_payload({"prompt": "x", "duration": 5})
        assert payload["frames"] == 121

    def test_duration_10_maps_to_241_frames(self):
        payload = JimengVideo._build_payload({"prompt": "x", "duration": 10})
        assert payload["frames"] == 241

    def test_duration_defaults_to_5_when_absent(self):
        payload = JimengVideo._build_payload({"prompt": "x"})
        assert payload["frames"] == 121

    def test_frames_takes_priority_over_duration(self):
        payload = JimengVideo._build_payload({"prompt": "x", "frames": 241, "duration": 5})
        assert payload["frames"] == 241
