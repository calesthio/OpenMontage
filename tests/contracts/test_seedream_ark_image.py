"""Contract tests for direct Volcengine Ark Seedream image generation."""

from __future__ import annotations

import base64
import io
import json

import pytest
from PIL import Image

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.graphics.seedream_ark_image import SeedreamArkImage
from tools.provider_pricing import PriceQuoteRequired


@pytest.fixture(autouse=True)
def _isolate_seedance_config(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(tmp_path / "missing-config.json"))
    for name in ("ARK_API_KEY", "ARK_BASE_URL", "ARK_SEEDREAM_MODEL"):
        monkeypatch.delenv(name, raising=False)


class _FakeResponse:
    def __init__(self, payload=None, *, content: bytes = b"", status_code: int = 200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _png_bytes(color="white") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(stream, format="PNG")
    return stream.getvalue()


def _write_config(tmp_path, **overrides):
    config = {
        "api_key": "ark-image-test-key",
        "api_base": "https://ark.example.test/api/v3",
        "image_model": "doubao-seedream-test-model",
    }
    config.update(overrides)
    path = tmp_path / "seedance-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _inputs(tmp_path, product_image, **overrides):
    inputs = {
        "prompt": "轻奢生活风，精华液放在大理石台面上，保持产品主体不变。",
        "source_image_path": str(product_image),
        "scene_preset": "luxury",
        "product_name": "精华液",
        "count": 3,
        "size": "1024x1024",
        "output_dir": str(tmp_path / "images"),
    }
    inputs.update(overrides)
    return inputs


def test_identity_and_contract():
    tool = SeedreamArkImage()

    assert isinstance(tool, BaseTool)
    assert tool.name == "seedream_ark_image"
    assert tool.provider == "ark"
    assert tool.capability == "image_generation"
    assert tool.runtime == ToolRuntime.API
    assert tool.supports["image_to_image"] is True
    assert tool.supports["product_scene"] is True


def test_status_uses_local_seedance_config(monkeypatch, tmp_path):
    config_path = _write_config(tmp_path)
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(config_path))

    assert SeedreamArkImage().get_status() == ToolStatus.AVAILABLE


def test_missing_key_never_reaches_network(monkeypatch, tmp_path):
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())

    def fail_network(*args, **kwargs):
        raise AssertionError("missing key must not call network")

    monkeypatch.setattr("requests.post", fail_network)
    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=1))

    assert result.success is False
    assert "ARK_API_KEY" in result.error or "火山方舟" in result.error


def test_product_image_is_embedded_and_uses_ark_payload(monkeypatch, tmp_path):
    config_path = _write_config(tmp_path)
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(config_path))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes("red"))
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _FakeResponse(
            {"data": [{"b64_json": base64.b64encode(_png_bytes("blue")).decode()}]}
        )

    monkeypatch.setattr("requests.post", fake_post)
    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=1))

    assert result.success is True
    assert captured["url"] == "https://ark.example.test/api/v3/images/generations"
    assert captured["headers"]["Authorization"] == "Bearer ark-image-test-key"
    assert captured["json"]["model"] == "doubao-seedream-test-model"
    assert captured["json"]["size"] == "1024x1024"
    assert captured["json"]["output_format"] == "png"
    assert captured["json"]["watermark"] is False
    assert captured["json"]["image"].startswith("data:image/png;base64,")
    assert result.data["scene_preset"] == "luxury"
    assert result.data["product_name"] == "精华液"


def test_three_base64_images_get_stable_output_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    encoded = base64.b64encode(_png_bytes("green")).decode()

    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse({"data": [{"b64_json": encoded}]}),
    )
    result = SeedreamArkImage().execute(_inputs(tmp_path, product))

    assert result.success is True
    assert [path.rsplit("/", 1)[-1] for path in result.data["outputs"]] == [
        "scene_luxury_1.png",
        "scene_luxury_2.png",
        "scene_luxury_3.png",
    ]
    for path in result.data["outputs"]:
        assert Image.open(path).size == (16, 16)


