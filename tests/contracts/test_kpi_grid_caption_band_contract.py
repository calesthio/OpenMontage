"""KPIGrid positions its cards itself, so it must lay them out above the caption band."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "remotion-composer/src"
LAYOUT = SRC / "components/charts/kpiLayout.ts"


def _layout(**kwargs) -> dict:
    """Run the production layout calculation, not a copy of it."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    script = (
        f"import {{ kpiGridLayout }} from {json.dumps(LAYOUT.as_uri())};"
        f"console.log(JSON.stringify(kpiGridLayout({json.dumps(kwargs)})));"
    )
    proc = subprocess.run(
        [node, "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and "bad option" in proc.stderr:
        pytest.skip("This Node cannot strip TypeScript types")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _bottom(layout: dict) -> float:
    return max(card["top"] for card in layout["cards"]) + layout["cardHeight"]


def _right(layout: dict) -> float:
    return max(card["left"] for card in layout["cards"]) + layout["cardWidth"]


@pytest.mark.parametrize("count", [3, 6, 9, 12])
@pytest.mark.parametrize("has_title", [True, False])
@pytest.mark.parametrize("width, height", [(1920, 1080), (1080, 1920)])
def test_every_card_ends_above_the_caption_band(count, has_title, width, height) -> None:
    inset = round(height * 0.15)
    layout = _layout(
        count=count, columns=3, hasTitle=has_title, width=width, height=height, bottomInset=inset
    )
    assert len(layout["cards"]) == count
    assert _bottom(layout) <= height - inset
    assert _right(layout) <= width


def test_without_captions_the_landscape_layout_does_not_move() -> None:
    layout = _layout(count=6, columns=3, hasTitle=True, width=1920, height=1080, bottomInset=0)
    assert layout["cardHeight"] == 320
    assert layout["cardWidth"] == pytest.approx((1720 - 56) / 3)
    assert layout["cards"][0] == {"left": 100, "top": 266}
    assert _bottom(layout) == 934


def test_explainer_hands_the_band_to_kpi_grid() -> None:
    source = (SRC / "Explainer.tsx").read_text(encoding="utf-8")
    start = source.index("<KPIGrid")
    assert "bottomInset={captionSafeBottom}" in source[start : source.index("/>", start)]
    # Shrinking the parent does not move KPIGrid's cards, so it must not rely on that.
    chart_types = source[source.index("const CHART_TYPES") :].split("\n", 1)[0]
    assert "kpi_grid" not in chart_types


def test_kpi_grid_uses_the_shared_layout() -> None:
    source = (SRC / "components/charts/KPIGrid.tsx").read_text(encoding="utf-8")
    assert "kpiGridLayout(" in source
