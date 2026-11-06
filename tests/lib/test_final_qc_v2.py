"""Final QC V2 creative-quality checks tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from lib.edit_decision_engine import EditDecision
from lib.final_qc import FinalQC, QCReport
from lib.production_timeline import ProductionTimeline, ProductionTimelineBuilder
from lib.render_engine import RenderResult


def _make_decision(sid="S001", image_path="/tmp/x.png"):
    return EditDecision(
        scene_id=sid, sentence_id=sid, image_asset_id=f"IMG-{sid}",
        image_path=image_path, audio_asset_id=f"AUD-{sid}", audio_path="",
        start_ms=0, end_ms=500, duration_ms=500, motion_type="pan_zoom",
        camera_parameters={}, transition="cut", transition_duration=0.5,
        visual_effects=[], narrative_role="establish_context", hero_moment=False,
    )


def test_missing_assets_fail():
    qc = FinalQC(project_id="p")
    report = QCReport(project_id="p", version="1.0", created_at="x",
                      output_path="/tmp/o.mp4")
    decisions = [_make_decision("S001", image_path="/tmp/does_not_exist.png")]
    qc._check_missing_assets(report, decisions)
    assert report.checks[-1].status == "FAIL"
    assert report.checks[-1].blocking is True


def test_missing_assets_pass():
    qc = FinalQC(project_id="p")
    report = QCReport(project_id="p", version="1.0", created_at="x",
                      output_path="/tmp/o.mp4")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        p = f.name
    decisions = [_make_decision("S001", image_path=p)]
    qc._check_missing_assets(report, decisions)
    assert report.checks[-1].status == "PASS"


def test_composition_repeats_warning():
    qc = FinalQC(project_id="p")
    report = QCReport(project_id="p", version="1.0", created_at="x",
                      output_path="/tmp/o.mp4")
    d1 = _make_decision("S001")
    d2 = _make_decision("S002")
    # make identical image+motion
    d2.image_path = d1.image_path
    qc._check_composition_repeats(report, [d1, d2])
    assert report.checks[-1].status == "WARNING"


def test_timeline_mismatch_fail():
    qc = FinalQC(project_id="p")
    report = QCReport(project_id="p", version="1.0", created_at="x",
                      output_path="/tmp/o.mp4")
    tl = ProductionTimeline(project_id="p", run_id="r", version="1.0",
                            total_sentences=1, total_duration_ms=100000,
                            entries=[], status="validated")
    rr = RenderResult(project_id="p", output_path="/tmp/o.mp4", status="rendered",
                      duration_seconds=50.0, resolution="1920x1080", fps=30,
                      codec_video="h264", codec_audio="aac", bitrate_kbps=1000,
                      file_size_bytes=1000, scene_count=1, total_duration_ms=50000,
                      ffprobe={}, errors=[], warnings=[])
    qc._check_timeline_mismatch(report, tl, rr)
    assert report.checks[-1].status == "FAIL"


def test_timeline_mismatch_pass():
    qc = FinalQC(project_id="p")
    report = QCReport(project_id="p", version="1.0", created_at="x",
                      output_path="/tmp/o.mp4")
    tl = ProductionTimeline(project_id="p", run_id="r", version="1.0",
                            total_sentences=1, total_duration_ms=50000,
                            entries=[], status="validated")
    rr = RenderResult(project_id="p", output_path="/tmp/o.mp4", status="rendered",
                      duration_seconds=50.0, resolution="1920x1080", fps=30,
                      codec_video="h264", codec_audio="aac", bitrate_kbps=1000,
                      file_size_bytes=1000, scene_count=1, total_duration_ms=50000,
                      ffprobe={}, errors=[], warnings=[])
    qc._check_timeline_mismatch(report, tl, rr)
    assert report.checks[-1].status == "PASS"
