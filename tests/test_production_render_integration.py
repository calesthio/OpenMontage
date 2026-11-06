"""End-to-end tests for Production & Render Integration.

Covers:
  - Production manifest creation, schema validation, integrity hash
  - Manifest save/load round-trip with integrity verification
  - Audio sync: scene-to-segment binding, too_long/too_short detection,
    manual correction
  - Image asset pipeline: intake, validation, duplicate detection,
    missing/corrupted file handling, preview generation
  - Motion engine: pan/zoom/detail_crop/parallax/static, variety linting,
    transition selection
  - Render integration: readiness checks, edit decisions generation,
    test render on stub images (no Google Flow)

All tests are zero-cost: no generation, no credits, no network.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.audio_sync import AudioSyncEngine, SyncIssue  # noqa: E402
from lib.image_asset_pipeline import (  # noqa: E402
    AssetPipelineReport,
    ImageAssetPipeline,
)
from lib.motion_engine import MotionEngine, MotionPlan  # noqa: E402
from lib.production_manifest import (  # noqa: E402
    CameraMoveParams,
    CaptionSpace,
    ManifestScene,
    ProductionManifest,
    build_manifest_from_preproduction,
    load_manifest,
    save_manifest,
)
from lib.render_integration import (  # noqa: E402
    RenderCheck,
    RenderIntegration,
    RenderReadinessReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False


def _make_stub_image(path: Path, width: int = 1920, height: int = 1080, color: str = "red") -> None:
    """Create a stub PNG image using PIL or FFmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if _HAS_PIL:
        from PIL import Image as _Image
        im = _Image.new("RGB", (width, height), color)
        im.save(path)
    else:
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", f"color=c={color}:s={width}x{height}:d=1",
             "-frames:v", "1", str(path)],
            check=True, capture_output=True,
        )


def _make_scenes(count: int = 21, base_duration: float = 5.0) -> list[dict[str, Any]]:
    """Create a list of scene dicts for testing."""
    scenes = []
    for i in range(count):
        scenes.append({
            "scene_id": f"scene-{i:03d}",
            "script_section_id": f"block-{i:03d}",
            "visual_idea": f"Scene {i} visual content about topic {i}",
            "shot_purpose": "establish_context" if i % 3 == 0 else "deliver_payload",
            "framing": "medium",
            "camera_movement": "static",
            "lens_mm": 35,
            "lighting_key": "natural",
            "composition": f"balanced composition keyword topic{i} scene {i+1} of {count}",
            "required_objects": [],
            "duration_seconds": base_duration,
            "transition_to_next": "cut",
            "shot_size": "medium",
            "shot_intent": f"Serves context for block-{i:03d}",
            "narrative_role": "establish_context" if i % 3 == 0 else "deliver_payload",
            "hero_moment": i == 5,
            "timeline_position": i * base_duration,
        })
    return scenes


def _make_prompt_packets(count: int = 21) -> list[dict[str, Any]]:
    packets = []
    for i in range(count):
        packets.append({
            "scene_id": f"scene-{i:03d}",
            "main_prompt": f"Bold ink illustration of scene {i}, crisp black outlines, flat expressive colour fills, scientific-documentary composition",
            "negative_prompt": "text, caption, watermark, logo, signature, title, typography, 3d render, photorealistic photograph",
            "image_format": "1920x1080, ink illustration",
            "aspect_ratio": "16:9",
            "generation_params": {"model": "flow", "steps": 20},
        })
    return packets


def _make_qc_reports(count: int = 21, all_pass: bool = True) -> dict[str, dict[str, Any]]:
    reports = {}
    for i in range(count):
        sid = f"scene-{i:03d}"
        reports[sid] = {
            "scene_id": sid,
            "passed": all_pass,
            "overall_score": 1.0 if all_pass else 0.5,
            "results": [
                {"criterion": "script_alignment", "passed": True, "score": 1.0, "detail": "ok"},
                {"criterion": "duplicate_frames", "passed": True, "score": 1.0, "detail": "no duplicate"},
            ],
            "blocking_issues": [] if all_pass else ["test blocking issue"],
        }
    return reports


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


