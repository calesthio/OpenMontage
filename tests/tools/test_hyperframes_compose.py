"""Fast unit tests for the HyperFrames runtime integration.

These tests do NOT invoke the HyperFrames CLI — they verify schema
acceptance, tool contract wiring, governance routing in video_compose, the
style bridge, and workspace scaffolding. Subprocess-based smoke tests live
in tests/qa/test_09_hyperframes_compose.py and are opt-in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.base_tool import ToolStatus
from tools.video.hyperframes_compose import HyperFramesCompose
from tools.video.video_compose import VideoCompose


# ------------------------------------------------------------------
# Tool contract
# ------------------------------------------------------------------


def test_hyperframes_tool_identity():
    t = HyperFramesCompose()
    assert t.name == "hyperframes_compose"
    assert t.capability == "video_post"
    assert t.provider == "hyperframes"
    assert "hyperframes" in t.agent_skills
    assert "hyperframes-cli" in t.agent_skills


def test_hyperframes_get_info_reports_runtime():
    info = HyperFramesCompose().get_info()
    assert "hyperframes_runtime" in info
    rc = info["hyperframes_runtime"]
    assert set(rc.keys()) >= {
        "runtime_available",
        "node_major",
        "ffmpeg_available",
        "npx_available",
        "reasons",
    }


def test_hyperframes_layer2_skill_names_correct_package():
    """Regression: skills/core/hyperframes.md previously claimed HyperFrames
    was 'consumable via `npx @hyperframes/cli`' which is the 404-ing name.
    A Layer 2 skill reader would get bad advice even after the
    install_instructions fix. Must name the real published package."""
    from pathlib import Path
    body = (
        Path(__file__).resolve().parent.parent.parent
        / "skills" / "core" / "hyperframes.md"
    ).read_text(encoding="utf-8")
    # The dangerous invocation must be called out, not recommended.
    # If `@hyperframes/cli` appears it must be in a warning context.
    if "@hyperframes/cli" in body:
        # Only OK if it's named as a trap, not a recommendation.
        assert (
            "404" in body
            or "NOT" in body
            or "do not" in body.lower()
            or "trap" in body.lower()
        ), (
            "skills/core/hyperframes.md still recommends `@hyperframes/cli` "
            "(the 404-ing monorepo name) without a warning. Replace with "
            "`npx hyperframes` or flag it as a trap."
        )
    # Must mention the correct published name.
    assert "npx hyperframes" in body, (
        "skills/core/hyperframes.md must reference `npx hyperframes` (the real "
        "published package). A Layer 2 skill missing this would leave agents "
        "stuck if they bypass the tool's install_instructions."
    )


def test_animation_proposal_director_has_no_hardcoded_costs_or_keys():
    """Regression: multiple audit rounds found hardcoded per-unit dollar costs
    and specific API key names in the animation proposal-director. Uses a
    regex to catch the ENTIRE class of drift, not just specific strings. Covers
    the whole file, not just Step 3 — dry-run round 3 found hardcoded values
    surviving in the decision matrix and Common Pitfalls after Step 3 was
    cleaned."""
    from pathlib import Path
    import re

    body = (
        Path(__file__).resolve().parent.parent.parent
        / "skills" / "pipelines" / "animation" / "proposal-director.md"
    ).read_text(encoding="utf-8")

    # Only flag NON-ZERO dollar figures. `$0` and `$0.00` labeling something
    # as free is fine (local tools don't drift in cost), but any real price
    # ($0.05, $3-15, etc.) is drift-prone and must come from estimate_cost.
    dollar_pattern = re.compile(
        r"\$(?!0(?!\.?\d*[1-9]))"          # dollar sign
        r"\d+(?:[.,]\d+)?"                  # integer or decimal part
        r"(?:\s*-\s*\$?\d+(?:[.,]\d+)?)?"   # optional range tail
    )
    env_var_pattern = re.compile(
        r"\b(FAL_KEY|OPENAI_API_KEY|RUNWAY_API_KEY|KLING_API_KEY|"
        r"REPLICATE_API_TOKEN|ANTHROPIC_API_KEY|GEMINI_API_KEY|"
        r"ELEVENLABS_API_KEY|HEYGEN_API_KEY)\b"
    )
    # Lines in anti-pattern bullets or registry-pointer bullets are allowed
    # to mention banned shapes as counter-examples.
    anti_pattern_markers = [
        "do not hardcode",
        "do not fill in",
        "don't type them from memory",
        "drift between releases",
        "governance regression",
        "if you find yourself typing",
        "read each missing tool",
        "do not fill in a dollar figure",
    ]

    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        if not (dollar_pattern.search(line) or env_var_pattern.search(line)):
            continue
        if any(marker in line.lower() for marker in anti_pattern_markers):
            continue
        if line.strip() in ("```", "```python", "```bash"):
            continue
        violations.append((lineno, line.strip()[:140]))

    if violations:
        formatted = "\n".join(f"  line {n}: {text}" for n, text in violations)
        raise AssertionError(
            f"Hardcoded cost figures or env var names in "
            f"animation/proposal-director.md. Director skills must pull these "
            f"from the registry (estimate_cost / install_instructions) because "
            f"provider pricing drifts between releases. Violations:\n{formatted}"
        )
    assert "provider_menu_summary" in body or "estimate_cost" in body, (
        "Animation proposal-director must reference provider_menu_summary() "
        "or estimate_cost so agents know where live pricing comes from."
    )


def test_provider_menu_summary_deduplicates_providers_across_buckets():
    """Regression: when a provider has multiple tools (e.g. two seedance tools
    both reporting provider='seedance'), the summary previously listed the
    provider as BOTH available and unavailable — reads as a contradiction to
    users. Any-available wins over any-unavailable."""
    from tools.tool_registry import registry

    registry.discover()
    s = registry.provider_menu_summary()
    for cap_entry in s["capabilities"]:
        both = set(cap_entry["available_providers"]) & set(
            cap_entry["unavailable_providers"]
        )
        assert not both, (
            f"Capability {cap_entry['capability']!r} lists providers in BOTH "
            f"available and unavailable buckets: {sorted(both)}. A provider "
            f"with any available tool must not also show as unavailable."
        )


def test_provider_menu_summary_is_cp1252_safe():
    """Regression: on Windows cp1252 stdout, printing any string with an
    em-dash crashes with UnicodeEncodeError (or renders as `?` / mojibake).
    provider_menu_summary() post-processes its output via
    _scrub_unicode_dashes so preflight pasting works on every shell.
    This protects preflight even if a future tool author writes em-dashes
    into install_instructions."""
    import json
    from tools.tool_registry import registry, _scrub_unicode_dashes

    # Direct unit test of the helper.
    dirty = "one \u2014 two \u2013 three \u2018quoted\u2019"
    clean = _scrub_unicode_dashes(dirty)
    assert "\u2014" not in clean
    assert "\u2013" not in clean
    assert "--" in clean

    # And the summary itself is scrubbed.
    registry.discover()
    summary_json = json.dumps(registry.provider_menu_summary())
    assert "\u2014" not in summary_json, (
        "em-dash leaked into provider_menu_summary — Windows cp1252 users "
        "will see mojibake in preflight."
    )
    assert "\u2013" not in summary_json, "en-dash leaked"
    # Nested structures must also be scrubbed.
    nested = _scrub_unicode_dashes({"a": ["x \u2014 y", {"b": "c \u2014 d"}]})
    assert "\u2014" not in json.dumps(nested)


def test_install_instructions_reference_correct_npm_package_name():
    """Regression: install_instructions previously pointed at `npx @hyperframes/cli`,
    which returns a 404 on the public npm registry. The real published package
    name is `hyperframes`. A fresh-session agent reading install_instructions
    and trying to verify setup would hit 404 and conclude HyperFrames isn't
    available.
    """
    hint = HyperFramesCompose.install_instructions
    # Must name the correct published package name.
    assert "`npx hyperframes" in hint or "npm package: `hyperframes`" in hint, (
        "install_instructions must reference `npx hyperframes` / npm package "
        "`hyperframes` — NOT the monorepo-internal `@hyperframes/cli` name."
    )
    # And ideally warns about the 404 trap so agents don't re-introduce it.
    assert "404" in hint or "@hyperframes/cli" in hint, (
        "install_instructions should mention that the monorepo-internal name "
        "`@hyperframes/cli` is NOT the published name — this is the exact trap "
        "that misled a previous audit."
    )


def test_runtime_check_fails_when_npm_package_unresolvable(monkeypatch):
    """Regression: `_runtime_check()` previously returned runtime_available=True
    based only on local binaries (node/ffmpeg/npx). That meant the tool lied
    when the machine was offline, npm was down, or the package name was wrong.
    The check must now include a real npm resolve."""
    # Clear process cache and force _resolve_npm_package to return a 404.
    monkeypatch.setattr(
        HyperFramesCompose, "_npm_resolve_cache", None, raising=False
    )
    monkeypatch.setattr(
        HyperFramesCompose,
        "_resolve_npm_package",
        classmethod(lambda cls: {"error": "npm package `hyperframes` not found (404)"}),
    )
    rc = HyperFramesCompose()._runtime_check()
    assert rc["runtime_available"] is False, (
        "Runtime must report NOT available when the npm package can't be "
        "resolved — even if node/ffmpeg/npx are all on PATH."
    )
    assert any("404" in r for r in rc["reasons"]), (
        "reasons must include the actual npm-resolve failure, not just a "
        "generic 'runtime unavailable' message."
    )
    assert rc["npm_resolve_error"] is not None
    assert rc["npm_package"] == "hyperframes"


def test_runtime_check_succeeds_when_npm_resolves(monkeypatch):
    monkeypatch.setattr(
        HyperFramesCompose, "_npm_resolve_cache", None, raising=False
    )
    monkeypatch.setattr(
        HyperFramesCompose,
        "_resolve_npm_package",
        classmethod(lambda cls: {"version": "0.4.5"}),
    )
    rc = HyperFramesCompose()._runtime_check()
    # Local binaries must still pass for this to go green.
    if rc["node_major"] is None or not rc["ffmpeg_available"] or not rc["npx_available"]:
        pytest.skip("Local runtime floor not met on this machine")
    assert rc["runtime_available"] is True
    assert rc["npm_package_version"] == "0.4.5"
    assert rc["reasons"] == []


def test_video_compose_render_engines_follow_hyperframes_runtime_check(monkeypatch):
    """Regression: `video_compose.get_info()['render_engines']['hyperframes']`
    must track the true availability, not just the local-binary floor.
    Without this, the 'Present Both Composition Runtimes' HARD RULE surfaces
    a runtime that cannot actually render."""
    monkeypatch.setattr(
        HyperFramesCompose, "_npm_resolve_cache", None, raising=False
    )
    monkeypatch.setattr(
        HyperFramesCompose,
        "_resolve_npm_package",
        classmethod(lambda cls: {"error": "npm package not found (404)"}),
    )
    info = VideoCompose().get_info()
    assert info["render_engines"]["hyperframes"] is False, (
        "video_compose must mark hyperframes as unavailable when the real "
        "runtime check fails. Otherwise the HARD RULE lies."
    )


def test_provider_menu_summary_returns_expected_shape():
    """Regression: AGENT_GUIDE.md line 246 points agents at provider_menu_summary
    for the capability menu. The shape must be stable and cover the four fields
    the guide references."""
    from tools.tool_registry import registry

    registry.discover()
    s = registry.provider_menu_summary()

    assert set(s.keys()) == {
        "composition_runtimes",
        "capabilities",
        "setup_offers",
        "runtime_warnings",
    }
    # Composition runtimes MUST include all three engines so the HARD RULE
    # presentation has the data it needs.
    for engine in ("ffmpeg", "remotion", "hyperframes"):
        assert engine in s["composition_runtimes"]
        assert isinstance(s["composition_runtimes"][engine], bool)

    # Capabilities rollup is a list of dicts with configured/total counts.
    assert isinstance(s["capabilities"], list)
    assert len(s["capabilities"]) > 0
    for entry in s["capabilities"]:
        assert set(entry.keys()) >= {
            "capability",
            "configured",
            "total",
            "available_providers",
            "unavailable_providers",
        }
        assert entry["configured"] <= entry["total"]

    # setup_offers and runtime_warnings must be lists (possibly empty).
    assert isinstance(s["setup_offers"], list)
    assert isinstance(s["runtime_warnings"], list)


def test_agent_guide_references_provider_menu_summary():
    """Regression: AGENT_GUIDE.md must route agents to provider_menu_summary
    instead of dumping support_envelope raw. If this gets reverted a fresh-
    session agent will paste the firehose into chat."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    guide = (root / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "provider_menu_summary" in guide, (
        "AGENT_GUIDE.md must reference provider_menu_summary() as the primary "
        "preflight helper — without this, agents fall back to the firehose."
    )


