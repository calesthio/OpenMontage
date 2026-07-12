"""Regression tests for tool_registry.py / base_tool.py / cost_tracker.py core
contract behavior: per-instance mutable defaults, loud failure on a malformed
dependency declaration, the tool-name collision guard, the get_by_capability
vs find_by_capabilities distinction, the DEGRADED provider_menu() bucket, the
name-agnostic composition-runtime discovery in provider_menu_summary(), the
music line-item cost default, and discover()'s per-module fault isolation.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, DependencyError, ToolResult, ToolStatus
from tools.cost_tracker import CostTracker
from tools.tool_registry import ToolRegistry


class _PlainTool(BaseTool):
    name = "plain_tool"

    def execute(self, inputs):
        return ToolResult(success=True)


class _CapableTool(BaseTool):
    name = "capable_tool"
    capabilities = ["alpha", "beta"]

    def execute(self, inputs):
        return ToolResult(success=True)


def test_mutable_defaults_left_at_baseclass_level_are_not_shared():
    a = _PlainTool()
    b = _PlainTool()
    a.capabilities.append("mutated")
    a.best_for.append("mutated")
    a.resource_profile.vram_mb = 9999
    a.retry_policy.retryable_errors.append("mutated")

    assert b.capabilities == []
    assert b.best_for == []
    assert b.resource_profile.vram_mb == 0
    assert b.retry_policy.retryable_errors == []


def test_subclass_class_level_defaults_are_preserved_but_still_isolated():
    a = _CapableTool()
    b = _CapableTool()
    assert a.capabilities == ["alpha", "beta"]

    a.capabilities.append("gamma")
    assert b.capabilities == ["alpha", "beta"]


class _BadDepTool(BaseTool):
    name = "bad_dep_tool"
    dependencies = ["binary:ffmpeg"]

    def execute(self, inputs):
        return ToolResult(success=True)


def test_unrecognized_dependency_prefix_fails_loud_instead_of_passing_silently():
    tool = _BadDepTool()
    with pytest.raises(DependencyError):
        tool.check_dependencies()
    # get_status() must not report AVAILABLE for a dependency it never
    # actually understood how to check.
    assert tool.get_status() == ToolStatus.UNAVAILABLE


class _DupA(BaseTool):
    name = "dup_name"

    def execute(self, inputs):
        return ToolResult(success=True)


class _DupB(BaseTool):
    name = "dup_name"

    def execute(self, inputs):
        return ToolResult(success=True)


def test_register_raises_on_name_collision_between_different_classes():
    reg = ToolRegistry()
    reg.register(_DupA())
    with pytest.raises(ValueError):
        reg.register(_DupB())


def test_register_allows_idempotent_reregistration_of_the_same_class():
    reg = ToolRegistry()
    reg.register(_DupA())
    reg.register(_DupA())  # e.g. a second discover() pass; must not raise
    assert reg.get("dup_name") is not None


class _SemTool(BaseTool):
    name = "sem_tool"
    capability = "video_generation"
    capabilities = ["image_to_video"]

    def execute(self, inputs):
        return ToolResult(success=True)


def test_get_by_capability_and_find_by_capabilities_check_different_fields():
    reg = ToolRegistry()
    reg.register(_SemTool())

    assert reg.get_by_capability("video_generation")[0].name == "sem_tool"
    assert reg.get_by_capability("image_to_video") == []

    assert reg.find_by_capabilities("image_to_video")[0].name == "sem_tool"
    assert reg.find_by_capabilities("video_generation") == []


class _DegradedTool(BaseTool):
    name = "degraded_tool"
    capability = "video_generation"
    provider = "degraded_provider"

    def get_status(self):
        return ToolStatus.DEGRADED

    def execute(self, inputs):
        return ToolResult(success=True)


def test_provider_menu_buckets_degraded_tools_separately_from_unavailable():
    reg = ToolRegistry()
    reg.register(_DegradedTool())
    reg._discovered_packages.add("tools")  # skip real package discovery

    menu = reg.provider_menu()
    bucket = menu["video_generation"]
    assert bucket["available"] == []
    assert bucket["unavailable"] == []
    assert bucket["degraded"][0]["name"] == "degraded_tool"


class _FakeCompositionTool(BaseTool):
    name = "fake_composer"
    capability = "composition"

    def get_info(self):
        info = super().get_info()
        info["render_engines"] = {"remotion": True, "hyperframes": False, "ffmpeg": True}
        return info

    def execute(self, inputs):
        return ToolResult(success=True)


def test_provider_menu_summary_finds_render_engines_without_hardcoded_tool_name():
    """Regression: provider_menu_summary() used to look up composition
    runtimes via self._tools.get("video_compose") by name. A tool reporting
    render_engines under any other name must still surface them."""
    reg = ToolRegistry()
    reg.register(_FakeCompositionTool())
    reg._discovered_packages.add("tools")

    summary = reg.provider_menu_summary()
    assert summary["composition_runtimes"] == {
        "remotion": True,
        "hyperframes": False,
        "ffmpeg": True,
    }


def test_estimate_from_reference_music_line_item_defaults_to_nonzero_cost():
    """Regression: cost_per_track used to default to $0.00 while every other
    category (image/video/tts) defaulted non-zero, understating estimates
    whenever a tool_plan omitted an explicit music cost."""
    tracker = CostTracker()
    result = tracker.estimate_from_reference(
        video_analysis_brief={
            "structure_analysis": {
                "total_scenes": 5,
                "pacing_profile": {"pacing_style": "steady_educational"},
            },
            "narration_transcript": {"word_count": 100},
            "source": {"duration_seconds": 60},
        },
        target_duration_seconds=60,
        tool_plan={"music": {"tool": "suno_music"}},
    )
    music_item = next(item for item in result["line_items"] if item["category"] == "music")
    assert music_item["unit_cost_usd"] > 0
    assert music_item["total_usd"] > 0


def test_discover_skips_broken_module_but_registers_the_rest(tmp_path, monkeypatch, caplog):
    """Regression: discover() used to have no try/except around importing or
    registering each discovered module, so one tool module that raises at
    import time or __init__ time took down the ENTIRE registry scan -- not
    just the one broken tool. It must now log a warning naming the broken
    module and keep discovering the rest."""
    pkg_dir = tmp_path / "fault_iso_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "good_tool.py").write_text(
        "from tools.base_tool import BaseTool, ToolResult\n"
        "\n"
        "class GoodTool(BaseTool):\n"
        "    name = 'fault_iso_good_tool'\n"
        "\n"
        "    def execute(self, inputs):\n"
        "        return ToolResult(success=True)\n"
    )
    (pkg_dir / "broken_tool.py").write_text(
        "raise RuntimeError('boom: simulated import-time failure')\n"
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    for mod_name in (
        "fault_iso_pkg",
        "fault_iso_pkg.good_tool",
        "fault_iso_pkg.broken_tool",
    ):
        monkeypatch.delitem(sys.modules, mod_name, raising=False)

    reg = ToolRegistry()
    with caplog.at_level("WARNING"):
        discovered = reg.discover(package_name="fault_iso_pkg")

    assert "fault_iso_good_tool" in discovered
    assert reg.get("fault_iso_good_tool") is not None
    assert any(
        "fault_iso_pkg.broken_tool" in record.message for record in caplog.records
    )