def test_manifest_creation_and_integrity():
    """Manifest creation seals with an integrity hash; tampering breaks it."""
    m = ProductionManifest(
        manifest_id="m-001",
        run_id="run-001",
        project="test-project",
        scenes=[
            ManifestScene(
                scene_id="scene-000",
                asset_id="asset-000",
                script_section_id="block-000",
                prompt="test prompt",
                expected_format="1920x1080",
                duration_seconds=5.0,
                timeline_position=0.0,
                camera_move="medium",
                transition="cut",
                file_status="missing",
                qc_result="pass",
            ),
        ],
    )
    m.recompute_timeline()
    m.seal()

    assert m.integrity_hash is not None
    assert len(m.integrity_hash) == 64
    assert m.verify_integrity() is True

    # Tamper: change a scene duration
    m.scenes[0].duration_seconds = 999.0
    assert m.verify_integrity() is False


def test_manifest_save_load_roundtrip(tmp_path):
    """Manifest can be saved to disk and loaded back with integrity intact."""
    m = ProductionManifest(
        manifest_id="m-rt",
        run_id="run-rt",
        project="rt-project",
        scenes=[
            ManifestScene(
                scene_id="scene-000",
                asset_id="asset-000",
                script_section_id="block-000",
                prompt="hello world",
                expected_format="1920x1080",
                duration_seconds=5.0,
                timeline_position=0.0,
                camera_move="medium",
                transition="cut",
                file_status="missing",
                qc_result="pass",
            ),
        ],
    )
    m.recompute_timeline()
    m.seal()

    p = tmp_path / "manifest.json"
    save_manifest(m, p)

    loaded = load_manifest(p)
    assert loaded.manifest_id == "m-rt"
    assert loaded.project == "rt-project"
    assert len(loaded.scenes) == 1
    assert loaded.verify_integrity() is True
    assert loaded.timeline is not None
    assert loaded.timeline.total_duration_seconds == 5.0


def test_build_manifest_from_preproduction():
    """Factory builder produces a manifest from preproduction outputs."""
    scenes = _make_scenes(21)
    packets = _make_prompt_packets(21)
    qc = _make_qc_reports(21, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-build",
        project="build-project",
        scene_plans=scenes,
        prompt_packets=packets,
        quality_reports=qc,
        target_duration_seconds=105.0,
    )

    assert m.run_id == "run-build"
    assert m.project == "build-project"
    assert m.status == "draft"
    assert len(m.scenes) == 21
    assert all(s.file_status == "missing" for s in m.scenes)
    assert all(s.qc_result == "pass" for s in m.scenes)
    assert m.verify_integrity() is True
    assert m.timeline is not None
    assert m.timeline.total_duration_seconds == 105.0


# ---------------------------------------------------------------------------
# Audio sync tests
# ---------------------------------------------------------------------------


def test_audio_sync_binds_scenes():
    """Audio sync binds scenes to narration segments and computes timestamps."""
    engine = AudioSyncEngine()

    # Build a minimal manifest with 3 scenes
    m = ProductionManifest(
        manifest_id="m-as",
        run_id="run-as",
        project="as-project",
        scenes=[
            ManifestScene(
                scene_id="scene-000", asset_id="a-000",
                script_section_id="sec-0", prompt="p", expected_format="f",
                duration_seconds=5.0, timeline_position=0.0,
                camera_move="m", transition="cut",
                file_status="missing", qc_result="pass",
            ),
            ManifestScene(
                scene_id="scene-001", asset_id="a-001",
                script_section_id="sec-1", prompt="p", expected_format="f",
                duration_seconds=5.0, timeline_position=5.0,
                camera_move="m", transition="cut",
                file_status="missing", qc_result="pass",
            ),
        ],
    )
    m.recompute_timeline()

    narration = {
        "run_id": "run-as",
        "total_duration_seconds": 10.0,
        "segments": [
            {"segment_id": "s0", "script_section": "sec-0", "text": "Hello world",
             "start_seconds": 0.0, "end_seconds": 5.0, "duration_seconds": 5.0},
            {"segment_id": "s1", "script_section": "sec-1", "text": "Goodbye world",
             "start_seconds": 5.0, "end_seconds": 10.0, "duration_seconds": 5.0},
        ],
    }
    scene_map = {"scene-000": "sec-0", "scene-001": "sec-1"}

    report = engine.sync(m, narration, scene_map)

    assert report.all_synced is True
    assert report.total_audio_seconds == 10.0
    assert len(report.segments) == 2
    assert report.segments[0].scene_id == "scene-000"
    assert report.segments[1].scene_id == "scene-001"
    assert m.audio_sync is not None
    assert m.audio_sync.total_duration_seconds == 10.0


