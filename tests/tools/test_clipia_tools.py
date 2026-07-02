"""Contract, status, and mocked-execution tests for the Clipia provider tools.

No network and no real API key are required: HTTP is faked by injecting a
stub ``requests`` module into ``sys.modules`` (the tools import requests
lazily inside ``execute()``, matching the other API tools).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

import tools.graphics.clipia_image as clipia_image
import tools.video.clipia_video as clipia_video
from tools.base_tool import ToolStatus
from tools.graphics.clipia_image import ClipiaImage
from tools.video.clipia_video import ClipiaVideo

API_BASE = "https://api.clipia.ai"


# ---------------------------------------------------------------------------
# Fake `requests` module
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, json_data: Any = None, content: bytes = b"", status_code: int = 200):
        self._json = json_data
        self.content = content
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FakeRequests.RequestException(f"HTTP {self.status_code}")


class FakeRequests:
    """Minimal stand-in for the `requests` module, routed by URL."""

    class RequestException(Exception):
        pass

    def __init__(self, post_response: FakeResponse, get_routes: dict[str, FakeResponse]):
        self._post_response = post_response
        self._get_routes = get_routes
        self.post_calls: list[dict[str, Any]] = []
        self.get_calls: list[str] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        return self._post_response

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_calls.append(url)
        for prefix, response in self._get_routes.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"unexpected GET {url}")


# ---------------------------------------------------------------------------
# Contract / metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_cls, capability",
    [(ClipiaVideo, "video_generation"), (ClipiaImage, "image_generation")],
)
def test_contract_metadata(tool_cls, capability):
    tool = tool_cls()
    assert tool.provider == "clipia"
    assert tool.capability == capability
    assert tool.runtime.value == "api"
    assert "prompt" in tool.input_schema["required"]
    # get_info() must serialize without touching the network.
    info = tool.get_info()
    assert info["name"] == tool.name
    assert info["fallback_tools"]


def test_video_default_model_constants_match_schema():
    schema_default = ClipiaVideo().input_schema["properties"]["model"]["default"]
    assert clipia_video._DEFAULT_T2V_MODEL == schema_default
    assert clipia_video._DEFAULT_I2V_MODEL == "seedance-2-fast-i2v"


def test_image_default_model_constant_matches_schema():
    schema_default = ClipiaImage().input_schema["properties"]["model"]["default"]
    assert clipia_image._DEFAULT_MODEL == schema_default


@pytest.mark.parametrize("tool_cls", [ClipiaVideo, ClipiaImage])
def test_estimate_default_model_matches_schema(tool_cls):
    tool = tool_cls()
    schema_default = tool.input_schema["properties"]["model"]["default"]
    assert tool.estimate_cost({}) == tool.estimate_cost({"model": schema_default})
    assert tool.estimate_cost({}) > 0


def test_estimate_cost_is_offline_and_scales():
    video = ClipiaVideo()
    # Per-second models scale with duration; flat models do not.
    assert video.estimate_cost({"duration": "10"}) == pytest.approx(
        2 * video.estimate_cost({"duration": "5"})
    )
    assert video.estimate_cost({"model": "sora-2", "duration": "5"}) == video.estimate_cost(
        {"model": "sora-2", "duration": "10"}
    )
    image = ClipiaImage()
    assert image.estimate_cost({"num_images": 4}) == pytest.approx(
        4 * image.estimate_cost({"num_images": 1})
    )


# ---------------------------------------------------------------------------
# Status / dependency behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_cls", [ClipiaVideo, ClipiaImage])
def test_status_reflects_api_key(tool_cls, monkeypatch):
    monkeypatch.delenv("CLIPIA_API_KEY", raising=False)
    assert tool_cls().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("CLIPIA_API_KEY", "clipia_test_dummy")
    assert tool_cls().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize("tool_cls", [ClipiaVideo, ClipiaImage])
def test_execute_without_key_fails_cleanly(tool_cls, monkeypatch):
    monkeypatch.delenv("CLIPIA_API_KEY", raising=False)
    result = tool_cls().execute({"prompt": "a test"})
    assert result.success is False
    assert "CLIPIA_API_KEY" in result.error


def test_image_to_video_requires_image_url(monkeypatch):
    monkeypatch.setenv("CLIPIA_API_KEY", "clipia_test_dummy")
    result = ClipiaVideo().execute({"prompt": "x", "operation": "image_to_video"})
    assert result.success is False
    assert "image_url" in result.error


# ---------------------------------------------------------------------------
# Registry discovery (runs against the real registry, still offline)
# ---------------------------------------------------------------------------


def test_registry_discovers_clipia_tools():
    from tools.tool_registry import registry

    registry.ensure_discovered()
    video_names = {t.name for t in registry.get_by_capability("video_generation")}
    image_names = {t.name for t in registry.get_by_capability("image_generation")}
    assert "clipia_video" in video_names
    assert "clipia_image" in image_names


# ---------------------------------------------------------------------------
# Mocked execution (sandbox-shaped: submit returns COMPLETED immediately)
# ---------------------------------------------------------------------------


def test_video_execute_happy_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIPIA_API_KEY", "clipia_test_dummy")
    request_url = f"{API_BASE}/v1/requests/req-vid-1"
    fake = FakeRequests(
        post_response=FakeResponse(
            {
                "request_id": "req-vid-1",
                "status": "COMPLETED",
                "queue_position": 0,
                "status_url": f"{request_url}/status",
                "response_url": request_url,
                "cost": 47,
            }
        ),
        get_routes={
            f"{request_url}/status": FakeResponse({"status": "COMPLETED"}),
            request_url: FakeResponse(
                {
                    "request_id": "req-vid-1",
                    "status": "COMPLETED",
                    "model": "seedance-2-fast-t2v",
                    "output": {
                        "video": {
                            "url": "https://media.example/sample.mp4",
                            "width": 1280,
                            "height": 720,
                            "duration": 5,
                        }
                    },
                    "cost": 47,
                }
            ),
            "https://media.example/sample.mp4": FakeResponse(content=b"fake-mp4-bytes"),
        },
    )
    monkeypatch.setitem(sys.modules, "requests", fake)

    out = tmp_path / "clip.mp4"
    result = ClipiaVideo().execute({"prompt": "a sunset, cinematic", "output_path": str(out)})

    assert result.success is True
    assert out.read_bytes() == b"fake-mp4-bytes"
    assert result.artifacts == [str(out)]
    assert result.data["provider"] == "clipia"
    assert result.data["request_id"] == "req-vid-1"
    assert result.data["cost_credits"] == 47
    assert result.data["sandbox"] is True
    assert result.cost_usd == pytest.approx(47 * 0.04)
    # Submit went to the right endpoint with the schema-default model.
    assert fake.post_calls[0]["url"] == f"{API_BASE}/v1/models/seedance-2-fast-t2v"
    assert fake.post_calls[0]["json"]["input"]["prompt"] == "a sunset, cinematic"
    assert "Idempotency-Key" in fake.post_calls[0]["headers"]


def test_image_execute_happy_path_multi_image(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIPIA_API_KEY", "clipia_test_dummy")
    request_url = f"{API_BASE}/v1/requests/req-img-1"
    fake = FakeRequests(
        post_response=FakeResponse(
            {
                "request_id": "req-img-1",
                "status": "COMPLETED",
                "queue_position": 0,
                "status_url": f"{request_url}/status",
                "response_url": request_url,
                "cost": 8,
            }
        ),
        get_routes={
            f"{request_url}/status": FakeResponse({"status": "COMPLETED"}),
            request_url: FakeResponse(
                {
                    "request_id": "req-img-1",
                    "status": "COMPLETED",
                    "model": "nano-banana-2",
                    "output": {
                        "images": [
                            {
                                "url": "https://media.example/a.webp",
                                "original_url": "https://media.example/a.png",
                                "width": 1024,
                                "height": 1024,
                            },
                            {
                                "url": "https://media.example/b.webp",
                                "original_url": "https://media.example/b.png",
                                "width": 1024,
                                "height": 1024,
                            },
                        ]
                    },
                    "cost": 8,
                }
            ),
            "https://media.example/a.png": FakeResponse(content=b"png-a"),
            "https://media.example/b.png": FakeResponse(content=b"png-b"),
        },
    )
    monkeypatch.setitem(sys.modules, "requests", fake)

    out = tmp_path / "img.png"
    result = ClipiaImage().execute(
        {"prompt": "a red apple", "num_images": 2, "output_path": str(out)}
    )

    assert result.success is True
    assert result.data["num_images"] == 2
    assert result.artifacts == [str(out), str(tmp_path / "img_2.png")]
    assert out.read_bytes() == b"png-a"
    assert (tmp_path / "img_2.png").read_bytes() == b"png-b"
    # original_url (full quality) preferred over the display-optimized url.
    assert "https://media.example/a.png" in fake.get_calls
    assert result.cost_usd == pytest.approx(8 * 0.04)
    assert fake.post_calls[0]["json"]["input"]["num_images"] == 2


@pytest.mark.parametrize("tool_cls", [ClipiaVideo, ClipiaImage])
def test_execute_surfaces_api_error_envelope(tool_cls, monkeypatch):
    monkeypatch.setenv("CLIPIA_API_KEY", "clipia_live_dummy")
    fake = FakeRequests(
        post_response=FakeResponse(
            {
                "error": {
                    "type": "invalid_request_error",
                    "code": "insufficient_credits",
                    "message": "Not enough credits.",
                }
            },
            status_code=402,
        ),
        get_routes={},
    )
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = tool_cls().execute({"prompt": "x"})
    assert result.success is False
    assert "insufficient_credits" in result.error
