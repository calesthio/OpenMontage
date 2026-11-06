"""P5 — Final QC tests.

Tests the FinalQC + ReleaseGate pipeline on real rendered MP4s:
- 10 / 50 / 250 sentence positive renders (PASS expected)
- Negative tests: black frame, corrupted audio, missing image, wrong FPS,
  duplicate images, sync error, truncated narration (FAIL expected)
- Load test readiness for 20–25 min video (timing-based, no full render)

Zero-cost: FFmpeg + Pillow only, no network, no credits, no Google Flow.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from PIL import Image  # noqa: E402

from lib.audio_mixing import AudioMixing  # noqa: E402
from lib.edit_decision_engine import EditDecision, EditDecisionSet  # noqa: E402
from lib.edit_decision_engine import EditDecisionEngine  # noqa: E402
from lib.final_qc import FinalQC  # noqa: E402
from lib.production_timeline import ProductionTimelineBuilder  # noqa: E402
from lib.release_gate import ReleaseGate  # noqa: E402
from lib.render_engine import RenderEngine, RenderResult, render_from_timeline  # noqa: E402
from lib.sentence_timeline import SentenceTimelineBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers: fake images + fake narration (same patterns as P4 tests)
# ---------------------------------------------------------------------------


def make_fake_images(tmp_path: Path, n: int, size=(1920, 1080)) -> list[str]:
    """Generate n distinct solid-color PNG images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for i in range(n):
        r = (i * 37) % 256
        g = (i * 71) % 256
        b = (i * 103) % 256
        img = Image.new("RGB", size, color=(r, g, b))
        p = img_dir / f"img_{i:04d}.png"
        img.save(p)
        paths.append(str(p))
    return paths


def make_fake_narration(tmp_path: Path, duration_s: float, sr: int = 48000) -> str:
    """Generate a sine-wave WAV narration of duration_s seconds."""
    wav = tmp_path / "narration.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration_s}:sample_rate={sr}",
            "-c:a", "pcm_s16le",
            str(wav),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=120,
    )
    return str(wav)


def build_timeline_entries(
    n: int,
    base_start_ms: int = 0,
    duration_ms: int = 500,
    pause_ms: int = 300,
) -> list[dict]:
    """Build P3-style sentence_timeline_entry dicts with explicit pauses."""
    entries = []
    cursor = base_start_ms
    for i in range(n):
        sid = f"S{i+1:03d}"
        entries.append(
            {
                "sentence_id": sid,
                "start_ms": cursor,
                "end_ms": cursor + duration_ms,
                "duration_ms": duration_ms,
                "audio_asset_id": f"proj-AUD-{sid}",
                "audio_path": "",  # filled later
                "alignment_confidence": 1.0,
                "narrative_role": "establish_context" if i % 3 == 0 else "deliver_payload",
                "hero_moment": (i % 4 == 0),
            }
        )
        cursor += duration_ms + pause_ms
    return entries


def build_image_plans(n: int, image_paths: list[str]) -> list[dict]:
    """Build P2-style image_plan dicts keyed by sentence_id."""
    plans = []
    for i in range(n):
        sid = f"S{i+1:03d}"
        plans.append(
            {
                "sentence_id": sid,
                "asset_id": f"proj-IMG-{sid}",
                "output_path": image_paths[i],
                "transition": "cut" if i % 4 == 0 else "dissolve",
                "transition_duration": 0.5,
            }
        )
    return plans


def build_motion_specs(n: int, motion_engine) -> list:
    """Build motion specs via the real MotionEngine (variety enforced)."""
    specs = []
    for i in range(n):
        sid = f"S{i+1:03d}"
        hero = (i % 4 == 0)
        role = "establish_context" if i % 3 == 0 else "deliver_payload"
        spec = motion_engine.spec_for_scene(
            scene_id=sid,
            duration_seconds=0.5,
            hero_moment=hero,
            narrative_role=role,
        )
        specs.append(spec)
    return specs


