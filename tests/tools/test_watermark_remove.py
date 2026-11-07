"""Synthesise two clips that share one white box and nothing else, then check
that detect finds the box and delogo flattens it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.video.watermark_remove import WatermarkRemove

W, H = 320, 240
BOX = {"x": 250, "y": 200, "w": 40, "h": 20}


def _make_clip(path: Path, seed: int) -> None:
    """Two seconds of noise with a fixed white box burned into a corner.

    Noise, not testsrc: a test pattern has bright features in the same place in
    every clip, which is exactly what the detector is looking for.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=gray:size={W}x{H}:rate=25:duration=2",
            "-vf", f"noise=alls=45:allf=t+u:all_seed={seed},"
                   f"drawbox=x={BOX['x']}:y={BOX['y']}:w={BOX['w']}:h={BOX['h']}"
                   ":color=white@0.9:t=fill",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
    )


def _frame(path: Path, at: float) -> np.ndarray:
    png = path.with_suffix(".png")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", str(path),
         "-frames:v", "1", str(png)],
        check=True,
    )
    return np.asarray(Image.open(png).convert("L"), dtype=float)


@pytest.fixture()
def clips(tmp_path: Path) -> list[Path]:
    paths = []
    for name, seed in [("a.mp4", 11), ("b.mp4", 977)]:
        p = tmp_path / name
        _make_clip(p, seed)
        paths.append(p)
    return paths


def test_detect_finds_the_shared_box(clips: list[Path]) -> None:
    res = WatermarkRemove().execute(
        {"operation": "detect", "input_paths": [str(p) for p in clips]}
    )
    assert res.success, res.error
    region = res.data["region"]
    # The detected box must cover the drawn one; encoder ringing can spread it.
    assert region["x"] <= BOX["x"] and region["y"] <= BOX["y"]
    assert region["x"] + region["w"] >= BOX["x"] + BOX["w"]
    assert region["y"] + region["h"] >= BOX["y"] + BOX["h"]
    assert res.data["looks_like_watermark"]


def test_detect_refuses_a_single_clip(clips: list[Path]) -> None:
    res = WatermarkRemove().execute(
        {"operation": "detect", "input_paths": [str(clips[0])]}
    )
    assert not res.success
    assert "at least two clips" in res.error


def test_delogo_flattens_the_box(clips: list[Path], tmp_path: Path) -> None:
    src = clips[0]
    out = tmp_path / "clean.mp4"
    res = WatermarkRemove().execute({
        "operation": "remove", "input_path": str(src), "output_path": str(out),
        "method": "delogo", "region": BOX, "pad": 2,
    })
    assert res.success, res.error
    assert out.is_file()

    sl = (slice(BOX["y"], BOX["y"] + BOX["h"]), slice(BOX["x"], BOX["x"] + BOX["w"]))
    before = _frame(src, 1.0)[sl].mean()
    after = _frame(out, 1.0)[sl].mean()
    # The box was near-white; interpolation must pull it down toward the scene.
    assert before > 200
    assert after < before - 40
