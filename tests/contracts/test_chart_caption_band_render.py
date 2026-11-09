"""Renders real frames: chart scenes must leave the caption band empty.

The caption starts after the rendered frame, so the band is reserved but nothing
is drawn in it yet. Any second color inside it is chart or background leaking in.
Skipped when Remotion is not installed, which includes the Python-only CI job.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer"
FRAME = 75
LATE_CAPTION = [{"word": "later", "startMs": 3500, "endMs": 3900}]
LANDSCAPE = (1920, 1080)
PORTRAIT = (1080, 1920)
CARD_COLOR = (249, 250, 251)  # KPIGrid's default card background, #F9FAFB.


def _metrics(count: int, **extra) -> list[dict]:
    return [{"label": f"Metric {i}", "value": 1000 + i, "change": 1.5, **extra} for i in range(count)]


def _points(count: int) -> list[dict]:
    return [{"label": f"L{i}", "value": i + 1} for i in range(count)]


CHART_SCENES = {
    "bar": {"type": "bar_chart", "chartData": _points(6)},
    "line": {
        "type": "line_chart",
        "chartSeries": [{"name": "A", "data": [{"x": i, "y": i + 1} for i in range(6)]}],
        "xLabel": "Year",
        "showLegend": True,
    },
    "pie": {"type": "pie_chart", "chartData": _points(8)},
    "kpi6": {"type": "kpi_grid", "chartData": _metrics(6)},
    "kpi9": {"type": "kpi_grid", "chartData": _metrics(9)},
    "kpi12": {"type": "kpi_grid", "chartData": _metrics(12, icon="X")},
}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    if not (shutil.which("npx") and shutil.which("ffmpeg") and (COMPOSER / "node_modules").exists()):
        pytest.skip("Remotion is not installed")
    public = tmp_path_factory.mktemp("public")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x334455:s=1080x1920:r=30:d=5",
         "-pix_fmt", "yuv420p", str(public / "host.mp4")],
        check=True,
    )
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(
        ["npx", "remotion", "bundle", "src/index.tsx", f"--out-dir={out}", f"--public-dir={public}", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    return out


def _render(bundle: Path, tmp_path: Path, composition: str, props: dict, size: tuple[int, int]):
    props_file = tmp_path / "props.json"
    props_file.write_text(json.dumps(props))
    png = tmp_path / "frame.png"
    subprocess.run(
        ["npx", "remotion", "still", str(bundle), composition, str(png), f"--props={props_file}",
         f"--frame={FRAME}", f"--width={size[0]}", f"--height={size[1]}", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    return Image.open(png).convert("RGB")


@pytest.mark.parametrize("scene", CHART_SCENES)
@pytest.mark.parametrize("size", [LANDSCAPE, PORTRAIT], ids=["landscape", "portrait"])
def test_chart_scene_leaves_the_caption_band_empty(bundle, tmp_path, scene, size) -> None:
    cut = {"id": "c", "in_seconds": 0, "out_seconds": 4, "title": "Title", **CHART_SCENES[scene]}
    frame = _render(
        bundle, tmp_path, "Explainer",
        {"cuts": [cut], "captions": LATE_CAPTION, "theme": "clean-professional"}, size,
    )
    width, height = size
    # Top of a one-line default caption box: bottomOffset 80 + 42 * 1.4 line + 28 padding.
    band = frame.crop((0, height - 167, width, height))
    colors = band.getcolors(maxcolors=100_000)
    assert len(colors) == 1, f"caption band is not one flat color: {len(colors)} colors"


def test_kpi_cards_stay_visible_inside_a_talking_head_panel(bundle, tmp_path) -> None:
    """The panel is shorter than the composition, so KPIGrid must not lay out for the whole frame."""
    overlay = {
        "id": "o", "type": "kpi_grid", "in_seconds": 0, "out_seconds": 4,
        "position": "lower_third", "title": "Quarter", "chartData": _metrics(6),
    }
    frame = _render(
        bundle, tmp_path, "TalkingHead",
        {"videoSrc": "host.mp4", "captions": [], "overlays": [overlay]}, PORTRAIT,
    )
    # lower_third sits 320 px from the bottom and is 480 px tall.
    panel = frame.crop((40, 1120, 1040, 1600))
    pixels = panel.width * panel.height
    card_pixels = sum(count for count, color in panel.getcolors(maxcolors=pixels) if color == CARD_COLOR)
    assert card_pixels > pixels * 0.05, f"only {card_pixels} of {pixels} panel pixels are KPI cards"
