#!/usr/bin/env python3
"""Failing tests first (TDD) for the QC module per docs/openmontage/QA_SPEC.md.

Fixtures are generated at test time with ffmpeg lavfi into tmp dirs; no media
is committed. ffmpeg/ffprobe are local (no network) so the socket guard does
not apply to these tests.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.qa.qc import QCTool  # noqa: E402  (import after path insert)

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def _run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _gen_video(path, duration=10, size="1920x1080", rate=30, audio=True, fps_src="testsrc", audio_path=None):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"{fps_src}=size={size}:rate={rate}",
    ]
    if audio_path:
        cmd += ["-i", audio_path, "-map", "0:v", "-map", "1:a"]
    elif audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    cmd += ["-t", str(duration), "-c:v", "libx264", "-preset", "veryfast"]
    if audio or audio_path:
        cmd += ["-c:a", "aac"]
    cmd += [path]
    _run(cmd)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def _gen_normalized_audio(path, duration=10):
    """Two-pass loudnorm to land near I=-14 LUFS so ebur128 passes."""
    pass1 = _run([
        FFMPEG, "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-af", "loudnorm=print_format=json", "-f", "null", "-",
    ])
    m = re.search(r'"input_i"\s*:\s*([-\d.]+)', pass1.stderr)
    lra = re.search(r'"input_lra"\s*:\s*([-\d.]+)', pass1.stderr)
    tp = re.search(r'"input_tp"\s*:\s*([-\d.]+)', pass1.stderr)
    i_val = float(m.group(1)) if m else -21.8
    lra_val = float(lra.group(1)) if lra else 0.0
    tp_val = float(tp.group(1)) if tp else -17.8
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-af",
        f"loudnorm=I=-14:TP=-1.5:measured_I={i_val}:measured_LRA={lra_val}:"
        f"measured_TP={tp_val}:offset=0:linear=true",
        "-c:a", "aac", str(path),
    ])


def _gen_black(path, duration=10, size="1920x1080"):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=black:size={size}:rate=30",
        "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", path,
    ]
    _run(cmd)


def _gen_silent_audio(path, duration=10, size="1920x1080"):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30",
        "-f", "lavfi", "-i", "anullsrc=duration=10",
        "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", path,
    ]
    _run(cmd)


def _gen_frozen(path, duration=10, size="1920x1080"):
    # Static solid color -> every frame identical -> frozen.
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=blue:size={size}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", path,
    ]
    _run(cmd)


def _gen_no_audio(path, duration=10, size="1920x1080"):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30",
        "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", path,
    ]
    _run(cmd)


def _gen_wrong_res(path, duration=10):
    _gen_video(path, duration=duration, size="320x240", rate=25)


def _truncate(path):
    """Create a corrupt/truncated copy of the good clip."""
    good = Path(path).with_suffix(".good.mp4")
    _gen_video(good, duration=10)
    data = good.read_bytes()
    Path(path).write_bytes(data[: len(data) // 3])


def _write_report(qc, inputs, tmp):
    out = tmp / "qa_report.json"
    inputs["output_path"] = str(out)
    res = qc.execute(inputs)
    assert res.success, f"qc.execute failed: {res.error}"
    assert out.exists()
    report = json.loads(out.read_text())
    return report, res


def _find(report, check_id):
    for entry in report:
        if entry.get("check_id") == check_id:
            return entry
    return None


def test_good_clip_all_pass(tmp_path):
    """1080p color + loudnorm'd sine tone clip with all optional inputs -> PASS."""
    audio = tmp_path / "audio_norm.aac"
    _gen_normalized_audio(audio, duration=10)
    vid = tmp_path / "good.mp4"
    _gen_video(vid, duration=10, audio_path=audio)
    # supporting optional inputs so no check is NOT_RUN
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"expected_duration": 10.0, "tolerance": 1.0}))
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n")
    credits = tmp_path / "credits.txt"
    credits.write_text("Title: Test\nDirector: T\nProduction: P\n")
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps([{"text": "The crash happened.", "claim_id": "CID-01", "source_flags": ""}]))
    rights = tmp_path / "rights.json"
    rights.write_text(json.dumps([{"asset_id": "good.mp4", "rights_basis": "source_policy_us_gov"}]))
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "| claim_id | claim | sources | source_type | verification_status | evidence_notes |\n"
        "|---|---|---|---|---|---|\n"
        "| CID-01 | some claim | FS | TWO | AGENT_VERIFIED_TEXT | note |\n"
    )
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps({
        "cuts": [
            {"source": "a.mp4", "in_seconds": 0, "out_seconds": 5, "annotation": "intro"},
            {"source": "b.mp4", "in_seconds": 5, "out_seconds": 10, "annotation": "impact"},
        ]
    }))

    qc = QCTool()
    report, res = _write_report(qc, {
        "input_path": str(vid),
        "narration_manifest": str(manifest),
        "subtitle_path": str(subs),
        "credits_path": str(credits),
        "claim_ids_path": str(claims),
        "claim_ledger_path": str(ledger),
        "rights_records_path": str(rights),
        "edit_decisions_path": str(edits),
    }, tmp_path)

    by_id = {e["check_id"]: e for e in report}
    assert by_id["ffprobe_streams"]["status"] == "PASS", by_id["ffprobe_streams"]
    assert by_id["full_decode"]["status"] == "PASS", by_id["full_decode"]
    assert by_id["blackdetect"]["status"] == "PASS", by_id["blackdetect"]
    assert by_id["freezedetect"]["status"] == "PASS", by_id["freezedetect"]
    assert by_id["silencedetect"]["status"] == "PASS", by_id["silencedetect"]
    assert by_id["ebur128"]["status"] == "PASS", by_id["ebur128"]
    assert by_id["duration_vs_script"]["status"] == "PASS", by_id["duration_vs_script"]
    assert by_id["subtitle_sync"]["status"] == "PASS", by_id["subtitle_sync"]
    assert by_id["credits_complete"]["status"] == "PASS", by_id["credits_complete"]
    assert by_id["claim_ids"]["status"] == "PASS", by_id["claim_ids"]
    assert by_id["claim_ids_resolve"]["status"] == "PASS", by_id["claim_ids_resolve"]
    assert by_id["rights_basis"]["status"] == "PASS", by_id["rights_basis"]
    assert res.data["verdict"] == "PASS", res.data