def test_hyperframes_unknown_operation_returns_error():
    result = HyperFramesCompose().execute({"operation": "bogus"})
    assert not result.success
    assert "Unknown operation" in (result.error or "")


def test_hyperframes_lint_requires_workspace():
    # No workspace_path → ValueError surfaced through execute as a ToolResult.
    result = HyperFramesCompose().execute({"operation": "lint"})
    assert not result.success
    assert "workspace_path" in (result.error or "")


def test_hyperframes_render_requires_workspace():
    result = HyperFramesCompose().execute({"operation": "render"})
    assert not result.success
    # Depending on runtime availability, error mentions either workspace or runtime.
    err = (result.error or "").lower()
    assert ("workspace" in err) or ("runtime" in err) or ("hyperframes" in err)


def test_hyperframes_inspect_invokes_cli_with_layout_options(monkeypatch, tmp_path):
    workspace = tmp_path / "hyperframes"
    workspace.mkdir()
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    calls = []

    def fake_run_hf(self, args, *, cwd, timeout, check):
        calls.append({"args": args, "cwd": cwd, "timeout": timeout, "check": check})
        return __import__("subprocess").CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"ok": True, "issues": []}),
            stderr="",
        )

    monkeypatch.setattr(HyperFramesCompose, "_run_hf", fake_run_hf)
    result = HyperFramesCompose().execute(
        {
            "operation": "inspect",
            "workspace_path": str(workspace),
            "samples": 4,
            "timestamps": [1.5, 3],
            "overflow_tolerance_px": 3,
            "max_issues": 12,
            "collapse_static": False,
            "strict": True,
        }
    )

    assert result.success
    assert result.data["report"]["ok"] is True
    args = calls[0]["args"]
    assert args[:2] == ["inspect", "--json"]
    assert "--samples=4" in args
    assert "--tolerance=3" in args
    assert "--max-issues=12" in args
    assert "--no-collapse-static" in args
    assert "--strict" in args
    assert "--at" in args
    assert args[args.index("--at") + 1] == "1.5,3"