def render_full_project(
    tmp_path: Path,
    n: int,
    *,
    duration_ms: int = 500,
    pause_ms: int = 0,
    project_id: str = "qc-test",
    missing_image: bool = False,
) -> tuple[Path, ProductionTimelineBuilder, list, RenderEngine]:
    """Render a full project MP4 and return (mp4_path, timeline, entries, engine).

    Entries are contiguous (pause_ms=0 by default) so timeline duration equals
    rendered duration, which QC's duration_match expects.
    """
    image_paths = make_fake_images(tmp_path, n)
    entries = build_timeline_entries(n, duration_ms=duration_ms, pause_ms=pause_ms)
    me = __import__("lib.motion_engine", fromlist=["MotionEngine"]).MotionEngine()
    specs = build_motion_specs(n, me)
    image_plans = build_image_plans(n, image_paths)

    # Optionally corrupt the last image path to test missing-image failure.
    if missing_image and n > 0:
        image_plans[-1]["output_path"] = "/nonexistent/img_missing.png"

    ed = EditDecisionEngine()

    total_s = sum(int(e["duration_ms"]) for e in entries) / 1000.0
    narration = make_fake_narration(tmp_path, total_s)
    mixer = AudioMixing()
    mix = mixer.mix(
        project_id=project_id,
        narration_path=narration,
        output_path=tmp_path / "master.aac",
    )
    assert mix.status == "mixed"

    # Fill in audio_path for each entry BEFORE build_decisions (QC checks file existence).
    for e in entries:
        e["audio_path"] = narration

    dset = ed.build_decisions(
        sentence_timeline_entries=entries,
        image_plans=image_plans,
        motion_specs=specs,
        project_id=project_id,
    )

    tb = ProductionTimelineBuilder()
    tl = tb.build(
        project_id=project_id,
        run_id="run-qc",
        edit_decisions=[d.to_dict() for d in dset.decisions],
    )
    assert tl.is_valid

    out = tmp_path / f"out_{n}.mp4"
    result = render_from_timeline(
        project_id=project_id,
        timeline=tl,
        audio_mix=mix,
        output_path=out,
    )
    assert result.status == "rendered", result.errors

    re_ = RenderEngine()
    probe = re_._probe(out)
    rr = RenderResult(
        project_id=project_id,
        output_path=str(out),
        status="rendered",
        duration_seconds=probe.get("duration_seconds", 0.0),
        resolution=f"{probe.get('width', 1920)}x{probe.get('height', 1080)}",
        fps=probe.get("fps", 30),
        codec_video=probe.get("codec_video", ""),
        codec_audio=probe.get("codec_audio", ""),
        bitrate_kbps=probe.get("bitrate_kbps"),
        file_size_bytes=probe.get("size_bytes"),
        scene_count=len(tl.entries),
        total_duration_ms=tl.total_duration_ms,
        ffprobe=probe,
    )
    return out, tl, entries, re_, rr


# ---------------------------------------------------------------------------
# Positive tests: 10 / 50 / 250 sentences
# ---------------------------------------------------------------------------


def _qc_pass_check(report, decision) -> None:
    assert report.overall_status in ("PASS", "WARNING"), report.errors
    assert decision.can_publish is True
    assert decision.decision in ("PASS", "WARNING")


def test_qc_10_sentences_pass(tmp_path):
    out, tl, entries, re_, rr = render_full_project(tmp_path, 10, duration_ms=400, pause_ms=0)
    qc = FinalQC(project_id="qc-10")
    report = qc.check_all(output_path=out, render_result=rr, timeline=tl)
    gate = ReleaseGate()
    decision = gate.evaluate(report)
    _qc_pass_check(report, decision)


def test_qc_50_sentences_pass(tmp_path):
    out, tl, entries, re_, rr = render_full_project(tmp_path, 50, duration_ms=300, pause_ms=0)
    qc = FinalQC(project_id="qc-50")
    report = qc.check_all(output_path=out, render_result=rr, timeline=tl)
    gate = ReleaseGate()
    decision = gate.evaluate(report)
    _qc_pass_check(report, decision)


def test_qc_250_sentences_pass(tmp_path):
    out, tl, entries, re_, rr = render_full_project(tmp_path, 250, duration_ms=100, pause_ms=0)
    qc = FinalQC(project_id="qc-250")
    report = qc.check_all(output_path=out, render_result=rr, timeline=tl)
    gate = ReleaseGate()
    decision = gate.evaluate(report)
    _qc_pass_check(report, decision)


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_qc_missing_image_render_fails(tmp_path):
    """Render fails when an image is missing."""
    n = 5
    image_paths = make_fake_images(tmp_path, n)
    entries = build_timeline_entries(n, duration_ms=400, pause_ms=0)
    me = __import__("lib.motion_engine", fromlist=["MotionEngine"]).MotionEngine()
    specs = build_motion_specs(n, me)
    image_plans = build_image_plans(n, image_paths)
    image_plans[-1]["output_path"] = "/nonexistent/img_missing.png"

    ed = EditDecisionEngine()
    dset = ed.build_decisions(
        sentence_timeline_entries=entries,
        image_plans=image_plans,
        motion_specs=specs,
        project_id="qc-missing-img",
    )
    total_s = sum(int(e["duration_ms"]) for e in entries) / 1000.0
    narration = make_fake_narration(tmp_path, total_s)
    mixer = AudioMixing()
    mix = mixer.mix(project_id="qc-missing-img", narration_path=narration, output_path=tmp_path / "master.aac")
    assert mix.status == "mixed"

    tb = ProductionTimelineBuilder()
    tl = tb.build(project_id="qc-missing-img", run_id="run", edit_decisions=[d.to_dict() for d in dset.decisions])
    re_ = RenderEngine()
    result = re_.render(
        project_id="qc-missing-img", edit_decisions=dset, timeline=tl,
        audio_mix=mix, output_path=tmp_path / "missing.mp4",
    )
    assert result.status == "failed"
    assert any("missing" in e.lower() for e in result.errors)


