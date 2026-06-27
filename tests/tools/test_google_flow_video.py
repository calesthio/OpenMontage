from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.video.google_flow_browser_bridge import (
    GoogleFlowBridgeError,
    GoogleFlowBrowserBridge,
    redact_payload,
    redact_text,
)
from tools.video.google_flow_video import GoogleFlowVideo
from tools.video.video_selector import VideoSelector


def enable_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_FLOW_ENABLED", "true")
    monkeypatch.setenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", "1")
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_available", staticmethod(lambda: True))
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_chromium_available", staticmethod(lambda: True))


def disable_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_FLOW_ENABLED", "false")
    monkeypatch.delenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", raising=False)
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_available", staticmethod(lambda: False))
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_chromium_available", staticmethod(lambda: False))


def assert_no_secret_leaks(value: Any) -> None:
    blob = json.dumps(value, default=str) if not isinstance(value, str) else value
    forbidden = [
        "SID=secret",
        "Bearer secret",
        "ya29.secret",
        "user@example.com",
        "/Users/tester/.openmontage/google-flow-profile",
        "google-flow-profile/Default",
        "Authorization",
        "Cookie:",
    ]
    for needle in forbidden:
        assert needle not in blob


class FakeBridge:
    instances: list["FakeBridge"] = []
    mode = "success"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.closed = False
        self.profile_dir = kwargs.get("profile_dir")
        self.__class__.instances.append(self)

    def open_login(self, *, keep_open: bool = True) -> dict[str, Any]:
        return {
            "authenticated": False,
            "flow_url": "https://labs.google/fx/tools/flow",
            "profile_dir": "/Users/tester/.openmontage/google-flow-profile",
            "account": "user@example.com",
            "browser_open": keep_open,
        }

    def check_auth(self) -> dict[str, Any]:
        if self.mode == "logged_out":
            return {"authenticated": False, "account": "user@example.com"}
        return {"authenticated": True, "account": "user@example.com"}

    def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        if self.mode != "success":
            raise GoogleFlowBridgeError(
                "Cookie: SID=secret Authorization: Bearer secret user@example.com "
                "/Users/tester/.openmontage/google-flow-profile",
                code=self.mode,
                retryable=self.mode in {"timeout", "ui_changed", "download_failed"},
                details={
                    "Authorization": "Bearer secret",
                    "profile_dir": "/Users/tester/.openmontage/google-flow-profile",
                    "account": "user@example.com",
                },
            )
        output = Path(kwargs["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-mp4")
        return {
            "output_path": str(output),
            "flow_url": "https://labs.google/fx/tools/flow",
            "Cookie": "SID=secret",
            "Authorization": "Bearer secret",
            "account": "user@example.com",
            "profile_dir": "/Users/tester/.openmontage/google-flow-profile",
        }

    def close(self) -> None:
        self.closed = True


class FakeVideoProvider(BaseTool):
    tier = ToolTier.GENERATE
    capability = "video_generation"
    stability = ToolStability.EXPERIMENTAL
    runtime = ToolRuntime.HYBRID
    capabilities = ["text_to_video"]
    input_schema = {"type": "object", "properties": {"prompt": {"type": "string"}}}

    def __init__(
        self,
        *,
        name: str,
        provider: str,
        requires_explicit_preference: bool = False,
        quality_score: float = 0.5,
    ) -> None:
        self.name = name
        self.provider = provider
        self.supports = {
            "text_to_video": True,
            "requires_explicit_preference": requires_explicit_preference,
        }
        self.quality_score = quality_score
        self.best_for = ["social video", provider]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={"selected": self.provider})


def test_google_flow_provider_metadata() -> None:
    tool = GoogleFlowVideo()
    info = tool.get_info()
    assert info["name"] == "google_flow_video"
    assert info["provider"] == "google_flow"
    assert info["capability"] == "video_generation"
    assert info["stability"] == "experimental"
    assert info["runtime"] == "hybrid"
    assert tool.supports["requires_explicit_preference"] is True
    assert tool.supports["requires_browser_automation_confirmation"] is True
    assert tool.supports["stores_browser_session"] is True
    assert tool.supports["stores_repo_auth_artifacts"] is False
    assert "playwright-recording" in tool.agent_skills