def test_black_segment(tmp_path):
    """All-black clip -> blackdetect FAILED."""
    vid = tmp_path / "black.mp4"
    _gen_black(vid, duration=10)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    entry = _find(report, "blackdetect")
    assert entry is not None
    assert entry["status"] in ("FAILED", "REVIEW"), entry
    assert float(entry["measured_value"]) > 0.05, entry


def test_silent_segment(tmp_path):
    """Silent-audio clip -> silencedetect FAILED."""
    vid = tmp_path / "silent.mp4"
    _gen_silent_audio(vid, duration=10)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    entry = _find(report, "silencedetect")
    assert entry is not None
    assert entry["status"] in ("FAILED", "REVIEW"), entry


def test_frozen_segment(tmp_path):
    """Static clip -> freezedetect FAILED."""
    vid = tmp_path / "frozen.mp4"
    _gen_frozen(vid, duration=10)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    entry = _find(report, "freezedetect")
    assert entry is not None
    assert entry["status"] in ("FAILED", "REVIEW"), entry


def test_freeze_in_static_segment_review(tmp_path):
    """Frozen clip with freeze inside a static_by_design segment -> freezedetect REVIEW (not FAILED)."""
    vid = tmp_path / "frozen_in_static.mp4"
    _gen_frozen(vid, duration=10)
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps({
        "cuts": [],
        "static_segments": [
            {"start": 0.0, "end": 10.0, "reason": "title card", "static_by_design": True}
        ]
    }))
    qc = QCTool()
    report, _ = _write_report(qc, {
        "input_path": str(vid),
        "edit_decisions_path": str(edits),
    }, tmp_path)
    entry = _find(report, "freezedetect")
    assert entry is not None, "freezedetect entry missing"
    assert entry["status"] == "REVIEW", entry
    assert "static" in entry["evidence"].lower(), entry


def test_freeze_outside_static_segment_failed(tmp_path):
    """Frozen clip with freeze outside static_by_design segments -> freezedetect FAILED."""
    vid = tmp_path / "frozen_outside.mp4"
    _gen_frozen(vid, duration=10)
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps({
        "cuts": [],
        "static_segments": [
            {"start": 8.0, "end": 9.0, "reason": "brief title card", "static_by_design": True}
        ]
    }))
    qc = QCTool()
    report, _ = _write_report(qc, {
        "input_path": str(vid),
        "edit_decisions_path": str(edits),
    }, tmp_path)
    entry = _find(report, "freezedetect")
    assert entry is not None, "freezedetect entry missing"
    assert entry["status"] == "FAILED", entry