def test_hyperframes_snapshot_collects_new_png_artifacts(monkeypatch, tmp_path):
    workspace = tmp_path / "hyperframes"
    workspace.mkdir()
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    before = workspace / "existing.png"
    before.write_bytes(b"before")

    def fake_run_hf(self, args, *, cwd, timeout, check):
        (workspace / "snapshots").mkdir(exist_ok=True)
        (workspace / "snapshots" / "frame-0001.png").write_bytes(b"after")
        return __import__("subprocess").CompletedProcess(
            args=args,
            returncode=0,
            stdout="Captured 1 frame",
            stderr="",
        )

    monkeypatch.setattr(HyperFramesCompose, "_run_hf", fake_run_hf)
    result = HyperFramesCompose().execute(
        {
            "operation": "snapshot",
            "workspace_path": str(workspace),
            "snapshot_frames": 1,
            "timestamps": [2],
        }
    )

    assert result.success
    assert result.data["snapshot_count"] == 1
    assert result.artifacts == result.data["snapshots"]
    assert result.artifacts[0].endswith("frame-0001.png")


# ------------------------------------------------------------------
# video_compose runtime routing
# ------------------------------------------------------------------


def test_video_compose_reports_hyperframes_engine():
    info = VideoCompose().get_info()
    assert "render_engines" in info
    assert "hyperframes" in info["render_engines"]
    assert "hyperframes_note" in info
    # Both legacy key and new alias must be present.
    assert "render_runtimes" in info
    assert info["render_engines"] == info["render_runtimes"]


