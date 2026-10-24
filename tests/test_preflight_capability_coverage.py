from __future__ import annotations

from dataclasses import dataclass

from lib.pipeline_loader import get_stage_tools, load_pipeline
from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry


@dataclass
class FakeTool:
    name: str
    capability: str
    status: ToolStatus
    provider: str = "fake"

    def get_status(self) -> ToolStatus:
        return self.status


def registry_with(*tools: FakeTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry._discovered_packages.add("tools")
    for tool in tools:
        registry.register(tool)  # type: ignore[arg-type]
    return registry


def test_capability_coverage_counts_available_providers() -> None:
    registry = registry_with(
        FakeTool("video_selector", "video_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("video_a", "video_generation", ToolStatus.AVAILABLE),
        FakeTool("video_b", "video_generation", ToolStatus.UNAVAILABLE),
    )

    assert registry.capability_coverage(["video_selector"]) == {
        "video_generation": {"available": 1, "total": 2}
    }


def test_capability_coverage_deduplicates_capabilities_and_ignores_unknown_tools() -> None:
    registry = registry_with(
        FakeTool("image_selector", "image_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("image_a", "image_generation", ToolStatus.AVAILABLE),
    )

    assert registry.capability_coverage(
        ["image_selector", "image_selector", "missing_tool"]
    ) == {"image_generation": {"available": 1, "total": 1}}


def test_uncovered_capabilities_returns_only_zero_provider_families() -> None:
    registry = registry_with(
        FakeTool("image_selector", "image_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("image_a", "image_generation", ToolStatus.UNAVAILABLE),
        FakeTool("video_selector", "video_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("video_a", "video_generation", ToolStatus.AVAILABLE),
    )

    assert registry.uncovered_capabilities(["image_selector", "video_selector"]) == [
        "image_generation"
    ]


def test_get_stage_tools_unions_every_declared_tool_field() -> None:
    manifest = {
        "stages": [
            {
                "name": "assets",
                "required_tools": ["required"],
                "optional_tools": ["optional", "shared"],
                "fallback_tools": ["fallback"],
                "preferred_tools": ["preferred"],
                "tools_available": ["available", "shared"],
                "sub_stages": [{"tools_available": ["sub-stage"]}],
            }
        ]
    }

    assert get_stage_tools(manifest, "assets") == {
        "required",
        "optional",
        "fallback",
        "preferred",
        "available",
        "shared",
        "sub-stage",
    }


def test_get_stage_tools_returns_empty_set_for_unknown_stage() -> None:
    assert get_stage_tools({"stages": []}, "missing") == set()


def test_cinematic_assets_exposes_provider_capabilities_to_preflight() -> None:
    manifest = load_pipeline("cinematic")
    tools = get_stage_tools(manifest, "assets")
    registry = registry_with(
        FakeTool("image_selector", "image_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("image_a", "image_generation", ToolStatus.UNAVAILABLE),
        FakeTool("video_selector", "video_generation", ToolStatus.UNAVAILABLE, "selector"),
        FakeTool("video_a", "video_generation", ToolStatus.UNAVAILABLE),
        FakeTool("music_gen", "music_generation", ToolStatus.UNAVAILABLE),
    )

    assert {"image_selector", "video_selector", "music_gen"}.issubset(tools)
    assert registry.uncovered_capabilities(tools) == [
        "image_generation",
        "music_generation",
        "video_generation",
    ]
