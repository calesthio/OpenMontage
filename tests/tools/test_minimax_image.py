"""Contract tests for the MiniMax image generation tool."""

from __future__ import annotations

import base64

import pytest
import requests

from tools.base_tool import ToolStatus
from tools.graphics import minimax_image
from tools.graphics.minimax_image import MiniMaxImage
from tools.tool_registry import ToolRegistry


class FakeResponse:
    def __init__(self, *, json_data=None, content: bytes = b"") -> None:
        self._json_data = json_data
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def clear_minimax_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_REGION", raising=False)
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)


def test_registry_registers_minimax_image_tool() -> None:
    registry = ToolRegistry()
    assert registry.register_module(minimax_image) == ["minimax_image"]

    tool = registry.get("minimax_image")
    assert tool is not None
    assert tool.provider == "minimax"
    assert tool.capability == "image_generation"
    assert tool.input_schema["properties"]["model"]["enum"] == [
        "image-01",
        "image-01-live",
    ]


def test_status_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = MiniMaxImage()
    assert tool.get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_cost_estimate_and_result_report_paid_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json_data={
                "data": {
                    "image_base64": [
                        base64.b64encode(b"one").decode("ascii"),
                        base64.b64encode(b"two").decode("ascii"),
                    ]
                },
                "base_resp": {"status_code": 0},
            }
        ),
    )

    tool = MiniMaxImage()
    inputs = {
        "prompt": "A lighthouse at dusk",
        "response_format": "base64",
        "n": 2,
        "output_path": str(tmp_path / "image.png"),
    }
    assert tool.estimate_cost(inputs) == pytest.approx(0.007)
    result = tool.execute(inputs)
    assert result.success, result.error
    assert result.cost_usd == pytest.approx(0.007)


def test_image_selector_can_route_to_minimax(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from tools.graphics.image_selector import ImageSelector

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json_data={
                "data": {
                    "image_base64": [base64.b64encode(b"image").decode("ascii")]
                },
                "base_resp": {"status_code": 0},
            }
        ),
    )
    tool = MiniMaxImage()
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])

    result = selector.execute(
        {
            "prompt": "A lighthouse at dusk",
            "preferred_provider": "minimax",
            "response_format": "base64",
            "output_path": str(tmp_path / "selected.png"),
        }
    )

    assert result.success, result.error
    assert result.data["selected_provider"] == "minimax"
    assert result.data["selected_tool"] == "minimax_image"


@pytest.mark.parametrize(
    ("region", "expected_base_url"),
    [
        ("global", "https://api.minimax.io"),
        ("global_en", "https://api.minimax.io"),
        ("cn", "https://api.minimaxi.com"),
        ("cn_zh", "https://api.minimaxi.com"),
    ],
)
def test_region_routes_to_official_endpoint(
    monkeypatch: pytest.MonkeyPatch, region: str, expected_base_url: str
) -> None:
    monkeypatch.setenv("MINIMAX_REGION", region)
    assert MiniMaxImage()._base_url() == expected_base_url


def test_url_response_downloads_all_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_REGION", "cn")
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse(
            json_data={
                "id": "request-1",
                "data": {
                    "image_urls": [
                        "https://example.test/one.png",
                        "https://example.test/two.png",
                    ]
                },
                "metadata": {"success_count": 2, "failed_count": 0},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    def fake_get(url, *, timeout):
        assert timeout == 120
        return FakeResponse(content=url.rsplit("/", 1)[-1].encode())

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    output_path = tmp_path / "image.png"
    result = MiniMaxImage().execute(
        {
            "prompt": "A lighthouse at dusk",
            "model": "image-01-live",
            "subject_reference": [
                {"type": "character", "image_file": "https://example.test/ref.png"}
            ],
            "aspect_ratio": "16:9",
            "response_format": "url",
            "seed": 42,
            "n": 2,
            "prompt_optimizer": True,
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert captured["url"] == "https://api.minimaxi.com/v1/image_generation"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "image-01-live",
        "prompt": "A lighthouse at dusk",
        "response_format": "url",
        "n": 2,
        "prompt_optimizer": True,
        "subject_reference": [
            {"type": "character", "image_file": "https://example.test/ref.png"}
        ],
        "aspect_ratio": "16:9",
        "seed": 42,
    }
    assert result.artifacts == [
        str(tmp_path / "image_1.png"),
        str(tmp_path / "image_2.png"),
    ]
    assert (tmp_path / "image_1.png").read_bytes() == b"one.png"
    assert (tmp_path / "image_2.png").read_bytes() == b"two.png"
    assert result.data["metadata"] == {"success_count": 2, "failed_count": 0}


def test_base64_response_writes_inline_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    image_bytes = b"inline image"

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json_data={
                "data": {
                    "image_base64": [
                        "data:image/png;base64,"
                        + base64.b64encode(image_bytes).decode("ascii")
                    ]
                },
                "metadata": {"success_count": "1", "failed_count": "0"},
                "base_resp": {"status_code": 0},
            }
        ),
    )
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("base64 output must not be downloaded"),
    )

    output_path = tmp_path / "inline.png"
    result = MiniMaxImage().execute(
        {
            "prompt": "A paper-cut forest",
            "response_format": "base64",
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert output_path.read_bytes() == image_bytes
    assert result.data["response_format"] == "base64"


def test_base_response_error_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json_data={
                "base_resp": {
                    "status_code": 1008,
                    "status_msg": "insufficient balance",
                }
            }
        ),
    )

    result = MiniMaxImage().execute({"prompt": "A mountain cabin"})

    assert not result.success
    assert result.error == "MiniMax API error 1008: insufficient balance"


def test_width_and_height_must_be_provided_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: pytest.fail("invalid inputs must not call the API"),
    )

    result = MiniMaxImage().execute(
        {"prompt": "A mountain cabin", "width": 1024}
    )

    assert not result.success
    assert "width and height must be set together" in (result.error or "")