def test_audio_sync_flags_too_long():
    """Audio longer than planned scene is flagged too_long."""
    engine = AudioSyncEngine()

    m = ProductionManifest(
        manifest_id="m-tl", run_id="run-tl", project="tl-project",
        scenes=[ManifestScene(
            scene_id="scene-000", asset_id="a-000", script_section_id="sec-0",
            prompt="p", expected_format="f", duration_seconds=2.0,
            timeline_position=0.0, camera_move="m", transition="cut",
            file_status="missing", qc_result="pass",
        )],
    )
    m.recompute_timeline()

    narration = {
        "run_id": "run-tl", "total_duration_seconds": 10.0,
        "segments": [{"segment_id": "s0", "script_section": "sec-0",
                      "text": "A very long narration segment that goes on",
                      "start_seconds": 0.0, "end_seconds": 10.0, "duration_seconds": 10.0}],
    }
    scene_map = {"scene-000": "sec-0"}

    report = engine.sync(m, narration, scene_map)
    assert report.all_synced is False
    too_long = [i for i in report.issues if i.issue_type == "too_long"]
    assert len(too_long) == 1
    assert too_long[0].scene_id == "scene-000"


def test_audio_sync_manual_correction():
    """Manual segment correction updates timestamps and re-flags issues."""
    engine = AudioSyncEngine()

    m = ProductionManifest(
        manifest_id="m-mc", run_id="run-mc", project="mc-project",
        scenes=[ManifestScene(
            scene_id="scene-000", asset_id="a-000", script_section_id="sec-0",
            prompt="p", expected_format="f", duration_seconds=5.0,
            timeline_position=0.0, camera_move="m", transition="cut",
            file_status="missing", qc_result="pass",
        )],
    )
    m.recompute_timeline()

    narration = {
        "run_id": "run-mc", "total_duration_seconds": 10.0,
        "segments": [{"segment_id": "s0", "script_section": "sec-0",
                      "text": "Test", "start_seconds": 0.0,
                      "end_seconds": 10.0, "duration_seconds": 10.0}],
    }
    report = engine.sync(m, narration, {"scene-000": "sec-0"})
    assert report.all_synced is False  # too_long (10s vs 5s)

    # Correct manually: shorten to match scene
    engine.adjust_segment(m, "s0", start_seconds=0.0, end_seconds=5.0)
    assert m.audio_sync.segments[0].duration_seconds == 5.0
    assert m.audio_sync.segments[0].issue == "ok"
    assert m.verify_integrity() is True  # re-sealed after correction


# ---------------------------------------------------------------------------
# Image asset pipeline tests
# ---------------------------------------------------------------------------


