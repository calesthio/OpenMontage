"""Stickman Rig v1 — mock tests.

Pure data/SVG, no network, no spend, no rendering except one FFmpeg MP4
smoke test with fake images.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from PIL import Image  # noqa: E402

from lib.character_consistency_manager import (  # noqa: E402
    CharacterConsistencyManager,
)
from lib.edit_decision_engine import (  # noqa: E402
    EditDecisionEngine,
)
from lib.final_qc import FinalQC  # noqa: E402
from lib.production_timeline import (  # noqa: E402
    ProductionTimelineBuilder,
)
from lib.stickman_continuity import (  # noqa: E402
    StickmanContinuityChecker,
)
from lib.stickman_pose_library import (  # noqa: E402
    POSES, get_pose, list_poses, mirror_pose, pose_to_frame,
)
from lib.stickman_rig import (  # noqa: E402
    RigFrame, RigProfile, emit_svg, validate_keyframes,
    validate_rig_motion_events, SIGNATURE_DETAIL_ID,
)
from lib.visual_director import VisualDirector  # noqa: E402


def _make_profile():
    from lib.stickman_rig import RigProfile
    from lib.stickman_pose_library import list_poses
    return RigProfile(
        rig_id="rig-1",
        character_id="char-researcher",
        allowed_poses=list_poses(),
        allowed_expressions=["neutral", "curious", "focused", "surprised", "determined",
                            "happy", "frustrated", "concerned"],
    )


def test_rig_profile_validates():
    profile = _make_profile()
    assert profile.validate() == []
    assert profile.signature_detail_id == "magnifying_lens"
    assert "magnifying_lens" == SIGNATURE_DETAIL_ID


def test_all_poses_present():
    expected = {"idle", "walking", "running", "pointing", "explaining", "thinking",
                "surprised", "examining", "holding", "looking_through_lens", "interacting"}
    assert expected.issubset(set(list_poses()))
    assert len(POSES) >= 11


def test_pose_to_frame_signature_detail():
    for pid in list_poses():
        f = pose_to_frame(pid)
        assert f.signature_detail_present is True
        assert f.validate(_make_profile(), POSES) == [], pid


def test_emit_svg_contains_signature_detail_and_joints():
    profile = _make_profile()
    f = pose_to_frame("explaining", expression_id="curious", view="front")
    pose = get_pose("explaining")
    svg = emit_svg(f, pose, profile)
    assert "<svg" in svg
    assert svg.count("<line") >= 8
    assert svg.count("<circle") >= 3
    # accent color present (lens)
    assert profile.accent_color in svg


def test_forward_kinematics_positions():
    profile = _make_profile()
    f = pose_to_frame("idle")
    pose = get_pose("idle")
    from lib.stickman_rig import _positions
    pos = _positions(f, pose, profile)
    assert "hip" in pos and "head" in pos and "wrist_r" in pos
    # head above hip (Y down => head y < hip y)
    assert pos["head"][1] < pos["hip"][1]


def test_mirror_pose_swaps_sides():
    p = get_pose("pointing")
    m = mirror_pose(p)
    assert m["joint_angles"]["arm_l_shoulder"] == p["joint_angles"]["arm_r_shoulder"]
    assert m["joint_angles"]["arm_r_shoulder"] == p["joint_angles"]["arm_l_shoulder"]


def test_keyframe_validation():
    assert validate_keyframes("arm", [{"t": 0.0, "angle": 0.0}, {"t": 0.5, "angle": 1.0}]) == []
    bad = validate_keyframes("arm", [{"t": 0.5, "angle": 0.0}, {"t": 0.2, "angle": 1.0}])
    assert any("strictly increasing" in b for b in bad)
    bad2 = validate_keyframes("arm", [{"t": 0.0, "foo": 1.0}])
    assert any("unsupported" in b for b in bad2)


def test_rig_motion_events_validation():
    ev = [{"part_id": "arm_r", "keyframes": [{"t": 0.0, "angle": 0.0}, {"t": 1.0, "angle": 0.5}]}]
    assert validate_rig_motion_events(ev) == []
    bad = validate_rig_motion_events([{"part_id": "arm_r", "keyframes": []}])
    assert bad


def test_character_consistency_rig():
    mgr = CharacterConsistencyManager()
    profile = mgr.register_stickman_rig(
        rig_id="rig-1", character_id="c1", allowed_poses=list_poses(),
        allowed_expressions=["neutral", "curious"],
    )
    assert profile.rig_id == "rig-1"
    issues = mgr.validate_rig_pose(scene_id="s1", rig_id="rig-1", pose_id="idle",
                                  expression_id="neutral", signature_detail_present=True)
    assert issues == []
    issues2 = mgr.validate_rig_pose(scene_id="s2", rig_id="rig-1", pose_id="idle",
                                    expression_id="bogus", signature_detail_present=False)
    assert any(i.issue_type == "unknown_expression" for i in issues2)
    assert any(i.issue_type == "missing_signature_detail" for i in issues2)


def test_continuity_repeated_composition():
    checker = StickmanContinuityChecker()
    frame = {"rig_pose_id": "idle", "rig_expression_id": "neutral", "rig_view": "front",
             "signature_detail_present": True, "prop_ids": []}
    i1 = checker.check_frame("s1", frame)
    i2 = checker.check_frame("s2", frame)
    assert not any(x.issue_type == "repeated_composition" for x in i1)
    assert any(x.issue_type == "repeated_composition" for x in i2)


def test_continuity_missing_signature():
    checker = StickmanContinuityChecker()
    frame = {"rig_pose_id": "idle", "rig_expression_id": "neutral", "rig_view": "front",
             "signature_detail_present": False, "prop_ids": []}
    issues = checker.check_frame("s1", frame)
    assert any(x.issue_type == "missing_signature_detail" for x in issues)


def test_visual_director_stickman_aware():
    vd = VisualDirector(visual_style="ink", stickman_aware=True)
    scenes = [{"scene_id": f"s{i}", "shot_size": "medium"} for i in range(5)]
    report = vd.direct(scenes)
    assert report.directives[0].rig_pose_hint is not None
    assert report.directives[0].rig_expression_hint is not None
    d = vd.to_dict(report)
    assert "rig_pose_hint" in d["directives"][0]


def test_edit_decision_rig_fields():
    n = 4
    image_paths = []
    tmp = Path(tempfile.mkdtemp())
    img_dir = tmp / "images"; img_dir.mkdir()
    for i in range(n):
        img = Image.new("RGB", (64, 64), color=(i * 40, 0, 0))
        p = img_dir / f"img_{i}.png"
        img.save(p)
        image_paths.append(str(p))

    entries = []
    cursor = 0
    for i in range(n):
        sid = f"S{i+1:03d}"
        entries.append({
            "sentence_id": sid, "start_ms": cursor, "end_ms": cursor + 500,
            "duration_ms": 500, "audio_asset_id": f"AUD-{sid}", "audio_path": "",
            "alignment_confidence": 1.0, "rig_pose_id": "idle",
            "rig_expression_id": "neutral", "rig_view": "front",
            "rig_motion_events": [{"part_id": "arm_r", "keyframes": [{"t": 0.0, "angle": 0.0}, {"t": 0.5, "angle": 0.3}]}],
            "signature_detail_present": True,
        })
        cursor += 800

    plans = [{"sentence_id": f"S{i+1:03d}", "asset_id": f"IMG-S{i+1:03d}",
              "output_path": image_paths[i]} for i in range(n)]

    engine = EditDecisionEngine()
    dset = engine.build_decisions(
        sentence_timeline_entries=entries,
        image_plans=plans,
        project_id="p", run_id="r",
    )
    assert dset.total_scenes == n
    for d in dset.decisions:
        assert d.rig_pose_id == "idle"
        assert d.signature_detail_present is True
        assert len(d.rig_motion_events) == 1

    # validate_one_to_one: adjacent identical pose without motivated_hold -> problem
    # Make all same pose/view/expression
    res = engine.validate_one_to_one(dset)
    assert not res["ok"]  # should flag repetition


def test_production_timeline_copies_rig_fields():
    n = 3
    entries = []
    cursor = 0
    for i in range(n):
        sid = f"S{i+1:03d}"
        entries.append({
            "sentence_id": sid, "start_ms": cursor, "end_ms": cursor + 500,
            "duration_ms": 500, "audio_asset_id": f"AUD-{sid}", "audio_path": "",
            "rig_pose_id": "idle", "rig_expression_id": "neutral",
            "rig_view": "front", "signature_detail_present": True,
        })
        cursor += 500
    # motivate hold on middle to avoid repetition flag irrelevant here
    decisions = []
    for i, e in enumerate(entries):
        decisions.append({
            "sentence_id": e["sentence_id"], "scene_id": e["sentence_id"],
            "image_asset_id": f"IMG-{e['sentence_id']}", "image_path": "/tmp/x.png",
            "audio_asset_id": e["audio_asset_id"], "audio_path": "",
            "start_ms": e["start_ms"], "end_ms": e["end_ms"],
            "duration_ms": e["duration_ms"], "motion_type": "static",
            "camera_parameters": {}, "transition": "cut",
            "transition_duration": 0.5, "visual_effects": [],
            "narrative_role": "establish_context", "hero_moment": False,
            "rig_pose_id": e["rig_pose_id"],
            "rig_expression_id": e["rig_expression_id"],
            "rig_view": e["rig_view"],
            "signature_detail_present": True,
        })
    builder = ProductionTimelineBuilder()
    tl = builder.build(project_id="p", run_id="r", edit_decisions=decisions,
                       audio_timings=entries)
    assert tl.total_sentences == n
    for e in tl.entries:
        assert e.rig_pose_id == "idle"
        assert e.signature_detail_present is True


def test_final_qc_rig_checks():
    n = 3
    tmp = Path(tempfile.mkdtemp())
    img_dir = tmp / "images"; img_dir.mkdir()
    image_paths = []
    for i in range(n):
        img = Image.new("RGB", (64, 64), color=(i * 40, 0, 0))
        p = img_dir / f"img_{i}.png"
        img.save(p)
        image_paths.append(str(p))

    # build timeline via ProductionTimelineBuilder with rig fields
    decisions = []
    cursor = 0
    for i in range(n):
        sid = f"S{i+1:03d}"
        decisions.append({
            "sentence_id": sid, "scene_id": sid,
            "image_asset_id": f"IMG-{sid}", "image_path": image_paths[i],
            "audio_asset_id": f"AUD-{sid}", "audio_path": "",
            "start_ms": cursor, "end_ms": cursor + 500,
            "duration_ms": 500, "motion_type": "static",
            "camera_parameters": {}, "transition": "cut",
            "transition_duration": 0.5, "visual_effects": [],
            "narrative_role": "establish_context", "hero_moment": False,
            "rig_pose_id": "idle", "rig_expression_id": "neutral",
            "rig_view": "front", "signature_detail_present": True,
            "rig_motion_events": [],
        })
        cursor += 500

    from lib.production_timeline import ProductionTimelineBuilder
    builder = ProductionTimelineBuilder()
    tl = builder.build(project_id="p", run_id="r", edit_decisions=decisions)
    # make valid status
    tl.status = "validated"
    tl.issues = []

    from lib.render_engine import RenderEngine, RenderResult
    rr = RenderResult(
        project_id="p", output_path="/tmp/x.mp4", status="rendered",
        duration_seconds=tl.total_duration_ms / 1000.0, resolution="1920x1080",
        fps=30, codec_video="h264", codec_audio="aac",
        bitrate_kbps=1000, file_size_bytes=1000, scene_count=n,
        total_duration_ms=tl.total_duration_ms, ffprobe={},
    )

    qc = FinalQC(project_id="p")
    report = qc.check_all(output_path=Path("/tmp/x.mp4"), render_result=rr,
                         timeline=tl, edit_decisions=decisions)
    ids = [c.check_id for c in report.checks]
    assert "rig_signature_detail_present" in ids
    assert "rig_no_frozen_limbs" in ids
    assert "rig_prop_continuity" in ids


def test_preview_system_rig_check():
    from lib.preview_system import PreviewSystem
    ps = PreviewSystem()
    decisions = [{
        "sentence_id": "S001", "scene_id": "S001",
        "image_asset_id": "IMG-S001", "image_path": "/tmp/nope.png",
        "audio_asset_id": "AUD-S001", "audio_path": "",
        "start_ms": 0, "end_ms": 500, "duration_ms": 500,
        "motion_type": "static", "camera_parameters": {},
        "transition": "cut", "transition_duration": 0.5,
        "visual_effects": [], "narrative_role": "establish_context",
        "hero_moment": False, "rig_pose_id": "idle",
        "signature_detail_present": True, "rig_motion_events": [],
    }]
    # render will fail (no images) but preview qc still runs checks
    res = ps.build_preview(preview_id="pv", project_id="p", edit_decisions=decisions,
                           count=1, output_path=Path(tempfile.mkdtemp()) / "p.mp4")
    crits = [c.criterion for c in res.checks]
    # rig checks only added if rig cuts present and render path; signature check added
    assert "render_success" in crits


def test_production_metrics():
    from lib.production_metrics import MetricsCollector
    mc = MetricsCollector(project_id="p", run_id="r")
    mc.start()
    mc.record_images(10, regenerations=2)
    mc.record_sentences(10)
    mc.record_render(duration_s=5.0, file_size_bytes=1000, output_duration_s=10.0)
    mc.record_cost(1.23)
    m = mc.finalize()
    assert m.image_count == 10
    assert m.regeneration_count == 2
    assert m.cost_usd == 1.23
    assert m.cost_per_finished_minute_usd is not None
    assert m.cost_per_finished_minute_usd > 0


def test_render_mp4_with_fake_images(tmp_path):
    """Real FFmpeg render with fake images + rig fields (no spend)."""
    n = 5
    img_dir = tmp_path / "images"; img_dir.mkdir()
    image_paths = []
    for i in range(n):
        img = Image.new("RGB", (320, 180), color=(i * 50 % 256, 100, 100))
        p = img_dir / f"img_{i}.png"
        img.save(p)
        image_paths.append(str(p))

    decisions = []
    cursor = 0
    for i in range(n):
        sid = f"S{i+1:03d}"
        decisions.append({
            "sentence_id": sid, "scene_id": sid,
            "image_asset_id": f"IMG-{sid}", "image_path": image_paths[i],
            "audio_asset_id": f"AUD-{sid}", "audio_path": "",
            "start_ms": cursor, "end_ms": cursor + 400,
            "duration_ms": 400, "motion_type": "static",
            "camera_parameters": {"start_scale": 1.0, "end_scale": 1.0,
                                 "easing": "linear", "direction": "in", "fps": 30,
                                 "resolution": "320x180"},
            "transition": "cut", "transition_duration": 0.5,
            "visual_effects": [], "narrative_role": "establish_context",
            "hero_moment": False, "rig_pose_id": "idle",
            "rig_expression_id": "neutral", "rig_view": "front",
            "signature_detail_present": True,
        })
        cursor += 400

    from lib.render_engine import RenderEngine
    engine = RenderEngine(fps=30, width=320, height=180, crf=28, preset="ultrafast")
    out = tmp_path / "out.mp4"
    res = engine.render(project_id="p", edit_decisions=decisions, output_path=out)
    assert res.status == "rendered", res.errors
    assert out.exists() and out.stat().st_size > 0
    # rig overlay warning not present (no overlays)
    assert not any("rig overlays" in w for w in res.warnings)
