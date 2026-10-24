"""Unit tests for the Qwen-Image model catalog and parameter gating.

The legacy 2.0 request shape must stay unchanged. The 2.1 and 3.0 series add
``prompt_extend_mode`` / ``enable_thinking`` / ``size="auto"``, and the 2.1
series dropped ``negative_prompt`` — sending it there is an API error.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.graphics.dashscope_image import DashscopeImage

IMAGE_URL = "https://example.com/out.png"


class _FakeResponse:
    def __init__(self, payload: dict | None = None, content: bytes = b"PNG"):
        self._payload = payload or {
            "output": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": [{"image": IMAGE_URL}]},
                    }
                ]
            },
            "usage": {"image_count": 1},
        }
        self.content = content
        self.status_code = 200

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")


def _run(inputs: dict, tmp_path) -> tuple[dict, object]:
    payload = dict(inputs)
    payload.setdefault("output_path", str(tmp_path / "img.png"))
    with patch("requests.post", return_value=_FakeResponse()) as post, patch(
        "requests.get", return_value=_FakeResponse(content=b"PNG")
    ):
        result = DashscopeImage().execute(payload)
    assert result.success, result.error
    return post.call_args.kwargs["json"], result


# ----------------------------------------------------------------------
# Legacy behavior
# ----------------------------------------------------------------------


class TestLegacyPayload:
    def test_default_payload_is_unchanged(self, api_key, tmp_path):
        body, result = _run({"prompt": "a cat"}, tmp_path)

        assert body["model"] == "qwen-image-2.0-pro"
        assert body["parameters"] == {
            "size": "1024*1024",
            "n": 1,
            "prompt_extend": True,
            "watermark": False,
        }
        assert result.data["parameters"] == body["parameters"]

    def test_legacy_keeps_negative_prompt(self, api_key, tmp_path):
        body, _ = _run(
            {"prompt": "x", "model": "qwen-image-2.0", "negative_prompt": "blurry"},
            tmp_path,
        )
        assert body["parameters"]["negative_prompt"] == "blurry"


# ----------------------------------------------------------------------
# Model catalog
# ----------------------------------------------------------------------


class TestModelCatalog:
    def test_current_generations_are_offered(self):
        enum = DashscopeImage.input_schema["properties"]["model"]["enum"]
        for model in (
            "qwen-image-3.0-pro",
            "qwen-image-3.0",
            "qwen-image-2.1-pro",
            "qwen-image-2.1-turbo",
            "qwen-image-2.0-pro",
            "qwen-image-2.0",
        ):
            assert model in enum

    def test_default_stays_on_legacy_model(self):
        props = DashscopeImage.input_schema["properties"]["model"]
        assert props["default"] == "qwen-image-2.0-pro"


# ----------------------------------------------------------------------
# 2.1 / 3.0 parameter support
# ----------------------------------------------------------------------


class TestModernParameters:
    def test_v30_keeps_negative_prompt(self, api_key, tmp_path):
        body, _ = _run(
            {
                "prompt": "x",
                "model": "qwen-image-3.0-pro",
                "negative_prompt": "blurry",
            },
            tmp_path,
        )
        assert body["parameters"]["negative_prompt"] == "blurry"

    def test_v21_omits_negative_prompt(self, api_key, tmp_path):
        body, _ = _run(
            {
                "prompt": "x",
                "model": "qwen-image-2.1-pro",
                "negative_prompt": "blurry",
            },
            tmp_path,
        )
        assert "negative_prompt" not in body["parameters"]

    def test_v21_forwards_mode_thinking_and_auto_size(self, api_key, tmp_path):
        body, result = _run(
            {
                "prompt": "x",
                "model": "qwen-image-2.1-turbo",
                "size": "auto",
                "prompt_extend_mode": "agent",
                "enable_thinking": True,
            },
            tmp_path,
        )

        assert body["parameters"]["size"] == "auto"
        assert body["parameters"]["prompt_extend_mode"] == "agent"
        assert body["parameters"]["enable_thinking"] is True
        assert result.data["parameters"]["prompt_extend_mode"] == "agent"

    def test_v30_forwards_extended_parameters(self, api_key, tmp_path):
        body, _ = _run(
            {
                "prompt": "x",
                "model": "qwen-image-3.0",
                "size": "auto",
                "prompt_extend_mode": "direct",
                "enable_thinking": False,
            },
            tmp_path,
        )
        assert body["parameters"]["prompt_extend_mode"] == "direct"
        assert body["parameters"]["enable_thinking"] is False

    def test_legacy_rejects_auto_size(self, api_key, tmp_path):
        with patch("requests.post") as post:
            result = DashscopeImage().execute(
                {
                    "prompt": "x",
                    "model": "qwen-image-2.0-pro",
                    "size": "auto",
                    "output_path": str(tmp_path / "img.png"),
                }
            )
        assert result.success is False
        assert 'size="auto"' in result.error
        post.assert_not_called()

    def test_legacy_rejects_extended_parameters(self, api_key, tmp_path):
        with patch("requests.post") as post:
            result = DashscopeImage().execute(
                {
                    "prompt": "x",
                    "model": "qwen-image-2.0-pro",
                    "prompt_extend_mode": "agent",
                    "output_path": str(tmp_path / "img.png"),
                }
            )
        assert result.success is False
        assert "prompt_extend_mode" in result.error
        post.assert_not_called()

    def test_thinking_requires_prompt_extend(self, api_key, tmp_path):
        with patch("requests.post") as post:
            result = DashscopeImage().execute(
                {
                    "prompt": "x",
                    "model": "qwen-image-3.0-pro",
                    "prompt_extend": False,
                    "enable_thinking": True,
                    "output_path": str(tmp_path / "img.png"),
                }
            )
        assert result.success is False
        assert "prompt_extend=true" in result.error
        post.assert_not_called()

    def test_family_detection(self):
        assert DashscopeImage._model_family("qwen-image-3.0-pro") == "v30"
        assert DashscopeImage._model_family("qwen-image-2.1-turbo") == "v21"
        assert DashscopeImage._model_family("qwen-image-2.0-pro") == "legacy"
        assert DashscopeImage._model_family("wan2.7-image") == "legacy"


# ----------------------------------------------------------------------
# Multi-image handling still works on the new path
# ----------------------------------------------------------------------


class TestMultiImage:
    def test_two_images_are_written(self, api_key, tmp_path):
        payload = {
            "output": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": [
                                {"image": "https://example.com/a.png"},
                                {"image": "https://example.com/b.png"},
                            ]
                        },
                    }
                ]
            },
            "usage": {"image_count": 2},
        }
        out = tmp_path / "gen.png"
        with patch("requests.post", return_value=_FakeResponse(payload)), patch(
            "requests.get", return_value=_FakeResponse(content=b"PNG")
        ):
            result = DashscopeImage().execute(
                {
                    "prompt": "x",
                    "model": "qwen-image-3.0",
                    "n": 2,
                    "output_path": str(out),
                }
            )

        assert result.success, result.error
        assert [p.name for p in sorted(tmp_path.glob("*.png"))] == [
            "gen_1.png",
            "gen_2.png",
        ]
