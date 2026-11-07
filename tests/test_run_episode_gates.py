#!/usr/bin/env python3
"""Red/green tests for the G2 gates wired into scripts/run_episode.py.

Covers: zero-cost gate (fail-closed on unnamed/unknown-cost routes),
speculative-evolution gate (label + motion lint), release gate (never
publishable by an agent) and the `episode_dir` state override.

No network, no media toolchain: state paths point at temp files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_episode  # noqa: E402

LABEL = "Speculative illustration"


def _cut(cid, move, easing="easeinout", direction="left", label=LABEL,
         generator="AI", duration=5.0):
    return {
        "id": cid,
        "generator": generator,
        "label": label,
        "description": "A speculative illustration of the creature.",
        "duration": duration,
        "move": move,
        "easing": easing,
        "direction": direction,
    }


def _episode(tmp_path, cuts=None):
    ep = tmp_path / "ep"
    (ep / "artifacts").mkdir(parents=True, exist_ok=True)
    edl = ep / "edit_decisions.json"
    edl.write_text(json.dumps({
        "episode_id": "t_ep",
        "duration": 20.0,
        "cuts": cuts or [_cut("c1", "pan"), _cut("c2", "zoom")],
    }), encoding="utf-8")
    return ep, edl


# ----------------------------------------------------------- zero-cost gate
def test_zero_cost_gate_default_routes_pass(tmp_path):
    res = run_episode.cmd_zero_cost_gate("t_ep", {"episode_dir": str(tmp_path)})
    assert res["status"] == "OK", res
    assert res["outputs"]["blocked"] == 0
    assert Path(res["outputs"]["report"]).is_file()


def test_zero_cost_gate_blocks_unknown_cost(tmp_path):
    state = {"episode_dir": str(tmp_path), "zero_cost_routes": [
        {"tool": "paid_image", "operation": "generate", "provider": "x",
         "runtime": "api", "route": "https://api.example/v1", "cost_usd": None},
    ]}
    res = run_episode.cmd_zero_cost_gate("t_ep", state)
    assert res["status"] == "BLOCKED", res
    assert "cost_usd" in res["error"]


def test_zero_cost_gate_blocks_unnamed_route(tmp_path):
    state = {"episode_dir": str(tmp_path), "zero_cost_routes": [
        {"tool": "mystery", "operation": "run", "runtime": "api",
         "route": "", "cost_usd": 0.0},
    ]}
    res = run_episode.cmd_zero_cost_gate("t_ep", state)
    assert res["status"] == "BLOCKED", res


# ------------------------------------------------------- speculative gate
def test_speculative_gate_passes_labelled_cuts(tmp_path):
    ep, edl = _episode(tmp_path)
    res = run_episode.cmd_speculative_gate(
        "t_ep", {"episode_dir": str(ep), "edl_path": str(edl), "speculative": True})
    assert res["status"] == "OK", res
    assert res["outputs"]["ai_labeled"] == 2


def test_speculative_gate_blocks_unlabelled_ai_cut(tmp_path):
    ep, edl = _episode(tmp_path, cuts=[_cut("c1", "pan", label="Illustration")])
    res = run_episode.cmd_speculative_gate(
        "t_ep", {"episode_dir": str(ep), "edl_path": str(edl), "speculative": True})
    assert res["status"] == "BLOCKED", res
    assert "Speculative illustration" in res["error"]


def test_speculative_gate_blocks_identical_consecutive_moves(tmp_path):
    ep, edl = _episode(tmp_path, cuts=[_cut("c1", "pan"), _cut("c2", "pan")])
    res = run_episode.cmd_speculative_gate(
        "t_ep", {"episode_dir": str(ep), "edl_path": str(edl), "speculative": True})
    assert res["status"] == "BLOCKED", res
    assert "identical" in res["error"]


def test_speculative_gate_blocks_without_edl(tmp_path):
    res = run_episode.cmd_speculative_gate(
        "t_ep", {"episode_dir": str(tmp_path), "speculative": True})
    assert res["status"] == "BLOCKED", res


def test_speculative_gate_skipped_for_non_speculative_niche(tmp_path):
    res = run_episode.cmd_speculative_gate(
        "t_ep", {"episode_dir": str(tmp_path), "speculative": False})
    assert res["status"] == "OK"
    assert res["outputs"].get("skipped") is True


# ---------------------------------------------------------- release gate
def test_release_gate_blocked_without_qc_report(tmp_path):
    ep, _ = _episode(tmp_path)
    res = run_episode.cmd_release_gate("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "BLOCKED", res
    assert "QC" in res["error"]


def test_release_gate_marks_draft_not_publishable(tmp_path):
    ep, _ = _episode(tmp_path)
    qa = ep / "artifacts" / "qa_report.json"
    qa.write_text(json.dumps([
        {"check_id": "duration", "status": "PASS"},
        {"check_id": "rights", "status": "FAILED", "detail": "unknown rights"},
    ]), encoding="utf-8")
    res = run_episode.cmd_release_gate("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "OK", res
    assert res["outputs"]["publishable"] is False
    verdict = json.loads(Path(res["outputs"]["verdict"]).read_text())
    assert verdict["publishable"] is False
    reasons = " ".join(verdict["reasons"])
    assert "FAILED" in reasons and "owner sign-off missing: voice" in reasons


def test_release_gate_reports_single_source_blocker(tmp_path):
    ep, _ = _episode(tmp_path)
    (ep / "artifacts" / "qa_report.json").write_text(
        json.dumps([{"check_id": "duration", "status": "PASS"}]), encoding="utf-8")
    ledger = ep / "artifacts" / "claim_ledger.md"
    ledger.write_text(
        "| claim_id | paraphrase | source | source_type | note |\n"
        "| C1-01 | one source only | https://example.org | SINGLE_SOURCE | x |\n",
        encoding="utf-8")
    ids = ep / "artifacts" / "claim_ids.json"
    ids.write_text(json.dumps([
        {"sentence": "One source only.", "claim_id": "C1-01"},
    ]), encoding="utf-8")
    res = run_episode.cmd_release_gate("t_ep", {
        "episode_dir": str(ep), "claim_ledger_path": str(ledger),
        "claim_ids_path": str(ids)})
    verdict = json.loads(Path(res["outputs"]["verdict"]).read_text())
    assert verdict["single_source_count"] == 1
    assert any("single-source" in r for r in verdict["reasons"])


# ------------------------------------------------------- episode_dir override
def test_episode_dir_override_used_by_package_draft(tmp_path):
    ep, _ = _episode(tmp_path)
    (ep / "renders").mkdir(parents=True, exist_ok=True)
    (ep / "script.md").write_text(
        "## 3 truthful titles\n\n1. Test Title\n\n## Hook\n\n"
        "- Beneath the ice there is an ocean. [T-01]\n", encoding="utf-8")
    res = run_episode.cmd_package_draft("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "OK", res
    assert str(ep / "package") in res["outputs"]["package"]
    assert (ep / "package" / "metadata.json").is_file()
    assert (ep / "package" / "shorts_plan.json").is_file()


def test_stage_order_puts_gates_around_the_expensive_stages():
    s = run_episode.STAGES
    assert s[0] == "zero_cost_gate"
    assert s.index("speculative_gate") == s.index("edl") + 1
    assert s.index("release_gate") == s.index("qc") + 1
    assert s.index("package_draft") > s.index("release_gate")


# ------------------------------------------------------------- integration
def test_pipeline_runs_real_gates_end_to_end(tmp_path):
    ep, edl = _episode(tmp_path)

    def ok(stage):
        def _f(topic_id, state):
            return {"status": "OK", "outputs": {}}
        return _f

    real = {"zero_cost_gate", "speculative_gate", "release_gate"}
    stages = {s: (getattr(run_episode, f"cmd_{s}") if s in real else ok(s))
              for s in run_episode.STAGES}
    # QC produced a report in the episode dir before the release gate runs.
    (ep / "artifacts" / "qa_report.json").write_text(
        json.dumps([{"check_id": "duration", "status": "PASS"}]), encoding="utf-8")
    state_path = ep / "episode_state.json"
    res = run_episode.run_pipeline(
        "t_ep", state_path=state_path, stages=stages,
        initial_state={"episode_dir": str(ep), "edl_path": str(edl),
                       "speculative": True})
    assert res["verdict"] == "OK", res
    assert res["state"]["stages"]["release_gate"]["status"] == "OK"
    assert json.loads(state_path.read_text())["stages"]["speculative_gate"]["status"] == "OK"


# ---------------------------------------------------------------- qc inputs
def test_qc_reads_episode_artifacts_not_legacy_shared_ones(tmp_path, monkeypatch):
    """A pilot must be QC'd against its OWN manifest/credits/claims.

    The legacy `docs/openmontage/slice/artifacts/` folder holds another
    episode's files; reading them produced a false verdict.
    """
    ep, edl = _episode(tmp_path)
    art = ep / "artifacts"
    (ep / "renders").mkdir(parents=True)
    (ep / "renders" / "final_t_ep_draft.mp4").write_bytes(b"not-a-video")
    for name in ("credits.txt", "claim_ids.json", "rights_records.json",
                 "narration_manifest.json"):
        (art / name).write_text("{}", encoding="utf-8")
    (ep / "claim_ledger.md").write_text("| id | claim |\n", encoding="utf-8")
    (ep / "subtitles.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n",
                                      encoding="utf-8")

    captured = {}

    class FakeQC:
        def execute(self, params):
            captured.update(params)

            class R:
                success = True
                data = {"verdict": "REVIEW"}

            return R()

    monkeypatch.setattr("tools.qa.qc.QCTool", FakeQC)
    res = run_episode.cmd_qc("t_ep", {"episode_dir": str(ep),
                                      "edl_path": str(edl)})
    assert res["status"] == "OK", res
    for key in ("narration_manifest", "credits_path", "claim_ids_path",
                "rights_records_path", "output_path"):
        assert Path(captured[key]).parent == art, (key, captured[key])
    assert Path(captured["edit_decisions_path"]) == edl


def test_package_draft_copies_only_episode_artifacts(tmp_path, monkeypatch):
    """The package must never inherit another episode's credits/subtitles."""
    ep, _edl = _episode(tmp_path)
    art = ep / "artifacts"
    (art / "narration_manifest.json").write_text('{"expected_duration": 1.0}',
                                                 encoding="utf-8")
    (art / "credits.txt").write_text("episode credits", encoding="utf-8")

    monkeypatch.setattr(
        "tools.packaging.package_builder.build_package",
        lambda *a, **k: {"ok": True, "manifest": {
            "title": "T", "shorts_beats": [], "credits_lines": []},
            "outputs": {"metadata.json": "m", "shorts_plan.json": "s",
                        "DISCLOSURE.md": "d"}})
    res = run_episode.cmd_package_draft("t_ep", {"episode_dir": str(ep),
                                                 "speculative": True})
    assert res["status"] == "OK", res
    pkg = ep / "package"
    assert (pkg / "narration_manifest.json").is_file()
    assert (pkg / "credits.txt").read_text() == "episode credits"
    assert not (pkg / "subtitles.srt").exists(), "legacy subtitles leaked in"


