"""Provider-routing regression coverage for VideoSelector (REVIEW §8 #3, #5, #7, #10).

The selector had NO routing tests (``ls tests | grep video`` turned up only
provider-specific suites), so several routing defects shipped:

- #3 Seedance dedup race: two tools sharing provider="seedance" (the fal and
  Replicate backends) were keyed by provider string in tool_by_provider, so
  only the first-registered was ever selectable. The other was invisible.
- #5 preferred_provider had no score-gap gate: it returned the preferred
  provider on the first ranking match regardless of how far below the top it
  scored (the comment claimed "unless drastically worse" but nothing enforced it).
- #7 fallback_tools appended image_selector unconditionally — a motion-required
  brief could fall back to an image-only tool.

These tests exercise _select_best_tool / estimate_cost / estimate_runtime /
fallback_tools_for directly with stub providers, patching lib.scoring.rank_providers
for deterministic rankings so we test ROUTING logic, not the scorer.
"""

from __future__ import annotations

from typing import Any

import pytest

from tools.base_tool import ToolStatus
from tools.video.video_selector import VideoSelector


class _StubTool:
    """Minimal stand-in satisfying what _select_best_tool / _filter_candidates touch."""

    capability = "video_generation"

    def __init__(
        self,
        name: str,
        provider: str,
        *,
        supports_image_to_video: bool = True,
        status: ToolStatus = ToolStatus.AVAILABLE,
        cost: float = 0.10,
        runtime: float = 60.0,
    ) -> None:
        self.name = name
        self.provider = provider
        self.quality_score: float | None = None
        self.best_for = [name]
        self.supports = {
            "text_to_video": True,
            "image_to_video": supports_image_to_video,
        }
        self.input_schema = {"properties": {"prompt": {}}}
        self._status = status
        self._cost = cost
        self._runtime = runtime

    # --- BaseTool surface used by the selector -------------------------------
    def get_status(self) -> ToolStatus:
        return self._status

    def is_operation_available(self, operation: str) -> bool:
        return self.supports.get(operation, False)

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "agent_skills": [],
            "best_for": self.best_for,
            "supports": self.supports,
            "quality_score": self.quality_score,
        }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return self._cost

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return self._runtime


# ProviderScore.weighted_score is a read-only computed property, so we can't
# override it per-instance. Instead _ScoreStub exposes the same attribute surface
# (provider / tool_name / weighted_score) the selector reads via getattr.
class _ScoreStub:
    def __init__(self, tool_name: str, provider: str, weighted: float) -> None:
        self.tool_name = tool_name
        self.provider = provider
        self.weighted_score = weighted

    def explain(self) -> str:  # noqa: D401 - selector may call this
        return f"{self.tool_name} ({self.provider}): {self.weighted_score:.2f}"

    def to_dict(self) -> dict[str, Any]:
        return {"tool_name": self.tool_name, "provider": self.provider, "weighted_score": self.weighted_score}


@pytest.fixture()
def rankings(monkeypatch):
    """Set the ranking table the patched rank_providers returns."""
    table: list[_ScoreStub] = []

    def fake_rank(candidates, task_context):  # noqa: ANN001
        return list(table)

    monkeypatch.setattr("lib.scoring.rank_providers", fake_rank)
    return table


# ---------------------------------------------------------------------------
# #3 — Seedance dedup race: two tools, same provider, must both be selectable
# ---------------------------------------------------------------------------

def test_two_tools_sharing_provider_are_both_selectable(rankings):
    """The higher-RANKED of two same-provider tools wins; the other isn't shadowed.

    Pre-fix, tool_by_provider keyed by provider string, so whichever of
    seedance_video / seedance_replicate registered second was unreachable
    even if it ranked higher.
    """
    fal = _StubTool("seedance_video", "seedance")
    rep = _StubTool("seedance_replicate", "seedance")
    rankings.extend([
        _ScoreStub("seedance_replicate", "seedance", 0.90),  # ranked higher
        _ScoreStub("seedance_video", "seedance", 0.80),
    ])

    tool, score = VideoSelector()._select_best_tool(
        {"preferred_provider": "auto"}, [fal, rep], {}
    )
    assert tool is not None
    assert tool.name == "seedance_replicate", "higher-ranked same-provider tool must win"


def test_lower_ranked_same_provider_still_reachable_when_higher_unavailable(rankings):
    """If the top-ranked same-provider tool is unavailable, the other is selected.

    Pre-fix the unavailable one could shadow the available one in tool_by_provider
    depending on registration order.
    """
    fal = _StubTool("seedance_video", "seedance", status=ToolStatus.UNAVAILABLE)
    rep = _StubTool("seedance_replicate", "seedance")
    rankings.extend([
        _ScoreStub("seedance_video", "seedance", 0.95),     # ranked higher but unavailable
        _ScoreStub("seedance_replicate", "seedance", 0.80),
    ])

    tool, score = VideoSelector()._select_best_tool(
        {"preferred_provider": "auto"}, [fal, rep], {}
    )
    assert tool is not None
    assert tool.name == "seedance_replicate"