def test_video_compose_governance_note_present():
    info = VideoCompose().get_info()
    assert "runtime_governance" in info
    assert "silent swap" in info["runtime_governance"].lower()


def test_video_compose_rejects_unknown_render_runtime(tmp_path):
    """Governance: an unknown render_runtime must fail, not silently fall back."""
    comp_out = tmp_path / "out.mp4"
    result = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": {
                "version": "1.0",
                "cuts": [
                    {
                        "id": "c1",
                        "source": "nonexistent",
                        "in_seconds": 0,
                        "out_seconds": 3,
                    }
                ],
                "render_runtime": "totally-made-up",
                "renderer_family": "explainer-data",
            },
            "asset_manifest": {"assets": []},
            "output_path": str(comp_out),
        }
    )
    assert not result.success
    assert "Unknown render_runtime" in (result.error or "")


def test_video_compose_rejects_missing_render_runtime(tmp_path):
    """Regression: missing render_runtime MUST NOT silently fall back to Remotion.

    Prior behavior: empty/missing render_runtime fell through to the
    Remotion-default path, which defeated the auditable-runtime-selection
    governance contract.
    """
    comp_out = tmp_path / "out.mp4"
    result = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": {
                "version": "1.0",
                "cuts": [
                    {
                        "id": "c1",
                        "source": "nonexistent",
                        "in_seconds": 0,
                        "out_seconds": 3,
                    }
                ],
                # NOTE: no render_runtime field
                "renderer_family": "explainer-data",
            },
            "asset_manifest": {"assets": []},
            "output_path": str(comp_out),
        }
    )
    assert not result.success
    err = (result.error or "").lower()
    assert "render_runtime" in err
    assert "not set" in err or "must be" in err
    # Explicitly NOT treated as a Remotion request.
    assert "remotion render failed" not in err


