"""code_snippet must honor the border_radius and width its input_schema declares."""

import pytest
from PIL import Image

from tools.graphics.code_snippet import CodeSnippet

CODE = "def f(x):\n    return x * 2\n"


def _render(tmp_path, name, **inputs):
    path = tmp_path / f"{name}.png"
    result = CodeSnippet().execute({"code": CODE, "output_path": str(path), **inputs})
    return result, path


def test_border_radius_rounds_the_corners(tmp_path):
    result, path = _render(tmp_path, "rounded", border_radius=30)
    assert result.success, result.error
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((img.width - 1, img.height - 1))[3] == 0
        assert rgba.getpixel((img.width // 2, img.height // 2))[3] == 255


def test_border_radius_zero_keeps_square_corners(tmp_path):
    result, path = _render(tmp_path, "square", border_radius=0)
    assert result.success, result.error
    with Image.open(path) as img:
        assert img.convert("RGBA").getpixel((0, 0))[3] == 255


def test_default_border_radius_matches_schema_default(tmp_path):
    default_result, default_path = _render(tmp_path, "default")
    explicit_result, explicit_path = _render(
        tmp_path, "explicit",
        border_radius=CodeSnippet.input_schema["properties"]["border_radius"]["default"],
    )
    assert default_result.success and explicit_result.success
    assert default_path.read_bytes() == explicit_path.read_bytes()


@pytest.mark.parametrize("title", [None, "example.py"])
def test_width_forces_the_image_width(tmp_path, title):
    extra = {"title": title} if title else {}
    natural, _ = _render(tmp_path, "natural", **extra)
    assert natural.success, natural.error
    target = natural.data["width"] + 300
    result, path = _render(tmp_path, "wide", width=target, **extra)
    assert result.success, result.error
    with Image.open(path) as img:
        assert img.width == target
        assert img.height == natural.data["height"]
    assert result.data["width"] == target


def test_width_narrower_than_the_code_is_an_error(tmp_path):
    natural, _ = _render(tmp_path, "natural")
    result, path = _render(tmp_path, "narrow", width=natural.data["width"] - 50)
    assert not result.success
    assert "width" in result.error
    assert not path.exists()


def test_rounded_card_with_a_jpg_output_path_still_renders(tmp_path):
    # The formatter always writes PNG bytes; the extension must not pick the encoder.
    path = tmp_path / "card.jpg"
    result = CodeSnippet().execute({"code": CODE, "output_path": str(path), "width": 800})
    assert result.success, result.error
    with Image.open(path) as img:
        assert img.format == "PNG"
        assert img.getpixel((0, 0))[3] == 0


def test_null_border_radius_uses_the_default(tmp_path):
    result, path = _render(tmp_path, "null", border_radius=None)
    default_result, default_path = _render(tmp_path, "default")
    assert result.success, result.error
    assert path.read_bytes() == default_path.read_bytes()