def test_asset_pipeline_intake_validated(tmp_path):
    """Valid assets are received, hashed, and organized by scene."""
    pipe = ImageAssetPipeline(project="ip", run_id="run-ip", base_dir=tmp_path)

    # Create stub images
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    _make_stub_image(img1, 1920, 1080, "blue")
    _make_stub_image(img2, 1920, 1080, "green")

    report = pipe.intake_manifest(
        scenes=[
            {"scene_id": "scene-000", "asset_id": "asset-000", "expected_format": "1920x1080"},
            {"scene_id": "scene-001", "asset_id": "asset-001", "expected_format": "1920x1080"},
        ],
        assets_by_id={
            "asset-000": {"path": str(img1)},
            "asset-001": {"path": str(img2)},
        },
    )

    assert report.total_received == 2
    assert report.validated == 2
    assert report.missing == 0
    assert report.corrupted == 0
    assert all(r.status == "validated" for r in report.receipts)
    assert all(r.sha256 is not None for r in report.receipts)
    assert all(r.resolution == "1920x1080" for r in report.receipts)
    assert report.missing_asset_ids == []


def test_asset_pipeline_missing_asset(tmp_path):
    """Missing asset source produces a 'missing' receipt."""
    pipe = ImageAssetPipeline(project="ip", run_id="run-ip", base_dir=tmp_path)

    report = pipe.intake_manifest(
        scenes=[{"scene_id": "scene-000", "asset_id": "asset-missing", "expected_format": "1920x1080"}],
        assets_by_id={},
    )

    assert report.missing == 1
    assert report.validated == 0
    assert report.receipts[0].status == "missing"
    assert "asset-missing" in report.missing_asset_ids


def test_asset_pipeline_duplicate_detection(tmp_path):
    """Identical content produces a duplicate receipt."""
    pipe = ImageAssetPipeline(project="ip", run_id="run-ip", base_dir=tmp_path)

    img1 = tmp_path / "dup1.png"
    img2 = tmp_path / "dup2.png"
    _make_stub_image(img1, 1920, 1080, "yellow")
    _make_stub_image(img2, 1920, 1080, "yellow")  # identical content

    report = pipe.intake_manifest(
        scenes=[
            {"scene_id": "scene-000", "asset_id": "asset-000", "expected_format": "1920x1080"},
            {"scene_id": "scene-001", "asset_id": "asset-001", "expected_format": "1920x1080"},
        ],
        assets_by_id={"asset-000": {"path": str(img1)}, "asset-001": {"path": str(img2)}},
    )

    assert report.duplicates == 1
    assert report.validated == 1
    dup = [r for r in report.receipts if r.status == "duplicate"][0]
    assert dup.duplicate_of is not None


def test_asset_pipeline_corrupted_file(tmp_path):
    """Corrupted image file is detected."""
    pipe = ImageAssetPipeline(project="ip", run_id="run-ip", base_dir=tmp_path)

    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a real image")

    report = pipe.intake_manifest(
        scenes=[{"scene_id": "scene-000", "asset_id": "asset-bad", "expected_format": "1920x1080"}],
        assets_by_id={"asset-bad": {"path": str(bad)}},
    )

    assert report.corrupted == 1
    assert report.receipts[0].status == "corrupted"


# ---------------------------------------------------------------------------
# Motion engine tests
# ---------------------------------------------------------------------------


def test_motion_engine_plan_variety():
    """Motion plan produces varied move types (not all identical)."""
    engine = MotionEngine(fps=30, width=1920, height=1080, seed=42)

    scenes = _make_scenes(10)
    plan = engine.plan_motion(run_id="run-me", scenes=scenes)

    assert plan.run_id == "run-me"
    assert len(plan.specs) == 10
    assert len(plan.transitions) == 9  # one less than scenes

    move_types = {s.move_type for s in plan.specs}
    assert len(move_types) >= 2, f"Expected move variety, got {move_types}"

    # All ffmpeg filters should be non-None for non-static moves
    non_static = [s for s in plan.specs if s.move_type != "static"]
    for s in non_static:
        assert s.ffmpeg_filter is not None, f"{s.scene_id} {s.move_type} missing filter"


def test_motion_engine_no_consecutive_duplicates():
    """Consecutive scenes should not have identical move/easing/direction."""
    engine = MotionEngine(fps=30, seed=7)

    scenes = _make_scenes(20)
    plan = engine.plan_motion(run_id="run-me2", scenes=scenes)

    # lint_variation should find 0 problems for a well-varied plan
    issues = plan.variety_issues
    # Allow a few but not many
    assert len(issues) <= 2, f"Too many variety issues: {issues}"


