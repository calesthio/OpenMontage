"""KPIGrid's count-up shows each value at the precision it was written with."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

FORMAT = Path(__file__).resolve().parents[2] / "remotion-composer/src/components/charts/format.ts"
# Where remotion's spring() settles for KPIGrid's two configs: just under 1.
SPRING_ENDS = (0.9999999999999998, 0.9999999999999999)


def _format(calls: list[tuple[float, float]]) -> list[str]:
    """Run the production formatter in Node, not a copy of it."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    script = (
        f"import {{ formatKpiValue }} from {json.dumps(FORMAT.as_uri())};"
        f"console.log(JSON.stringify({json.dumps(calls)}.map(([t, p]) => formatKpiValue(t, p))));"
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


@pytest.mark.parametrize(
    "target, shown",
    [
        (12.5, "12.5"),
        (1.76, "1.76"),
        (0.72, "0.72"),
        (0.4, "0.4"),
        (42, "42"),
        (14_000, "14.0K"),
        (2_500_000, "2.5M"),
    ],
)
def test_final_value_keeps_its_precision(target, shown) -> None:
    assert _format([(target, end) for end in SPRING_ENDS] + [(target, 1)]) == [shown] * 3


def test_count_up_keeps_the_target_digits_and_scale() -> None:
    assert _format([(1.76, 0), (1.76, 0.5), (14_000, 0.5), (2_500_000, 0.5)]) == [
        "0.00", "0.88", "7.0K", "1.3M",
    ]


def test_rendered_card_shows_the_decimals(tmp_path) -> None:
    """12.5, 1.76 and 0.72 used to render exactly like 12, 2 and 1."""
    image = pytest.importorskip("PIL.Image")
    chops = pytest.importorskip("PIL.ImageChops")
    composer = FORMAT.parents[3]
    if not (shutil.which("npx") and (composer / "node_modules").exists()):
        pytest.skip("Remotion is not installed")
    bundle = tmp_path / "bundle"
    subprocess.run(
        ["npx", "remotion", "bundle", "src/index.tsx", f"--out-dir={bundle}", "--log=error"],
        cwd=composer, check=True, capture_output=True,
    )

    def still(values: list[float]):
        cut = {
            "id": "k", "in_seconds": 0, "out_seconds": 6, "type": "kpi_grid", "title": "KPI",
            "chartData": [{"label": f"M{i}", "value": v} for i, v in enumerate(values)],
        }
        props = tmp_path / "props.json"
        props.write_text(json.dumps({"cuts": [cut], "theme": "clean-professional"}))
        png = tmp_path / f"{len(list(tmp_path.glob('*.png')))}.png"
        subprocess.run(
            ["npx", "remotion", "still", str(bundle), "Explainer", str(png), f"--props={props}",
             "--frame=120", "--log=error"],
            cwd=composer, check=True, capture_output=True,
        )
        return image.open(png).convert("RGB")

    assert chops.difference(still([12.5, 1.76, 0.72]), still([12, 2, 1])).getbbox() is not None