def test_no_audio(tmp_path):
    """Video-only clip -> ffprobe_streams FAILED (audio missing)."""
    vid = tmp_path / "noaudio.mp4"
    _gen_no_audio(vid, duration=10)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    entry = _find(report, "ffprobe_streams")
    assert entry is not None
    assert entry["status"] == "FAILED", entry


def test_wrong_resolution(tmp_path):
    """320x240 clip -> ffprobe_streams FAILED (resolution mismatch)."""
    vid = tmp_path / "wrong.mp4"
    _gen_wrong_res(vid)
    qc = QCTool()
    report, _ = _write_report(qc, {
        "input_path": str(vid),
        "expected_width": 1920,
        "expected_height": 1080,
    }, tmp_path)
    entry = _find(report, "ffprobe_streams")
    assert entry is not None
    assert entry["status"] == "FAILED", entry


def test_corrupt_file(tmp_path):
    """Truncated file -> full_decode FAILED or BLOCKED."""
    vid = tmp_path / "corrupt.mp4"
    _truncate(vid)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    entry = _find(report, "full_decode")
    assert entry is not None
    assert entry["status"] in ("FAILED", "BLOCKED"), entry


def test_subtitle_drift(tmp_path):
    """SRT last cue after audio duration -> subtitle_sync FAILED."""
    vid = tmp_path / "good_drift.mp4"
    _gen_video(vid, duration=10)
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:08,000 --> 00:00:15,000\nlate cue\n")
    qc = QCTool()
    report, _ = _write_report(qc, {
        "input_path": str(vid),
        "subtitle_path": str(subs),
    }, tmp_path)
    entry = _find(report, "subtitle_sync")
    assert entry is not None
    assert entry["status"] == "FAILED", entry


def test_tool_missing_blocked(tmp_path, monkeypatch):
    """ffprobe/ffmpeg unavailable -> tool-dependent checks BLOCKED, never PASS."""
    import shutil

    orig_which = shutil.which

    def fake_which(cmd):
        if os.path.basename(cmd) in ("ffprobe", "ffmpeg"):
            return None
        return orig_which(cmd)

    monkeypatch.setattr("shutil.which", fake_which)

    vid = tmp_path / "good.mp4"
    _gen_video(vid, duration=5)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    tool_checks = {
        "ffprobe_streams", "full_decode", "blackdetect", "freezedetect",
        "silencedetect", "ebur128",
    }
    for entry in report:
        if entry["check_id"] in tool_checks:
            assert entry["status"] == "BLOCKED", entry


def test_not_run_when_input_absent(tmp_path):
    """Absent optional inputs -> NOT_RUN, listed explicitly; verdict NOT_RUN."""
    audio = tmp_path / "audio_norm.aac"
    _gen_normalized_audio(audio, duration=10)
    vid = tmp_path / "good.mp4"
    _gen_video(vid, duration=10, audio_path=audio)
    qc = QCTool()
    report, res = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    by_id = {e["check_id"]: e for e in report}
    assert by_id["credits_complete"]["status"] == "NOT_RUN", by_id["credits_complete"]
    assert by_id["claim_ids"]["status"] == "NOT_RUN", by_id["claim_ids"]
    assert by_id["rights_basis"]["status"] == "NOT_RUN", by_id["rights_basis"]
    assert by_id["duration_vs_script"]["status"] == "NOT_RUN", by_id["duration_vs_script"]
    assert by_id["subtitle_sync"]["status"] == "NOT_RUN", by_id["subtitle_sync"]
    assert res.data["verdict"] == "NOT_RUN", res.data


def test_report_schema(tmp_path):
    """Every report entry conforms to QA_SPEC schema."""
    vid = tmp_path / "good.mp4"
    _gen_video(vid, duration=5)
    qc = QCTool()
    report, _ = _write_report(qc, {"input_path": str(vid)}, tmp_path)
    required = {"job_id", "check_id", "status", "evidence", "measured_value",
                "threshold", "tool_version", "timestamp"}
    for entry in report:
        assert required <= set(entry.keys()), entry
        assert entry["status"] in ("PASS", "REVIEW", "BLOCKED", "FAILED", "NOT_RUN")
        assert entry["tool_version"], entry
        assert entry["timestamp"], entry