def test_schemas_require_render_runtime():
    """Regression: both proposal_packet and edit_decisions schemas must
    REQUIRE render_runtime, not just declare it as an optional property."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent

    ed = json.loads(
        (root / "schemas" / "artifacts" / "edit_decisions.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "render_runtime" in ed["required"], (
        "edit_decisions.schema.json must require render_runtime — missing means "
        "governance bypass (silent Remotion fallback)."
    )

    pp = json.loads(
        (root / "schemas" / "artifacts" / "proposal_packet.schema.json").read_text(
            encoding="utf-8"
        )
    )
    pp_prod = pp["properties"]["production_plan"]
    assert "render_runtime" in pp_prod["required"], (
        "proposal_packet.production_plan must require render_runtime — "
        "the proposal stage MUST pick a runtime explicitly."
    )


def test_runtime_swap_detected_flips_when_proposal_packet_disagrees(tmp_path):
    """Regression: runtime_swap_detected was previously dead code because the
    check read a metadata field no one writes. The fix accepts
    `proposal_packet` directly so the signal actually fires."""
    # Build a minimal real MP4 so final_review can probe it.
    import subprocess

    mp4 = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=#000000:s=320x240:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest", str(mp4),
        ],
        capture_output=True, check=True, timeout=30,
    )

    edit_decisions = {
        "version": "1.0",
        "render_runtime": "hyperframes",  # what compose actually ran
        "renderer_family": "animation-first",
        "cuts": [{"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}],
    }
    proposal_packet = {
        "production_plan": {
            "render_runtime": "remotion",  # what proposal approved
        },
    }

    review = VideoCompose()._run_final_review(
        mp4, edit_decisions, proposal_packet
    )
    pp = review["checks"]["promise_preservation"]
    assert pp.get("runtime_swap_detected") is True
    assert "runtime_swap_check" in pp
    assert "detected" in pp["runtime_swap_check"]
    # And the human-readable issues list mentions the swap.
    assert any("render_runtime changed" in i for i in pp.get("issues", []))


def test_runtime_swap_detected_stays_false_when_proposal_matches(tmp_path):
    import subprocess

    mp4 = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=#000000:s=320x240:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest", str(mp4),
        ],
        capture_output=True, check=True, timeout=30,
    )
    edit_decisions = {
        "version": "1.0",
        "render_runtime": "remotion",
        "cuts": [{"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}],
    }
    proposal_packet = {"production_plan": {"render_runtime": "remotion"}}
    review = VideoCompose()._run_final_review(
        mp4, edit_decisions, proposal_packet
    )
    pp = review["checks"]["promise_preservation"]
    assert pp.get("runtime_swap_detected", False) is False
    assert "ok" in pp["runtime_swap_check"]


def test_both_runtimes_visible_in_render_engines_when_available():
    """Regression for the 'silently picks Remotion' failure mode.

    A fresh-session agent decides which runtime to present based on
    `video_compose.get_info()["render_engines"]`. That dict MUST expose
    BOTH remotion and hyperframes as separate boolean entries — not
    collapse them under one 'composition' key or hide hyperframes behind
    a remotion-specific note. If this test fails on a machine where both
    should be available, the agent's runtime discovery is broken and it
    will likely silently default to Remotion.
    """
    info = VideoCompose().get_info()
    engines = info["render_engines"]
    # Both entries must exist as keys regardless of availability.
    assert "remotion" in engines, (
        "render_engines dict is missing 'remotion' — agents won't see it as "
        "an option."
    )
    assert "hyperframes" in engines, (
        "render_engines dict is missing 'hyperframes' — agents won't see it "
        "as an option and will silently default to Remotion."
    )
    assert "ffmpeg" in engines
    # Both notes must exist independently so onboarding can surface both.
    assert "remotion_note" in info
    assert "hyperframes_note" in info
    # Governance note must be present — this is what reminds the agent
    # not to silently pick a default.
    assert "runtime_governance" in info
    assert "silent" in info["runtime_governance"].lower()


def _valid_runtime_decision(options: list[dict]) -> dict:
    """Build a minimal schema-valid decision_log entry with given options."""
    return {
        "decision_id": "d-runtime-1",
        "stage": "proposal",
        "category": "render_runtime_selection",
        "subject": "composition runtime",
        "options_considered": options,
        "selected": options[0]["option_id"],
        "reason": "fit-for-brief",
    }


def test_decision_log_accepts_render_runtime_selection_with_both_options():
    """Schema-level: a decision_log with BOTH runtimes in options_considered
    must validate. This is the contract the reviewer enforces."""
    import json
    from pathlib import Path
    try:
        import jsonschema
    except ImportError:  # pragma: no cover
        pytest.skip("jsonschema not installed")

    root = Path(__file__).resolve().parent.parent.parent
    schema = json.loads(
        (root / "schemas" / "artifacts" / "decision_log.schema.json").read_text(
            encoding="utf-8"
        )
    )

    log = {
        "version": "1.0",
        "project_id": "p-test",
        "decisions": [
            _valid_runtime_decision(
                [
                    {
                        "option_id": "remotion",
                        "label": "Remotion",
                        "score": 0.6,
                        "reason": "existing React scene stack fits",
                    },
                    {
                        "option_id": "hyperframes",
                        "label": "HyperFrames",
                        "score": 0.4,
                        "reason": "GSAP motion is natural but caption parity deferred",
                    },
                ]
            )
        ],
    }
    # No raise = valid.
    jsonschema.validate(log, schema)


def test_transcript_comparison_catches_literal_punctuation_leak(tmp_path):
    """Regression: Chirp3-HD (and some other TTS engines) read literal `...`
    as the word 'dot' in audio output. This failure is invisible to
    volume-based audio spotchecks but ships audio that literally says
    'dot dot dot' twelve times. The transcript_comparison check catches
    this automatically before the video is marked pass."""
    import json

    # Real-world example: user's script had `...` everywhere for dramatic
    # pause, Chirp read them all as "dot", transcript contains "dot dot dot"
    # phrases the script never had.
    script_text = (
        "A computer just did in five minutes what would take every machine on Earth, "
        "running since the Big Bang, ten septillion years to finish. "
        "We may have gotten help from parallel universes."
    )
    transcript_data = {
        "word_timestamps": [
            {"word": "A", "start": 0.0, "end": 0.1},
            {"word": "computer", "start": 0.1, "end": 0.5},
            {"word": "just", "start": 0.5, "end": 0.7},
            {"word": "did", "start": 0.7, "end": 0.9},
            {"word": "in", "start": 0.9, "end": 1.0},
            {"word": "five", "start": 1.0, "end": 1.3},
            {"word": "minutes", "start": 1.3, "end": 1.7},
            {"word": "dot", "start": 1.7, "end": 1.9},    # leak!
            {"word": "dot", "start": 1.9, "end": 2.1},    # leak!
            {"word": "dot", "start": 2.1, "end": 2.3},    # leak!
            {"word": "what", "start": 2.5, "end": 2.8},
            {"word": "would", "start": 2.8, "end": 3.0},
            {"word": "take", "start": 3.0, "end": 3.3},
            {"word": "every", "start": 3.3, "end": 3.6},
            {"word": "machine", "start": 3.6, "end": 4.0},
            {"word": "on", "start": 4.0, "end": 4.2},
            {"word": "Earth", "start": 4.2, "end": 4.6},
            {"word": "running", "start": 4.7, "end": 5.1},
            {"word": "since", "start": 5.1, "end": 5.4},
            {"word": "the", "start": 5.4, "end": 5.5},
            {"word": "Big", "start": 5.5, "end": 5.8},
            {"word": "Bang", "start": 5.8, "end": 6.2},
            {"word": "ten", "start": 6.2, "end": 6.5},
            {"word": "septillion", "start": 6.5, "end": 7.3},
            {"word": "years", "start": 7.3, "end": 7.7},
            {"word": "to", "start": 7.7, "end": 7.9},
            {"word": "finish", "start": 7.9, "end": 8.3},
            {"word": "dot", "start": 8.3, "end": 8.5},    # another leak
            {"word": "We", "start": 9.0, "end": 9.2},
            {"word": "may", "start": 9.2, "end": 9.4},
            {"word": "have", "start": 9.4, "end": 9.6},
            {"word": "gotten", "start": 9.6, "end": 9.9},
            {"word": "help", "start": 9.9, "end": 10.3},
            {"word": "from", "start": 10.3, "end": 10.5},
            {"word": "parallel", "start": 10.5, "end": 11.0},
            {"word": "universes", "start": 11.0, "end": 11.7},
        ]
    }
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript_data), encoding="utf-8")

    result = VideoCompose._compare_transcript_to_script(transcript_path, script_text)

    # Must catch the punctuation leak
    assert result["spurious_punctuation_words"], (
        "transcript_comparison failed to detect the 'dot' leak from literal ... punctuation."
    )
    leak_counts = {
        entry["word"]: entry["count"]
        for entry in result["spurious_punctuation_words"]
    }
    assert leak_counts.get("dot") == 4, f"Expected 4 'dot' leaks, got {leak_counts}"

    # Must produce a CRITICAL-severity issue message
    issue_text = " ".join(result["issues"]).lower()
    assert "tts punctuation leak" in issue_text
    assert "not in the script" in issue_text

    # Must NOT mark the transcript as matching
    assert result["transcript_matches_script"] is False


def test_transcript_comparison_passes_clean_audio(tmp_path):
    """Clean audio with no punctuation leaks must NOT trigger a false
    positive."""
    import json

    script_text = "The quick brown fox jumps over the lazy dog."
    transcript_data = {
        "word_timestamps": [
            {"word": "The", "start": 0.0, "end": 0.1},
            {"word": "quick", "start": 0.1, "end": 0.4},
            {"word": "brown", "start": 0.4, "end": 0.7},
            {"word": "fox", "start": 0.7, "end": 1.0},
            {"word": "jumps", "start": 1.0, "end": 1.3},
            {"word": "over", "start": 1.3, "end": 1.6},
            {"word": "the", "start": 1.6, "end": 1.7},
            {"word": "lazy", "start": 1.7, "end": 2.0},
            {"word": "dog", "start": 2.0, "end": 2.3},
        ]
    }
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript_data), encoding="utf-8")

    result = VideoCompose._compare_transcript_to_script(transcript_path, script_text)
    assert result["spurious_punctuation_words"] == []
    assert result["transcript_matches_script"] is True
    assert result["word_accuracy"] >= 0.9
    # issues may still have informational content but no CRITICAL TTS leak
    assert not any("tts punctuation leak" in i.lower() for i in result["issues"])


def test_transcript_comparison_graceful_when_inputs_missing(tmp_path):
    """When transcript or script is unavailable, the check should NOT
    crash — it should record the skip in issues so the silence is visible."""
    # No transcript
    result = VideoCompose._compare_transcript_to_script(None, "some script text")
    assert any("not provided" in i for i in result["issues"])

    # No script
    dummy = tmp_path / "t.json"
    dummy.write_text('{"word_timestamps": []}', encoding="utf-8")
    result = VideoCompose._compare_transcript_to_script(dummy, "")
    assert any("not provided" in i for i in result["issues"])

    # Transcript file missing
    result = VideoCompose._compare_transcript_to_script(tmp_path / "nonexistent.json", "script")
    assert any("not provided" in i for i in result["issues"])


def test_run_final_review_includes_transcript_comparison_section(tmp_path):
    """Regression: the `transcript_comparison` section must ALWAYS appear in
    the final_review output — even when the caller doesn't provide a
    transcript. A missing section = silent governance failure."""
    import subprocess

    # Build a minimal MP4 so _run_final_review can probe it.
    mp4 = tmp_path / "out.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=#000000:s=320x240:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(mp4),
        ],
        capture_output=True, check=True, timeout=30,
    )

    review = VideoCompose()._run_final_review(
        mp4,
        edit_decisions={
            "version": "1.0",
            "renderer_family": "animation-first",
            "render_runtime": "hyperframes",
            "cuts": [{"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}],
        },
    )
    assert "transcript_comparison" in review["checks"], (
        "final_review must always include a transcript_comparison section. "
        "When the caller doesn't provide a transcript, the section should "
        "still appear with a 'skipped' issue entry — not be omitted."
    )
    tc = review["checks"]["transcript_comparison"]
    assert any("not provided" in i for i in tc["issues"])


def test_hyperframes_root_composition_has_data_start_and_duration(tmp_path):
    """Regression: the generated root composition was missing data-start
    and data-duration, violating the HyperFrames contract (SKILL.md table)."""
    asset = tmp_path / "hero.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 512)
    workspace = tmp_path / "hyperframes"
    result = HyperFramesCompose().execute(
        {
            "operation": "scaffold_workspace",
            "workspace_path": str(workspace),
            "edit_decisions": {
                "version": "1.0",
                "render_runtime": "hyperframes",
                "renderer_family": "animation-first",
                "cuts": [
                    {
                        "id": "c1",
                        "source": "a1",
                        "in_seconds": 0,
                        "out_seconds": 5,
                        "type": "image",
                    }
                ],
            },
            "asset_manifest": {"assets": [{"id": "a1", "path": str(asset)}]},
        }
    )
    assert result.success, result.error
    html = (workspace / "index.html").read_text(encoding="utf-8")
    # Must have all four required root attributes per the HyperFrames contract.
    assert 'data-composition-id="root"' in html
    assert 'data-start="0"' in html  # per SKILL.md: root composition: use "0"
    # data-duration must match the timeline total; value can be '5' or '5.0' etc.
    import re
    m = re.search(r'data-duration="([^"]+)"', html)
    assert m, "root composition missing data-duration"
    assert float(m.group(1)) == pytest.approx(5.0)
    assert 'data-width="1920"' in html
    assert 'data-height="1080"' in html


def test_video_compose_blocks_hyperframes_when_runtime_unavailable(
    tmp_path, monkeypatch
):
    """Governance: if render_runtime='hyperframes' is locked but runtime is
    missing, the tool must NOT silently substitute another engine."""

    # Force HyperFrames availability to False regardless of the machine state.
    monkeypatch.setattr(
        VideoCompose, "_hyperframes_available", lambda self: False, raising=True
    )

    result = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": {
                "version": "1.0",
                "cuts": [
                    {
                        "id": "c1",
                        "source": "a1",
                        "in_seconds": 0,
                        "out_seconds": 3,
                    }
                ],
                "render_runtime": "hyperframes",
                "renderer_family": "animation-first",
            },
            "asset_manifest": {"assets": [{"id": "a1", "path": "does-not-matter.png"}]},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert not result.success
    err = (result.error or "").lower()
    assert "hyperframes" in err
    assert "blocker" in err or "not available" in err


# ------------------------------------------------------------------
# Scaffold / workspace generation (no CLI invocation)
# ------------------------------------------------------------------


def test_scaffold_workspace_generates_html_and_assets(tmp_path: Path):
    # Build a minimal asset manifest + edit decisions referencing a real
    # file so the staging copy has something to move.
    asset = tmp_path / "hero.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 1024)

    workspace = tmp_path / "hyperframes"
    edit_decisions: dict[str, Any] = {
        "version": "1.0",
        "renderer_family": "animation-first",
        "render_runtime": "hyperframes",
        "cuts": [
            {
                "id": "c1",
                "source": "asset_hero",
                "in_seconds": 0,
                "out_seconds": 3,
                "type": "image",
            },
            {
                "id": "c2",
                "source": "",
                "in_seconds": 3,
                "out_seconds": 6,
                "type": "text_card",
                "text": "Hello HyperFrames",
            },
        ],
    }
    asset_manifest = {
        "assets": [{"id": "asset_hero", "path": str(asset)}],
    }

    result = HyperFramesCompose().execute(
        {
            "operation": "scaffold_workspace",
            "workspace_path": str(workspace),
            "edit_decisions": edit_decisions,
            "asset_manifest": asset_manifest,
            "playbook": {
                "name": "test-playbook",
                "visual_language": {
                    "color_palette": {
                        "background": "#0B0F1A",
                        "text": "#F5F5F5",
                        "accent": "#F59E0B",
                    }
                },
                "typography": {
                    "heading": {"font": "Inter"},
                    "body": {"font": "Inter"},
                },
            },
        }
    )

    assert result.success, result.error
    index = workspace / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    # HyperFrames authoring contract requirements we MUST emit:
    assert 'data-composition-id="root"' in html
    assert 'window.__timelines["root"]' in html
    assert 'paused: true' in html
    assert 'class="clip' in html
    assert "gsap" in html.lower()

    # Text card for c2 must carry data-start and data-duration.
    assert 'data-start="3"' in html
    assert 'Hello HyperFrames' in html

    # Image asset was staged into the workspace.
    staged = workspace / "assets" / "hero.png"
    assert staged.is_file()
    # And index.html references it via a relative path.
    assert "assets/hero.png" in html

    # hyperframes.json registry config was written.
    hf_json = workspace / "hyperframes.json"
    assert hf_json.is_file()
    config = json.loads(hf_json.read_text(encoding="utf-8"))
    assert config["paths"]["blocks"] == "compositions"

    # DESIGN.md was written from the playbook.
    design = workspace / "DESIGN.md"
    assert design.is_file()
    design_text = design.read_text(encoding="utf-8")
    assert "#0B0F1A" in design_text or "test-playbook" in design_text


def test_scaffold_rejects_empty_cuts(tmp_path: Path):
    result = HyperFramesCompose().execute(
        {
            "operation": "scaffold_workspace",
            "workspace_path": str(tmp_path / "hyperframes"),
            "edit_decisions": {"version": "1.0", "cuts": []},
            "asset_manifest": {"assets": []},
        }
    )
    assert not result.success
    assert "cuts" in (result.error or "").lower()


# ------------------------------------------------------------------
# Style bridge
# ------------------------------------------------------------------


def test_style_bridge_fallback_has_all_required_vars():
    from lib.hyperframes_style_bridge import style_bridge

    css, design = style_bridge(None, None)
    for key in (
        "--color-bg",
        "--color-fg",
        "--color-accent",
        "--color-primary",
        "--font-heading",
        "--font-body",
        "--ease-primary",
        "--duration-entrance",
    ):
        assert key in css, f"missing CSS var: {key}"
    assert "# DESIGN" in design


def test_style_bridge_picks_up_playbook_palette():
    from lib.hyperframes_style_bridge import style_bridge

    playbook = {
        "name": "neon-test",
        "visual_language": {
            "color_palette": {
                "background": "#000000",
                "text": "#FFFFFF",
                "accent": ["#FF00FF", "#FF66FF"],
                "primary": "#00FFFF",
            }
        },
        "typography": {
            "heading": {"font": "Space Grotesk"},
            "body": {"font": "Inter"},
        },
        "motion": {"pace": "fast"},
    }
    css, design = style_bridge(playbook, None)
    assert css["--color-bg"] == "#000000"
    assert css["--color-accent"] == "#FF00FF"  # list → first
    assert css["--color-primary"] == "#00FFFF"
    assert css["--font-heading"] == "Space Grotesk"
    # Fast pace → shorter entrance duration.
    assert css["--duration-entrance"].startswith("0.")
    assert "neon-test" in design


def test_style_bridge_edit_decision_override_wins():
    from lib.hyperframes_style_bridge import style_bridge

    playbook = {
        "visual_language": {"color_palette": {"background": "#111", "text": "#eee"}},
    }
    edit = {"metadata": {"background_color": "#fff", "accent_color": "#09f"}}
    css, _ = style_bridge(playbook, edit)
    assert css["--color-bg"] == "#fff"
    assert css["--color-accent"] == "#09f"


# ------------------------------------------------------------------
# Schema acceptance for render_runtime
# ------------------------------------------------------------------


def test_proposal_packet_schema_accepts_render_runtime():
    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "schemas"
        / "artifacts"
        / "proposal_packet.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema["properties"]["production_plan"]["properties"]
    assert "render_runtime" in props
    assert "renderer_family" in props
    assert props["render_runtime"]["enum"] == ["remotion", "hyperframes", "ffmpeg"]


def test_edit_decisions_schema_accepts_render_runtime():
    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "schemas"
        / "artifacts"
        / "edit_decisions.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "render_runtime" in schema["properties"]
    assert schema["properties"]["render_runtime"]["enum"] == [
        "remotion",
        "hyperframes",
        "ffmpeg",
    ]


def test_final_review_tracks_runtime_and_swap():
    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "schemas"
        / "artifacts"
        / "final_review.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    pp = schema["properties"]["checks"]["properties"]["promise_preservation"][
        "properties"
    ]
    assert "render_runtime_used" in pp
    assert "runtime_swap_detected" in pp


def test_decision_log_has_render_runtime_category():
    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "schemas"
        / "artifacts"
        / "decision_log.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    category_enum = schema["properties"]["decisions"]["items"]["properties"][
        "category"
    ]["enum"]
    assert "render_runtime_selection" in category_enum


# ------------------------------------------------------------------
# Slideshow risk runtime threading
# ------------------------------------------------------------------


def test_slideshow_risk_accepts_render_runtime():
    from lib.slideshow_risk import score_slideshow_risk

    scenes = [
        {
            "type": "image",
            "description": "Opening shot of city",
            "shot_language": {"shot_size": "wide"},
            "shot_intent": "establish",
        },
        {
            "type": "text_card",
            "description": "Title overlay",
            "shot_language": {"shot_size": "medium"},
            "shot_intent": "announce",
        },
    ]
    out = score_slideshow_risk(scenes, render_runtime="hyperframes")
    assert out["render_runtime"] == "hyperframes"
    assert out["verdict"] in {"strong", "acceptable", "revise", "fail"}


# ------------------------------------------------------------------
# Composition validator runtime awareness
# ------------------------------------------------------------------


def test_composition_validator_hyperframes_asset_root(tmp_path: Path):
    """With render_runtime='hyperframes', the validator should look for
    assets next to index.html, not under remotion-composer/public."""
    from tools.analysis.composition_validator import CompositionValidator

    # Set up a fake HyperFrames workspace: hyperframes/ with index.html +
    # assets/. Composition JSON lives a sibling directory away.
    workspace = tmp_path / "hyperframes"
    (workspace / "assets").mkdir(parents=True)
    (workspace / "index.html").write_text("<!-- stub -->", encoding="utf-8")
    asset = workspace / "assets" / "hero.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    comp_json = artifacts_dir / "comp.json"
    comp_json.write_text(
        json.dumps(
            {
                "render_runtime": "hyperframes",
                "cuts": [
                    {
                        "id": "c1",
                        "source": "hero.png",
                        "in_seconds": 0,
                        "out_seconds": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = CompositionValidator().execute({"composition_path": str(comp_json)})
    # Asset exists in workspace/assets/ — should resolve without errors.
    assert result.success, result.error
    info_lines = " ".join(result.data.get("info", []))
    assert "hyperframes" in info_lines.lower() or "assets" in info_lines.lower()