def test_url_response_is_downloaded(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    png = _png_bytes("yellow")
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse(
            {"data": [{"url": "https://ark-cdn.example/result.png"}]}
        ),
    )
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: _FakeResponse(content=png),
    )

    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=1))

    assert result.success is True
    assert result.data["outputs"][0].endswith("scene_luxury_1.png")


@pytest.mark.parametrize("status_code, hint", [(401, "Key"), (403, "权限"), (429, "额度")])
def test_http_errors_are_friendly(monkeypatch, tmp_path, status_code, hint):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse({"error": {"message": "failed"}}, status_code=status_code),
    )

    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=1))

    assert result.success is False
    assert hint in result.error


def test_empty_or_invalid_image_response_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse(
            {"data": [{"b64_json": base64.b64encode(b"not-an-image").decode()}]}
        ),
    )

    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=1))

    assert result.success is False
    assert "图片" in result.error
    assert not (tmp_path / "images" / "scene_luxury_1.png").exists()


@pytest.mark.parametrize("count", [0, 4])
def test_count_outside_pipeline_limit_is_rejected_before_network(
    monkeypatch, tmp_path, count
):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())

    def fail_network(*args, **kwargs):
        raise AssertionError("invalid count must not call network")

    monkeypatch.setattr("requests.post", fail_network)
    result = SeedreamArkImage().execute(_inputs(tmp_path, product, count=count))

    assert result.success is False
    assert "1 到 3" in result.error or "1 to 3" in result.error


def test_missing_source_image_is_rejected_before_network(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))

    def fail_network(*args, **kwargs):
        raise AssertionError("missing source must not call network")

    monkeypatch.setattr("requests.post", fail_network)
    result = SeedreamArkImage().execute(
        _inputs(tmp_path, tmp_path / "missing-product.png", count=1)
    )

    assert result.success is False
    assert "产品图" in result.error


def test_partial_batch_preserves_images_already_generated(monkeypatch, tmp_path):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    encoded = base64.b64encode(_png_bytes("green")).decode()
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _FakeResponse({"data": [{"b64_json": encoded}]})
        return _FakeResponse({"error": "failed"}, status_code=500)

    monkeypatch.setattr("requests.post", fake_post)
    result = SeedreamArkImage().execute(_inputs(tmp_path, product))

    assert result.success is False
    assert result.cost_usd is None
    assert result.data["partial_outputs"] == [
        str(tmp_path / "images" / "scene_luxury_1.png")
    ]
    assert result.artifacts == result.data["partial_outputs"]
    assert (tmp_path / "images" / "scene_luxury_1.png").is_file()


def test_invalid_scene_preset_is_rejected_before_output_path_use(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())

    def fail_network(*args, **kwargs):
        raise AssertionError("invalid preset must not call network")

    monkeypatch.setattr("requests.post", fail_network)
    result = SeedreamArkImage().execute(
        _inputs(tmp_path, product, count=1, scene_preset="../../escape")
    )

    assert result.success is False
    assert result.cost_usd is None
    assert "scene_preset" in result.error
    assert not (tmp_path / "escape").exists()


def test_existing_candidate_batch_is_rejected_before_paid_network(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(_write_config(tmp_path)))
    product = tmp_path / "product.png"
    product.write_bytes(_png_bytes())
    output_dir = tmp_path / "images"
    output_dir.mkdir()
    (output_dir / "scene_luxury_1.png").write_bytes(_png_bytes("red"))

    def fail_network(*args, **kwargs):
        raise AssertionError("existing output batch must not call network")

    monkeypatch.setattr("requests.post", fail_network)
    result = SeedreamArkImage().execute(
        _inputs(tmp_path, product, output_dir=str(output_dir))
    )

    assert result.success is False
    assert result.cost_usd is None
    assert "已存在" in result.error


def test_unknown_image_pricing_requires_quote():
    with pytest.raises(PriceQuoteRequired):
        SeedreamArkImage().estimate_cost({"count": 3})
