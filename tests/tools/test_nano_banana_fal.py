"""Unit tests for nano_banana_fal — Google Nano Banana 2 / Pro via the fal.ai gateway."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import ToolStatus


# ---------------------------------------------------------------------------
# Tool discovery & metadata
# ---------------------------------------------------------------------------


def test_nano_banana_fal_is_discovered_by_registry():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("nano_banana_fal")
    assert tool is not None
    assert tool.provider == "google"
    assert tool.capability == "image_generation"
    assert tool.name == "nano_banana_fal"


def test_metadata():
    from tools.graphics.nano_banana_fal import NanoBananaFal

    tool = NanoBananaFal()
    info = tool.get_info()

    assert info["tier"] == "generate"
    assert info["stability"] == "beta"
    assert info["runtime"] == "api"
    assert "image_edit" in info["capabilities"]
    assert info["supports"]["multiple_reference_images"] is True
    assert info["supports"]["web_grounding"] is True
    assert "env:FAL_KEY" in info["dependencies"]


# ---------------------------------------------------------------------------
# Idempotency — every output-affecting input must change the key
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_model_variant_changes_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key({**base, "model": "nano-banana-2"}) != tool.idempotency_key(
            {**base, "model": "nano-banana-pro"}
        )

    def test_seed_changes_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key(base) != tool.idempotency_key({**base, "seed": 42})

    def test_num_images_changes_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "num_images": 4}
        )

    def test_output_format_changes_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key({**base, "output_format": "png"}) != tool.idempotency_key(
            {**base, "output_format": "webp"}
        )

    def test_edit_reference_images_change_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "edit this", "operation": "edit"}
        assert tool.idempotency_key(
            {**base, "image_urls": ["https://example.com/a.png"]}
        ) != tool.idempotency_key(
            {**base, "image_urls": ["https://example.com/b.png"]}
        )

    def test_extra_params_changes_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "extra_params": {"enable_google_search": True}}
        )

    def test_same_inputs_produce_same_key(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        inputs = {"prompt": "a cat", "model": "nano-banana-pro", "resolution": "2K"}
        assert tool.idempotency_key(inputs) == tool.idempotency_key(dict(inputs))


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------


def test_status_unavailable_when_no_api_key(monkeypatch):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    assert NanoBananaFal().get_status() == ToolStatus.UNAVAILABLE


def test_status_available_when_api_key_set(monkeypatch):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")
    assert NanoBananaFal().get_status() == ToolStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_default_cost(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        assert tool.estimate_cost({}) == pytest.approx(0.08)

    def test_cost_scales_with_num_images(self):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        assert tool.estimate_cost({"num_images": 3}) == pytest.approx(0.08 * 3)

    @pytest.mark.parametrize(
        "resolution,multiplier",
        [("0.5K", 0.75), ("1K", 1.0), ("2K", 1.5), ("4K", 2.0)],
    )
    def test_cost_varies_by_resolution(self, resolution, multiplier):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        tool = NanoBananaFal()
        cost = tool.estimate_cost({"resolution": resolution})
        assert cost == pytest.approx(0.08 * multiplier)


# ---------------------------------------------------------------------------
# Validation & error handling (no network call should happen)
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_api_key_returns_error(self, monkeypatch):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        monkeypatch.delenv("FAL_KEY", raising=False)
        monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
        result = NanoBananaFal().execute({"prompt": "a cat"})
        assert not result.success
        assert "FAL_KEY" in result.error

    def test_unsupported_model_operation_combo_returns_error(self, monkeypatch):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        result = NanoBananaFal().execute(
            {"prompt": "a cat", "model": "nano-banana-3", "operation": "generate"}
        )
        assert not result.success
        assert "unsupported model/operation" in result.error

    def test_edit_without_images_returns_error(self, monkeypatch):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        result = NanoBananaFal().execute({"prompt": "edit this", "operation": "edit"})
        assert not result.success
        assert "requires at least one image" in result.error

    def test_edit_rejects_too_many_images(self, monkeypatch):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        urls = [f"https://example.com/{i}.png" for i in range(15)]
        result = NanoBananaFal().execute(
            {"prompt": "edit this", "operation": "edit", "image_urls": urls}
        )
        assert not result.success
        assert "at most 14 images" in result.error

    def test_validation_error_makes_no_network_call(self, monkeypatch):
        from tools.graphics.nano_banana_fal import NanoBananaFal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        with patch("requests.post") as mock_post:
            NanoBananaFal().execute({"prompt": "edit this", "operation": "edit"})
            mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-end with mocked API
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, json_data=None, content: bytes = b""):
        self._json_data = json_data or {}
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_execute_generate_full_flow(monkeypatch, tmp_path):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json))
        return _FakeResponse({"images": [{"url": "https://cdn.fal.ai/out.png"}]})

    def fake_get(url, timeout):
        return _FakeResponse(content=b"NANO_BANANA_BYTES")

    out = tmp_path / "gen.png"
    with patch("requests.post", side_effect=fake_post), patch(
        "requests.get", side_effect=fake_get
    ):
        result = NanoBananaFal().execute(
            {"prompt": "a neon city", "output_path": str(out)}
        )

    assert result.success, result.error
    assert result.data["provider"] == "google"
    assert result.data["model"] == "fal-ai/nano-banana-2"
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"NANO_BANANA_BYTES"
    assert calls[0][0] == "https://fal.run/fal-ai/nano-banana-2"
    assert calls[0][1]["Authorization"] == "Key test-fal-key"


def test_execute_pro_generate_uses_pro_endpoint(monkeypatch, tmp_path):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        return _FakeResponse({"images": [{"url": "https://cdn.fal.ai/out.png"}]})

    def fake_get(url, timeout):
        return _FakeResponse(content=b"PRO_BYTES")

    out = tmp_path / "gen.png"
    with patch("requests.post", side_effect=fake_post), patch(
        "requests.get", side_effect=fake_get
    ):
        result = NanoBananaFal().execute(
            {"prompt": "a neon city", "model": "nano-banana-pro", "output_path": str(out)}
        )

    assert result.success, result.error
    assert calls[0] == "https://fal.run/fal-ai/nano-banana-pro"


def test_execute_edit_uploads_local_reference(monkeypatch, tmp_path):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    ref = tmp_path / "ref.png"
    ref.write_bytes(b"local-ref")

    monkeypatch.setattr(
        "tools.video._shared.upload_image_fal",
        lambda path: "https://cdn.fal.ai/uploaded.png",
    )

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, json))
        return _FakeResponse({"images": [{"url": "https://cdn.fal.ai/out.png"}]})

    def fake_get(url, timeout):
        return _FakeResponse(content=b"EDITED_BYTES")

    out = tmp_path / "edited.png"
    with patch("requests.post", side_effect=fake_post), patch(
        "requests.get", side_effect=fake_get
    ):
        result = NanoBananaFal().execute(
            {
                "prompt": "add neon signs",
                "operation": "edit",
                "image_paths": [str(ref)],
                "output_path": str(out),
            }
        )

    assert result.success, result.error
    assert calls[0][0] == "https://fal.run/fal-ai/nano-banana-2/edit"
    assert calls[0][1]["image_urls"] == ["https://cdn.fal.ai/uploaded.png"]


def test_execute_returns_error_when_no_images_in_response(monkeypatch):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    with patch("requests.post", return_value=_FakeResponse({"images": []})):
        result = NanoBananaFal().execute({"prompt": "a cat"})

    assert not result.success
    assert "no image outputs" in result.error


def test_execute_multi_output_writes_all_files(monkeypatch, tmp_path):
    from tools.graphics.nano_banana_fal import NanoBananaFal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    def fake_post(url, headers, json, timeout):
        return _FakeResponse(
            {
                "images": [
                    {"url": "https://cdn.fal.ai/1.png"},
                    {"url": "https://cdn.fal.ai/2.png"},
                ]
            }
        )

    def fake_get(url, timeout):
        return _FakeResponse(content=b"BYTES_" + url.encode()[-5:])

    out = tmp_path / "gen.png"
    with patch("requests.post", side_effect=fake_post), patch(
        "requests.get", side_effect=fake_get
    ):
        result = NanoBananaFal().execute(
            {"prompt": "a cat", "num_images": 2, "output_path": str(out)}
        )

    assert result.success, result.error
    assert len(result.artifacts) == 2
    assert result.data["images_generated"] == 2
    assert result.cost_usd == pytest.approx(NanoBananaFal().estimate_cost({"num_images": 2}))
