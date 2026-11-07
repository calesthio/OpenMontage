"""Characterization tests for product-scene image selector routing."""

from __future__ import annotations

import base64
import io
import json

import pytest
from PIL import Image

from tools.graphics.image_selector import ImageSelector


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_ark_image_provider_is_discovered_and_routed(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "api_key": "ark-selector-key",
                "api_base": "https://ark.example.test/api/v3",
                "image_model": "doubao-seedream-test",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(config_path))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    encoded = base64.b64encode(_png_bytes()).decode("ascii")
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse({"data": [{"b64_json": encoded}]}),
    )
    selector = ImageSelector()

    candidates = selector._providers()
    result = selector.execute(
        {
            "prompt": "luxury product scene",
            "source_image_path": str(product),
            "scene_preset": "luxury",
            "product_name": "精华液",
            "count": 1,
            "size": "1024x1024",
            "output_dir": str(tmp_path / "images"),
            "preferred_provider": "ark",
        }
    )

    assert "seedream_ark_image" in {tool.name for tool in candidates}
    assert result.success, result.error
    assert result.data["selected_tool"] == "seedream_ark_image"
    assert result.data["selected_provider"] == "ark"