# ------------------------------------------------------- rights manifest gate
def test_footage_manifest_rights_reads_episode_assets_and_allows_ai(tmp_path):
    """An all-illustration episode must pass: ai_generated_illustration is a
    valid rights basis, and the episode's own records are the input."""
    ep, _edl = _episode(tmp_path)
    (ep / "artifacts" / "rights_records.json").write_text(json.dumps({
        "assets": [
            {"asset_id": "ill_1", "kind": "ai_illustration",
             "rights_basis": "ai_generated_illustration", "usable": True,
             "label": "Speculative illustration"},
            {"asset_id": "card_1", "kind": "graphics",
             "rights_basis": "explicit_license", "usable": True},
        ]}), encoding="utf-8")
    res = run_episode.cmd_footage_manifest_rights("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "OK", res
    assert res["outputs"]["assets"] == 2


def test_footage_manifest_rights_blocks_unknown_basis(tmp_path):
    ep, _edl = _episode(tmp_path)
    (ep / "artifacts" / "rights_records.json").write_text(json.dumps({
        "assets": [{"asset_id": "x", "kind": "footage", "rights_basis": "unknown"}]}),
        encoding="utf-8")
    res = run_episode.cmd_footage_manifest_rights("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "BLOCKED", res
    assert "unknown" in res["error"]


def test_footage_manifest_rights_blocks_unlabelled_ai(tmp_path):
    ep, _edl = _episode(tmp_path)
    (ep / "artifacts" / "rights_records.json").write_text(json.dumps({
        "assets": [{"asset_id": "ill_1", "kind": "ai_illustration",
                    "rights_basis": "ai_generated_illustration"}]}),
        encoding="utf-8")
    res = run_episode.cmd_footage_manifest_rights("t_ep", {"episode_dir": str(ep)})
    assert res["status"] == "BLOCKED", res
    assert "label" in res["error"]
