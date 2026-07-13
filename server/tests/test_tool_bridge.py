"""Tool bridge: file ops, artifact writes, compose routing, budget pre-check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runner.tool_bridge import execute_tool, BudgetExceededError, variant_slug


class _FakeResult:
    def __init__(self, success=True, cost_usd=0.0, artifacts=None):
        self.success = success
        self.cost_usd = cost_usd
        self.artifacts = artifacts or []
        self.data = {}
        self.error = None


class FakeTool:
    """Minimal BaseTool stand-in — no network."""

    def __init__(self, capability="video_generation", cost=0.0):
        self.capability = capability
        self._cost = cost
        self.executed_with = None

    def estimate_cost(self, inputs):
        return self._cost

    def execute(self, inputs):
        self.executed_with = inputs
        return _FakeResult(cost_usd=self._cost, artifacts=[inputs.get("output_path", "")])


class FakeToolWithSchema(FakeTool):
    """FakeTool variant that declares an input_schema with a required field —
    used to test the generic required-field guardrail. FakeTool itself has no
    input_schema at all (by design), so it exercises the no-op path instead."""
    input_schema = {"type": "object", "required": ["operation"]}


class FakeMultiArtifactTool(FakeTool):
    """FakeTool variant whose execute() returns multiple artifacts, like a
    TTS tool emitting both an audio file and a metadata file."""

    def execute(self, inputs):
        self.executed_with = inputs
        return _FakeResult(cost_usd=self._cost, artifacts=["audio.mp3", "metadata.json"])


def _run_tool(project_dir, tool, monkeypatch, **kw):
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    args = {"tool_name": "maas_video", "inputs": {"prompt": "x", "operation": "t2v"}}
    return execute_tool("run_openmontage_tool", args, project_dir, **kw)


def test_read_file_missing(tmp_path):
    out = execute_tool("read_file", {"path": "nope/does-not-exist.xyz"}, tmp_path)
    assert out.startswith("ERROR: File not found")


def test_write_artifact_and_missing_params(tmp_path):
    ok = execute_tool("write_artifact", {"artifact_name": "research", "content": {"a": 1}}, tmp_path)
    assert "Written to" in ok
    written = json.loads((tmp_path / "artifacts" / "research.json").read_text())
    assert written == {"a": 1}

    assert "requires 'artifact_name'" in execute_tool("write_artifact", {"content": {}}, tmp_path)
    assert "requires 'content'" in execute_tool("write_artifact", {"artifact_name": "x"}, tmp_path)


# ── security: path containment for read_file / write_artifact ───────────────

def test_read_file_blocks_absolute_path_escape():
    # Confirmed live (deep quality review): OM_ROOT / "/etc/passwd" silently
    # discards OM_ROOT (pathlib's absolute-path-override behavior) and reads
    # a real system file with zero containment check.
    out = execute_tool("read_file", {"path": "/etc/passwd"}, Path("/tmp"))
    assert out.startswith("ERROR:")
    assert "outside the OpenMontage root" in out


def test_read_file_blocks_traversal_escape(tmp_path):
    out = execute_tool("read_file", {"path": "../../../../../../../../etc/passwd"}, tmp_path)
    assert out.startswith("ERROR:")
    assert "outside the OpenMontage root" in out


def test_read_file_blocks_env_dotfile():
    # Even a plain in-bounds relative read discloses MAAS_API_KEY, since .env
    # sits directly at OM_ROOT — containment alone isn't enough.
    out = execute_tool("read_file", {"path": ".env"}, Path("/tmp"))
    assert out.startswith("ERROR:")
    assert "dotfile" in out.lower()


def test_write_artifact_rejects_absolute_path_name(tmp_path):
    out = execute_tool(
        "write_artifact", {"artifact_name": "/etc/cron.d/x", "content": {}}, tmp_path,
    )
    assert out.startswith("ERROR:")
    assert "invalid artifact_name" in out
    assert not Path("/etc/cron.d/x.json").exists()


def test_write_artifact_rejects_traversal_name(tmp_path):
    out = execute_tool(
        "write_artifact", {"artifact_name": "../../escaped", "content": {}}, tmp_path,
    )
    assert out.startswith("ERROR:")
    assert "invalid artifact_name" in out
    assert not (tmp_path.parent.parent / "escaped.json").exists()


def test_write_artifact_rejects_embedded_slash(tmp_path):
    out = execute_tool(
        "write_artifact", {"artifact_name": "sub/dir", "content": {}}, tmp_path,
    )
    assert out.startswith("ERROR:")
    assert "invalid artifact_name" in out


def test_unknown_tool(tmp_path):
    assert execute_tool("bogus", {}, tmp_path).startswith("ERROR: Unknown tool")


def test_compose_routes_final_to_renders(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "compose"}},
                 tmp_path)
    assert tool.executed_with["output_path"].endswith("/renders/final.mp4")


def test_video_post_non_compose_stays_in_assets(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "trim"}},
                 tmp_path)
    op = tool.executed_with["output_path"]
    assert "/assets/video_post/" in op and "renders" not in op


def test_repeated_calls_to_same_tool_get_distinct_output_paths(tmp_path, monkeypatch):
    # Regression: a fixed "{tool_name}_output.{ext}" filename meant every call
    # to the same tool within a job silently overwrote the previous one's
    # file. Confirmed live: an assets-stage run that generated 6 distinct
    # video clips (without the agent overriding output_path) left exactly ONE
    # file on disk — each call clobbered the last.
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)

    paths = []
    for _ in range(5):
        execute_tool("run_openmontage_tool",
                     {"tool_name": "maas_video", "inputs": {"prompt": "same prompt every time"}},
                     tmp_path)
        paths.append(tool.executed_with["output_path"])

    assert len(set(paths)) == 5, f"expected 5 distinct paths, got {paths}"
    assert all(p.endswith(".mp4") for p in paths)


def test_budget_precheck_blocks_over_budget(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    with pytest.raises(BudgetExceededError):
        _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=10.0, base_cost=8.0)
    # blocked before execution → nothing spent, tool not run
    assert acc == []
    assert tool.executed_with is None


def test_budget_precheck_allows_within_budget(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    out = _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=100.0, base_cost=8.0)
    assert json.loads(out)["success"] is True
    assert acc == [5.0]                      # CNY cost accumulated
    assert tool.executed_with is not None


def test_no_budget_runs_freely(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=None, base_cost=0.0)
    assert acc == [5.0]


def test_variant_slug_from_model_id():
    assert variant_slug("leapfast/ltx-2.3") == "ltx-2-3"
    assert variant_slug("leapfast/wan2.2") == "wan2-2"
    assert variant_slug("ltx") == "ltx"
    assert variant_slug("") == "default"


def test_model_choice_filled_in_when_agent_omits_it(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x"}},
        tmp_path,
        options={"video_model": "leapfast/ltx-2.3"},
    )
    assert tool.executed_with["model"] == "leapfast/ltx-2.3"


def test_model_choice_rejects_mismatch_before_calling_tool(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x", "model": "volcengine/doubao-seedance-2.0"}},
        tmp_path,
        options={"video_model": "leapfast/ltx-2.3"},
    )
    assert "ERROR" in out
    assert "leapfast/ltx-2.3" in out
    assert tool.executed_with is None  # rejected before the (paid) call


def test_model_choice_allows_any_listed_variant(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    for model in ("leapfast/ltx-2.3", "leapfast/wan2.2"):
        execute_tool(
            "run_openmontage_tool",
            {"tool_name": "maas_video", "inputs": {"prompt": "x", "model": model}},
            tmp_path,
            options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
        )
        assert tool.executed_with["model"] == model


def test_model_choice_requires_explicit_model_when_ab_variants_declared(tmp_path, monkeypatch):
    # Regression: omitting `model` on an A/B job used to silently autofill
    # allowed[0] for every call, collapsing every "variant" onto the same
    # model with nothing anywhere flagging it. Now it must be rejected
    # before the (paid) call, same as an explicit mismatch is.
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
    )
    assert "ERROR" in out
    assert "leapfast/ltx-2.3" in out and "leapfast/wan2.2" in out
    assert tool.executed_with is None  # rejected before the (paid) call


def test_model_choice_still_autofills_single_variant_list(tmp_path, monkeypatch):
    # A variants list with exactly one entry has nothing to collapse —
    # requiring an explicit echo back would just be friction, so the
    # permissive autofill behavior is preserved.
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3"]},
    )
    assert tool.executed_with["model"] == "leapfast/ltx-2.3"


def test_unconstrained_job_options_dont_touch_model(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x", "model": "anything-the-agent-picked"}},
        tmp_path,
        options={},
    )
    assert tool.executed_with["model"] == "anything-the-agent-picked"


def test_variant_tag_keeps_asset_output_paths_distinguishable(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x", "model": "leapfast/wan2.2"}},
        tmp_path,
    )
    assert "_wan2-2_" in tool.executed_with["output_path"]


def test_compose_variant_tag_produces_distinct_render_filenames(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)

    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "compose", "variant": "leapfast/ltx-2.3"}},
                 tmp_path)
    ltx_path = tool.executed_with["output_path"]

    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "compose", "variant": "leapfast/wan2.2"}},
                 tmp_path)
    wan_path = tool.executed_with["output_path"]

    assert ltx_path != wan_path
    assert ltx_path.endswith("/renders/final_ltx-2-3.mp4")
    assert wan_path.endswith("/renders/final_wan2-2.mp4")
    assert "variant" not in tool.executed_with  # popped — not a real tool param


def test_compose_rejects_missing_variant_when_ab_job_declared(tmp_path, monkeypatch):
    # Regression: a compose call that omits inputs.variant on a job with
    # multiple video_model_variants used to silently fall back to the
    # untagged "final.mp4" path, colliding with (and potentially
    # overwriting) whichever variant's compose call ran first/last.
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "compose"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
    )
    assert "ERROR" in out
    assert "leapfast/ltx-2.3" in out and "leapfast/wan2.2" in out
    assert tool.executed_with is None  # rejected before writing/overwriting a render


def test_compose_allows_missing_variant_when_only_one_variant_declared(tmp_path, monkeypatch):
    # Nothing to collide with when there's only one (or zero) variants —
    # the existing permissive default-tag behavior is preserved.
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "compose"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3"]},
    )
    assert json.loads(out)["success"] is True
    assert tool.executed_with["output_path"].endswith("/renders/final.mp4")


def test_compose_with_explicit_variant_proceeds_on_ab_job(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "compose", "variant": "leapfast/ltx-2.3"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
    )
    assert json.loads(out)["success"] is True
    assert tool.executed_with["output_path"].endswith("/renders/final_ltx-2-3.mp4")


def test_compose_variant_requirement_ignores_non_compose_video_post_ops(tmp_path, monkeypatch):
    # The guard is specific to the compose op — trim/stitch calls within an
    # A/B job aren't subject to the same collision (they already get a
    # unique random-suffixed filename in assets/, not a deterministic
    # renders/final.mp4).
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "trim"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
    )
    assert json.loads(out)["success"] is True


def test_tts_emotion_defaults_filled_when_agent_omits(tmp_path, monkeypatch):
    tool = FakeTool(capability="tts")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_tts", "inputs": {"text": "hi"}},
        tmp_path,
        options={"tts_emotion": {
            "emo_alpha": 0.6, "use_emo_text": True, "emo_text": "excited", "interval_silence": 300,
        }},
    )
    assert tool.executed_with["emo_alpha"] == 0.6
    assert tool.executed_with["use_emo_text"] is True
    assert tool.executed_with["emo_text"] == "excited"
    assert tool.executed_with["interval_silence"] == 300


def test_tts_emotion_defaults_zero_alpha_is_applied_not_treated_as_unset(tmp_path, monkeypatch):
    # Regression guard: emo_alpha=0.0 (flat delivery) is a real, meaningful
    # value — a truthiness check would silently drop it.
    tool = FakeTool(capability="tts")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_tts", "inputs": {"text": "hi"}},
        tmp_path,
        options={"tts_emotion": {"emo_alpha": 0.0}},
    )
    assert tool.executed_with["emo_alpha"] == 0.0


def test_tts_emotion_defaults_respect_agent_override(tmp_path, monkeypatch):
    tool = FakeTool(capability="tts")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_tts", "inputs": {"text": "hi", "emo_alpha": 0.9}},
        tmp_path,
        options={"tts_emotion": {"emo_alpha": 0.2}},
    )
    assert tool.executed_with["emo_alpha"] == 0.9


def test_tts_emotion_defaults_ignored_for_other_tools(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {"prompt": "x"}},
        tmp_path,
        options={"tts_emotion": {"emo_alpha": 0.2}},
    )
    assert "emo_alpha" not in tool.executed_with


def test_tts_emotion_defaults_no_op_without_options(tmp_path, monkeypatch):
    tool = FakeTool(capability="tts")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_tts", "inputs": {"text": "hi"}},
        tmp_path,
    )
    assert "emo_alpha" not in tool.executed_with


def test_cost_tracker_ledger_records(tmp_path, monkeypatch):
    from tools.cost_tracker import CostTracker
    from lib.config_model import BudgetMode
    ct = CostTracker(budget_total_usd=1e9, reserve_pct=0.0, single_action_approval_usd=1e9,
                     require_approval_for_new_paid_tool=False, mode=BudgetMode.OBSERVE,
                     cost_log_path=tmp_path / "cost_log.json")
    tool = FakeTool(capability="video_generation", cost=5.0)
    _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=[], cost_tracker=ct)
    assert ct.cost_snapshot()["total_spent_usd"] == 5.0
    assert (tmp_path / "cost_log.json").exists()


def test_tool_call_and_asset_ready_events_carry_model_and_cost(tmp_path, monkeypatch):
    # Regression: the live event log only ever showed "调用工具 maas_video" with
    # no indication of which model or how much a call actually cost — an
    # operator watching a real (paid) run had no way to tell what was
    # generating without digging through inputs_preview's 80-char-truncated
    # dump. tool_call's model is the agent's raw request (captured before
    # _enforce_model_choice's autofill); asset_ready's model is the fully
    # resolved one, alongside the real per-call cost.
    events = []
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    tool = FakeTool(capability="video_generation", cost=0.35)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    args = {"tool_name": "maas_video", "inputs": {"prompt": "x", "operation": "t2v", "model": "leapfast/ltx-2.3"}}
    execute_tool("run_openmontage_tool", args, tmp_path, emit_event=events.append)

    tool_call = next(e for e in events if e["type"] == "tool_call")
    assert tool_call["model"] == "leapfast/ltx-2.3"

    asset_ready = next(e for e in events if e["type"] == "asset_ready")
    assert asset_ready["model"] == "leapfast/ltx-2.3"
    assert asset_ready["cost_cny"] == 0.35


# ── compose variant tag: membership check (not just truthiness) ────────────

def test_compose_rejects_invalid_variant_not_in_declared_list(tmp_path, monkeypatch):
    # Regression: a typo'd/invented variant tag used to pass enforcement
    # (only inputs.get("variant") truthiness was checked), run an expensive
    # render, and only fail later in stage_runner's _missing_variants check —
    # after money was already spent. Must now be rejected up front, mirroring
    # _enforce_model_choice's membership check.
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "compose", "variant": "leapfast/typo-model"}},
        tmp_path,
        options={"video_model_variants": ["leapfast/ltx-2.3", "leapfast/wan2.2"]},
    )
    assert "ERROR" in out
    assert "leapfast/typo-model" in out
    assert "leapfast/ltx-2.3" in out and "leapfast/wan2.2" in out
    assert tool.executed_with is None  # rejected before the (paid) render


# ── generic required-field validation ───────────────────────────────────────

def test_missing_required_field_rejected_before_execute(tmp_path, monkeypatch):
    # Confirmed exploitable live: a real agent call to video_compose omitted
    # the tool's one schema-required field ("operation") twice, and nothing
    # rejected it before tool.execute(inputs) was reached.
    tool = FakeToolWithSchema(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {}},
        tmp_path,
    )
    assert out.startswith("ERROR:")
    assert "missing required field" in out
    assert "operation" in out
    assert tool.executed_with is None


def test_required_field_present_is_allowed(tmp_path, monkeypatch):
    tool = FakeToolWithSchema(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "video_compose", "inputs": {"operation": "compose"}},
        tmp_path,
    )
    assert json.loads(out)["success"] is True
    assert tool.executed_with is not None


def test_fake_tool_without_input_schema_is_unaffected_by_required_field_check(tmp_path, monkeypatch):
    # FakeTool (used across most of this suite) never declares input_schema —
    # getattr(tool, "input_schema", None) or {} must evaluate to {} for it, so
    # the new guardrail is a complete no-op and every existing FakeTool-based
    # test keeps passing unmodified.
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    assert not hasattr(FakeTool, "input_schema")
    out = execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_video", "inputs": {}},
        tmp_path,
    )
    assert json.loads(out)["success"] is True


# ── asset_ready cost_cny: only on the last artifact of a multi-artifact call ─

def test_asset_ready_cost_cny_only_on_last_artifact(tmp_path, monkeypatch):
    # Regression: the whole call's cost_cny used to repeat identically on
    # EVERY artifact_ready event for a multi-artifact call (e.g. a TTS tool
    # emitting both an audio file and a metadata file). The underlying cost
    # ledger accumulates correctly (once per call) — only the live
    # per-artifact display misleadingly read as if the same money was spent
    # once per artifact.
    events = []
    tool = FakeMultiArtifactTool(capability="tts", cost=1.25)
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "ensure_discovered", lambda *a, **k: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool(
        "run_openmontage_tool",
        {"tool_name": "maas_tts", "inputs": {"text": "hi"}},
        tmp_path,
        emit_event=events.append,
    )
    asset_events = [e for e in events if e["type"] == "asset_ready"]
    assert len(asset_events) == 2
    assert "cost_cny" not in asset_events[0]
    assert asset_events[1]["cost_cny"] == 1.25


# ── BudgetExceededError: structured fields for cross-file contract ─────────

def test_budget_exceeded_error_carries_structured_fields(tmp_path, monkeypatch):
    # stage_runner.py's pre-call budget block needs tool_name/est_cost/
    # projected_cny as structured attributes (not just baked into the message
    # string) to build a structured pause/resume payload.
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    with pytest.raises(BudgetExceededError) as excinfo:
        _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=10.0, base_cost=8.0)
    exc = excinfo.value
    assert exc.tool_name == "maas_video"
    assert exc.est_cost == 5.0
    assert exc.projected_cny == 13.0
    # str(exc) must keep working for any existing caller that only cares
    # about the message text.
    assert "over budget" in str(exc)
