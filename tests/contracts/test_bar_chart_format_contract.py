from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bar_chart_value_labels_preserve_fractional_input_precision() -> None:
    """Value labels must not reuse the one-decimal axis tick formatter."""
    source = (
        REPO_ROOT / "remotion-composer/src/components/charts/BarChart.tsx"
    ).read_text(encoding="utf-8")

    value_label = source[source.index("{/* Value label */}") : source.index(
        "{/* Label */}", source.index("{/* Value label */}")
    )]
    assert "{formatValue(datum.value)}" in value_label
    assert "{formatNumber(datum.value)}" not in value_label

    formatter = source[source.index("function formatValue") :]
    assert "return String(n);" in formatter
    assert "return n.toFixed(1);" not in formatter
