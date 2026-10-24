#!/usr/bin/env python3
"""L7 QC-gate tests: added-value maths, motion variety, speculative label,
rights flags/provenance and the emitted qa_report schema.

Red-first: these were written before the qc.py wiring they exercise.
Run: python -m pytest tests/qa/test_qc_gates_l7.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from jsonschema import validate  # noqa: E402

from tools.qa.qc import QCTool  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA = ROOT / "schemas/artifacts/qc_report.schema.json"


def make_video(path, seconds=10, w=160, h=90, fps=24):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate={fps}",
         "-t", str(seconds), "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True,
    )


def run_qc(tmp_path, video, **inputs):
    ed = tmp_path / "edits.json"
    out = tmp_path / "report.json"
    base = {
        "input_path": str(video),
        "output_path": str(out),
        "expected_width": 160,
        "expected_height": 90,
        "expected_fps": 24,
    }
    base.update(inputs)
    res = QCTool().execute(base)
    assert out.is_file(), res.error
    report = json.loads(out.read_text())
    return report, {e["check_id"]: e for e in report}


def by_id(report, check_id):
    for e in report:
        if e["check_id"] == check_id:
            return e
    return None


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


# ---------------------------------------------------------------- added_value
def test_added_value_reads_start_end_not_a_missing_duration_key(tmp_path):
    """A 25 s unannotated archive cut must FAIL; the generic EDL has no `duration`."""
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "c1", "start": 0.0, "end": 25.0, "role": "archive_insert",
         "asset_id": "a1"},
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed))
    assert checks["added_value"]["status"] == "FAILED", checks["added_value"]


def test_added_value_narration_share_below_90_percent_fails(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video, 10)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "c1", "start": 0.0, "end": 9.0, "role": "graphics_card",
         "annotation": "Key numbers card"},
    ]})
    manifest = _write_json(tmp_path / "nm.json", {"expected_duration": 4.0})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed),
                             narration_manifest=str(manifest))
    assert checks["added_value"]["status"] == "FAILED", checks["added_value"]
    assert "narration" in checks["added_value"]["evidence"].lower()


def test_added_value_pass_when_narrated_and_annotated(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video, 10)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "c1", "start": 0.0, "end": 9.5, "role": "graphics_card",
         "annotation": "Key numbers card", "move": "zoom",
         "easing": "easeinout", "direction": "in"},
    ]})
    manifest = _write_json(tmp_path / "nm.json", {"expected_duration": 9.6})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed),
                             narration_manifest=str(manifest))
    assert checks["added_value"]["status"] == "PASS", checks["added_value"]


# -------------------------------------------------------------- motion variety
def _motion_cut(i, move, easing="easeinout", direction="in", start=0.0):
    return {"id": f"c{i}", "start": start + i * 2.0, "end": start + i * 2.0 + 2.0,
            "role": "still", "annotation": "illustration", "move": move,
            "easing": easing, "direction": direction}


def test_motion_variety_two_identical_moves_in_a_row_fails(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        _motion_cut(0, "pan"), _motion_cut(1, "pan"),
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed))
    assert checks["motion_variety"]["status"] == "FAILED", checks["motion_variety"]


def test_motion_variety_distinct_moves_pass(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        _motion_cut(0, "pan"), _motion_cut(1, "zoom", direction="out"),
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed))
    assert checks["motion_variety"]["status"] == "PASS", checks["motion_variety"]


def test_motion_variety_declared_static_cards_do_not_trip_the_lint(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "t", "start": 0.0, "end": 1.0, "static_by_design": True},
        {"id": "c", "start": 1.0, "end": 2.0, "static_by_design": True},
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed))
    assert checks["motion_variety"]["status"] in ("REVIEW", "PASS")


# ------------------------------------------------------------ speculative label
def test_speculative_label_required_for_speculative_niche(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "c1", "start": 0.0, "end": 1.0, "generator": "AI",
         "label": "Illustration", "description": "A vent grazer.",
         "duration": 1.0},
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed),
                             speculative_niche=True, ai_label_max_share=1.0)
    assert checks["speculative_label"]["status"] == "FAILED", checks["speculative_label"]


def test_speculative_label_present_passes(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    ed = _write_json(tmp_path / "edits.json", {"cuts": [
        {"id": "c1", "start": 0.0, "end": 1.0, "generator": "AI",
         "label": "Speculative illustration",
         "description": "A hypothetical vent grazer.",
         "duration": 1.0},
    ]})
    _report, checks = run_qc(tmp_path, video, edit_decisions_path=str(ed),
                             speculative_niche=True, ai_label_max_share=0.15)
    assert checks["speculative_label"]["status"] == "PASS", checks["speculative_label"]


def test_speculative_label_not_run_when_edit_decisions_absent(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    _report, checks = run_qc(tmp_path, video, speculative_niche=True)
    assert checks["speculative_label"]["status"] == "NOT_RUN"


# ------------------------------------------------------------------ rights gate
def _rights(tmp_path, records):
    return _write_json(tmp_path / "rights.json", records)


def _base_record(**over):
    rec = {
        "asset_id": "asset-1", "kind": "video",
        "rights_basis": "source_policy_us_gov",
        "source_url": "https://example.gov/item/1",
        "credit": "NASA", "sha256": "a" * 64,
        "flags": {},
    }
    rec.update(over)
    return rec


def test_rights_third_party_credit_flag_rejects(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    rp = _rights(tmp_path, [_base_record(flags={"third_party_credit": True})])
    _report, checks = run_qc(tmp_path, video, rights_records_path=str(rp))
    assert checks["rights_basis"]["status"] == "FAILED", checks["rights_basis"]


def test_rights_nc_nd_license_rejects(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    rp = _rights(tmp_path, [_base_record(license="CC BY-NC-ND 4.0")])
    _report, checks = run_qc(tmp_path, video, rights_records_path=str(rp))
    assert checks["rights_basis"]["status"] == "FAILED", checks["rights_basis"]


def test_rights_emblem_as_main_picture_rejects(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    rp = _rights(tmp_path, [_base_record(flags={"emblem_as_main_picture": True})])
    _report, checks = run_qc(tmp_path, video, rights_records_path=str(rp))
    assert checks["rights_basis"]["status"] == "FAILED", checks["rights_basis"]


def test_rights_missing_provenance_fails(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    rec = _base_record()
    rec.pop("sha256")
    rp = _rights(tmp_path, [rec])
    _report, checks = run_qc(tmp_path, video, rights_records_path=str(rp))
    assert checks["rights_basis"]["status"] == "FAILED", checks["rights_basis"]


def test_rights_complete_record_passes(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    rp = _rights(tmp_path, [_base_record()])
    _report, checks = run_qc(tmp_path, video, rights_records_path=str(rp))
    assert checks["rights_basis"]["status"] == "PASS", checks["rights_basis"]


# ---------------------------------------------------------------------- schema
def test_emitted_qa_report_matches_committed_schema(tmp_path):
    video = tmp_path / "v.mp4"
    make_video(video)
    report, _checks = run_qc(tmp_path, video)
    validate(instance=report, schema=json.loads(SCHEMA.read_text()))
