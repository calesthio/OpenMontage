"""Parallel forced-FFmpeg captions own their temporary subtitle files."""

import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
import tools.video.remotion_caption_burn as producer


def _source(tmp_path):
    source = tmp_path / "source.mp4"
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
            "color=c=black:s=320x240:r=2:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        timeout=10,
    )
    return source


def _request(source, output, word):
    return {
        "input_path": str(source),
        "output_path": str(output),
        "force_ffmpeg": True,
        "segments": [{"start": 0, "end": 1, "text": word}],
    }


def _pixels(path):
    return subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
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


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_same_second_native_caption_calls_have_private_subtitles(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    monkeypatch.setattr(
        producer, "time", SimpleNamespace(time=lambda: 1_700_000_000.25)
    )
    source = _source(tmp_path)
    real_run = producer.RemotionCaptionBurn.run_command
    barrier, lock, observed = Barrier(2), Lock(), []

    def run(self, cmd, *args, **kwargs):
        if "-vf" in cmd:
            subtitle = Path(
                re.search(r"subtitles='([^']+)'", cmd[cmd.index("-vf") + 1])[1]
            )
            with lock:
                observed.append(subtitle)
            barrier.wait(timeout=5)
        return real_run(self, cmd, *args, **kwargs)

    monkeypatch.setattr(producer.RemotionCaptionBurn, "run_command", run)
    outputs = [tmp_path / "alpha.mp4", tmp_path / "beta.mp4"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                producer.RemotionCaptionBurn().execute, _request(source, output, word)
            )
            for output, word in zip(outputs, ("ALPHA", "BETA"))
        ]
        results = [future.result(timeout=20) for future in futures]
    assert len(set(observed)) == 2
    assert all(result.success for result in results), [
        result.error for result in results
    ]
    monkeypatch.setattr(producer.RemotionCaptionBurn, "run_command", real_run)
    for output, word in zip(outputs, ("ALPHA", "BETA")):
        oracle = tmp_path / f"oracle-{word}.mp4"
        result = producer.RemotionCaptionBurn().execute(_request(source, oracle, word))
        assert result.success, result.error
        assert _pixels(output) == _pixels(oracle)
    assert _pixels(outputs[0]) != _pixels(outputs[1])
    assert all(not path.exists() for path in observed)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_native_encoder_failure_cleans_only_owned_subtitle(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    source = _source(tmp_path)
    sentinel = tmp_path / "_tmp_captions_other.srt"
    sentinel.write_text("An unrelated render owns this file", encoding="utf-8")
    real_run = producer.RemotionCaptionBurn.run_command
    observed = []

    def run(self, cmd, *args, **kwargs):
        subtitle = Path(re.search(r"subtitles='([^']+)'", cmd[cmd.index("-vf") + 1])[1])
        observed.append(subtitle)
        modified = list(cmd)
        modified[modified.index("-c:v") + 1] = "missing_encoder_fixture"
        return real_run(self, modified, *args, **kwargs)

    monkeypatch.setattr(producer.RemotionCaptionBurn, "run_command", run)
    with pytest.raises(subprocess.CalledProcessError):
        producer.RemotionCaptionBurn().execute(
            _request(source, tmp_path / "failed.mp4", "ALPHA")
        )
    assert len(observed) == 1
    assert not observed[0].exists()
    assert sentinel.read_text(encoding="utf-8") == "An unrelated render owns this file"
