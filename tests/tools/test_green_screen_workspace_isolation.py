"""Parallel native chromakey calls own their frame workspace and cleanup."""

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest

import tools.video.green_screen_processor as producer


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_same_second_native_scene_calls_have_independent_workspaces(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    monkeypatch.setattr(
        producer, "time", SimpleNamespace(time=lambda: 1_700_000_000.25)
    )
    sources = []
    for color in ("red", "blue"):
        source = tmp_path / f"{color}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=64x48:r=2:d=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ],
            check=True,
            timeout=10,
        )
        sources.append(source)
    barrier, lock, observed = Barrier(2), Lock(), []
    real_extract = producer.GreenScreenProcessor._extract_frames

    def extract(self, input_path, frames_dir, *args):
        with lock:
            observed.append(frames_dir.parent)
        barrier.wait(timeout=5)
        return real_extract(self, input_path, frames_dir, *args)

    monkeypatch.setattr(producer.GreenScreenProcessor, "_extract_frames", extract)
    outputs = [tmp_path / "red-keyed.mp4", tmp_path / "blue-keyed.mp4"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                producer.GreenScreenProcessor().execute,
                {
                    "input_path": str(source),
                    "output_path": str(output),
                    "method": "chromakey",
                    "fps": 2,
                    "bg_color": "#0E172A",
                },
            )
            for source, output in zip(sources, outputs)
        ]
        results = [future.result(timeout=20) for future in futures]
    assert (
        len(set(observed)) == 2
    ), "Same-second calls share and delete one frame workspace"
    assert all(result.success for result in results), [
        result.error for result in results
    ]
    for output, expected_channel in zip(outputs, (0, 2)):
        frame = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
            timeout=10,
        ).stdout
        totals = [sum(frame[channel::3]) for channel in range(3)]
        assert totals[expected_channel] > 2 * max(
            totals[channel] for channel in range(3) if channel != expected_channel
        )
    assert all(not path.exists() for path in observed)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_same_second_native_detection_has_private_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(
        producer, "time", SimpleNamespace(time=lambda: 1_700_000_000.25)
    )
    source = tmp_path / "red.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x48:r=2:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        timeout=10,
    )
    real_run = producer.GreenScreenProcessor.run_command
    barrier, lock, observed = Barrier(2), Lock(), []

    def run(self, cmd, *args, **kwargs):
        if str(cmd[-1]).endswith("sample_0.png"):
            from pathlib import Path

            with lock:
                observed.append(Path(cmd[-1]).parent)
            barrier.wait(timeout=5)
        return real_run(self, cmd, *args, **kwargs)

    monkeypatch.setattr(producer.GreenScreenProcessor, "run_command", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                producer.GreenScreenProcessor()._auto_detect_method, source, 1.0, 64, 48
            )
            for _ in range(2)
        ]
        methods = [future.result(timeout=20) for future in futures]
    assert len(set(observed)) == 2
    assert methods == ["rembg", "rembg"]  # Detection only; no model is loaded or run.
    assert all(not path.exists() for path in observed)
