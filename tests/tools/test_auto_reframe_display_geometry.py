"""Native anamorphic framing must preserve display geometry and subject pixels."""

import json
import shutil
import subprocess
from fractions import Fraction

import pytest

from tools.video.auto_reframe import AutoReframe

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)


def run(command):
    return subprocess.run(command, check=True, capture_output=True, timeout=10).stdout


@pytest.mark.parametrize(
    "sar,width,height,crop,tracking",
    [
        ("2:1", 48, 64, "24:64:36:0", "none"),
        ("1:2", 48, 48, "96:48:0:8", "none"),
        ("1:2", 48, 64, "96:64:0:0", "none"),
        ("2:1", 48, 64, "24:64:36:0", "stable"),
        ("2:1", 48, 64, "24:64:36:0", "short_trajectory"),
        ("1:1", 48, 48, "64:64:16:0", "none"),
    ],
)
def test_actual_reframe_matches_independent_display_crop(
    tmp_path, sar, width, height, crop, tracking
):
    source = tmp_path / "source.mp4"
    output = tmp_path / "framed.mp4"
    oracle = tmp_path / "oracle.mp4"
    faces = tmp_path / "tracking.json"
    centers = {"none": [], "stable": [0.5], "short_trajectory": [0.25, 0.75]}[tracking]
    faces.write_text(
        json.dumps(
            {
                "faces": [
                    {
                        "timestamp_seconds": i / 4,
                        "bbox": {
                            "x": center - 0.05,
                            "y": 0.4,
                            "width": 0.1,
                            "height": 0.2,
                        },
                    }
                    for i, center in enumerate(centers)
                ]
            }
        ),
        encoding="utf-8",
    )
    # A central stripe distinguishes correct display-space crop from merely
    # stamping square pixels on the existing, too-wide encoded-pixel crop.
    sar_expression = sar.replace(":", "/")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=96x64:r=4:d=0.5",
            "-vf",
            f"drawbox=x=36:y=0:w=24:h=64:color=lime:t=fill,setsar={sar_expression}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ]
    )
    source_stream = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=sample_aspect_ratio",
                "-of",
                "json",
                str(source),
            ]
        )
    )["streams"][0]
    assert Fraction(source_stream["sample_aspect_ratio"].replace(":", "/")) == Fraction(
        sar_expression
    )
    result = AutoReframe().execute(
        {
            "input_path": str(source),
            "output_path": str(output),
            "target_width": width,
            "target_height": height,
            "face_tracking_json": str(faces),
            "smoothing_window": 1,
        }
    )
    assert result.success, result.error
    assert result.artifacts == [str(output)]
    stream = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,sample_aspect_ratio,display_aspect_ratio",
                "-of",
                "json",
                str(output),
            ]
        )
    )["streams"][0]
    assert (stream["width"], stream["height"]) == (width, height)
    assert Fraction(stream["sample_aspect_ratio"].replace(":", "/")) == 1
    assert Fraction(stream["display_aspect_ratio"].replace(":", "/")) == Fraction(
        width, height
    )
    # Hand-derived crops: width/height in encoded coordinates must equal the
    # requested display ratio divided by source SAR; positions are centered.
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"crop={crop},scale={width}:{height},setsar=1",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            str(oracle),
        ]
    )
    decode = ["ffmpeg", "-v", "error", "-i"]
    suffix = ["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    assert run(decode + [str(output)] + suffix) == run(decode + [str(oracle)] + suffix)


def test_old_version_cache_is_missed_then_new_render_is_reused(tmp_path, monkeypatch):
    from lib.asset_cache import get_default_asset_cache, reset_default_asset_cache

    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    reset_default_asset_cache()
    try:
        source = tmp_path / "source.mp4"
        legacy = tmp_path / "legacy.mp4"
        output = tmp_path / "correct.mp4"
        repeat = tmp_path / "repeat.mp4"
        oracle = tmp_path / "oracle.mp4"
        faces = tmp_path / "faces.json"
        faces.write_text('{"faces": []}', encoding="utf-8")
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=black:s=96x64:r=4:d=0.5",
                "-vf",
                "drawbox=x=36:y=0:w=24:h=64:color=lime:t=fill,setsar=2/1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ]
        )
        # Portable compatibility fixture: the previous encoded-pixel crop and
        # previous version's real cache identity, without requiring git history.
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-vf",
                "crop=48:64:24:0,scale=48:64",
                "-c:v",
                "libx264",
                str(legacy),
            ]
        )
        inputs = {
            "input_path": str(source),
            "output_path": str(output),
            "target_width": 48,
            "target_height": 64,
            "face_tracking_json": str(faces),
            "smoothing_window": 1,
        }
        old_identity = AutoReframe()
        old_identity.version = "0.1.0"
        assert get_default_asset_cache().store(
            old_identity.cache_key(inputs),
            legacy,
            tool_name=old_identity.name,
            tool_version="0.1.0",
            data={"output": str(legacy)},
        )
        result = AutoReframe().execute(inputs)
        assert result.success, result.error
        assert not result.data.get("cached", False)
        stream = json.loads(
            run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=sample_aspect_ratio,display_aspect_ratio",
                    "-of",
                    "json",
                    str(output),
                ]
            )
        )["streams"][0]
        assert stream["sample_aspect_ratio"] == "1:1"
        assert stream["display_aspect_ratio"] == "3:4"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-vf",
                "crop=24:64:36:0,scale=48:64,setsar=1",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "fast",
                str(oracle),
            ]
        )
        suffix = ["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        assert run(["ffmpeg", "-v", "error", "-i", str(output)] + suffix) == run(
            ["ffmpeg", "-v", "error", "-i", str(oracle)] + suffix
        )
        repeated = AutoReframe().execute(dict(inputs, output_path=str(repeat)))
        assert repeated.success and repeated.data["cached"]
        assert repeat.read_bytes() == output.read_bytes()
        assert legacy.exists()
    finally:
        reset_default_asset_cache()
