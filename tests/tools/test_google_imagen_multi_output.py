"""Regression tests: google_imagen must return every image it requests and bills for.

`execute()` sends `sampleCount = number_of_images` to the Imagen API and
`estimate_cost` scales with `number_of_images`, but result handling was
hardcoded to `predictions[0]` — images 1..n-1 were decoded never, written
never, and absent from `artifacts`. Worse, `images_generated` reported
`len(predictions)`, so the result claimed n images while only one reached
disk. The user paid for n images and received one.

Mirrors tests/tools/test_openai_image_multi_output.py, which covers the same
defect class in the OpenAI provider.
"""

import base64
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _FakeResponse:
    def __init__(self, count: int):
        self._count = count

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "predictions": [
                {"bytesBase64Encoded": base64.b64encode(f"IMAGE_{i}".encode()).decode()}
                for i in range(self._count)
            ]
        }


@pytest.fixture
def imagen_tool(monkeypatch):
    # Stub `requests` so execute() runs fully offline; echo back sampleCount
    # images so the fake provider honors what the tool asked and billed for.
    fake = types.ModuleType("requests")

    def _post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(json["parameters"]["sampleCount"])

    fake.post = _post
    monkeypatch.setitem(sys.modules, "requests", fake)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    from tools.graphics.google_imagen import GoogleImagen

    return GoogleImagen()


def test_all_requested_images_are_written(imagen_tool, tmp_path):
    out = tmp_path / "gen.png"
    result = imagen_tool.execute(
        {"prompt": "p", "number_of_images": 4, "output_path": str(out)}
    )

    assert result.success
    assert result.data["images_generated"] == 4
    assert len(result.artifacts) == 4

    files = sorted(tmp_path.glob("*.png"))
    assert len(files) == 4  # every image reached disk, none overwritten
    contents = {f.read_bytes() for f in files}
    assert contents == {b"IMAGE_0", b"IMAGE_1", b"IMAGE_2", b"IMAGE_3"}


def test_artifacts_match_billed_image_count(imagen_tool, tmp_path):
    # What the user pays for must equal what they receive.
    inputs = {
        "prompt": "p",
        "number_of_images": 3,
        "output_path": str(tmp_path / "img.png"),
    }
    result = imagen_tool.execute(inputs)
    billed = imagen_tool.estimate_cost(inputs)

    assert len(result.artifacts) == 3
    assert billed == pytest.approx(0.04 * 3)


def test_single_image_keeps_exact_output_path(imagen_tool, tmp_path):
    out = tmp_path / "single.png"
    result = imagen_tool.execute(
        {"prompt": "p", "number_of_images": 1, "output_path": str(out)}
    )

    assert result.success
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"IMAGE_0"


def test_multi_output_paths_are_suffixed_and_unique():
    from tools.graphics.google_imagen import GoogleImagen

    paths = GoogleImagen._output_paths("/tmp/art/pic.png", 3)
    assert [p.name for p in paths] == ["pic_1.png", "pic_2.png", "pic_3.png"]
    assert len(set(paths)) == 3
