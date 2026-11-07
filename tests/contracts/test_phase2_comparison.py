"""Phase 2 side-by-side comparison: Phase 1 vs Phase 2 enhanced output.

Runs the talking-head compose handler twice — once with enhance=False
(Phase 1 baseline) and once with enhance=True (Phase 2 enhanced) —
then asserts both outputs exist and reports file size / duration for
manual comparison.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FOOTAGE = Path(
    r"C:\Users\ishan\Documents\SocialMedia\IshanAIVideos\pipeline\2026-03-08\seg1_intro.mp4"
)


def _has_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


def _get_file_size_mb(path: str) -> float:
    return Path(path).stat().st_size / (1024 * 1024)


@pytest.fixture(scope="module")
def comparison_outputs(tmp_path_factory):
    """Run compose handler twice: baseline and enhanced."""
    if not FOOTAGE.exists():
        pytest.skip("Test footage not available")
    if not _has_ffmpeg():
        pytest.skip("FFmpeg not available")

    from tools.video.video_compose import VideoCompose
    from tools.enhancement.face_enhance import FaceEnhance
    from tools.enhancement.color_grade import ColorGrade
    from tools.audio.audio_enhance import AudioEnhance

    tmp = tmp_path_factory.mktemp("comparison")
    results = {}

    # Phase 1 baseline: just encode
    composer = VideoCompose()
    baseline_path = str(tmp / "phase1_baseline.mp4")
    r = composer.execute({
        "operation": "encode",
        "input_path": str(FOOTAGE),
        "output_path": baseline_path,
        "codec": "libx264",
        "crf": 20,
    })
    assert r.success, f"Baseline encode failed: {r.error}"
    results["baseline"] = baseline_path

    # Phase 2 enhanced: face -> color -> audio
    current = str(FOOTAGE)
    enhancements = []

    face = FaceEnhance()
    face_out = str(tmp / "step_face.mp4")
    r = face.execute({
        "input_path": current,
        "output_path": face_out,
        "presets": ["talking_head_standard"],
    })
    if r.success:
        current = r.data["output"]
        enhancements.append("face_enhance:talking_head_standard")

    color = ColorGrade()
    color_out = str(tmp / "step_color.mp4")
    r = color.execute({
        "input_path": current,
        "output_path": color_out,
        "profile": "cinematic_warm",
        "intensity": 0.85,
    })
    if r.success:
        current = r.data["output"]
        enhancements.append("color_grade:cinematic_warm@0.85")

    audio = AudioEnhance()
    audio_out = str(tmp / "step_audio.mp4")
    r = audio.execute({
        "input_path": current,
        "output_path": audio_out,
        "preset": "clean_speech",
    })
    if r.success:
        current = r.data["output"]
        enhancements.append("audio_enhance:clean_speech")

    # Final encode
    enhanced_path = str(tmp / "phase2_enhanced.mp4")
    r = composer.execute({
        "operation": "encode",
        "input_path": current,
        "output_path": enhanced_path,
        "codec": "libx264",
        "crf": 20,
    })
    assert r.success, f"Enhanced encode failed: {r.error}"
    results["enhanced"] = enhanced_path
    results["enhancements"] = enhancements

    return results


class TestPhase2Comparison:
    def test_baseline_exists(self, comparison_outputs):
        assert Path(comparison_outputs["baseline"]).exists()

    def test_enhanced_exists(self, comparison_outputs):
        assert Path(comparison_outputs["enhanced"]).exists()

    def test_both_have_valid_duration(self, comparison_outputs):
        base_dur = _get_duration(comparison_outputs["baseline"])
        enh_dur = _get_duration(comparison_outputs["enhanced"])
        assert base_dur > 0
        assert enh_dur > 0
        # Durations should be within 1 second of each other
        assert abs(base_dur - enh_dur) < 1.0, (
            f"Duration mismatch: baseline={base_dur:.1f}s, enhanced={enh_dur:.1f}s"
        )

    def test_enhancements_were_applied(self, comparison_outputs):
        enhancements = comparison_outputs["enhancements"]
        assert len(enhancements) > 0, "No enhancements were applied"

    def test_report(self, comparison_outputs):
        """Print comparison report for manual review."""
        baseline = comparison_outputs["baseline"]
        enhanced = comparison_outputs["enhanced"]

        base_size = _get_file_size_mb(baseline)
        enh_size = _get_file_size_mb(enhanced)
        base_dur = _get_duration(baseline)
        enh_dur = _get_duration(enhanced)
        enhancements = comparison_outputs["enhancements"]

        report = (
            f"\n{'='*60}\n"
            f"  Phase 1 vs Phase 2 Comparison\n"
            f"{'='*60}\n"
            f"  Baseline:  {base_size:.2f} MB, {base_dur:.1f}s\n"
            f"  Enhanced:  {enh_size:.2f} MB, {enh_dur:.1f}s\n"
            f"  Enhancements: {', '.join(enhancements)}\n"
            f"  Baseline path:  {baseline}\n"
            f"  Enhanced path:  {enhanced}\n"
            f"{'='*60}\n"
        )
        print(report)
        # Always passes — this test is for reporting
        assert True
