"""Deterministic tests for the strobing-stills detector in `comfyui_video`.

`ComfyUIVideo._assess_coherence()` is the only check that can catch #526: a
workflow whose latent is an image latent emits N unrelated stills, and the
resulting mp4 has the right frame count, duration, codec and a clean ffprobe.
Nothing structural separates it from a real render — only the relationship
between consecutive frames does.

Because the verdict can flip a user-visible `success=True` to `success=False`,
the threshold cannot rest on measurements taken once by hand. These tests pin
the behaviour against synthetic frame buffers fed through a mocked ffmpeg, so
every branch is checked without a GPU, a server, or a real video file:

- coherent motion is not condemned,
- strobing stills are caught,
- a *high-motion* clip that is not strobing is not condemned (the false
  positive that would matter most — an action shot failing to render),
- and every way the check can fail to run returns None rather than a verdict,
  because a diagnostic that cannot run must never fail a good render.

The frame buffers are built with seeded generators, so the numbers below are
reproducible: the assertions compare against the thresholds in the
implementation, not against magic constants recorded from one run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from tools.video.comfyui_video import ComfyUIVideo

# Must match the decode size in `_assess_coherence`; the mocked ffmpeg has to
# hand back a buffer the reshape can consume.
W, H = 104, 60


# ------------------------------------------------------------------
# Synthetic clips
# ------------------------------------------------------------------

def _coherent_motion(n: int = 24) -> np.ndarray:
    """A gradient panning across frame — small, smoothly varying differences."""
    yy, xx = np.mgrid[0:H, 0 : W * 3]
    base = ((np.sin(xx / 9.0) * 0.5 + 0.5) * 180 + (yy / H) * 60).astype(np.uint8)
    rng = np.random.default_rng(7)
    starts = np.cumsum(rng.integers(1, 4, size=n))
    return np.stack([base[:, s : s + W] for s in starts])


def _strobing_stills(n: int = 24) -> np.ndarray:
    """Independent frames — every adjacent pair is equally unrelated."""
    return np.random.default_rng(3).integers(0, 256, size=(n, H, W), dtype=np.uint8)


def _high_motion_cuts(n: int = 24) -> np.ndarray:
    """Hard cuts between holds: differences are large *and* wildly uneven.

    This is the shape that a naive "big frame deltas means strobing" rule gets
    wrong. The mean adjacent difference clears the strobing threshold, but the
    variation does not, because most pairs are static and a few are total.
    """
    frames = []
    value = 20
    for i in range(n):
        if i % 4 == 0:
            value = 20 if value > 128 else 235
        frames.append(np.full((H, W), value, np.uint8))
    return np.stack(frames)


def _raw(frames: np.ndarray) -> bytes:
    return frames.astype(np.uint8).tobytes()


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    """Replace the ffmpeg decode with a canned rawvideo buffer."""

    def _install(stdout: bytes, returncode: int = 0):
        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=b"")

        monkeypatch.setattr(subprocess, "run", _run)
        return calls

    return _install


# ------------------------------------------------------------------
# Verdicts
# ------------------------------------------------------------------

def test_coherent_motion_is_not_condemned(fake_ffmpeg, tmp_path):
    fake_ffmpeg(_raw(_coherent_motion()))

    report = ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4")

    assert report is not None
    assert report["verdict"] == "COHERENT_MOTION"
    assert report["frames_analyzed"] == 24
    assert report["mean_abs_diff"] <= 25.0


def test_strobing_stills_are_caught(fake_ffmpeg, tmp_path):
    """The #526 signature: a large mean difference that barely varies."""
    fake_ffmpeg(_raw(_strobing_stills()))

    report = ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4")

    assert report is not None
    assert report["verdict"] == "STROBING_STILLS"
    assert report["mean_abs_diff"] > 25.0
    assert report["cv"] < 0.35


def test_high_motion_clip_is_not_a_false_positive(fake_ffmpeg, tmp_path):
    """Both conditions must hold, so a busy clip survives.

    Large differences alone are not the signal. Here the mean is far above the
    threshold and the clip is still ruled coherent, because the differences are
    uneven — which is what separates real cuts from independent stills.
    """
    fake_ffmpeg(_raw(_high_motion_cuts()))

    report = ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4")

    assert report is not None
    assert report["mean_abs_diff"] > 25.0, "premise: this clip really is high-motion"
    assert report["cv"] >= 0.35
    assert report["verdict"] == "COHERENT_MOTION"