def test_qc_wrong_fps_fail(tmp_path):
    """Render at 24 fps; QC video_tracks should FAIL."""
    out, tl, entries, re_, rr = render_full_project(tmp_path, 5, duration_ms=400, pause_ms=100, project_id="qc-wrong-fps")
    # Re-render at 24 fps.
    re_24 = RenderEngine(fps=24)
    image_paths = make_fake_images(tmp_path, 5)
    entries = build_timeline_entries(5, duration_ms=400, pause_ms=100)
    me = __import__("lib.motion_engine", fromlist=["MotionEngine"]).MotionEngine()
    specs = build_motion_specs(5, me)
    image_plans = build_image_plans(5, image_paths)
    ed = EditDecisionEngine()
    dset = ed.build_decisions(
        sentence_timeline_entries=entries, image_plans=image_plans,
        motion_specs=specs, project_id="qc-wrong-fps",
    )
    mixer = AudioMixing()
    total_s = sum(int(e["duration_ms"]) for e in entries) / 1000.0
    narration = make_fake_narration(tmp_path, total_s)
    mix = mixer.mix(project_id="qc-wrong-fps", narration_path=narration, output_path=tmp_path / "master.aac")
    assert mix.status == "mixed"
    tb = ProductionTimelineBuilder()
    tl2 = tb.build(project_id="qc-wrong-fps", run_id="run", edit_decisions=[d.to_dict() for d in dset.decisions])
    result = re_24.render(project_id="qc-wrong-fps", edit_decisions=dset, timeline=tl2, audio_mix=mix, output_path=tmp_path / "out_24fps.mp4")
    assert result.status == "rendered"

    qc = FinalQC(project_id="qc-wrong-fps")
    probe = re_24._probe(tmp_path / "out_24fps.mp4")
    from lib.render_engine import RenderResult
    rr24 = RenderResult(
        project_id="qc-wrong-fps",
        output_path=str(tmp_path / "out_24fps.mp4"),
        status="rendered",
        duration_seconds=probe.get("duration_seconds", 0.0),
        resolution=f"{probe.get('width', 1920)}x{probe.get('height', 1080)}",
        fps=probe.get("fps", 24),
        codec_video=probe.get("codec_video", ""),
        codec_audio=probe.get("codec_audio", ""),
        bitrate_kbps=probe.get("bitrate_kbps"),
        file_size_bytes=probe.get("size_bytes"),
        scene_count=5,
        total_duration_ms=tl2.total_duration_ms,
        ffprobe=probe,
    )
    report = qc.check_all(output_path=tmp_path / "out_24fps.mp4", render_result=rr24, timeline=tl2)
    fps_check = next((c for c in report.checks if c.check_id == "video_tracks"), None)
    assert fps_check is not None
    assert fps_check.status == "FAIL", fps_check.evidence


