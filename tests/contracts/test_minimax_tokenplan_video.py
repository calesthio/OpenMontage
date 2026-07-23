"""Contract tests for the MiniMax Token Plan video provider tool.

These tests verify that the tool satisfies the BaseTool contract without
requiring a real MiniMax API key or making any API calls.

Run: pytest tests/contracts/test_minimax_tokenplan_video.py -v
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
from tools.video.minimax_tokenplan_video import MinimaxTokenPlanVideo


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------

class TestContract:

    def test_inherits_base_tool(self):
        assert issubclass(MinimaxTokenPlanVideo, BaseTool)

    def test_has_required_identity(self):
        tool = MinimaxTokenPlanVideo()
        assert tool.name == "minimax_tokenplan_video"
        assert tool.version
        assert tool.provider == "minimax_tokenplan"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.API

    def test_execution_mode_is_async(self):
        assert MinimaxTokenPlanVideo().execution_mode == ExecutionMode.ASYNC

    def test_has_input_schema(self):
        schema = MinimaxTokenPlanVideo().input_schema
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        required = schema.get("required", [])
        assert required == ["prompt"]
        for field in required:
            assert field in props

    def test_has_capabilities(self):
        tool = MinimaxTokenPlanVideo()
        assert "text_to_video" in tool.capabilities
        assert "image_to_video" in tool.capabilities

    def test_has_agent_skills(self):
        tool = MinimaxTokenPlanVideo()
        assert "ai-video-gen" in tool.agent_skills

    def test_has_fallbacks(self):
        tool = MinimaxTokenPlanVideo()
        assert "minimax_video" in tool.fallback_tools
        assert "kling_video" in tool.fallback_tools

    def test_has_install_instructions(self):
        tool = MinimaxTokenPlanVideo()
        assert "MINIMAX_API_KEY" in tool.install_instructions

    def test_get_info_returns_dict(self):
        info = MinimaxTokenPlanVideo().get_info()
        assert isinstance(info, dict)
        assert info["name"] == "minimax_tokenplan_video"
        assert info["provider"] == "minimax_tokenplan"
        assert info["runtime"] == "api"

    def test_status_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        assert MinimaxTokenPlanVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_status_available_with_key(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "fake-key-for-testing")
        assert MinimaxTokenPlanVideo().get_status() == ToolStatus.AVAILABLE

    def test_status_available_with_token_plan_key(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "fake-key-for-testing")
        assert MinimaxTokenPlanVideo().get_status() == ToolStatus.AVAILABLE

    def test_has_resource_profile(self):
        rp = MinimaxTokenPlanVideo().resource_profile
        assert rp.network_required is True
        assert rp.vram_mb == 0

    def test_has_retry_policy(self):
        assert MinimaxTokenPlanVideo().retry_policy.max_retries >= 0

    def test_has_side_effects(self):
        side = MinimaxTokenPlanVideo().side_effects
        assert len(side) > 0
        assert any("API" in s for s in side)

    def test_has_user_visible_verification(self):
        assert len(MinimaxTokenPlanVideo().user_visible_verification) > 0

    def test_lazy_imports_requests(self, monkeypatch):
        import importlib
        import sys
        mod_name = "tools.video.minimax_tokenplan_video"
        if "requests" in sys.modules:
            monkeypatch.delitem(sys.modules, "requests")
        importlib.reload(sys.modules[mod_name])

    def test_estimate_cost_returns_float(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        cost = MinimaxTokenPlanVideo().estimate_cost({"prompt": "x", "duration": 6})
        assert isinstance(cost, float)
        assert cost > 0.0

    def test_dry_run_returns_dict(self):
        result = MinimaxTokenPlanVideo().dry_run({"prompt": "test"})
        assert isinstance(result, dict)
        assert result["tool"] == "minimax_tokenplan_video"


# ------------------------------------------------------------------
# Idempotency keys (learned from DashScope PR #240 review)
# ------------------------------------------------------------------

class TestIdempotencyKeys:

    def test_includes_all_output_affecting_fields(self):
        fields = MinimaxTokenPlanVideo().idempotency_key_fields
        for field in (
            "prompt", "model", "operation", "duration", "resolution",
            "first_frame_image", "prompt_optimizer", "fast_pretreatment",
            "aigc_watermark",
        ):
            assert field in fields, f"missing idempotency field: {field}"

    def test_excludes_execution_only_fields(self):
        fields = MinimaxTokenPlanVideo().idempotency_key_fields
        # These affect execution, not the result — must NOT be in the key
        for field in ("output_path", "poll_interval_seconds", "timeout_seconds"):
            assert field not in fields

    def test_differs_on_duration(self):
        tool = MinimaxTokenPlanVideo()
        base = {"prompt": "x", "model": "MiniMax-Hailuo-2.3"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "duration": 10}
        )

    def test_differs_on_resolution(self):
        tool = MinimaxTokenPlanVideo()
        base = {"prompt": "x", "model": "MiniMax-Hailuo-2.3"}
        assert tool.idempotency_key({**base, "resolution": "768P"}) != tool.idempotency_key(
            {**base, "resolution": "1080P"}
        )

    def test_differs_on_watermark(self):
        tool = MinimaxTokenPlanVideo()
        base = {"prompt": "x", "model": "MiniMax-Hailuo-2.3"}
        assert tool.idempotency_key({**base, "aigc_watermark": False}) != tool.idempotency_key(
            {**base, "aigc_watermark": True}
        )

    def test_differs_on_prompt_optimizer(self):
        tool = MinimaxTokenPlanVideo()
        base = {"prompt": "x", "model": "MiniMax-Hailuo-2.3"}
        assert tool.idempotency_key({**base, "prompt_optimizer": True}) != tool.idempotency_key(
            {**base, "prompt_optimizer": False}
        )


# ------------------------------------------------------------------
# Tool-specific behavior
# ------------------------------------------------------------------

class TestToolSpecific:

    def test_default_model_is_hailuo_23(self):
        tool = MinimaxTokenPlanVideo()
        assert tool.input_schema["properties"]["model"]["default"] == "MiniMax-Hailuo-2.3"

    def test_default_resolution_is_768p(self):
        tool = MinimaxTokenPlanVideo()
        assert tool.input_schema["properties"]["resolution"]["default"] == "768P"

    def test_default_duration_is_6(self):
        tool = MinimaxTokenPlanVideo()
        assert tool.input_schema["properties"]["duration"]["default"] == 6

    def test_default_watermark_is_false(self):
        tool = MinimaxTokenPlanVideo()
        assert tool.input_schema["properties"]["aigc_watermark"]["default"] is False

    def test_cost_zero_when_token_plan_key_set(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "test-key")
        cost = MinimaxTokenPlanVideo().estimate_cost({"prompt": "x", "duration": 6})
        assert cost == 0.0

    def test_cost_payg_when_no_token_plan_key(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        cost = MinimaxTokenPlanVideo().estimate_cost({
            "prompt": "x", "duration": 6, "resolution": "768P",
            "model": "MiniMax-Hailuo-2.3",
        })
        assert cost == 0.28

    def test_payg_exact_prices(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        tool = MinimaxTokenPlanVideo()
        cases = [
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "768P", "duration": 6}, 0.28),
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "768P", "duration": 10}, 0.56),
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "1080P", "duration": 6}, 0.49),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "768P", "duration": 6}, 0.19),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "768P", "duration": 10}, 0.32),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "1080P", "duration": 6}, 0.33),
        ]
        for inputs, expected in cases:
            assert tool.estimate_cost(inputs) == expected, f"{inputs} expected {expected}"

    def test_quota_points_exact_values(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "test-key")
        tool = MinimaxTokenPlanVideo()
        cases = [
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "768P", "duration": 6}, 1),
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "768P", "duration": 10}, 2),
            ({"model": "MiniMax-Hailuo-2.3", "resolution": "1080P", "duration": 6}, 2),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "768P", "duration": 6}, 0.7),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "768P", "duration": 10}, 1.1),
            ({"model": "MiniMax-Hailuo-2.3-Fast", "resolution": "1080P", "duration": 6}, 1.3),
        ]
        for inputs, expected in cases:
            assert tool._estimate_quota_points(inputs) == expected, f"{inputs} expected {expected}"

    def test_schema_duration_enum(self):
        schema = MinimaxTokenPlanVideo().input_schema
        assert schema["properties"]["duration"]["enum"] == [6, 10]

    def test_schema_resolution_no_720p(self):
        schema = MinimaxTokenPlanVideo().input_schema
        assert "720P" not in schema["properties"]["resolution"]["enum"]

    def test_execute_rejects_1080p_10s(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        result = MinimaxTokenPlanVideo().execute({
            "prompt": "x", "duration": 10, "resolution": "1080P",
        })
        assert result.success is False
        assert "1080P" in result.error

    def test_execute_accepts_1080p_6s(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "test-key")
        payload = MinimaxTokenPlanVideo()._build_payload({
            "prompt": "x", "duration": 6, "resolution": "1080P",
        })
        assert payload["duration"] == 6
        assert payload["resolution"] == "1080P"

    def test_build_payload_t2v(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({"prompt": "a cat"})
        assert payload["model"] == "MiniMax-Hailuo-2.3"
        assert payload["prompt"] == "a cat"
        assert payload["duration"] == 6
        assert payload["resolution"] == "768P"
        assert payload["prompt_optimizer"] is True
        assert payload["aigc_watermark"] is False
        assert "first_frame_image" not in payload

    def test_build_payload_i2v_includes_first_frame(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({
            "prompt": "motion desc",
            "operation": "image_to_video",
            "first_frame_image": "https://example.com/img.png",
        })
        assert payload["first_frame_image"] == "https://example.com/img.png"

    def test_build_payload_omits_first_frame_for_t2v(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({"prompt": "a cat", "operation": "text_to_video"})
        assert "first_frame_image" not in payload

    def test_build_payload_includes_fast_pretreatment_when_set(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({"prompt": "x", "fast_pretreatment": True})
        assert payload["fast_pretreatment"] is True

    def test_build_payload_omits_callback_url_when_absent(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({"prompt": "x"})
        assert "callback_url" not in payload

    def test_build_payload_includes_callback_url_when_set(self):
        tool = MinimaxTokenPlanVideo()
        payload = tool._build_payload({"prompt": "x", "callback_url": "https://cb.example.com"})
        assert payload["callback_url"] == "https://cb.example.com"

    def test_fast_model_rejects_t2v(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
        tool = MinimaxTokenPlanVideo()
        result = tool.execute({
            "prompt": "test",
            "model": "MiniMax-Hailuo-2.3-Fast",
            "operation": "text_to_video",
        })
        assert result.success is False
        assert "does not support text-to-video" in result.error

    def test_i2v_without_first_frame_fails(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
        tool = MinimaxTokenPlanVideo()
        result = tool.execute({
            "prompt": "test",
            "operation": "image_to_video",
        })
        assert result.success is False
        assert "first_frame_image" in result.error

    def test_no_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        result = MinimaxTokenPlanVideo().execute({"prompt": "test"})
        assert result.success is False
        assert "MINIMAX_TOKEN_PLAN_API_KEY" in result.error
        assert "MINIMAX_API_KEY" in result.error

    def test_base_url_defaults_to_cn(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_REGION", raising=False)
        tool = MinimaxTokenPlanVideo()
        assert tool._base_url() == "https://api.minimaxi.com"

    def test_base_url_global_when_region_set(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_REGION", "global")
        tool = MinimaxTokenPlanVideo()
        assert tool._base_url() == "https://api.minimax.io"

    def test_safe_error_redacts_key(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "secret-key-12345")
        redacted = MinimaxTokenPlanVideo._safe_error(
            Exception("failed with key secret-key-12345")
        )
        assert "secret-key-12345" not in redacted
        assert "[redacted]" in redacted

    def test_safe_error_redacts_token_plan_key(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "token-plan-secret-999")
        redacted = MinimaxTokenPlanVideo._safe_error(
            Exception("failed with token-plan-secret-999")
        )
        assert "token-plan-secret-999" not in redacted
        assert "[redacted]" in redacted

    def test_safe_error_no_empty_string_bug(self, monkeypatch):
        """Regression: when no key is set, _safe_error must not insert
        [redacted] between every character (the empty-string replace bug)."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_TOKEN_PLAN_API_KEY", raising=False)
        msg = MinimaxTokenPlanVideo._safe_error(Exception("abc"))
        assert msg == "abc"

    def test_api_key_prefers_token_plan(self, monkeypatch):
        """When both keys are set, the Token Plan key must be preferred
        (Fix #1 from calesthio review: the route is the product)."""
        monkeypatch.setenv("MINIMAX_API_KEY", "generic-key")
        monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "token-plan-key")
        tool = MinimaxTokenPlanVideo()
        assert tool._api_key() == "token-plan-key"

    def test_callback_url_declared_in_schema(self):
        """callback_url is forwarded to the API, so it must be in the
        input schema (Fix #3: undocumented public input)."""
        props = MinimaxTokenPlanVideo().input_schema["properties"]
        assert "callback_url" in props
        assert props["callback_url"]["type"] == "string"

    def test_check_base_resp_passes_on_success(self):
        MinimaxTokenPlanVideo._check_base_resp(200, {"base_resp": {"status_code": 0, "status_msg": "success"}})

    def test_check_base_resp_raises_on_error_code(self):
        with pytest.raises(RuntimeError, match="code 1008"):
            MinimaxTokenPlanVideo._check_base_resp(
                200, {"base_resp": {"status_code": 1008, "status_msg": "Insufficient balance"}}
            )

    def test_check_base_resp_raises_on_http_error(self):
        with pytest.raises(RuntimeError, match="HTTP 401"):
            MinimaxTokenPlanVideo._check_base_resp(
                401, {"base_resp": {"status_code": 1004, "status_msg": "Auth failed"}}
            )

    def test_json_or_raise_returns_dict(self):
        class FakeResp:
            status_code = 200
            def json(self):
                return {"ok": True}
        assert MinimaxTokenPlanVideo._json_or_raise(FakeResp()) == {"ok": True}

    def test_json_or_raise_raises_on_non_json(self):
        class FakeResp:
            status_code = 500
            def json(self):
                raise ValueError("not JSON")
        with pytest.raises(RuntimeError, match="Non-JSON"):
            MinimaxTokenPlanVideo._json_or_raise(FakeResp())


# ------------------------------------------------------------------
# Registry discovery
# ------------------------------------------------------------------

class TestRegistryDiscovery:

    def test_discoverable(self):
        from tools.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover()
        names = {t.name for t in registry._tools.values()}
        assert "minimax_tokenplan_video" in names

    def test_distinct_from_fal_minimax(self):
        """The Token Plan tool must be a separate entry from the FAL-backed
        minimax_video — this is the core point of issue #216: the cost route
        must be explicit."""
        from tools.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover()
        minimax_tools = [
            t for t in registry._tools.values()
            if t.provider in ("minimax", "minimax_tokenplan")
        ]
        names = {t.name for t in minimax_tools}
        assert "minimax_tokenplan_video" in names
        assert "minimax_video" in names
        assert "minimax_tokenplan_video" != "minimax_video"
