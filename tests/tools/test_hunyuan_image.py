"""Unit tests for hunyuan_image — TokenHub 混元生图 3.0 tool."""

from __future__ import annotations

import json
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


def test_hunyuan_image_is_discovered_by_registry():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("hunyuan_image")
    assert tool is not None
    assert tool.provider == "hunyuan_cloud"
    assert tool.capability == "image_generation"
    assert tool.name == "hunyuan_image"


def test_hunyuan_image_metadata():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    info = tool.get_info()

    assert info["tier"] == "generate"
    assert info["stability"] == "experimental"
    assert info["runtime"] == "api"
    assert "text_to_image" in info["capabilities"]
    assert info["supports"]["seed"] is True
    assert info["supports"]["reference_image"] is True
    assert info["supports"]["prompt_rewrite"] is True
    assert info["supports"]["negative_prompt"] is False
    assert "env:TENCENT_TOKENHUB_API_KEY" in info["dependencies"]
    assert "visual-style" in info["agent_skills"]


def test_idempotency_includes_custom_watermark():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    base = {"prompt": "x"}
    assert tool.idempotency_key(base) != tool.idempotency_key(
        {**base, "logo_param": {"logo_url": "https://example.com/logo.png"}}
    )


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------


def test_status_unavailable_when_no_api_key(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.delenv("TENCENT_TOKENHUB_API_KEY", raising=False)
    assert HunyuanImage().get_status() == ToolStatus.UNAVAILABLE


def test_status_available_when_api_key_set(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "test-key-123")
    assert HunyuanImage().get_status() == ToolStatus.AVAILABLE


def test_api_key_filters_comment_like_values(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "# this-is-a-comment")
    assert HunyuanImage()._api_key() is None
    assert HunyuanImage().get_status() == ToolStatus.UNAVAILABLE


def test_api_key_strips_whitespace(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "  my-key  ")
    assert HunyuanImage()._api_key() == "my-key"


# ---------------------------------------------------------------------------
# Cost & runtime estimation
# ---------------------------------------------------------------------------


def test_estimate_cost():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    cost = tool.estimate_cost({})
    assert cost > 0
    assert cost == pytest.approx(0.08, rel=0.1)


def test_estimate_runtime():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    runtime = tool.estimate_runtime({})
    assert runtime == 120.0


# ---------------------------------------------------------------------------
# Payload construction (_build_payload)
# ---------------------------------------------------------------------------


def test_build_payload_minimal():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    payload = tool._build_payload({"prompt": "a cat"})
    assert payload == {"prompt": "a cat"}


def test_build_payload_all_params():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "resolution": "768:1024",
        "seed": 42,
        "revise": 0,
        "logo_add": 1,
        "images": ["https://example.com/ref.jpg"],
    })
    assert payload["prompt"] == "a cat"
    assert payload["resolution"] == "768:1024"
    assert payload["seed"] == 42
    assert payload["revise"] == 0
    assert payload["logo_add"] == 1
    assert payload["images"] == ["https://example.com/ref.jpg"]


def test_build_payload_with_logo_param():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "logo_param": {"logo_url": "https://example.com/wm.png"},
    })
    assert payload["logo_param"] == {"logo_url": "https://example.com/wm.png"}


def test_build_payload_logo_param_skips_empty():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    payload = tool._build_payload({
        "prompt": "a cat",
        "logo_param": {},
    })
    assert "logo_param" not in payload


def test_build_payload_omits_none_seed():
    from tools.graphics.hunyuan_image import HunyuanImage

    tool = HunyuanImage()
    payload = tool._build_payload({"prompt": "a cat", "seed": None})
    assert "seed" not in payload


# ---------------------------------------------------------------------------
# Image resolution (_resolve_images)
# ---------------------------------------------------------------------------


def test_resolve_images_passes_urls_through():
    from tools.graphics.hunyuan_image import HunyuanImage

    refs = [
        "https://example.com/a.jpg",
        "data:image/png;base64,abc123",
    ]
    resolved = HunyuanImage._resolve_images(refs)
    assert resolved == refs


def test_resolve_images_encodes_local_file(tmp_path):
    from tools.graphics.hunyuan_image import HunyuanImage

    img = tmp_path / "test.png"
    img.write_bytes(b"fake-png-data")

    resolved = HunyuanImage._resolve_images([str(img)])
    assert len(resolved) == 1
    assert resolved[0].startswith("data:image/png;base64,")


def test_resolve_images_raises_on_missing_file():
    from tools.graphics.hunyuan_image import HunyuanImage

    with pytest.raises(FileNotFoundError):
        HunyuanImage._resolve_images(["/nonexistent/path.jpg"])


