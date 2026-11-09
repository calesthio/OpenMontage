"""LineChart's x ticks sit on real x values and print years as years."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer"
X_TICKS = COMPOSER / "src/components/charts/xTicks.ts"


def _run(expression: str):
    """Evaluate an expression against the production xTicks.ts in Node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    script = (
        f"import {{ formatXTick, pickXTicks }} from {json.dumps(X_TICKS.as_uri())};"
        f"console.log(JSON.stringify({expression}));"
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


def test_integer_x_values_get_integer_ticks() -> None:
    # Two series of four years: 8 points, 6 intervals of 5 years.
    assert _run("pickXTicks([1990, 2000, 2010, 2020, 1990, 2000, 2010, 2020])") == [
        1990, 1995, 2000, 2005, 2010, 2015, 2020,
    ]
    years = list(range(1990, 2025))
    assert _run(f"pickXTicks({years})") == [1990, 1996, 2001, 2007, 2013, 2018, 2024]


def test_irregular_and_fractional_x_values_keep_even_spacing() -> None:
    assert _run("pickXTicks([0, 1, 2, 5, 13, 30])") == [0, 6, 12, 18, 24, 30]
    assert _run("pickXTicks([0, 0.5, 1])") == [0, 0.5, 1]


def test_degenerate_ranges_do_not_produce_nan() -> None:
    assert _run("[pickXTicks([]), pickXTicks([2020]), pickXTicks([3, 3])]") == [[], [2020], [3]]


def test_years_print_as_years_and_other_values_keep_the_chart_format() -> None:
    chart_format = "(n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}K` : n.toFixed(1))"
    assert _run(f"[2020, 1990, 9999, 12000, 2.5].map((n) => formatXTick(n, {chart_format}))") == [
        "2020", "1990", "9999", "12.0K", "2.5",
    ]


def test_rendered_year_axis_shows_the_years(tmp_path) -> None:
    """1990-2020 and 1991-2021 used to print the same "2.0K" on every tick."""
    image = pytest.importorskip("PIL.Image")
    chops = pytest.importorskip("PIL.ImageChops")
    if not (shutil.which("npx") and (COMPOSER / "node_modules").exists()):
        pytest.skip("Remotion is not installed")
    bundle = tmp_path / "bundle"
    subprocess.run(
        ["npx", "remotion", "bundle", "src/index.tsx", f"--out-dir={bundle}", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )

    def axis(first_year: int):
        series = [{"name": "A", "data": [{"x": first_year + 10 * i, "y": i + 1} for i in range(4)]}]
        cut = {"id": "l", "in_seconds": 0, "out_seconds": 4, "type": "line_chart", "chartSeries": series}
        props = tmp_path / "props.json"
        props.write_text(json.dumps({"cuts": [cut], "theme": "clean-professional"}))
        png = tmp_path / f"{first_year}.png"
        subprocess.run(
            ["npx", "remotion", "still", str(bundle), "Explainer", str(png), f"--props={props}",
             "--frame=60", "--log=error"],
            cwd=COMPOSER, check=True, capture_output=True,
        )
        frame = image.open(png).convert("RGB")
        # Strip under the plot where the x tick labels sit.
        return frame.crop((0, int(frame.height * 0.80), frame.width, int(frame.height * 0.92)))

    assert chops.difference(axis(1990), axis(1991)).getbbox() is not None
