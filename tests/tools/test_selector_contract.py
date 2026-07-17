"""Characterization tests for the three scored selectors.

Written BEFORE the SelectorBase extraction (audit 2026-07-15, structural
item 1) because the selectors had almost no behavioral coverage — the only
existing tests bind private methods (_filter_candidates/_tool_selectable/
_rank_inputs) directly and would keep passing through a behavior change.

These pin what the selectors do TODAY, including the places where the three
disagree. A refactor that keeps them green is behavior-preserving; a
deliberate convergence must update the specific test and say so.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.tts_selector import TTSSelector  # noqa: E402
from tools.base_tool import (  # noqa: E402
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.graphics.image_selector import ImageSelector  # noqa: E402
from tools.video.video_selector import VideoSelector  # noqa: E402


class _FakeProvider(BaseTool):
    """A minimal selectable provider. Records the dict it was executed with."""

    tier = ToolTier.GENERATE
    stability = ToolStability.PRODUCTION
    runtime = ToolRuntime.API
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC

    def __init__(self, name, provider, *, schema_props=None, cost=1.0):
        self.name = name
        self.provider = provider
        self.capability = "test"
        self.best_for = [f"{provider} strength"]
        self.agent_skills = [f"{provider}-skill"]
        self.input_schema = {"properties": schema_props or {"prompt": {}, "text": {}}}
        self.supports = {"text_to_video": True, "generate": True}
        self._cost = cost
        self.seen_inputs = None
        super().__init__()

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs) -> float:
        return self._cost

    def estimate_runtime(self, inputs) -> float:
        return 1.0

    def execute(self, inputs) -> ToolResult:
        self.seen_inputs = dict(inputs)
        return ToolResult(success=True, data={"ok": True})


SELECTORS = [
    pytest.param(VideoSelector, "prompt", "text_to_video", id="video"),
    pytest.param(TTSSelector, "text", "generate", id="tts"),
    pytest.param(ImageSelector, "prompt", "generate", id="image"),
]


def _patch_providers(monkeypatch, selector, providers):
    monkeypatch.setattr(type(selector), "_providers", lambda self: list(providers))


@pytest.mark.parametrize("cls,prompt_key,default_op", SELECTORS)
class TestSharedSelectorContract:
    """Behavior all three genuinely agree on — the extraction must keep it."""

    def test_selection_decorates_the_result(self, cls, prompt_key, default_op, monkeypatch):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        b = _FakeProvider("beta_tool", "beta")
        _patch_providers(monkeypatch, sel, [a, b])

        result = sel.execute({prompt_key: "hello world"})
        assert result.success
        assert result.data["selected_tool"] in {"alpha_tool", "beta_tool"}
        assert result.data["selected_provider"] in {"alpha", "beta"}
        assert result.data["selection_reason"]
        assert "provider_score" in result.data
        # _tool_context_payload keys
        assert "selected_tool_agent_skills" in result.data
        assert "required_agent_skills" in result.data
        assert "selected_tool_usage_location" in result.data
        assert "selected_tool_best_for" in result.data
        # every other AVAILABLE provider, minus the winner
        alternatives = result.data["alternatives_considered"]
        assert result.data["selected_tool"] not in alternatives
        assert len(alternatives) == 1

    def test_preferred_provider_wins(self, cls, prompt_key, default_op, monkeypatch):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        b = _FakeProvider("beta_tool", "beta")
        _patch_providers(monkeypatch, sel, [a, b])

        result = sel.execute({prompt_key: "x", "preferred_provider": "beta"})
        assert result.data["selected_provider"] == "beta"

    def test_allowed_providers_filters(self, cls, prompt_key, default_op, monkeypatch):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        b = _FakeProvider("beta_tool", "beta")
        _patch_providers(monkeypatch, sel, [a, b])

        result = sel.execute({prompt_key: "x", "allowed_providers": ["alpha"]})
        assert result.data["selected_provider"] == "alpha"

    def test_no_providers_fails_cleanly(self, cls, prompt_key, default_op, monkeypatch):
        sel = cls()
        _patch_providers(monkeypatch, sel, [])
        result = sel.execute({prompt_key: "x"})
        assert result.success is False
        assert "available" in (result.error or "").lower()

    def test_get_status_reflects_providers(self, cls, prompt_key, default_op, monkeypatch):
        sel = cls()
        _patch_providers(monkeypatch, sel, [])
        assert sel.get_status() == ToolStatus.UNAVAILABLE
        _patch_providers(monkeypatch, sel, [_FakeProvider("a_tool", "alpha")])
        assert sel.get_status() == ToolStatus.AVAILABLE

    def test_fallback_tools_and_provider_matrix_are_discovered(
        self, cls, prompt_key, default_op, monkeypatch
    ):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        _patch_providers(monkeypatch, sel, [a])
        # video_selector appends image_selector as a cross-capability last resort.
        assert "alpha_tool" in sel.fallback_tools
        assert sel.provider_matrix["alpha"]["tool"] == "alpha_tool"
        assert "alpha strength" in sel.provider_matrix["alpha"]["strength"]

    def test_rank_mode_returns_rankings_not_a_generation(
        self, cls, prompt_key, default_op, monkeypatch
    ):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        b = _FakeProvider("beta_tool", "beta")
        _patch_providers(monkeypatch, sel, [a, b])

        result = sel.execute({prompt_key: "x", "operation": "rank"})
        assert result.success
        assert {r["tool_name"] for r in result.data["rankings"]} == {"alpha_tool", "beta_tool"}
        assert result.data["explanation"]
        assert result.data["normalized_task_context"]
        # No provider was actually run.
        assert a.seen_inputs is None and b.seen_inputs is None

    def test_rank_items_carry_agent_facing_metadata(
        self, cls, prompt_key, default_op, monkeypatch
    ):
        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        _patch_providers(monkeypatch, sel, [a])
        [item] = sel.execute({prompt_key: "x", "operation": "rank"}).data["rankings"]
        for key in ("agent_skills", "usage_location", "best_for", "status"):
            assert key in item


class TestDocumentedDivergences:
    """Where the three deliberately (or accidentally) disagree TODAY.

    Each of these is a decision point for the extraction, not a bug to fix
    silently — the plan's D1/D2/D4.
    """

    def test_d1_all_rank_items_now_carry_supports(self, monkeypatch):
        # D1 CONVERGED by the SelectorBase extraction: tts's hand-copied
        # _serialize_rankings omitted `supports` while video/image included
        # it. The base emits it for all three — purely additive (no key
        # removed), and an agent ranking TTS providers can now see what each
        # one supports, same as the other two capabilities.
        for cls, prompt_key in (
            (VideoSelector, "prompt"), (ImageSelector, "prompt"), (TTSSelector, "text"),
        ):
            sel = cls()
            a = _FakeProvider("alpha_tool", "alpha")
            _patch_providers(monkeypatch, sel, [a])
            [item] = sel.execute({prompt_key: "x", "operation": "rank"}).data["rankings"]
            assert "supports" in item, cls.__name__

    def test_d4_tts_and_video_forward_selector_keys_to_the_provider(self, monkeypatch):
        # tts passes `inputs` through RAW; video copies but still forwards
        # preferred_provider/allowed_providers. image strips them (below).
        for cls, prompt_key in ((TTSSelector, "text"), (VideoSelector, "prompt")):
            sel = cls()
            a = _FakeProvider("alpha_tool", "alpha")
            _patch_providers(monkeypatch, sel, [a])
            sel.execute({prompt_key: "x", "preferred_provider": "alpha",
                         "allowed_providers": ["alpha"]})
            assert "preferred_provider" in a.seen_inputs, cls.__name__
            assert "allowed_providers" in a.seen_inputs, cls.__name__

    def test_d4_image_strips_selector_keys_from_the_provider_payload(self, monkeypatch):
        sel = ImageSelector()
        a = _FakeProvider("alpha_tool", "alpha")
        _patch_providers(monkeypatch, sel, [a])
        sel.execute({"prompt": "x", "preferred_provider": "alpha",
                     "allowed_providers": ["alpha"]})
        assert "preferred_provider" not in a.seen_inputs
        assert "allowed_providers" not in a.seen_inputs

    def test_d4_image_strips_params_the_provider_schema_lacks(self, monkeypatch):
        sel = ImageSelector()
        # schema has prompt only → seed/width must be stripped.
        a = _FakeProvider("alpha_tool", "alpha", schema_props={"prompt": {}})
        _patch_providers(monkeypatch, sel, [a])
        sel.execute({"prompt": "x", "seed": 7, "width": 512})
        assert "seed" not in a.seen_inputs
        assert "width" not in a.seen_inputs

    def test_d4_video_and_image_add_query_for_stock_style_providers(self, monkeypatch):
        for cls in (VideoSelector, ImageSelector):
            sel = cls()
            a = _FakeProvider("stock_tool", "stock",
                              schema_props={"query": {}, "prompt": {}})
            _patch_providers(monkeypatch, sel, [a])
            sel.execute({"prompt": "a red bird"})
            assert a.seen_inputs["query"] == "a red bird", cls.__name__

    def test_d2_estimate_cost_prices_only_selectable_providers(self, monkeypatch):
        # D2 CONVERGED: every selector now filters candidates before pricing,
        # so estimate_cost reports what execute() would actually run. image
        # previously priced over ALL providers — with generation_mode="edit"
        # it could quote a non-edit-capable provider that could never be
        # selected, and that number feeds the budget gate.
        sel = ImageSelector()
        cheap_no_edit = _FakeProvider("cheap_tool", "alpha",
                                      schema_props={"prompt": {}}, cost=1.0)
        cheap_no_edit.supports = {"generate": True}
        pricey_edit = _FakeProvider("edit_tool", "beta",
                                    schema_props={"prompt": {}, "image_url": {}}, cost=9.0)
        pricey_edit.supports = {"generate": True, "image_edit": True}
        _patch_providers(monkeypatch, sel, [cheap_no_edit, pricey_edit])

        # An edit request can only run on the edit-capable provider, so its
        # price is the honest estimate.
        assert sel.estimate_cost({"prompt": "x", "generation_mode": "edit"}) == 9.0
        # A plain generate request still prices across everything.
        assert sel.estimate_cost({"prompt": "x"}) in (1.0, 9.0)

    def test_d6_video_rank_mode_filters_by_target_operation(self, monkeypatch):
        # target_operation reaches _filter_candidates, which drops providers
        # that can't do it. (It does NOT reach the task context —
        # normalize_task_context maps text_to_video and image_to_video to the
        # same semantic fields, so the ranking itself is unaffected.)
        sel = VideoSelector()
        t2v_only = _FakeProvider("t2v_tool", "alpha", schema_props={"prompt": {}})
        t2v_only.supports = {"text_to_video": True}
        i2v_able = _FakeProvider("i2v_tool", "beta",
                                 schema_props={"prompt": {}, "image_url": {}})
        i2v_able.supports = {"text_to_video": True, "image_to_video": True}
        _patch_providers(monkeypatch, sel, [t2v_only, i2v_able])

        ranked = sel.execute({
            "prompt": "x", "operation": "rank", "target_operation": "image_to_video",
        }).data["rankings"]
        assert {r["tool_name"] for r in ranked} == {"i2v_tool"}

        ranked_default = sel.execute({"prompt": "x", "operation": "rank"}).data["rankings"]
        assert {r["tool_name"] for r in ranked_default} == {"t2v_tool", "i2v_tool"}

    def test_d7_video_fallback_tools_append_image_selector(self, monkeypatch):
        sel = VideoSelector()
        _patch_providers(monkeypatch, sel, [_FakeProvider("a_tool", "alpha")])
        assert sel.fallback_tools[-1] == "image_selector"

        sel_t = TTSSelector()
        _patch_providers(monkeypatch, sel_t, [_FakeProvider("a_tool", "alpha")])
        assert sel_t.fallback_tools == ["a_tool"]


class TestInstrumentationDepth:
    """H1: execute() must be wrapped exactly once.

    BaseTool.__init_subclass__ auto-instruments each subclass's own
    execute(). If SelectorBase.execute is wrapped AND a subclass overrides
    execute() calling super(), the call is wrapped twice — duplicate Backlot
    events, and the selector's own event lands at depth 1 (the slot a
    PROVIDER occupies), corrupting the depth-0 cost attribution documented
    in base_tool's _instrument_execute.
    """

    @pytest.mark.parametrize("cls,prompt_key", [
        (VideoSelector, "prompt"), (TTSSelector, "text"), (ImageSelector, "prompt"),
    ])
    def test_selector_emits_one_event_per_execute(self, cls, prompt_key, monkeypatch):
        events = []
        import tools.base_tool as bt
        monkeypatch.setattr(bt, "emit_tool_event", lambda **kw: events.append(kw), raising=False)

        sel = cls()
        a = _FakeProvider("alpha_tool", "alpha")
        _patch_providers(monkeypatch, sel, [a])
        sel.execute({prompt_key: "x"})

        selector_events = [e for e in events if e.get("tool") == sel.name]
        # Either instrumentation is off in this build (no events at all) or
        # the selector emitted exactly one start/end pair — never two.
        if selector_events:
            starts = [e for e in selector_events if e.get("phase") in (None, "start")]
            assert len(starts) <= 1, f"{cls.__name__} double-instrumented"