def test_resolve_images_raises_on_oversized_file(tmp_path):
    from tools.graphics.hunyuan_image import HunyuanImage

    big = tmp_path / "big.jpg"
    big.write_bytes(b"x" * (7 * 1024 * 1024))  # 7MB > 6MB limit

    with pytest.raises(ValueError, match="too large"):
        HunyuanImage._resolve_images([str(big)])


def test_resolve_images_detects_mime_from_extension(tmp_path):
    from tools.graphics.hunyuan_image import HunyuanImage

    cases = [
        ("ref.jpg", "image/jpeg"),
        ("ref.jpeg", "image/jpeg"),
        ("ref.png", "image/png"),
        ("ref.bmp", "image/bmp"),
        ("ref.tiff", "image/tiff"),
        ("ref.tif", "image/tiff"),
        ("ref.webp", "image/webp"),
        ("ref.unknown", "image/png"),  # fallback
    ]
    for filename, expected_mime in cases:
        f = tmp_path / filename
        f.write_bytes(b"data")
        resolved = HunyuanImage._resolve_images([str(f)])
        assert resolved[0].startswith(f"data:{expected_mime};base64,")


# ---------------------------------------------------------------------------
# Output path resolution (_resolve_output_paths)
# ---------------------------------------------------------------------------


def test_resolve_output_paths_single():
    from tools.graphics.hunyuan_image import HunyuanImage

    paths = HunyuanImage._resolve_output_paths("/out/img.png", 1)
    assert len(paths) == 1
    assert paths[0] == Path("/out/img.png")


def test_resolve_output_paths_multi():
    from tools.graphics.hunyuan_image import HunyuanImage

    paths = HunyuanImage._resolve_output_paths("/out/img.png", 3)
    assert len(paths) == 3
    assert [p.name for p in paths] == ["img_1.png", "img_2.png", "img_3.png"]
    assert len(set(paths)) == 3


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


def test_auth_headers():
    from tools.graphics.hunyuan_image import HunyuanImage

    headers = HunyuanImage._auth_headers("my-api-key")
    assert headers["Authorization"] == "Bearer my-api-key"
    assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# JSON error handling
# ---------------------------------------------------------------------------


def test_json_or_raise_parses_valid_json():
    from tools.graphics.hunyuan_image import HunyuanImage

    class FakeResp:
        status_code = 200

        def json(self):
            return {"status": "ok"}

    assert HunyuanImage._json_or_raise(FakeResp()) == {"status": "ok"}


def test_json_or_raise_raises_on_invalid_json():
    from tools.graphics.hunyuan_image import HunyuanImage

    class FakeResp:
        status_code = 500

        def json(self):
            raise ValueError("not json")

    with pytest.raises(RuntimeError, match="Non-JSON response"):
        HunyuanImage._json_or_raise(FakeResp())


def test_check_response_passes_clean_payload():
    from tools.graphics.hunyuan_image import HunyuanImage

    HunyuanImage._check_response({"status": "completed"})  # no error -> no raise


def test_check_response_raises_on_error_field():
    from tools.graphics.hunyuan_image import HunyuanImage

    with pytest.raises(RuntimeError, match="TokenHub API error"):
        HunyuanImage._check_response({
            "error": {"code": "AUTH_FAILED", "message": "invalid key"},
        })


def test_check_response_raises_on_error_without_code():
    from tools.graphics.hunyuan_image import HunyuanImage

    with pytest.raises(RuntimeError, match="TokenHub API error"):
        HunyuanImage._check_response({"error": {"message": "something broke"}})


# ---------------------------------------------------------------------------
# Safe error redaction
# ---------------------------------------------------------------------------


def test_safe_error_redacts_api_key(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "secret-key-abc")
    msg = HunyuanImage._safe_error(Exception("failed with secret-key-abc"))
    assert "secret-key-abc" not in msg
    assert "[redacted]" in msg


def test_safe_error_preserves_other_text(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "sk-123")
    msg = HunyuanImage._safe_error(Exception("network timeout: connection refused"))
    assert "network timeout" in msg
    assert "sk-123" not in msg


# ---------------------------------------------------------------------------
# Execute guards
# ---------------------------------------------------------------------------