# ---------------------------------------------------------------------------
# #5 — preferred_provider score-gap gate
# ---------------------------------------------------------------------------

def test_preferred_provider_honored_when_within_gap(rankings):
    """Preferred provider ranked #2 but within the gap → selected."""
    veo = _StubTool("veo_video", "veo")
    kling = _StubTool("kling_video", "kling")
    rankings.extend([
        _ScoreStub("veo_video", "veo", 0.90),
        _ScoreStub("kling_video", "kling", 0.80),  # 0.10 below top, within default 0.15 gap
    ])

    tool, score = VideoSelector()._select_best_tool(
        {"preferred_provider": "kling"}, [veo, kling], {}
    )
    assert tool.name == "kling_video"


def test_preferred_provider_ignored_when_drastically_worse(rankings):
    """Preferred provider far below top → top-ranked provider wins instead.

    Pre-fix the preferred provider was returned on the first ranking match
    regardless of the gap (no gate), silently dragging selection to a worse tool.
    """
    veo = _StubTool("veo_video", "veo")
    kling = _StubTool("kling_video", "kling")
    rankings.extend([
        _ScoreStub("veo_video", "veo", 0.95),
        _ScoreStub("kling_video", "kling", 0.50),  # 0.45 below top, outside 0.15 gap
    ])

    tool, score = VideoSelector()._select_best_tool(
        {"preferred_provider": "kling"}, [veo, kling], {}
    )
    assert tool.name == "veo_video", "preference must yield to a drastically better top"


def test_preferred_provider_gap_is_configurable(rankings):
    """A wider gap lets an otherwise-too-low preferred provider win."""
    veo = _StubTool("veo_video", "veo")
    kling = _StubTool("kling_video", "kling")
    rankings.extend([
        _ScoreStub("veo_video", "veo", 0.95),
        _ScoreStub("kling_video", "kling", 0.70),  # 0.25 below top
    ])

    # default gap (0.15) → veo wins
    tool_default, _ = VideoSelector()._select_best_tool(
        {"preferred_provider": "kling"}, [veo, kling], {}
    )
    assert tool_default.name == "veo_video"

    # widened gap (0.30) → kling wins
    tool_wide, _ = VideoSelector()._select_best_tool(
        {"preferred_provider": "kling", "preferred_provider_gap": 0.30}, [veo, kling], {}
    )
    assert tool_wide.name == "kling_video"


def test_preferred_provider_not_in_rankings_falls_through(rankings):
    """An unknown/preferred provider that doesn't rank yields the top provider."""
    veo = _StubTool("veo_video", "veo")
    rankings.append(_ScoreStub("veo_video", "veo", 0.90))

    tool, _ = VideoSelector()._select_best_tool(
        {"preferred_provider": "nonexistent"}, [veo], {}
    )
    assert tool.name == "veo_video"


# ---------------------------------------------------------------------------
# #7 — fallback_tools gate for motion-required briefs
# ---------------------------------------------------------------------------

def test_fallback_excludes_image_selector_for_image_to_video():
    sel = VideoSelector()
    fallback = sel.fallback_tools_for({"operation": "image_to_video"})
    assert "image_selector" not in fallback


def test_fallback_excludes_image_selector_for_reference_to_video():
    sel = VideoSelector()
    fallback = sel.fallback_tools_for({"operation": "reference_to_video"})
    assert "image_selector" not in fallback


def test_fallback_keeps_image_selector_for_text_to_video():
    """A still-image degraded fallback is acceptable for a non-motion brief."""
    sel = VideoSelector()
    fallback = sel.fallback_tools_for({"operation": "text_to_video"})
    assert "image_selector" in fallback


def test_static_fallback_tools_property_still_lists_image_selector():
    """The input-agnostic property preserves the old shape for external consumers."""
    assert "image_selector" in VideoSelector().fallback_tools


# ---------------------------------------------------------------------------
# #10 — estimate_cost / estimate_runtime delegate to the selected provider
# ---------------------------------------------------------------------------

def test_estimate_cost_uses_selected_provider(rankings):
    veo = _StubTool("veo_video", "veo", cost=0.42)
    kling = _StubTool("kling_video", "kling", cost=0.99)
    rankings.append(_ScoreStub("veo_video", "veo", 0.90))
    rankings.append(_ScoreStub("kling_video", "kling", 0.50))

    sel = VideoSelector()
    sel._providers = lambda: [veo, kling]  # type: ignore[assignment]
    assert sel.estimate_cost({"prompt": "x"}) == pytest.approx(0.42)


def test_estimate_runtime_uses_selected_provider(rankings):
    veo = _StubTool("veo_video", "veo", runtime=123.0)
    rankings.append(_ScoreStub("veo_video", "veo", 0.90))

    sel = VideoSelector()
    sel._providers = lambda: [veo]  # type: ignore[assignment]
    assert sel.estimate_runtime({"prompt": "x"}) == pytest.approx(123.0)


def test_estimate_cost_zero_when_no_providers():
    sel = VideoSelector()
    sel._providers = lambda: []  # type: ignore[assignment]
    assert sel.estimate_cost({"prompt": "x"}) == 0.0
