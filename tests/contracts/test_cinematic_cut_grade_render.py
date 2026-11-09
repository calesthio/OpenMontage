"""Renders real CinematicRenderer frames: a cut's tone and filter reach the picture."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose

Image = pytest.importorskip("PIL.Image")

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer"
GREY = 128


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    if not (shutil.which("npx") and shutil.which("ffmpeg") and (COMPOSER / "node_modules").exists()):
        pytest.skip("Remotion is not installed")
    public = tmp_path_factory.mktemp("public")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x{GREY:02x}{GREY:02x}{GREY:02x}:s=640x360:r=30:d=3",
         "-pix_fmt", "yuv444p", "-c:v", "libx264", "-qp", "0", str(public / "grey.mp4")],
        check=True,
    )
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(
        ["npx", "remotion", "bundle", "src/index.tsx", f"--out-dir={out}", f"--public-dir={public}", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    return out


def _centre(bundle: Path, tmp_path: Path, cut_grade: dict) -> float:
    cut = {"id": "c", "source": "grey.mp4", "in_seconds": 0, "out_seconds": 2, **cut_grade}
    props = {"scenes": VideoCompose._cuts_to_cinematic_scenes([cut])}
    props_file = tmp_path / "props.json"
    props_file.write_text(json.dumps(props))
    png = tmp_path / "frame.png"
    subprocess.run(
        ["npx", "remotion", "still", str(bundle), "CinematicRenderer", str(png), f"--props={props_file}",
         "--frame=30", "--width=640", "--height=360", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    centre = Image.open(png).convert("L").crop((300, 160, 340, 200))
    histogram = centre.histogram()
    return sum(level * count for level, count in enumerate(histogram)) / sum(histogram)


def test_default_grade_still_darkens(bundle, tmp_path) -> None:
    assert _centre(bundle, tmp_path, {}) < GREY - 20


def test_tone_and_filter_none_keep_the_clip_colour(bundle, tmp_path) -> None:
    assert _centre(bundle, tmp_path, {"tone": "none", "filter": "none"}) == pytest.approx(GREY, abs=3)


def test_tone_none_only_removes_the_wash(bundle, tmp_path) -> None:
    default = _centre(bundle, tmp_path, {})
    assert default < _centre(bundle, tmp_path, {"tone": "none"}) < GREY - 3