def test_execute_returns_error_without_api_key(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.delenv("TENCENT_TOKENHUB_API_KEY", raising=False)
    result = HunyuanImage().execute({"prompt": "a cat"})
    assert not result.success
    assert "TENCENT_TOKENHUB_API_KEY" in result.error


def test_image_selector_maps_shared_reference_input(monkeypatch, tmp_path):
    from tools.base_tool import ToolResult
    from tools.graphics.hunyuan_image import HunyuanImage
    from tools.graphics.image_selector import ImageSelector

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "test-key")
    tool = HunyuanImage()
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [tool])
    monkeypatch.setattr(
        selector,
        "_select_best_tool",
        lambda _inputs, _candidates, _context: (tool, None),
    )
    observed = {}

    def fake_execute(inputs):
        observed.update(inputs)
        return ToolResult(success=True, data={}, artifacts=[inputs["output_path"]])

    monkeypatch.setattr(tool, "execute", fake_execute)
    result = selector.execute(
        {
            "prompt": "adapt this frame",
            "preferred_provider": "hunyuan_cloud",
            "image_path": str(tmp_path / "reference.png"),
            "output_path": str(tmp_path / "out.png"),
        }
    )
    assert result.success
    assert observed["images"] == [str(tmp_path / "reference.png")]
    assert result.data["selected_tool"] == "hunyuan_image"


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_dry_run_no_side_effects(monkeypatch):
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "test-key")
    tool = HunyuanImage()
    info = tool.dry_run({"prompt": "a cat"})
    assert info["tool"] == "hunyuan_image"
    assert info["estimated_cost_usd"] > 0
    assert info["would_execute"] is True


# ---------------------------------------------------------------------------
# End-to-end with mocked API
# ---------------------------------------------------------------------------


def test_execute_full_flow_with_mocked_api(monkeypatch, tmp_path):
    """Simulate the full submit → poll → download flow."""
    from tools.graphics.hunyuan_image import HunyuanImage, _MODEL, _HOST

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "test-key")

    # Track calls across all mocked endpoints
    api_calls = []
    poll_count = [0]  # mutable counter for poll iteration

    class _FakeResp:
        status_code = 200
        def __init__(self, data, content=None):
            self._data = data
            self.content = content
        def json(self):
            return self._data
        def raise_for_status(self):
            pass

    submit_url = f"https://{_HOST}/v1/api/image/submit"
    query_url = f"https://{_HOST}/v1/api/image/query"

    # Safety sentinel: if a real network call slips through the mock,
    # this flag is flipped and we fail-fast instead of leaking files.
    mock_active = [False]

    def fake_post(url, *, json, headers, timeout):
        mock_active[0] = True
        api_calls.append(("post", url, json))
        if "submit" in url:
            return _FakeResp({"id": "job-001", "status": "queued"})
        elif "query" in url:
            poll_count[0] += 1
            if poll_count[0] == 1:
                return _FakeResp({"status": "running"})
            return _FakeResp({
                "status": "completed",
                "data": [{"url": "https://example.com/result.png"}],
            })
        raise RuntimeError(f"Unexpected URL: {url}")

    def fake_get(url, timeout):
        mock_active[0] = True
        api_calls.append(("get", url))
        return _FakeResp({}, content=b"fake-image-data")

    with (
        patch("requests.post", side_effect=fake_post),
        patch("requests.get", side_effect=fake_get),
    ):
        out = tmp_path / "gen.png"
        result = HunyuanImage().execute({
            "prompt": "a programmer coding",
            "resolution": "1024:1024",
            "seed": 12345,
            "revise": 1,
            "logo_add": 0,
            "output_path": str(out),
        })

    # Guard: mock must have been exercised — if not, a real API call leaked
    assert mock_active[0], (
        "Mock was never triggered — a real API call may have leaked. "
        "Check that requests.post / requests.get patching is effective."
    )

    assert result.success, result.error
    assert result.data["provider"] == "hunyuan_cloud"
    assert result.data["model"] == _MODEL
    assert result.data["task_id"] == "job-001"
    assert result.data["resolution"] == "1024:1024"
    assert result.data["images_generated"] == 1
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"fake-image-data"

    # Verify submit payload was correct
    submit_calls = [c for c in api_calls if "submit" in c[1]]
    assert len(submit_calls) == 1
    _, _, submit_body = submit_calls[0]
    assert submit_body["prompt"] == "a programmer coding"
    assert submit_body["resolution"] == "1024:1024"
    assert submit_body["seed"] == 12345
    assert submit_body["revise"] == 1
    assert submit_body["logo_add"] == 0
    assert submit_body["model"] == _MODEL

    # Verify polling happened (submit + at least 1 query + download)
    assert any("query" in c[1] for c in api_calls)
    assert any(c[0] == "get" for c in api_calls)


def test_execute_with_local_reference_images(monkeypatch, tmp_path):
    """Reference images from local paths should be base64-encoded in payload."""
    from tools.graphics.hunyuan_image import HunyuanImage

    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "test-key")

    ref_img = tmp_path / "ref.png"
    ref_img.write_bytes(b"reference-data")

    tool = HunyuanImage()
    payload = tool._build_payload({
        "prompt": "enhance this",
        "images": [str(ref_img)],
    })

    assert "images" in payload
    assert len(payload["images"]) == 1
    assert payload["images"][0].startswith("data:image/png;base64,")
