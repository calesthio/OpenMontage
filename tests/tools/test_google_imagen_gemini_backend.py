"""Tests for the Gemini image backend in google_imagen.

Models named `gemini-*` (e.g. gemini-2.5-flash-image) are not served by the
Imagen `:predict` endpoint — they generate images through generate_content
with an image_config. This backend matters on Vertex projects that have no
Imagen catalog access, where it is the only working Google image path.
"""

import sys
import types as pytypes
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _FakeInline:
    def __init__(self, data: bytes):
        self.data = data


class _FakePart:
    def __init__(self, data: bytes):
        self.inline_data = _FakeInline(data)


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts):
        self.content = _FakeContent(parts)


class _FakeResponse:
    def __init__(self, parts):
        self.candidates = [_FakeCandidate(parts)]


@pytest.fixture
def imagen_tool(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    calls: list[dict] = []

    class _FakeModels:
        def generate_content(self, model=None, contents=None, config=None):
            calls.append({"model": model, "contents": contents, "config": config})
            return _FakeResponse([_FakePart(b"GEMINI_IMG")])

    class _FakeClient:
        models = _FakeModels()

    import tools.google_credentials as gc

    monkeypatch.setattr(
        gc, "get_genai_client", lambda http_options=None, location=None: _FakeClient()
    )

    from tools.graphics.google_imagen import GoogleImagen

    return GoogleImagen(), calls


def test_gemini_model_routes_to_generate_content(imagen_tool, tmp_path):
    tool, calls = imagen_tool
    out = tmp_path / "img.png"

    result = tool.execute(
        {
            "prompt": "a flower",
            "model": "gemini-2.5-flash-image",
            "aspect_ratio": "16:9",
            "output_path": str(out),
        }
    )

    assert result.success
    assert result.data["model"] == "gemini-2.5-flash-image"
    assert out.read_bytes() == b"GEMINI_IMG"

    assert len(calls) == 1
    assert calls[0]["model"] == "gemini-2.5-flash-image"
    # Aspect ratio must reach the API through image_config, not be dropped.
    assert calls[0]["config"].image_config.aspect_ratio == "16:9"


def test_image_selector_maps_model_name_to_google_model(
    imagen_tool, monkeypatch, tmp_path
):
    """The governed selector must be able to reach the Gemini backend."""
    from tools.graphics.image_selector import ImageSelector

    tool, calls = imagen_tool
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])

    result = selector.execute(
        {
            "prompt": "a flower",
            "preferred_provider": "google_imagen",
            "model_name": "gemini-2.5-flash-image",
            "output_path": str(tmp_path / "selected.png"),
        }
    )

    assert result.success, result.error
    assert calls[0]["model"] == "gemini-2.5-flash-image"
    assert result.data["selected_tool"] == "google_imagen"
    assert result.data["model"] == "gemini-2.5-flash-image"


def test_gemini_cost_estimate_is_per_image():
    from tools.graphics.google_imagen import GoogleImagen

    tool = GoogleImagen()
    assert tool.estimate_cost(
        {"model": "gemini-2.5-flash-image", "number_of_images": 2}
    ) == pytest.approx(0.039 * 2)


def test_text_only_response_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class _TextPart:
        inline_data = None

    class _FakeModels:
        def generate_content(self, model=None, contents=None, config=None):
            return _FakeResponse([_TextPart()])

    class _FakeClient:
        models = _FakeModels()

    import tools.google_credentials as gc

    monkeypatch.setattr(
        gc, "get_genai_client", lambda http_options=None, location=None: _FakeClient()
    )

    from tools.graphics.google_imagen import GoogleImagen

    result = GoogleImagen().execute(
        {
            "prompt": "a flower",
            "model": "gemini-2.5-flash-image",
            "output_path": str(tmp_path / "img.png"),
        }
    )

    assert not result.success
    assert "No image data" in result.error