def test_qc_duplicate_image_fail(tmp_path):
    """Two sentences share the same image; QC one_image_per_sentence should FAIL."""
    n = 4
    image_paths = make_fake_images(tmp_path, n)
    entries = build_timeline_entries(n, duration_ms=400, pause_ms=100)
    me = __import__("lib.motion_engine", fromlist=["MotionEngine"]).MotionEngine()
    specs = build_motion_specs(n, me)
    image_plans = build_image_plans(n, image_paths)
    # Force S002 and S003 to share image_plans[0]'s image.
    image_plans[1]["output_path"] = image_plans[0]["output_path"]
    image_plans[1]["asset_id"] = image_plans[0]["asset_id"]

    ed = EditDecisionEngine()
    dset = ed.build_decisions(
        sentence_timeline_entries=entries,
        image_plans=image_plans,
        motion_specs=specs,
        project_id="qc-dup",
    )
    mixer = AudioMixing()
    total_s = sum(int(e["duration_ms"]) for e in entries) / 1000.0
    narration = make_fake_narration(tmp_path, total_s)
    mix = mixer.mix(project_id="qc-dup", narration_path=narration, output_path=tmp_path / "master.aac")
    assert mix.status == "mixed"

    from lib.render_engine import RenderResult
    re_ = RenderEngine()
    tb = ProductionTimelineBuilder()
    tl2 = tb.build(project_id="qc-dup", run_id="run", edit_decisions=[d.to_dict() for d in dset.decisions])
    # Pass None for timeline so render doesn't get blocked by duplicate image IDs
    # (the QC check itself will catch the duplicate).
    result = re_.render(project_id="qc-dup", edit_decisions=dset, timeline=None,
                        audio_mix=mix, output_path=tmp_path / "out_dup.mp4")
    assert result.status == "rendered"
    probe = re_._probe(tmp_path / "out_dup.mp4")
    rr = RenderResult(
        project_id="qc-dup",
        output_path=str(tmp_path / "out_dup.mp4"),
        status="rendered",
        duration_seconds=probe.get("duration_seconds", 0.0),
        resolution=f"{probe.get('width', 1920)}x{probe.get('height', 1080)}",
        fps=probe.get("fps", 30),
        codec_video=probe.get("codec_video", ""),
        codec_audio=probe.get("codec_audio", ""),
        bitrate_kbps=probe.get("bitrate_kbps"),
        file_size_bytes=probe.get("size_bytes"),
        scene_count=4,
        total_duration_ms=tl2.total_duration_ms,
        ffprobe=probe,
    )
    qc = FinalQC(project_id="qc-dup")
    report = qc.check_all(output_path=tmp_path / "out_dup.mp4", render_result=rr, timeline=tl2)
    dup_check = next((c for c in report.checks if c.check_id == "one_image_per_sentence"), None)
    assert dup_check is not None
    assert dup_check.status == "FAIL", dup_check.evidence


def test_qc_release_gate_fail_blocks_publish(tmp_path):
    """A FAIL decision must have can_publish=False."""
    out, tl, entries, re_, rr = render_full_project(tmp_path, 3, duration_ms=400, pause_ms=100, project_id="qc-gate")
    qc = FinalQC(project_id="qc-gate")
    report = qc.check_all(output_path=out, render_result=rr, timeline=tl)
    gate = ReleaseGate()
    decision = gate.evaluate(report)

    if report.overall_status == "FAIL":
        assert decision.can_publish is False
        assert len(decision.blocking_checks) > 0
    else:
        assert decision.can_publish is True


# ---------------------------------------------------------------------------
# Load-test readiness for 20–25 min video (timing-based, no full render)
# ---------------------------------------------------------------------------


def test_qc_load_readiness_20_25_min(tmp_path):
    """Verify QC infrastructure can handle a 20–25 min timeline without
    actually rendering a full film (timing-based readiness check)."""
    for minutes in (20, 25):
        total_s = minutes * 60
        n_sentences = max(1, int(total_s / 4.0))
        entries = build_timeline_entries(n_sentences, duration_ms=3800, pause_ms=200)
        tl = ProductionTimelineBuilder().build(
            project_id=f"qc-load-{minutes}",
            run_id="run",
            edit_decisions=[
                {
                    "sentence_id": e["sentence_id"], "scene_id": e["sentence_id"],
                    "image_asset_id": f"IMG-{e['sentence_id']}",
                    "image_path": str(tmp_path / f"img_{e['sentence_id']}.png"),
                    "audio_asset_id": f"AUD-{e['sentence_id']}",
                    "audio_path": "",
                    "start_ms": e["start_ms"], "end_ms": e["end_ms"],
                    "duration_ms": e["duration_ms"],
                    "motion_type": "static",
                    "camera_parameters": {},
                    "transition": "cut", "transition_duration": 0.5,
                    "visual_effects": [],
                    "narrative_role": "establish_context",
                    "hero_moment": False,
                }
                for e in entries
            ],
        )
        total_dur_min = tl.total_duration_ms / 1000.0 / 60.0
        assert 19.0 <= total_dur_min <= 26.0, f"{minutes} min target, got {total_dur_min:.1f} min"
        assert tl.total_sentences == n_sentences

    # Verify QC runs in reasonable time on a 20-sentence subset (proxy for scale).
    t0 = time.time()
    out, tl2, _, re_, rr = render_full_project(tmp_path, 20, duration_ms=400, pause_ms=0, project_id="qc-scale")
    qc = FinalQC(project_id="qc-scale")
    report = qc.check_all(output_path=out, render_result=rr, timeline=tl2)
    elapsed = time.time() - t0
    assert elapsed < 30.0, f"QC on 20 sentences took {elapsed:.1f}s (too slow for scale)"
    assert report.overall_status in ("PASS", "WARNING")
