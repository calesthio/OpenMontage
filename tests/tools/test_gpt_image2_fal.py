"""Unit tests for gpt_image2_fal — OpenAI GPT Image 2 via the fal.ai gateway."""

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


def test_gpt_image2_fal_is_discovered_by_registry():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("gpt_image2_fal")
    assert tool is not None
    assert tool.provider == "openai"
    assert tool.capability == "image_generation"
    assert tool.name == "gpt_image2_fal"


def test_metadata():
    from tools.graphics.gpt_image2_fal import GptImage2Fal

    tool = GptImage2Fal()
    info = tool.get_info()

    assert info["tier"] == "generate"
    assert info["stability"] == "beta"
    assert info["runtime"] == "api"
    assert "image_edit" in info["capabilities"]
    assert info["supports"]["multiple_reference_images"] is True
    assert info["supports"]["mask_editing"] is True
    assert "env:FAL_KEY" in info["dependencies"]


# ---------------------------------------------------------------------------
# Idempotency — every output-affecting input must change the key
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_num_images_changes_key(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        base = {"prompt": "a cat"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "num_images": 4}
        )

    def test_output_format_changes_key(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        base = {"prompt": "a cat", "output_format": "png"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "output_format": "jpeg"}
        )

    def test_edit_reference_images_change_key(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        base = {"prompt": "edit this", "operation": "edit"}
        assert tool.idempotency_key(
            {**base, "image_urls": ["https://example.com/a.png"]}
        ) != tool.idempotency_key(
            {**base, "image_urls": ["https://example.com/b.png"]}
        )

    def test_mask_changes_key(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        base = {"prompt": "edit this", "operation": "edit"}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "mask_url": "https://example.com/mask.png"}
        )

    def test_same_inputs_produce_same_key(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        inputs = {"prompt": "a cat", "num_images": 2, "width": 1024, "height": 1024}
        assert tool.idempotency_key(inputs) == tool.idempotency_key(dict(inputs))


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------


def test_status_unavailable_when_no_api_key(monkeypatch):
    from tools.graphics.gpt_image2_fal import GptImage2Fal

    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
    assert GptImage2Fal().get_status() == ToolStatus.UNAVAILABLE


def test_status_available_when_api_key_set(monkeypatch):
    from tools.graphics.gpt_image2_fal import GptImage2Fal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")
    assert GptImage2Fal().get_status() == ToolStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_default_cost(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        cost = tool.estimate_cost({})
        assert cost == pytest.approx(0.211)  # 1024x1024, high

    def test_cost_scales_with_num_images(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        cost = tool.estimate_cost({"num_images": 3})
        assert cost == pytest.approx(0.211 * 3)

    def test_cost_varies_by_quality(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        low = tool.estimate_cost({"quality": "low"})
        high = tool.estimate_cost({"quality": "high"})
        assert low < high

    def test_unknown_size_falls_back_to_nearest_bucket(self):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        tool = GptImage2Fal()
        cost = tool.estimate_cost({"width": 100, "height": 100})
        assert cost > 0


# ---------------------------------------------------------------------------
# Validation & error handling (no network call should happen)
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_api_key_returns_error(self, monkeypatch):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        monkeypatch.delenv("FAL_KEY", raising=False)
        monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
        result = GptImage2Fal().execute({"prompt": "a cat"})
        assert not result.success
        assert "FAL_KEY" in result.error

    def test_unsupported_operation_returns_error(self, monkeypatch):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        result = GptImage2Fal().execute({"prompt": "a cat", "operation": "upscale"})
        assert not result.success
        assert "unsupported operation" in result.error

    def test_edit_without_images_returns_error(self, monkeypatch):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        result = GptImage2Fal().execute({"prompt": "edit this", "operation": "edit"})
        assert not result.success
        assert "requires at least one image" in result.error

    def test_edit_rejects_too_many_images(self, monkeypatch):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        urls = [f"https://example.com/{i}.png" for i in range(11)]
        result = GptImage2Fal().execute(
            {"prompt": "edit this", "operation": "edit", "image_urls": urls}
        )
        assert not result.success
        assert "at most 10 images" in result.error

    def test_validation_error_makes_no_network_call(self, monkeypatch):
        from tools.graphics.gpt_image2_fal import GptImage2Fal

        monkeypatch.setenv("FAL_KEY", "test-fal-key")
        with patch("requests.post") as mock_post:
            GptImage2Fal().execute({"prompt": "edit this", "operation": "edit"})
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
    from tools.graphics.gpt_image2_fal import GptImage2Fal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json))
        return _FakeResponse({"images": [{"url": "https://cdn.fal.ai/out.png"}]})

    def fake_get(url, timeout):
        return _FakeResponse(content=b"GPT_IMAGE_2_BYTES")

    out = tmp_path / "gen.png"
    with patch("requests.post", side_effect=fake_post), patch(
        "requests.get", side_effect=fake_get
    ):
        result = GptImage2Fal().execute(
            {
                "prompt": "a robot painting",
                "num_images": 1,
                "output_path": str(out),
            }
        )

    assert result.success, result.error
    assert result.data["provider"] == "openai"
    assert result.data["model"] == "fal-ai/gpt-image-2"
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"GPT_IMAGE_2_BYTES"
    assert calls[0][0] == "https://fal.run/fal-ai/gpt-image-2"
    assert calls[0][1]["Authorization"] == "Key test-fal-key"


def test_execute_edit_uploads_local_reference(monkeypatch, tmp_path):
    from tools.graphics.gpt_image2_fal import GptImage2Fal

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
        result = GptImage2Fal().execute(
            {
                "prompt": "add a hat",
                "operation": "edit",
                "image_paths": [str(ref)],
                "output_path": str(out),
            }
        )

    assert result.success, result.error
    assert calls[0][0] == "https://fal.run/fal-ai/gpt-image-2/image-to-image"
    assert calls[0][1]["image_urls"] == ["https://cdn.fal.ai/uploaded.png"]


def test_execute_returns_error_when_no_images_in_response(monkeypatch, tmp_path):
    from tools.graphics.gpt_image2_fal import GptImage2Fal

    monkeypatch.setenv("FAL_KEY", "test-fal-key")

    with patch("requests.post", return_value=_FakeResponse({"images": []})):
        result = GptImage2Fal().execute({"prompt": "a cat"})

    assert not result.success
    assert "no image outputs" in result.error


def test_execute_multi_output_writes_all_files(monkeypatch, tmp_path):
    from tools.graphics.gpt_image2_fal import GptImage2Fal

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
        result = GptImage2Fal().execute(
            {"prompt": "a cat", "num_images": 2, "output_path": str(out)}
        )

    assert result.success, result.error
    assert len(result.artifacts) == 2
    assert result.data["images_generated"] == 2
    assert result.cost_usd == pytest.approx(GptImage2Fal().estimate_cost({"num_images": 2}))
