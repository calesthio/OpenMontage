"""Regression tests: seedream_image must return every image it requests and bills for.

Covers:
- Multi-image output: all requested images must be written and returned
- Cost estimation: billed count matches delivered artifacts
- Single-image output: exact output path preserved
- Async polling: COMPLETED / FAILED / CANCELLED / timeout paths
- API key validation: graceful failure when FAL_KEY is unset
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _FakeResponse:
    def __init__(self, json_data: dict | None = None, status_code: int = 200, content: bytes = b""):
        self._json_data = json_data or {}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)

    def json(self):
        return self._json_data


def _build_submit_response(request_id: str = "req_123") -> _FakeResponse:
    return _FakeResponse({"request_id": request_id})


def _build_status_response(status: str, error: str | None = None) -> _FakeResponse:
    data = {"status": status}
    if error:
        data["error"] = error
    return _FakeResponse(data)


def _build_result_response(image_urls: list[str]) -> _FakeResponse:
    images = [{"url": url} for url in image_urls]
    return _FakeResponse({"images": images})


def _build_image_content(index: int) -> bytes:
    return f"SEEDREAM_IMAGE_{index}".encode()


@pytest.fixture
def seedream_tool(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-fal-key")
    from tools.graphics.seedream_image import SeedreamImage
    return SeedreamImage()


@pytest.fixture
def mock_requests(monkeypatch):
    mock_post = MagicMock()
    mock_get = MagicMock()
    fake_requests = types.ModuleType("requests")
    fake_requests.post = mock_post
    fake_requests.get = mock_get
    fake_requests.HTTPError = type("HTTPError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    return mock_post, mock_get


def _setup_mock_execution(mock_post, mock_get, num_images: int = 1, status: str = "COMPLETED",
                          error: str | None = None, extra_gets: list = None):
    """Helper to setup common mock execution flow."""
    mock_post.return_value = _build_submit_response()

    side_effects = [_build_status_response(status, error)]
    if status == "COMPLETED":
        urls = [f"http://img.url/{i}" for i in range(num_images)]
        side_effects.append(_build_result_response(urls))
        side_effects.extend([_FakeResponse(content=_build_image_content(i)) for i in range(num_images)])
    elif extra_gets:
        side_effects.extend(extra_gets)

    mock_get.side_effect = side_effects


# ========== Core Regression Tests ==========

class TestMultiOutputRegression:
    def test_all_requested_images_are_written(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=3)

        result = seedream_tool.execute({
            "prompt": "test", "num_images": 3,
            "output_format": "jpeg", "output_path": str(tmp_path / "gen.jpeg"),
        })

        assert result.success
        assert result.data["image_count"] == 3
        assert len(result.artifacts) == 3

        files = sorted(tmp_path.glob("*.jpeg"))
        assert len(files) == 3
        contents = {f.read_bytes() for f in files}
        assert contents == {b"SEEDREAM_IMAGE_0", b"SEEDREAM_IMAGE_1", b"SEEDREAM_IMAGE_2"}

    def test_artifacts_match_billed_count(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=4)

        inputs = {"prompt": "t", "num_images": 4, "output_path": str(tmp_path / "out.png")}
        result = seedream_tool.execute(inputs)
        billed = seedream_tool.estimate_cost(inputs)

        assert len(result.artifacts) == 4
        assert billed == pytest.approx(0.135 * 4)


class TestSingleOutput:
    def test_single_image_keeps_exact_path(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=1)

        out = tmp_path / "single.png"
        result = seedream_tool.execute({"prompt": "s", "num_images": 1, "output_path": str(out)})

        assert result.success
        assert result.artifacts == [str(out)]
        assert out.read_bytes() == b"SEEDREAM_IMAGE_0"


# ========== Cost Estimation (Parameterized) ==========

class TestCostEstimation:
    @pytest.mark.parametrize("size,expected", [
        ("square", 0.0675), ("landscape_4_3", 0.0675),
        ("portrait_4_3", 0.0675), ("auto_1K", 0.0675),
    ])
    def test_small_size_pricing(self, seedream_tool, size, expected):
        cost = seedream_tool.estimate_cost({"image_size": size, "num_images": 1})
        assert cost == pytest.approx(expected)

    @pytest.mark.parametrize("size,expected", [
        ("square_hd", 0.135), ("landscape_16_9", 0.135),
        ("portrait_16_9", 0.135), ("auto_2K", 0.135),
    ])
    def test_large_size_pricing(self, seedream_tool, size, expected):
        cost = seedream_tool.estimate_cost({"image_size": size, "num_images": 1})
        assert cost == pytest.approx(expected)

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_cost_scales_with_num_images(self, seedream_tool, n):
        cost = seedream_tool.estimate_cost({"image_size": "auto_2K", "num_images": n})
        assert cost == pytest.approx(round(0.135 * n, 4))

    def test_unknown_size_falls_back_to_high_price(self, seedream_tool):
        cost = seedream_tool.estimate_cost({"image_size": "unknown", "num_images": 1})
        assert cost == pytest.approx(0.135)

    def test_default_values(self, seedream_tool):
        cost = seedream_tool.estimate_cost({})
        assert cost == pytest.approx(0.135)


# ========== Async Polling States ==========

class TestAsyncPolling:
    def test_completed_on_first_poll(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=1)

        result = seedream_tool.execute({"prompt": "q", "output_path": str(tmp_path / "q.png")})
        assert result.success
        assert result.data["request_id"]

    @pytest.mark.parametrize("status,error_msg", [
        ("FAILED", "Content policy violation"),
        ("CANCELLED", None),
    ])
    def test_failed_states_return_error(self, seedream_tool, mock_requests, status, error_msg):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, status=status, error=error_msg)

        result = seedream_tool.execute({"prompt": "bad"})
        assert not result.success
        assert status in result.error

    def test_timeout_returns_error(self, seedream_tool, mock_requests):
        mock_post, mock_get = mock_requests
        mock_post.return_value = _build_submit_response()
        mock_get.side_effect = [_build_status_response("IN_PROGRESS")] * 100

        with patch("tools.graphics.seedream_image.time.sleep"):
            result = seedream_tool.execute({"prompt": "timeout"})
        assert not result.success
        assert "timed out" in result.error.lower()


# ========== Validation & Error Handling ==========

class TestValidation:
    @pytest.mark.parametrize("value", [0, 5, 1.5, True])
    def test_num_images_rejects_invalid_values(
        self, seedream_tool, mock_requests, value
    ):
        mock_post, _ = mock_requests
        result = seedream_tool.execute({"prompt": "t", "num_images": value})
        assert not result.success
        assert "num_images" in (result.error or "")
        mock_post.assert_not_called()

    def test_missing_api_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("FAL_KEY", raising=False)
        monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
        from tools.graphics.seedream_image import SeedreamImage
        result = SeedreamImage().execute({"prompt": "t"})
        assert not result.success
        assert "FAL_KEY" in result.error

    def test_status_available_with_key(self, seedream_tool):
        assert seedream_tool.get_status().name == "AVAILABLE"

    def test_status_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("FAL_KEY", raising=False)
        monkeypatch.delenv("FAL_AI_API_KEY", raising=False)
        from tools.graphics.seedream_image import SeedreamImage
        assert SeedreamImage().get_status().name == "UNAVAILABLE"

    def test_missing_request_id_raises_error(self, seedream_tool, mock_requests):
        mock_post, mock_get = mock_requests
        mock_post.return_value = _FakeResponse({})
        result = seedream_tool.execute({"prompt": "no id"})
        assert not result.success
        assert "request_id" in result.error.lower()

    def test_completed_without_images_raises_error(self, seedream_tool, mock_requests):
        mock_post, mock_get = mock_requests
        mock_post.return_value = _build_submit_response()
        mock_get.side_effect = [
            _build_status_response("COMPLETED"),
            _FakeResponse({"images": []}),
        ]
        result = seedream_tool.execute({"prompt": "empty"})
        assert not result.success
        assert "no images" in result.error.lower()


# ========== Metadata & Integration ==========

class TestMetadata:
    def test_provider_and_model_info(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=1)

        result = seedream_tool.execute({"prompt": "m", "output_path": str(tmp_path / "m.png")})
        assert result.data["provider"] == "seedream"
        assert result.data["model"] == "seedream_v5"
        assert result.model == "fal-ai/bytedance/seedream/v5"

    def test_cost_matches_estimate(self, seedream_tool, tmp_path, mock_requests):
        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=2)

        inputs = {"prompt": "c", "image_size": "square", "num_images": 2, "output_path": str(tmp_path / "c.jpeg")}
        result = seedream_tool.execute(inputs)
        assert result.cost_usd == pytest.approx(seedream_tool.estimate_cost(inputs))

    def test_image_selector_routes_count_and_returns_distinct_artifacts(
        self, seedream_tool, tmp_path, mock_requests, monkeypatch
    ):
        from tools.graphics.image_selector import ImageSelector

        mock_post, mock_get = mock_requests
        _setup_mock_execution(mock_post, mock_get, num_images=2)
        selector = ImageSelector()
        monkeypatch.setattr(selector, "_providers", lambda: [seedream_tool])

        result = selector.execute(
            {
                "prompt": "campaign artwork",
                "preferred_provider": "bytedance",
                "n": 2,
                "output_path": str(tmp_path / "selected.png"),
            }
        )

        assert result.success, result.error
        assert result.data["selected_tool"] == "seedream_image"
        assert len(set(result.artifacts)) == 2
        assert {Path(path).name for path in result.artifacts} == {
            "selected_1.png",
            "selected_2.png",
        }
