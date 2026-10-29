"""color_grade filter construction and intensity blending.

- `intensity` was ignored with `lut_path` (the LUT branch returned before blending).
- `intensity` was inverted: ffmpeg `blend` applies `all_opacity` to its FIRST input (the
  original), so 0 gave the full grade and 0.25 gave 75 % grade. The graded stream now goes first.
- A missing `lut_path` silently fell back to the default profile (`cinematic_warm`).
- `custom_vf` was not in the idempotency key: two different filters shared one key.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.enhancement.color_grade import ColorGrade, PROFILES

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _write_cube(path: Path) -> Path:
    """2x2x2 LUT that inverts colors."""
    lines = ["LUT_3D_SIZE 2"]
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                lines.append(f"{1 - r} {1 - g} {1 - b}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_video(tmp_path):
    p = tmp_path / "in.mp4"
    p.write_bytes(b"fake")
    return p


@pytest.fixture
def captured(monkeypatch):
    cmds: list[list[str]] = []

    def run(self, cmd, **kw):
        cmds.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ColorGrade, "run_command", run)
    return cmds


class TestLutIntensity:
    def test_full_lut_is_plain(self, tmp_path):
        lut = _write_cube(tmp_path / "inv.cube")
        vf = ColorGrade()._build_filter({"lut_path": str(lut)})
        assert vf.startswith("lut3d=") and "blend" not in vf

    def test_partial_lut_blends_with_original(self, tmp_path):
        lut = _write_cube(tmp_path / "inv.cube")
        vf = ColorGrade()._build_filter({"lut_path": str(lut), "intensity": 0.3})
        assert "split[original][tograde]" in vf and "lut3d=" in vf
        assert "blend=all_mode=normal:all_opacity=0.3" in vf


class TestIntensityZero:
    def test_zero_keeps_original(self):
        vf = ColorGrade()._build_filter({"profile": "cinematic_warm", "intensity": 0})
        assert "blend=all_mode=normal:all_opacity=0" in vf

    def test_full_intensity_is_plain_profile(self):
        vf = ColorGrade()._build_filter({"profile": "cinematic_warm"})
        assert vf == PROFILES["cinematic_warm"]["vf"]


class TestMissingLut:
    def test_missing_lut_is_error_not_silent_fallback(self, fake_video, captured, tmp_path):
        r = ColorGrade().execute({"input_path": str(fake_video),
                                  "lut_path": str(tmp_path / "nope.cube")})
        assert not r.success and "lut" in r.error.lower()
        assert captured == []


class TestIdempotencyKey:
    def test_custom_vf_in_key(self):
        assert "custom_vf" in ColorGrade.idempotency_key_fields


class TestBaseBehaviourKept:
    def test_command_uses_plain_vf(self, fake_video, captured):
        r = ColorGrade().execute({"input_path": str(fake_video), "profile": "neutral"})
        assert r.success, r.error
        cmd = captured[-1]
        assert cmd[cmd.index("-vf") + 1] == PROFILES["neutral"]["vf"]
        assert "-filter_complex" not in cmd
        assert cmd[cmd.index("-crf") + 1] == "20"


def _make_clip(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc2=size=320x180:rate=24:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


def _gray_mean(path: Path) -> float:
    gray = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    return sum(gray) / len(gray)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")
def test_lut_intensity_render(tmp_path):
    src = tmp_path / "src.mp4"
    _make_clip(src)
    lut = _write_cube(tmp_path / "inv.cube")
    means = {}
    for inten in (1.0, 0.5):
        out = tmp_path / f"lut_{inten}.mp4"
        r = ColorGrade().execute({"input_path": str(src), "output_path": str(out),
                                  "lut_path": str(lut), "intensity": inten})
        assert r.success, r.error
        means[inten] = _gray_mean(out)
    # half negative + half original tends toward mid gray
    assert abs(means[0.5] - 128) < abs(means[1.0] - 128)


def _make_solid_clip(path: Path, value: int) -> None:
    hexv = f"{value:02x}" * 3
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=0x{hexv}:size=64x64:rate=24:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


class TestBlendOrder:
    def test_graded_is_top_layer(self):
        # ffmpeg blend applies all_opacity to its FIRST input: graded must come first.
        vf = ColorGrade()._build_filter({"profile": "cinematic_warm", "intensity": 0.25})
        assert "[graded][original]blend=" in vf


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")
def test_intensity_direction_render(tmp_path):
    """Inverting LUT over gray 64: intensity 0 -> 64, 0.25 -> ~96, 1 -> ~191.

    0.5 cannot check the direction because the blend is symmetric there.
    """
    src = tmp_path / "solid.mp4"
    _make_solid_clip(src, 64)
    lut = _write_cube(tmp_path / "inv.cube")
    means = {}
    for inten in (0.0, 0.25, 1.0):
        out = tmp_path / f"solid_{inten}.mp4"
        r = ColorGrade().execute({"input_path": str(src), "output_path": str(out),
                                  "lut_path": str(lut), "intensity": inten})
        assert r.success, r.error
        means[inten] = _gray_mean(out)
    original = _gray_mean(src)
    inverted = 255 - original
    assert abs(means[0.0] - original) < 6
    assert abs(means[1.0] - inverted) < 6
    expected_quarter = original * 0.75 + inverted * 0.25
    assert abs(means[0.25] - expected_quarter) < 6