def test_status_is_gated_by_two_env_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = GoogleFlowVideo()
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_available", staticmethod(lambda: True))
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_chromium_available", staticmethod(lambda: True))

    monkeypatch.delenv("GOOGLE_FLOW_ENABLED", raising=False)
    monkeypatch.delenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("GOOGLE_FLOW_ENABLED", "true")
    assert tool.get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", "1")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_status_requires_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_FLOW_ENABLED", "true")
    monkeypatch.setenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", "1")
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_available", staticmethod(lambda: False))
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_chromium_available", staticmethod(lambda: True))
    assert GoogleFlowVideo().get_status() == ToolStatus.UNAVAILABLE


def test_status_requires_playwright_chromium(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_FLOW_ENABLED", "true")
    monkeypatch.setenv("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW", "1")
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_available", staticmethod(lambda: True))
    monkeypatch.setattr(GoogleFlowVideo, "_playwright_chromium_available", staticmethod(lambda: False))
    assert GoogleFlowVideo().get_status() == ToolStatus.UNAVAILABLE


def test_registry_discovers_google_flow_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    disable_flow(monkeypatch)
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("google_flow_video")
    assert isinstance(tool, GoogleFlowVideo)

    summary = registry.provider_menu_summary()
    video_cap = next(item for item in summary["capabilities"] if item["capability"] == "video_generation")
    assert "google_flow" in video_cap["unavailable_providers"]


def test_selector_auto_skips_explicit_only_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = FakeVideoProvider(
        name="fake_google_flow_video",
        provider="google_flow",
        requires_explicit_preference=True,
        quality_score=1.0,
    )
    fallback = FakeVideoProvider(
        name="fake_regular_video",
        provider="regular",
        requires_explicit_preference=False,
        quality_score=0.1,
    )
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [flow, fallback])

    result = selector.execute({"prompt": "make a travel short", "preferred_provider": "auto"})

    assert result.success
    assert result.data["selected_provider"] == "regular"
    assert result.data["selected_tool"] == "fake_regular_video"


def test_selector_explicit_preference_can_route_to_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = FakeVideoProvider(
        name="fake_google_flow_video",
        provider="google_flow",
        requires_explicit_preference=True,
        quality_score=1.0,
    )
    fallback = FakeVideoProvider(name="fake_regular_video", provider="regular")
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [flow, fallback])

    result = selector.execute({"prompt": "make a travel short", "preferred_provider": "google_flow"})

    assert result.success
    assert result.data["selected_provider"] == "google_flow"
    assert result.data["selected_tool"] == "fake_google_flow_video"


def test_selector_rank_auto_skips_explicit_only_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = FakeVideoProvider(
        name="fake_google_flow_video",
        provider="google_flow",
        requires_explicit_preference=True,
        quality_score=1.0,
    )
    fallback = FakeVideoProvider(name="fake_regular_video", provider="regular")
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [flow, fallback])

    result = selector.execute({"prompt": "make a travel short", "operation": "rank"})

    assert result.success
    ranked_providers = [item["provider"] for item in result.data["rankings"]]
    assert "google_flow" not in ranked_providers
    assert "regular" in ranked_providers


def test_selector_rank_explicit_preference_includes_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = FakeVideoProvider(
        name="fake_google_flow_video",
        provider="google_flow",
        requires_explicit_preference=True,
        quality_score=1.0,
    )
    fallback = FakeVideoProvider(name="fake_regular_video", provider="regular")
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [flow, fallback])

    result = selector.execute(
        {
            "prompt": "make a travel short",
            "operation": "rank",
            "preferred_provider": "google_flow",
        }
    )

    assert result.success
    ranked_providers = [item["provider"] for item in result.data["rankings"]]
    assert "google_flow" in ranked_providers


def test_generation_requires_explicit_provider_and_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_flow(monkeypatch)
    tool = GoogleFlowVideo()

    missing_preference = tool.execute({"prompt": "x", "confirm_browser_automation": True})
    assert not missing_preference.success
    assert "preferred_provider" in (missing_preference.error or "")

    missing_confirmation = tool.execute({"prompt": "x", "preferred_provider": "google_flow"})
    assert not missing_confirmation.success
    assert "confirm_browser_automation" in (missing_confirmation.error or "")