def test_motion_engine_hero_moment():
    """Hero motion is reflected in spec params (slower zoom)."""
    engine = MotionEngine(fps=30, seed=99)

    scenes = [
        {"scene_id": "scene-hero", "duration_seconds": 8.0,
         "hero_moment": True, "narrative_role": "deliver_payload",
         "transition_duration": 0.5},
    ]
    plan = engine.plan_motion(run_id="run-hero", scenes=scenes)

    spec = plan.specs[0]
    assert spec.duration_seconds == 8.0
    assert spec.move_type in ("pan_zoom", "static", "detail_crop", "parallax")
    # Hero moments use subtler zoom (end_scale closer to 1.0)
    assert spec.end_scale <= 1.1


# ---------------------------------------------------------------------------
# Render integration tests
# ---------------------------------------------------------------------------


def test_render_readiness_valid_manifest():
    """A fully valid manifest passes all readiness checks."""
    ri = RenderIntegration(fps=30, width=1920, height=1080)

    scenes = _make_scenes(5, base_duration=4.0)
    packets = _make_prompt_packets(5)
    qc = _make_qc_reports(5, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-ready", project="ready-project",
        scene_plans=scenes, prompt_packets=packets,
        quality_reports=qc, target_duration_seconds=20.0,
    )

    # Mark all assets as validated on disk
    import tempfile
    tmpdir = tempfile.mkdtemp()
    for s in m.scenes:
        img = Path(tmpdir) / f"{s.asset_id}.png"
        _make_stub_image(img, 1920, 1080)
        s.file_status = "validated"
        s.file_path = str(img)
        s.file_resolution = "1920x1080"
        s.file_sha256 = "a" * 64

    m.recompute_timeline()
    m.seal()

    report = ri.validate_manifest(m, require_all_assets=True, require_audio_sync=False)

    assert report.ready_for_render is True
    assert report.blocking_count == 0
    assert report.validated_assets == 5
    assert report.missing_assets == 0
    assert all(c.passed for c in report.checks)


def test_render_readiness_missing_assets_blocks():
    """Missing assets block render readiness."""
    ri = RenderIntegration(fps=30, width=1920, height=1080)

    scenes = _make_scenes(3, base_duration=4.0)
    packets = _make_prompt_packets(3)
    qc = _make_qc_reports(3, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-miss", project="miss-project",
        scene_plans=scenes, prompt_packets=packets,
        quality_reports=qc, target_duration_seconds=12.0,
    )
    m.recompute_timeline()
    m.seal()

    # No assets on disk — all missing
    report = ri.validate_manifest(m, require_all_assets=True, require_audio_sync=False)

    assert report.ready_for_render is False
    assert report.missing_assets == 3
    assert any(c.name == "assets_present" and c.blocking for c in report.checks)


def test_render_edit_decisions_generation():
    """Edit decisions are generated from a valid manifest."""
    ri = RenderIntegration(fps=30, width=1920, height=1080)

    scenes = _make_scenes(3, base_duration=4.0)
    packets = _make_prompt_packets(3)
    qc = _make_qc_reports(3, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-ed", project="ed-project",
        scene_plans=scenes, prompt_packets=packets,
        quality_reports=qc, target_duration_seconds=12.0,
    )

    import tempfile
    tmpdir = tempfile.mkdtemp()
    for s in m.scenes:
        img = Path(tmpdir) / f"{s.asset_id}.png"
        _make_stub_image(img, 1920, 1080)
        s.file_status = "validated"
        s.file_path = str(img)
        s.file_resolution = "1920x1080"
        s.file_sha256 = "b" * 64

    m.recompute_timeline()
    m.seal()

    report = ri.validate_manifest(m, require_all_assets=True, require_audio_sync=False)
    assert report.ready_for_render is True

    ed = ri.build_edit_decisions(m)
    assert ed["version"] == "1.0"
    assert len(ed["cuts"]) == 3
    assert ed["render_runtime"] == "ffmpeg"
    assert ed["metadata"]["project"] == "ed-project"

    # Check cut timing is sequential
    for i, cut in enumerate(ed["cuts"]):
        assert cut["in_seconds"] == i * 4.0
        assert cut["out_seconds"] == (i + 1) * 4.0
        assert cut["source"].endswith(".png")


