"""Validate local video render identity with supported native FFmpeg producers."""

import hashlib
import json
import math
import shutil
import struct
import subprocess
import wave

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.enhancement.face_enhance import FaceEnhance
from tools.video.auto_reframe import AutoReframe
from tools.video.green_screen_composite import GreenScreenComposite
from tools.video.silence_cutter import SilenceCutter
from tools.video.video_stitch import VideoStitch
from tools.video.video_trimmer import VideoTrimmer


def ff(args):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args],
        capture_output=True,
        check=True,
        timeout=20,
    )


def inspect(path):
    p = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    j = json.loads(p.stdout)
    frame = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout
    return {
        "codec": next(
            s["codec_name"] for s in j["streams"] if s["codec_type"] == "video"
        ),
        "duration": float(j["format"]["duration"]),
        "frame": hashlib.sha256(frame).hexdigest(),
        "pixel": list(frame[:3]),
    }


@pytest.fixture
def media(tmp_path):
    root = tmp_path
    files = {}
    for color in ["red", "blue"]:
        p = root / (color + ".mp4")
        ff(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:size=96x48:rate=20:duration=1",
                "-c:v",
                "libx264",
                str(p),
            ]
        )
        files[color] = str(p)
    bands = root / "bands.mp4"
    ff(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=red:size=96x48:rate=20:duration=1",
            "-vf",
            "drawbox=x=48:y=0:w=48:h=48:color=blue:t=fill",
            "-c:v",
            "libx264",
            str(bands),
        ]
    )
    tracks = {}
    for name, freq in [("voice", 330), ("other", 880), ("silence", 440)]:
        p = root / (name + ".wav")
        tracks[name] = str(p)
        with wave.open(str(p), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(
                b"".join(
                    struct.pack(
                        "<h",
                        round(4000 * math.sin(2 * math.pi * freq * i / 16000))
                        if name != "silence" or i / 16000 < 0.2 or i / 16000 >= 0.8
                        else 0,
                    )
                    for i in range(16000)
                )
            )
    silent = root / "silent.mkv"
    ff(
        [
            "-i",
            files["red"],
            "-i",
            tracks["silence"],
            "-c:v",
            "copy",
            "-c:a",
            "pcm_s16le",
            str(silent),
        ]
    )
    faces = []
    for name, x in [("left", 0.05), ("right", 0.85)]:
        p = root / (name + ".json")
        p.write_text(
            json.dumps(
                {
                    "faces": [
                        {
                            "timestamp_seconds": 0,
                            "bbox": {"x": x, "y": 0.2, "width": 0.1, "height": 0.2},
                        }
                    ]
                }
            )
        )
        faces.append(str(p))
    cases = [
        (
            "concat",
            VideoTrimmer,
            {"operation": "concat", "segments": [{"input_path": files["red"]}]},
            {"operation": "concat", "segments": [{"input_path": files["blue"]}]},
        ),
        (
            "pip",
            VideoStitch,
            {
                "operation": "spatial",
                "layout": "picture_in_picture",
                "clips": [files["red"], files["blue"]],
                "pip_scale": 0.5,
                "pip_margin": 0,
                "pip_position": "top_left",
            },
            {
                "operation": "spatial",
                "layout": "picture_in_picture",
                "clips": [files["red"], files["blue"]],
                "pip_scale": 0.5,
                "pip_margin": 0,
                "pip_position": "bottom_right",
            },
        ),
        (
            "face_encode",
            FaceEnhance,
            {"input_path": files["red"], "custom_vf": "null", "codec": "libx264"},
            {"input_path": files["red"], "custom_vf": "null", "codec": "mpeg4"},
        ),
        (
            "reframe",
            AutoReframe,
            {
                "input_path": str(bands),
                "face_tracking_json": faces[0],
                "target_aspect": "square",
                "target_width": 48,
                "target_height": 48,
            },
            {
                "input_path": str(bands),
                "face_tracking_json": faces[1],
                "target_aspect": "square",
                "target_width": 48,
                "target_height": 48,
            },
        ),
        (
            "silence_speed",
            SilenceCutter,
            {
                "input_path": str(silent),
                "mode": "speed_up",
                "silence_threshold_db": -35,
                "min_silence_duration": 0.1,
                "padding_seconds": 0,
                "silence_speed_factor": 2,
            },
            {
                "input_path": str(silent),
                "mode": "speed_up",
                "silence_threshold_db": -35,
                "min_silence_duration": 0.1,
                "padding_seconds": 0,
                "silence_speed_factor": 4,
            },
        ),
        (
            "composite_audio",
            GreenScreenComposite,
            {
                "speaker_path": files["red"],
                "background_path": files["blue"],
                "original_audio_path": tracks["voice"],
                "bg_shift_up": 0,
            },
            {
                "speaker_path": files["red"],
                "background_path": files["blue"],
                "original_audio_path": tracks["other"],
                "bg_shift_up": 0,
            },
        ),
    ]
    return cases


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Native FFmpeg required",
)
@pytest.mark.parametrize(
    "case",
    ["concat", "pip", "face_encode", "reframe", "silence_speed", "composite_audio"],
)
def test_actual_video_rendering_inputs_change_cached_artifact(
    media, tmp_path, monkeypatch, case
):
    _, cls, first, second = next(c for c in media if c[0] == case)
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_MAX_GB", "0.01")
    reset_default_asset_cache()
    tool = cls()
    rows, paths = [], []
    try:
        for name, inputs, enabled in [
            ("first", first, True),
            ("second", second, True),
            ("reference", second, False),
            ("repeat", second, True),
        ]:
            monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1" if enabled else "0")
            path = tmp_path / (name + (".mkv" if case == "face_encode" else ".mp4"))
            result = tool.execute({**inputs, "output_path": str(path)})
            assert result.success, result.error
            summary = inspect(path)
            summary["cached"] = result.from_cache
            if case == "composite_audio":
                pcm = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(path),
                        "-map",
                        "0:a:0",
                        "-f",
                        "s16le",
                        "-c:a",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                    timeout=10,
                ).stdout
                summary["audio"] = hashlib.sha256(pcm[3200:12800]).hexdigest()
            rows.append(summary)
            paths.append(path)
        field = (
            "codec"
            if case == "face_encode"
            else "duration"
            if case == "silence_speed"
            else "audio"
            if case == "composite_audio"
            else "frame"
        )
        # The native cache-disabled second request is an independent header,
        # decoded-image/audio or duration oracle, not a guessed cache key.
        assert rows[0][field] != rows[2][field]
        if case == "face_encode":
            assert rows[0][field] == "h264" and rows[2][field] == "mpeg4"
        elif case == "silence_speed":
            assert rows[2][field] < rows[0][field] - 0.1
        elif case in ("concat", "reframe"):
            assert rows[0]["pixel"][0] > 200 and rows[2]["pixel"][2] > 200
        elif case == "pip":
            assert rows[0]["pixel"][2] > 200 and rows[2]["pixel"][0] > 200
        assert rows[1][field] == rows[2][field]
        assert [r["cached"] for r in rows] == [False, False, False, True]
        assert paths[3].read_bytes() == paths[1].read_bytes()
    finally:
        reset_default_asset_cache()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Native FFmpeg required",
)
def test_scene_analysis_cache_tracks_requested_minimum_length(tmp_path, monkeypatch):
    from tools.analysis.scene_detect import SceneDetect

    source = tmp_path / "cuts.mp4"
    ff(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=black:size=32x32:rate=10:duration=3",
            "-vf",
            "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='between(t,1,1.99)'",
            "-c:v",
            "libx264",
            str(source),
        ]
    )
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_MAX_GB", "0.01")
    reset_default_asset_cache()
    rows, paths, flags = [], [], []
    try:
        tool = SceneDetect()
        for name, minimum, enabled in [
            ("first", 1, True),
            ("changed", 1.5, True),
            ("reference", 1.5, False),
            ("repeat", 1.5, True),
        ]:
            monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1" if enabled else "0")
            path = tmp_path / f"{name}.json"
            result = tool.execute(
                {
                    "input_path": str(source),
                    "min_scene_length_seconds": minimum,
                    "output_path": str(path),
                }
            )
            assert result.success, result.error
            rows.append(json.loads(path.read_text(encoding="utf-8")))
            paths.append(path)
            flags.append(result.from_cache)
        # Physical cuts at1s/2s: the second minimum excludes the first cut.
        # Read the produced JSON, independently of the key or cached metadata.
        assert len(rows[0]["scenes"]) == 3
        assert len(rows[2]["scenes"]) == 2
        assert rows[1] == rows[2] != rows[0]
        assert flags == [False, False, False, True]
        assert paths[3].read_bytes() == paths[1].read_bytes()
    finally:
        reset_default_asset_cache()