# ---------------------------------------------------------------------------
# SCR-05 — thresholds must come from config/qc_thresholds.json, fail-closed
# ---------------------------------------------------------------------------

def _quiet_video(tmp_path):
    """1080p clip whose audio is loudnorm'd to ~-14 LUFS (ebur128 PASS at default)."""
    audio = tmp_path / "audio_norm.aac"
    _gen_normalized_audio(audio, duration=10)
    vid = tmp_path / "good.mp4"
    _gen_video(vid, duration=10, audio_path=audio)
    return vid


def test_default_thresholds_come_from_repo_config(tmp_path):
    """With no config_path, the repo config file is the threshold source."""
    import tools.qa.qc as qc_module

    vid = _quiet_video(tmp_path)
    res = QCTool().execute({
        "input_path": str(vid),
        "output_path": str(tmp_path / "qa_report.json"),
    })
    assert res.success, res.error
    assert res.data["thresholds_source"].endswith("config/qc_thresholds.json")
    assert res.data["thresholds"]["lufs_target"] == -14.0


def test_config_path_overrides_default_thresholds(tmp_path):
    """An explicit config_path is used instead of the repo config."""
    vid = _quiet_video(tmp_path)
    cfg = tmp_path / "custom.json"
    cfg.write_text(json.dumps({"lufs_target": -13.0}), encoding="utf-8")
    res = QCTool().execute({
        "input_path": str(vid),
        "output_path": str(tmp_path / "qa_report.json"),
        "config_path": str(cfg),
    })
    assert res.success, res.error
    assert res.data["thresholds"]["lufs_target"] == -13.0


def test_changing_config_changes_verdict(tmp_path):
    """A stricter lufs_target in the config flips ebur128 and the verdict."""
    vid = _quiet_video(tmp_path)

    strict = tmp_path / "strict.json"
    strict.write_text(
        json.dumps({"lufs_target": -30.0, "lufs_tolerance": 2.0}),
        encoding="utf-8",
    )
    out_strict = tmp_path / "strict_report.json"
    res_strict = QCTool().execute({
        "input_path": str(vid),
        "output_path": str(out_strict),
        "config_path": str(strict),
    })
    assert res_strict.success, res_strict.error
    strict_checks = {e["check_id"]: e for e in json.loads(out_strict.read_text())}
    assert strict_checks["ebur128"]["status"] == "FAILED", strict_checks["ebur128"]
    assert res_strict.data["verdict"] == "FAILED"

    out_default = tmp_path / "default_report.json"
    res_default = QCTool().execute({
        "input_path": str(vid),
        "output_path": str(out_default),
    })
    assert res_default.success, res_default.error
    default_checks = {e["check_id"]: e for e in json.loads(out_default.read_text())}
    assert default_checks["ebur128"]["status"] == "PASS", default_checks["ebur128"]
    assert res_default.data["verdict"] != "FAILED"


def test_missing_thresholds_config_fails_closed(tmp_path, monkeypatch):
    """Missing config => BLOCKED, never PASS, even for a good clip."""
    import tools.qa.qc as qc_module

    monkeypatch.setattr(qc_module, "DEFAULT_CONFIG_PATH",
                        tmp_path / "does_not_exist.json")
    vid = _quiet_video(tmp_path)
    out = tmp_path / "qa_report.json"
    res = QCTool().execute({"input_path": str(vid), "output_path": str(out)})

    assert res.success is False
    assert res.data["verdict"] == "BLOCKED", res.data
    report = json.loads(out.read_text())
    assert [e["check_id"] for e in report] == ["thresholds_config"]
    assert report[0]["status"] == "BLOCKED"
    assert "not found" in report[0]["evidence"]


