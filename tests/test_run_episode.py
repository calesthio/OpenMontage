#!/usr/bin/env python3
"""TDD tests for scripts/run_episode.py (Milestone Z3).

All stage orchestration is tested with *fake* stages so no media, network or
the Kokoro/stable-ts toolchain is required. Run with the system python + pytest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_episode  # noqa: E402

STAGES = run_episode.STAGES


def _fake_states(ok_stages):
    return {"topic_id": "artemis", "stages": {s: {"status": "OK"} for s in ok_stages}}


def _make_fake(stage, status="OK", outputs=None, call_log=None, error=None):
    def fake(topic_id, state):
        call_log.append(stage)
        return {"status": status, "outputs": outputs or {}, "error": error}
    return fake


def test_resume_skips_done_stages(tmp_path, monkeypatch):
    """Stages already OK are skipped on resume; later stages still run."""
    calls = []
    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    for s in STAGES[:3]:
        fakes[s] = _make_fake(s, status="OK", call_log=calls)
    monkeypatch.setattr(run_episode, "STAGE_REGISTRY", fakes)
    state_path = tmp_path / "state.json"
    res = run_episode.run_pipeline("artemis", state_path=state_path, stages=fakes,
                                   initial_state=_fake_states(STAGES[:3]))
    assert res["verdict"] == "OK", res
    assert calls == STAGES[3:], calls
    state = json.loads(state_path.read_text())
    for s in STAGES[:3]:
        assert state["stages"][s].get("resumed") is True, s
    for s in STAGES[3:]:
        assert state["stages"][s]["status"] == "OK", s


def test_failure_mid_chain_blocks(tmp_path, monkeypatch):
    """A BLOCKED stage stops the chain; later stages never run."""
    calls = []
    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    fakes["edl"] = _make_fake("edl", status="BLOCKED", error="no cuts", call_log=calls)
    monkeypatch.setattr(run_episode, "STAGE_REGISTRY", fakes)
    res = run_episode.run_pipeline("artemis", state_path=tmp_path / "s.json", stages=fakes)
    assert res["verdict"] == "BLOCKED", res
    assert res["stage"] == "edl", res
    after = [s for s in calls if STAGES.index(s) > STAGES.index("edl")]
    assert after == [], after
    state = json.loads((tmp_path / "s.json").read_text())
    assert state["stages"]["edl"]["status"] == "BLOCKED"
    assert state["stages"]["edl"]["error"] == "no cuts"


def test_unknown_claim_id_blocked(tmp_path, monkeypatch):
    """claim_ledger_check with an unknown claim_id fails closed."""
    calls = []
    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    fakes["claim_ledger_check"] = _make_fake(
        "claim_ledger_check", status="BLOCKED", error="unknown claim_id: ARTEMIS-99", call_log=calls)
    monkeypatch.setattr(run_episode, "STAGE_REGISTRY", fakes)
    res = run_episode.run_pipeline("artemis", state_path=tmp_path / "s.json", stages=fakes)
    assert res["verdict"] == "BLOCKED", res
    assert res["stage"] == "claim_ledger_check"
    assert calls == ["claim_ledger_check"], calls


def test_rights_unknown_blocked(tmp_path, monkeypatch):
    """footage_manifest_rights with rights_basis unknown fails closed."""
    calls = []
    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    fakes["footage_manifest_rights"] = _make_fake(
        "footage_manifest_rights", status="BLOCKED",
        error="rights_basis unknown for GX010506", call_log=calls)
    monkeypatch.setattr(run_episode, "STAGE_REGISTRY", fakes)
    state = _fake_states(["claim_ledger_check", "script_validation"])
    res = run_episode.run_pipeline("artemis", state_path=tmp_path / "s.json",
                                   stages=fakes, initial_state=state)
    assert res["verdict"] == "BLOCKED", res
    assert res["stage"] == "footage_manifest_rights"


def test_hash_mismatch_triggers_rerun(tmp_path, monkeypatch):
    """A corrupt checkpoint hash forces the stage to re-execute on resume."""
    calls = []
    outputs_v1 = {"clip": "artemis_launch_source.mp4"}
    outputs_v2 = {"clip": "artemis_launch_source.mp4", "note": "rescanned"}

    def fake_footage(topic_id, state):
        calls.append("footage_manifest_rights")
        return {"status": "OK", "outputs": outputs_v2}

    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    fakes["footage_manifest_rights"] = fake_footage
    monkeypatch.setattr(run_episode, "STAGE_REGISTRY", fakes)

    pre = {"topic_id": "artemis", "stages": {
        s: {"status": "OK"} for s in STAGES[:2]
    } | {
        "footage_manifest_rights": {
            "status": "OK", "outputs": outputs_v1,
            "output_hash": run_episode._hash_obj(outputs_v2),  # deliberately stale
        }
    }}
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(pre))
    res = run_episode.run_pipeline("artemis", state_path=state_path, stages=fakes, initial_state=pre)
    assert res["verdict"] == "OK", res
    # pre-seeded as OK but with a stale hash -> re-executed exactly once (not skipped)
    assert calls.count("footage_manifest_rights") == 1, calls
    assert "resumed" not in json.loads(state_path.read_text())["stages"]["footage_manifest_rights"]
    final = json.loads(state_path.read_text())
    assert final["stages"]["footage_manifest_rights"]["output_hash"] == run_episode._hash_obj(outputs_v2)


def test_disk_below_threshold_blocks(tmp_path, monkeypatch):
    """Free disk below the 800 MB threshold fails closed before any stage."""
    monkeypatch.setattr(run_episode, "MIN_FREE_BYTES", 800 * 1024 * 1024)
    monkeypatch.setattr(run_episode, "disk_free_bytes", lambda path: 100)
    calls = []
    fakes = {s: _make_fake(s, call_log=calls) for s in STAGES}
    res = run_episode.run_pipeline("artemis", state_path=tmp_path / "s.json", stages=fakes)
    assert res["verdict"] == "BLOCKED", res
    assert res["stage"] == "disk", res
    assert calls == [], calls


# ---------------------------------------------------------------------------
# Generalized render stage tests (Milestone Y1)
# ---------------------------------------------------------------------------
import subprocess  # noqa: E402


def _ffmpeg(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-y"] + args,
                          capture_output=True, text=True)


def _probe_duration(path):
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    try:
        return float(__import__("json").loads(res.stdout)["format"]["duration"])
    except Exception:
        return None


def _has_stream(path, codec_type):
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return False
    try:
        return any(s.get("codec_type") == codec_type
                   for s in __import__("json").loads(res.stdout).get("streams", []))
    except Exception:
        return False


def _make_png(path):
    _ffmpeg(["-f", "lavfi", "-i", "color=c=blue:size=320x240",
             "-frames:v", "1", str(path)])


def _make_mp4(path, dur=5.0):
    _ffmpeg(["-f", "lavfi", "-i", "testsrc=size=640x480:rate=30",
             "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)])


def _make_wav(path, dur=3.0):
    _ffmpeg(["-f", "lavfi", "-i", "anoisesrc",
             "-t", str(dur), "-ar", "44100", "-ac", "2", str(path)])


def _render_state(tmp_path, png, mp4, wav, cuts, out_name="out.mp4"):
    edl = tmp_path / "edit_decisions.json"
    edl.write_text(__import__("json").dumps({
        "version": 1, "topic_id": "testep",
        "resolution": "1920x1080", "fps": 30,
        "cuts": cuts,
    }, indent=2), encoding="utf-8")
    manifest = tmp_path / "render_manifest.json"
    manifest.write_text(__import__("json").dumps({
        "version": 1, "topic_id": "testep",
        "resolution": "1920x1080", "fps": 30,
        "assets": {
            "card_title": {"kind": "graphics", "path": str(png)},
            "apollo9_clip": {"kind": "footage", "path": str(mp4)},
        },
    }, indent=2), encoding="utf-8")
    out = tmp_path / out_name
    return {
        "edl_path": str(edl),
        "render_manifest_path": str(manifest),
        "narration_wav": str(wav),
        "render_output_path": str(out),
    }, out


def test_render_generalized_uses_edl_and_manifest(tmp_path):
    """Render builds from EDL cuts + per-episode manifest (no Artemis hardcode)."""
    png = tmp_path / "card.png"; _make_png(png)
    mp4 = tmp_path / "clip.mp4"; _make_mp4(mp4, dur=6.0)
    wav = tmp_path / "narration.wav"; _make_wav(wav, dur=5.0)
    cuts = [
        {"cut_id": 1, "start": 0.0, "end": 2.0, "asset_id": "card_title",
         "role": "graphics_card", "clip": "Title", "layout": "static_card",
         "rationale": "title card", "rights_basis": "source_policy_us_gov"},
        {"cut_id": 2, "start": 2.0, "end": 5.0, "asset_id": "apollo9_clip",
         "role": "archive_insert", "clip": "Launch", "layout": "1080p_scaled",
         "source_segment": "0.0-3.0s", "rationale": "archive insert", "rights_basis": "source_policy_us_gov"},
    ]
    state, out = _render_state(tmp_path, png, mp4, wav, cuts)
    res = run_episode.cmd_render("testep", state)
    assert res["status"] == "OK", res
    assert out.exists(), out
    dur = _probe_duration(out)
    assert dur is not None and abs(dur - 5.0) < 0.5, dur
    assert _has_stream(out, "video"), "missing video stream"
    assert _has_stream(out, "audio"), "missing audio stream"


def test_render_blocked_when_manifest_missing(tmp_path):
    state, out = _render_state(tmp_path, tmp_path / "a.png", tmp_path / "b.mp4",
                               tmp_path / "c.wav", [])
    state.pop("render_manifest_path")
    res = run_episode.cmd_render("testep", state)
    assert res["status"] == "BLOCKED", res


def test_render_blocked_when_asset_missing(tmp_path):
    png = tmp_path / "card.png"; _make_png(png)
    wav = tmp_path / "narration.wav"; _make_wav(wav)
    edl = tmp_path / "edit_decisions.json"
    edl.write_text(__import__("json").dumps({
        "version": 1, "topic_id": "testep", "resolution": "1920x1080", "fps": 30,
        "cuts": [{"cut_id": 1, "start": 0.0, "end": 2.0, "asset_id": "card_title",
                  "role": "graphics_card", "clip": "T", "layout": "static_card",
                  "rationale": "t", "rights_basis": "source_policy_us_gov"}],
    }, indent=2), encoding="utf-8")
    manifest = tmp_path / "render_manifest.json"
    # manifest intentionally lacks card_title
    manifest.write_text(__import__("json").dumps({
        "version": 1, "topic_id": "testep", "resolution": "1920x1080", "fps": 30,
        "assets": {},
    }, indent=2), encoding="utf-8")
    state = {"edl_path": str(edl), "render_manifest_path": str(manifest),
             "narration_wav": str(wav), "render_output_path": str(tmp_path / "out.mp4")}
    res = run_episode.cmd_render("testep", state)
    assert res["status"] == "BLOCKED", res
