"""Tests for Backlot visual eval image comparison helpers."""

from pathlib import Path

from PIL import Image

from scripts.backlot_visual_eval import compare_images


def _img(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (10, 10), color).save(path)


def test_compare_images_detects_large_drift(tmp_path):
    expected = tmp_path / "expected.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _img(expected, (0, 0, 0))
    _img(actual, (255, 255, 255))

    result = compare_images(expected, actual, diff, threshold=0.015)

    assert result["passed"] is False
    assert result["changed_ratio"] == 1.0
    assert diff.exists()


def test_compare_images_can_mask_regions(tmp_path):
    expected = tmp_path / "expected.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _img(expected, (0, 0, 0))
    _img(actual, (0, 0, 0))
    img = Image.open(actual)
    for x in range(5):
        for y in range(5):
            img.putpixel((x, y), (255, 255, 255))
    img.save(actual)

    result = compare_images(expected, actual, diff, threshold=0.015, masks=[(0, 0, 5, 5)])

    assert result["passed"] is True
    assert result["changed_ratio"] == 0.0
