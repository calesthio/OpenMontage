#!/usr/bin/env python3
"""Render test: illustration cuts get a real Ken Burns move, no upscaling.

Builds two synthetic 1344x768 stills + a short sine wav with ffmpeg lavfi,
renders through the real `cmd_render` at 1280x720, and checks duration,
stream facts and that consecutive frames differ (motion actually happened).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_episode  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not installed",
)

W, H, DUR = 1280, 720, 4.0


def _still(path: Path, seed: int):
    img = Image.new("RGB", (1344, 768), (20, 69, 92))
    d = ImageDraw.Draw(img)
    for i in range(0, 1344, 7):
        shade = (seed * 53 + i * 3) % 255
        d.line([(i, 0), (i, 768)], fill=(shade, (shade * 3) % 255, 90))
    d.ellipse([500, 300, 900, 600], fill=(168, 224, 111))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def _wav(path: Path, dur: float):
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"sine=frequency=220:duration={dur}", "-c:a", "pcm_s16le", str(path)],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    return path


def _frames(path: Path, n=4):
    """Sample n frames as raw RGB bytes for a motion check."""
    import tempfile
    out = []
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            f = Path(td) / f"f{i}.png"
            ts = 0.2 + i * (DUR - 0.6) / max(1, n - 1)
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(path),
                 "-frames:v", "1", str(f)], capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, r.stderr[-400:]
            out.append(f.read_bytes())
    return out


def test_illustration_cuts_render_with_motion(tmp_path):
    ep = tmp_path / "ep"
    imgs = [_still(ep / "assets" / "illustrations" / f"i{i}.png", i + 1) for i in range(2)]
    wav = _wav(ep / "narration_finished.wav", DUR)
    edl = {
        "total_duration_s": DUR, "resolution": "1280x720", "fps": 30,
        "cuts": [
            {"cut_id": 1, "start": 0.0, "end": DUR / 2, "asset_id": "a0",
             "role": "illustration", "move": "pan", "easing": "easeinout",
             "direction": "left", "duration": DUR / 2},
            {"cut_id": 2, "start": DUR / 2, "end": DUR, "asset_id": "a1",
             "role": "illustration", "move": "zoom", "easing": "easein",
             "direction": "in", "duration": DUR / 2},
        ],
    }
    edl_path = ep / "edit_decisions.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")
    manifest = {"resolution": f"{W}x{H}", "fps": 30, "assets": {
        "a0": {"kind": "ai_illustration", "path": str(imgs[0])},
        "a1": {"kind": "ai_illustration", "path": str(imgs[1])},
    }}
    mpath = ep / "render_manifest.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")

    out = ep / "renders" / "final_t_ep_draft.mp4"
    state = {"episode_dir": str(ep), "edl_path": str(edl_path),
             "render_manifest_path": str(mpath), "narration_wav": str(wav),
             "render_output_path": str(out)}
    res = run_episode.cmd_render("t_ep", state)
    assert res["status"] == "OK", res
    assert out.is_file()

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
         "-show_format", str(out)], capture_output=True, text=True, timeout=60)
    info = json.loads(probe.stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    assert (v["width"], v["height"]) == (W, H)
    assert a, "audio stream missing"
    assert abs(float(info["format"]["duration"]) - DUR) < 0.3

    frames = _frames(out)
    assert len(set(hashlib.sha256(f).hexdigest() for f in frames)) == len(frames), \
        "frames are identical: Ken Burns move did not happen"