def test_malformed_thresholds_config_fails_closed(tmp_path, monkeypatch):
    """Malformed JSON / non-numeric threshold => BLOCKED, never PASS."""
    import tools.qa.qc as qc_module

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qc_module, "DEFAULT_CONFIG_PATH", bad)
    vid = _quiet_video(tmp_path)
    out = tmp_path / "qa_report.json"
    res = QCTool().execute({"input_path": str(vid), "output_path": str(out)})
    assert res.success is False
    assert res.data["verdict"] == "BLOCKED"
    assert json.loads(out.read_text())[0]["status"] == "BLOCKED"

    non_numeric = tmp_path / "non_numeric.json"
    non_numeric.write_text(json.dumps({"lufs_target": "loud"}), encoding="utf-8")
    monkeypatch.setattr(qc_module, "DEFAULT_CONFIG_PATH", non_numeric)
    res = QCTool().execute({"input_path": str(vid),
                            "output_path": str(tmp_path / "qa2.json")})
    assert res.success is False
    assert res.data["verdict"] == "BLOCKED"


# ---------------------------------------------------------------------------
# SCR-06 — claim_ids_resolve must inspect EVERY id on a line
# ---------------------------------------------------------------------------

def _claim_inputs(tmp_path, claims, ledger_rows):
    vid = tmp_path / "v.mp4"
    _gen_video(vid, duration=5)
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps(claims), encoding="utf-8")
    ledger = tmp_path / "ledger.md"
    lines = [
        "| claim_id | claim | sources | source_type | verification_status | evidence_notes |",
        "|---|---|---|---|---|---|",
    ]
    for cid, source_type in ledger_rows:
        lines.append(f"| {cid} | claim | src | {source_type} | AGENT_VERIFIED_TEXT | note |")
    ledger.write_text("\n".join(lines), encoding="utf-8")
    return {
        "input_path": str(vid),
        "claim_ids_path": str(claims_path),
        "claim_ledger_path": str(ledger),
    }


def _resolve_status(inputs, tmp_path):
    out = tmp_path / "qa_report.json"
    inputs = dict(inputs, output_path=str(out))
    res = QCTool().execute(inputs)
    assert res.success, res.error
    by_id = {e["check_id"]: e for e in json.loads(out.read_text())}
    return by_id["claim_ids_resolve"], res


def test_single_source_second_id_is_still_flagged(tmp_path):
    """SINGLE id first, TWO id last: the line must still FAIL (RED before fix)."""
    claims = [{"text": "s", "claim_id": "SINGLE-01, TWO-01", "source_flags": ""}]
    inputs = _claim_inputs(tmp_path, claims,
                           [("SINGLE-01", "SINGLE"), ("TWO-01", "TWO")])
    entry, res = _resolve_status(inputs, tmp_path)
    assert entry["status"] == "FAILED", entry
    assert "SINGLE_SOURCE" in entry["evidence"]
    assert res.data["verdict"] == "FAILED"


def test_single_source_first_id_is_flagged(tmp_path):
    """TWO first, SINGLE last: FAIL (guard against the reverse regression)."""
    claims = [{"text": "s", "claim_id": "TWO-01, SINGLE-01", "source_flags": ""}]
    inputs = _claim_inputs(tmp_path, claims,
                           [("SINGLE-01", "SINGLE"), ("TWO-01", "TWO")])
    entry, _ = _resolve_status(inputs, tmp_path)
    assert entry["status"] == "FAILED", entry


def test_unknown_id_in_the_middle_fails(tmp_path):
    """A ghost id in the middle of a mixed row must FAIL resolution."""
    claims = [{"text": "s", "claim_id": "TWO-01, GHOST-99, SINGLE-01",
               "source_flags": "SINGLE_SOURCE flagged"}]
    inputs = _claim_inputs(tmp_path, claims,
                           [("SINGLE-01", "SINGLE"), ("TWO-01", "TWO")])
    entry, _ = _resolve_status(inputs, tmp_path)
    assert entry["status"] == "FAILED", entry
    assert "GHOST-99" in entry["evidence"]


def test_all_ids_resolved_and_single_flagged_passes(tmp_path):
    """Every id resolves and the SINGLE one is flagged => PASS."""
    claims = [{"text": "s", "claim_id": "SINGLE-01, TWO-01",
               "source_flags": "SINGLE_SOURCE flagged"}]
    inputs = _claim_inputs(tmp_path, claims,
                           [("SINGLE-01", "SINGLE"), ("TWO-01", "TWO")])
    entry, _ = _resolve_status(inputs, tmp_path)
    assert entry["status"] == "PASS", entry