def test_mocked_bridge_success_and_safe_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    enable_flow(monkeypatch)
    FakeBridge.instances = []
    FakeBridge.mode = "success"
    monkeypatch.setattr("tools.video.google_flow_video.GoogleFlowBrowserBridge", FakeBridge)
    output_path = tmp_path / "flow.mp4"

    result = GoogleFlowVideo().execute(
        {
            "prompt": "A vertical travel opener",
            "operation": "text_to_video",
            "preferred_provider": "google_flow",
            "confirm_browser_automation": True,
            "aspect_ratio": "9:16",
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert result.data["provider"] == "google_flow"
    assert result.data["output_path"] == str(output_path)
    assert result.artifacts == [str(output_path)]
    assert FakeBridge.instances[-1].closed is True
    assert_no_secret_leaks(result.data)


@pytest.mark.parametrize("mode", ["logged_out", "timeout", "ui_changed", "download_failed"])
def test_mocked_bridge_failures_are_categorized_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
) -> None:
    enable_flow(monkeypatch)
    FakeBridge.instances = []
    FakeBridge.mode = mode
    monkeypatch.setattr("tools.video.google_flow_video.GoogleFlowBrowserBridge", FakeBridge)

    result = GoogleFlowVideo().execute(
        {
            "prompt": "A vertical travel opener",
            "operation": "text_to_video",
            "preferred_provider": "google_flow",
            "confirm_browser_automation": True,
            "output_path": str(tmp_path / "flow.mp4"),
        }
    )

    assert not result.success
    assert result.data["error_code"] == mode
    assert FakeBridge.instances[-1].closed is True
    assert_no_secret_leaks(result.error)
    assert_no_secret_leaks(result.data)


def test_check_auth_does_not_require_generation_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_flow(monkeypatch)
    FakeBridge.instances = []
    FakeBridge.mode = "logged_out"
    monkeypatch.setattr("tools.video.google_flow_video.GoogleFlowBrowserBridge", FakeBridge)

    result = GoogleFlowVideo().execute({"operation": "check_auth"})

    assert result.success
    assert result.data["authenticated"] is False
    assert FakeBridge.instances[-1].closed is True
    assert_no_secret_leaks(result.data)


def test_open_login_can_leave_browser_open(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_flow(monkeypatch)
    FakeBridge.instances = []
    FakeBridge.mode = "logged_out"
    monkeypatch.setattr("tools.video.google_flow_video.GoogleFlowBrowserBridge", FakeBridge)

    result = GoogleFlowVideo().execute({"operation": "open_login", "keep_open": True})

    assert result.success
    assert FakeBridge.instances[-1].closed is False
    assert_no_secret_leaks(result.data)


def test_redaction_removes_browser_session_material() -> None:
    profile = "/Users/tester/.openmontage/google-flow-profile"
    raw = (
        "Cookie: SID=secret Authorization: Bearer secret ya29.secret "
        "user@example.com /Users/tester/.openmontage/google-flow-profile/Default"
    )
    redacted = redact_text(raw, profile_dir=profile)
    assert_no_secret_leaks(redacted)
    assert "[REDACTED]" in redacted

    payload = {
        "headers": {"Authorization": "Bearer secret", "Cookie": "SID=secret"},
        "account": "user@example.com",
        "profile_dir": profile,
        "safe": "output.mp4",
    }
    cleaned = redact_payload(payload, profile_dir=profile)
    assert cleaned["safe"] == "output.mp4"
    assert_no_secret_leaks(cleaned)


def test_bridge_rejects_non_flow_urls() -> None:
    with pytest.raises(GoogleFlowBridgeError) as exc:
        GoogleFlowBrowserBridge(flow_url="https://example.com/fake-flow")
    assert exc.value.code == "validation"


def test_bridge_rejects_remote_cdp_urls() -> None:
    with pytest.raises(GoogleFlowBridgeError) as exc:
        GoogleFlowBrowserBridge(cdp_url="http://198.51.100.10:9222")
    assert exc.value.code == "validation"


def test_execute_returns_tool_result_for_invalid_flow_url(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_flow(monkeypatch)
    monkeypatch.setenv("GOOGLE_FLOW_URL", "https://example.com/fake-flow")

    result = GoogleFlowVideo().execute({"operation": "check_auth"})

    assert not result.success
    assert "validation" in (result.error or "")


@pytest.mark.skipif(os.environ.get("GOOGLE_FLOW_E2E") != "1", reason="live Flow E2E is opt-in")
def test_live_google_flow_check_auth() -> None:
    result = GoogleFlowVideo().execute({"operation": "check_auth"})
    assert result.success
    assert "authenticated" in result.data