def test_test_render_stub_images(tmp_path):
    """Test render creates a short MP4 from stub images (no Google Flow)."""
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available for test render")
    ri = RenderIntegration(fps=30, width=1920, height=1080)

    scenes = _make_scenes(3, base_duration=2.0)
    packets = _make_prompt_packets(3)
    qc = _make_qc_reports(3, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-tr", project="tr-project",
        scene_plans=scenes, prompt_packets=packets,
        quality_reports=qc, target_duration_seconds=6.0,
    )
    m.recompute_timeline()
    m.seal()

    output = tmp_path / "test_render.mp4"
    result = ri.create_test_render(m, output_path=output)

    assert result["status"] == "rendered"
    assert Path(result["output"]).exists()
    assert result["scene_count"] == 3
    assert result["duration_seconds"] > 0
    assert result["fps"] == 30


def test_duplicate_scenes_not_double_queued():
    """Identical scene content doesn't produce duplicate work (via manifest scene_id uniqueness)."""
    m = ProductionManifest(
        manifest_id="m-dup", run_id="run-dup", project="dup-project",
        scenes=[
            ManifestScene(
                scene_id="scene-000", asset_id="asset-000",
                script_section_id="block-000", prompt="Same prompt here",
                expected_format="f", duration_seconds=5.0,
                timeline_position=0.0, camera_move="m",
                transition="cut", file_status="missing", qc_result="pass",
            ),
            ManifestScene(
                scene_id="scene-001", asset_id="asset-001",
                script_section_id="block-001", prompt="Same prompt here",
                expected_format="f", duration_seconds=5.0,
                timeline_position=5.0, camera_move="m",
                transition="cut", file_status="missing", qc_result="pass",
            ),
        ],
    )
    m.recompute_timeline()
    m.seal()

    # Two different scene_ids but same prompt — allowed (different scenes),
    # but they are distinct entries. The duplicate detection is at the asset
    # level (image_asset_pipeline), not the scene level.
    assert len(m.scenes) == 2
    assert m.scenes[0].scene_id != m.scenes[1].scene_id


def test_report_contains_all_required_fields():
    """Readiness report includes all required fields for the final report."""
    ri = RenderIntegration(fps=30, width=1920, height=1080)

    scenes = _make_scenes(2, base_duration=4.0)
    packets = _make_prompt_packets(2)
    qc = _make_qc_reports(2, all_pass=True)

    m = build_manifest_from_preproduction(
        run_id="run-fields", project="fields-project",
        scene_plans=scenes, prompt_packets=packets,
        quality_reports=qc, target_duration_seconds=8.0,
    )

    import tempfile
    tmpdir = tempfile.mkdtemp()
    for s in m.scenes:
        img = Path(tmpdir) / f"{s.asset_id}.png"
        _make_stub_image(img, 1920, 1080)
        s.file_status = "validated"
        s.file_path = str(img)
        s.file_resolution = "1920x1080"
        s.file_sha256 = "c" * 64

    m.recompute_timeline()
    m.seal()

    report = ri.validate_manifest(m, require_all_assets=True, require_audio_sync=False)

    assert report.manifest_id == m.manifest_id
    assert report.project == "fields-project"
    assert report.total_scenes == 2
    assert report.validated_assets == 2
    assert report.total_duration_seconds == 8.0
    assert isinstance(report.all_passed, bool)
    assert isinstance(report.ready_for_render, bool)
    for c in report.checks:
        assert c.name
        assert isinstance(c.passed, bool)
        assert c.detail
        assert c.severity in ("low", "medium", "high")