def test_static_clip_is_coherent(fake_ffmpeg, tmp_path):
    """Identical frames give a zero mean, which must not divide by zero."""
    fake_ffmpeg(_raw(np.full((24, H, W), 128, np.uint8)))

    report = ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4")

    assert report is not None
    assert report["mean_abs_diff"] == 0.0
    assert report["cv"] == 0.0
    assert report["verdict"] == "COHERENT_MOTION"


def test_ffmpeg_is_asked_for_the_size_the_reshape_expects(fake_ffmpeg, tmp_path):
    """The decode geometry and the buffer geometry are one contract."""
    calls = fake_ffmpeg(_raw(_coherent_motion()))

    ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4")

    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "ffmpeg"
    assert f"scale={W}:{H},format=gray" in cmd
    assert "rawvideo" in cmd


# ------------------------------------------------------------------
# Every way the check can fail to run
# ------------------------------------------------------------------

def test_missing_ffmpeg_returns_no_verdict(monkeypatch, tmp_path):
    """No decoder is not evidence of a bad render."""

    def _boom(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(subprocess, "run", _boom)

    assert ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4") is None


def test_decode_timeout_returns_no_verdict(monkeypatch, tmp_path):
    def _boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(subprocess, "run", _boom)

    assert ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4") is None


def test_decode_failure_returns_no_verdict(fake_ffmpeg, tmp_path):
    """ffmpeg ran, ffmpeg failed: empty stdout, no frames, no verdict."""
    fake_ffmpeg(b"", returncode=1)

    assert ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4") is None


def test_too_few_frames_returns_no_verdict(fake_ffmpeg, tmp_path):
    """Two frames give a single difference — a distribution of one says nothing."""
    fake_ffmpeg(_raw(_coherent_motion(n=2)))

    assert ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4") is None


def test_missing_numpy_returns_no_verdict(monkeypatch, fake_ffmpeg, tmp_path):
    """numpy is not a hard dependency of the tool; absence must be silent."""
    fake_ffmpeg(_raw(_strobing_stills()))
    monkeypatch.setitem(sys.modules, "numpy", None)

    assert ComfyUIVideo._assess_coherence(tmp_path / "clip.mp4") is None


# ------------------------------------------------------------------
# The execute() failure path
# ------------------------------------------------------------------

class _StubClient:
    """Enough of ComfyUIClient to reach the coherence check offline."""

    def __init__(self, produced: Path):
        self._produced = produced

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:  # pragma: no cover - not reached
        return "unavailable"

    def check_models(self, required):
        return list(required), []

    def has_node(self, node_class: str) -> bool:
        return True

    def generate(self, workflow, **kwargs):
        return [self._produced]


def _t2v_tool(tmp_path: Path) -> tuple[ComfyUIVideo, Path]:
    produced = tmp_path / "out.mp4"
    produced.write_bytes(b"not really an mp4")
    tool = ComfyUIVideo()
    tool._client = _StubClient(produced)
    return tool, produced


def _t2v_inputs(produced: Path) -> dict:
    return {
        "prompt": "a slow dolly through a forest",
        "operation": "text_to_video",
        "output_path": str(produced),
        "seed": 42,
    }


def test_execute_fails_when_the_render_is_strobing_stills(fake_ffmpeg, tmp_path):
    """A structurally valid file that strobes must not report success.

    This is the whole point of the check: before it, `comfyui_video` returned
    `success=True` for the #526 output because every structural signal was
    fine. The failure has to name the cause -- an image latent where a temporal
    one belongs -- or the user is left debugging the encoder.
    """
    tool, produced = _t2v_tool(tmp_path)
    fake_ffmpeg(_raw(_strobing_stills()))

    result = tool.execute(_t2v_inputs(produced))

    assert result.success is False
    assert "unrelated stills" in result.error
    assert "latent" in result.error
    assert result.data["coherence"]["verdict"] == "STROBING_STILLS"
    # The artifact is still reported: the file exists and the user may want to
    # look at it to confirm the diagnosis.
    assert result.artifacts == [str(produced)]


def test_execute_succeeds_when_the_render_is_coherent(fake_ffmpeg, tmp_path):
    tool, produced = _t2v_tool(tmp_path)
    fake_ffmpeg(_raw(_coherent_motion()))

    result = tool.execute(_t2v_inputs(produced))

    assert result.success is True
    assert result.data["coherence"]["verdict"] == "COHERENT_MOTION"


def test_execute_succeeds_when_the_check_cannot_run(monkeypatch, tmp_path):
    """No ffmpeg, no verdict, no failure -- and no `coherence` key to mislead."""
    tool, produced = _t2v_tool(tmp_path)

    def _boom(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(subprocess, "run", _boom)

    result = tool.execute(_t2v_inputs(produced))

    assert result.success is True
    assert "coherence" not in result.data
