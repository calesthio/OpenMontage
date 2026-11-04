"""Regression tests for source_media_review against real media files.

The existing empty-input tests (test_source_media_review_empty.py) never
reach the real-media path in _probe_video(). That gap hid four contract
defects in how the review talks to the analysis tools:

1. frame_sampler was called without the required "strategy" input
2. the frame list was read from "frame_paths", a key that tool never returns
3. frame objects were passed through where the schema wants path strings
4. audio_probe's nested, audio-only output left every video summarised as
   "unknown resolution, without audio"
5. every video wrote its frames into one shared directory, so each clip
   overwrote the previous one's frames

(2) and (4) still produced schema-valid output -- an empty array and the
string "unknown" -- so nothing ever raised. These tests build tiny real
videos and assert the review is both accurate and schema-valid.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.source_media_review import review_source_media  # noqa: E402
from schemas.artifacts import validate_artifact  # noqa: E402


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe are required to build and probe the fixture video",
)


@pytest.fixture
def sample_video(tmp_path):
    """A 2s 320x240 clip carrying an AAC audio track."""
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-y", str(path),
        ],
        check=True,
    )
    return path


def _single_entry(path):
    artifact = review_source_media([path], {"pipeline_type": "hybrid"})
    assert len(artifact["files"]) == 1, artifact["summary"]
    return artifact["files"][0]


def test_video_probe_reports_resolution_and_audio(sample_video):
    """A video with a real audio track must not be reported as mute."""
    entry = _single_entry(sample_video)
    probe = entry["technical_probe"]

    assert probe["resolution"] == "320x240"
    assert probe["fps"] == pytest.approx(15.0, abs=0.1)
    assert probe["audio_codec"] == "aac"

    assert "with audio" in entry["content_summary"]
    assert "unknown" not in entry["content_summary"]


def test_video_probe_extracts_representative_frame_paths(sample_video):
    """Frames must be extracted, and unwrapped to path strings."""
    entry = _single_entry(sample_video)

    frames = entry["representative_frames"]
    assert len(frames) == 4
    assert all(isinstance(frame, str) for frame in frames)
    assert all(Path(frame).exists() for frame in frames)


def test_review_with_real_video_is_schema_valid(sample_video):
    """The artifact must survive validation once it carries real data."""
    artifact = review_source_media([sample_video], {"pipeline_type": "hybrid"})

    # Raises jsonschema.ValidationError on mismatch.
    validate_artifact("source_media_review", artifact)


def _make_solid_video(tmp_path, name, color):
    """A 2s single-colour clip, so two clips are distinguishable files."""
    path = tmp_path / name
    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x240:d=2:r=15",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(path),
        ],
        check=True,
    )
    return path


def test_multiple_videos_do_not_share_frame_directory(tmp_path):
    """Regression: the frame output dir was shared, so with several clips
    each one overwrote the previous one's frames and every entry ended up
    pointing at the last clip's frame_NNNN.jpg set.
    """
    clip_a = _make_solid_video(tmp_path, "a.mp4", "red")
    clip_b = _make_solid_video(tmp_path, "b.mp4", "blue")

    artifact = review_source_media([clip_a, clip_b], {"pipeline_type": "hybrid"})
    entries = {Path(e["path"]).name: e for e in artifact["files"]}

    frames_a = set(entries["a.mp4"]["representative_frames"])
    frames_b = set(entries["b.mp4"]["representative_frames"])

    assert frames_a, "clip a produced no representative frames"
    assert frames_b, "clip b produced no representative frames"
    assert frames_a.isdisjoint(frames_b), (
        "frames overlap between clips -- the output directory is shared: "
        f"{sorted(frames_a & frames_b)}"
    )
