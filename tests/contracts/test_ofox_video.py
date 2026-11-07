"""Contract tests for the OfoxAI unified video-generation gateway adapter.

All HTTP calls are mocked. This suite must never create a paid task.
"""

from __future__ import annotations

import pytest

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.video.ofox_video import OfoxVideo


class _FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self._payload}")


class TestContract:
    def test_identity_and_capabilities(self):
        assert issubclass(OfoxVideo, BaseTool)
        tool = OfoxVideo()
        assert tool.name == "ofox_video"
        assert tool.provider == "ofox"
        assert tool.capability == "video_generation"
        assert tool.runtime == ToolRuntime.API
        assert tool.supports["text_to_video"] is True
        assert tool.supports["image_to_video"] is True
        assert tool.supports["local_image_data_uri"] is False
        assert "env:OFOX_API_KEY" in tool.dependencies

    def test_status_requires_ofox_api_key(self, monkeypatch):
        monkeypatch.delenv("OFOX_API_KEY", raising=False)
        assert OfoxVideo().get_status() == ToolStatus.UNAVAILABLE
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        assert OfoxVideo().get_status() == ToolStatus.AVAILABLE

    def test_status_rejects_bearer_prefixed_key(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "Bearer fake-ofox-key")
        assert OfoxVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_default_model_and_matrix(self):
        assert OfoxVideo.DEFAULT_MODEL == "bytedance/seedance-2.5"
        assert "bytedance/seedance-2.5" in OfoxVideo.MODELS
        assert "alibaba/wan-3.0-prime" in OfoxVideo.MODELS
        assert "minimax/hailuo-3" in OfoxVideo.MODELS


class TestPayload:
    def test_text_to_video_payload(self):
        payload = OfoxVideo()._build_payload(
            {
                "prompt": "A golden retriever running on the beach at sunset",
                "duration": 5,
                "resolution": "1080p",
                "aspect_ratio": "16:9",
            }
        )
        assert payload == {
            "model": "bytedance/seedance-2.5",
            "duration": 5,
            "resolution": "1080p",
            "aspect_ratio": "16:9",
            "generate_audio": True,
            "prompt": "A golden retriever running on the beach at sunset",
        }

    def test_image_to_video_uses_frame_images_contract(self):
        payload = OfoxVideo()._build_payload(
            {
                "prompt": "Make the dog start running",
                "operation": "image_to_video",
                "model": "bytedance/seedance-2.0",
                "first_frame_url": "https://example.com/dog.jpg",
            }
        )
        assert payload["frame_images"] == [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/dog.jpg"},
                "frame_type": "first_frame",
            }
        ]

    def test_first_last_frame_payload(self):
        payload = OfoxVideo()._build_payload(
            {
                "operation": "first_last_frame",
                "prompt": "interpolate",
                "first_frame_url": "https://example.com/a.jpg",
                "last_frame_url": "https://example.com/b.jpg",
            }
        )
        frame_types = [f["frame_type"] for f in payload["frame_images"]]
        assert frame_types == ["first_frame", "last_frame"]

    def test_provider_pinning(self):
        payload = OfoxVideo()._build_payload(
            {"prompt": "x", "provider_type": "byteplus"}
        )
        assert payload["provider"] == {"type": "byteplus"}

    @pytest.mark.parametrize(
        "inputs, message",
        [
            ({"prompt": ""}, "prompt"),
            ({"prompt": "x", "model": "no/such-model"}, "unknown model"),
            (
                {"prompt": "x", "model": "bytedance/seedance-2.0-fast",
                 "resolution": "1080p"},
                "resolution",
            ),
            ({"prompt": "x", "aspect_ratio": "99:1"}, "aspect ratio"),
            ({"prompt": "x", "duration": 999}, "duration"),
            (
                {"prompt": "x", "operation": "image_to_video"},
                "first_frame_url",
            ),
            (
                {"prompt": "x", "operation": "image_to_video",
                 "first_frame_url": "http://insecure.example/a.jpg"},
                "https",
            ),
            (
                {"prompt": "x", "operation": "first_last_frame",
                 "first_frame_url": "https://example.com/a.jpg"},
                "last_frame_url",
            ),
        ],
    )
    def test_invalid_payload_rejected(self, inputs, message):
        with pytest.raises(ValueError, match=message):
            OfoxVideo()._build_payload(inputs)


class TestTaskActions:
    def test_create_uses_official_endpoint_bearer_auth_and_body(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured.update(url=url, headers=headers, json=json)
            return _FakeResponse({"id": "vgen_abc123", "status": "pending"})

        monkeypatch.setattr("requests.post", fake_post)
        result = OfoxVideo().execute(
            {
                "task_action": "create",
                "prompt": "A paper bird takes flight",
                "duration": 5,
                "resolution": "720p",
                "aspect_ratio": "16:9",
            }
        )

        assert result.success is True
        assert result.data["task_id"] == "vgen_abc123"
        assert result.data["status"] == "submitted"
        assert captured["url"] == "https://api.ofox.ai/v1/videos"
        assert captured["headers"]["Authorization"] == "Bearer fake-ofox-key"
        assert captured["json"]["model"] == "bytedance/seedance-2.5"
        assert captured["json"]["prompt"] == "A paper bird takes flight"

    def test_query_uses_get_and_returns_task(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        captured = {}

        def fake_get(url, *, headers, timeout):
            captured.update(url=url, headers=headers)
            return _FakeResponse(
                {
                    "id": "vgen_abc123",
                    "status": "completed",
                    "mirror_urls": ["https://cdn.ofox.ai/v/out.mp4?sig=x"],
                    "usage": {"video_seconds": 5, "video_cost": "0.4000000000"},
                }
            )

        monkeypatch.setattr("requests.get", fake_get)
        result = OfoxVideo().execute(
            {"task_action": "query", "task_id": "vgen_abc123"}
        )
        assert result.success is True
        assert result.data["task"]["status"] == "completed"
        assert result.cost_usd == pytest.approx(0.4)
        assert captured["url"].endswith("/v1/videos/vgen_abc123")
        assert captured["headers"]["Authorization"] == "Bearer fake-ofox-key"

    def test_cancel_uses_delete(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        captured = {}

        def fake_delete(url, *, headers, timeout):
            captured.update(url=url)
            return _FakeResponse({})

        monkeypatch.setattr("requests.delete", fake_delete)
        result = OfoxVideo().execute(
            {"task_action": "cancel", "task_id": "vgen_abc123"}
        )
        assert result.success is True
        assert result.data == {"task_id": "vgen_abc123", "status": "cancel_requested"}
        assert captured["url"].endswith("/v1/videos/vgen_abc123")

    def test_generate_polls_and_downloads(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        calls = {"post": 0, "task_get": 0, "download_get": 0}

        def fake_post(url, *, headers, json, timeout):
            calls["post"] += 1
            return _FakeResponse({"id": "vgen_abc123", "status": "pending"})

        def fake_get(url, *, headers=None, timeout):
            if url.endswith("/vgen_abc123"):
                calls["task_get"] += 1
                return _FakeResponse(
                    {
                        "id": "vgen_abc123",
                        "model": "bytedance/seedance-2.5",
                        "status": "completed",
                        "mirror_urls": ["https://cdn.ofox.ai/v/out.mp4?sig=x"],
                        "unsigned_urls": ["https://upstream.example/out.mp4"],
                        "usage": {"video_seconds": 5, "video_cost": "0.4"},
                    }
                )
            calls["download_get"] += 1
            return _FakeResponse(content=b"fake-mp4")

        monkeypatch.setattr("requests.post", fake_post)
        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "tools.video._shared.probe_output",
            lambda *_: {"duration_seconds": 5.0, "video_width": 1280},
        )

        output = tmp_path / "ofox.mp4"
        result = OfoxVideo().execute(
            {
                "prompt": "A paper bird takes flight",
                "poll_interval_seconds": 1,
                "output_path": str(output),
            }
        )
        assert result.success is True
        assert output.read_bytes() == b"fake-mp4"
        # CDN mirror preferred over upstream unsigned URL.
        assert result.data["video_url"] == "https://cdn.ofox.ai/v/out.mp4?sig=x"
        assert result.cost_usd == pytest.approx(0.4)
        assert result.artifacts == [str(output)]
        assert calls == {"post": 1, "task_get": 1, "download_get": 1}

    def test_failed_task_returns_error_with_task_id(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")

        monkeypatch.setattr(
            "requests.post",
            lambda *a, **k: _FakeResponse({"id": "vgen_fail", "status": "pending"}),
        )
        monkeypatch.setattr(
            "requests.get",
            lambda *a, **k: _FakeResponse(
                {
                    "id": "vgen_fail",
                    "status": "failed",
                    "error": {"code": "UpstreamError", "message": "model overloaded"},
                }
            ),
        )
        monkeypatch.setattr("time.sleep", lambda *_: None)
        result = OfoxVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["task_id"] == "vgen_fail"
        assert result.data["status"] == "failed"
        assert "model overloaded" in result.error


class TestResultUrlFallback:
    def test_mirror_preferred_over_unsigned(self):
        url = OfoxVideo._result_url(
            {
                "mirror_urls": ["https://cdn.ofox.ai/v/out.mp4?sig=x"],
                "unsigned_urls": ["https://upstream.example/out.mp4"],
            }
        )
        assert url == "https://cdn.ofox.ai/v/out.mp4?sig=x"

    def test_falls_back_to_unsigned_when_no_mirror(self):
        # The live gateway returns unsigned_urls with no mirror_urls; the tool
        # must still resolve a download URL from the upstream address.
        url = OfoxVideo._result_url(
            {"unsigned_urls": ["https://upstream.example/out.mp4"]}
        )
        assert url == "https://upstream.example/out.mp4"

    def test_empty_mirror_list_falls_back_to_unsigned(self):
        url = OfoxVideo._result_url(
            {
                "mirror_urls": [],
                "unsigned_urls": ["https://upstream.example/out.mp4"],
            }
        )
        assert url == "https://upstream.example/out.mp4"

    def test_nested_output_url_fallback(self):
        url = OfoxVideo._result_url({"output": {"url": "https://x.example/o.mp4"}})
        assert url == "https://x.example/o.mp4"

    def test_no_url_returns_none(self):
        assert OfoxVideo._result_url({"mirror_urls": [], "unsigned_urls": []}) is None
        assert OfoxVideo._result_url({}) is None

    def test_generate_downloads_from_unsigned_when_mirror_absent(
        self, monkeypatch, tmp_path
    ):
        # End-to-end mirror of the live gateway response shape: a completed task
        # with only unsigned_urls still polls, resolves, and downloads.
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")
        downloaded_from = {}

        monkeypatch.setattr(
            "requests.post",
            lambda *a, **k: _FakeResponse({"id": "vgen_mirrorless", "status": "pending"}),
        )

        def fake_get(url, *, headers=None, timeout):
            if url.endswith("/vgen_mirrorless"):
                return _FakeResponse(
                    {
                        "id": "vgen_mirrorless",
                        "model": "bytedance/seedance-2.0-mini",
                        "status": "completed",
                        "unsigned_urls": ["https://upstream.example/out.mp4"],
                        "usage": {"video_seconds": 5, "video_cost": "0.1"},
                    }
                )
            downloaded_from["url"] = url
            downloaded_from["headers"] = headers
            return _FakeResponse(content=b"fake-mp4")

        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "tools.video._shared.probe_output",
            lambda *_: {"duration_seconds": 5.0},
        )

        output = tmp_path / "ofox.mp4"
        result = OfoxVideo().execute(
            {"prompt": "x", "output_path": str(output)}
        )
        assert result.success is True
        assert output.read_bytes() == b"fake-mp4"
        assert result.data["video_url"] == "https://upstream.example/out.mp4"
        assert downloaded_from["url"] == "https://upstream.example/out.mp4"
        # Bearer token must NOT be sent to a non-ofox upstream/CDN host.
        assert not downloaded_from["headers"]
        assert result.cost_usd == pytest.approx(0.1)


class TestInputSafety:
    @pytest.mark.parametrize(
        "inputs, message",
        [
            ({"task_action": "create", "prompt": ""}, "prompt"),
            (
                {"task_action": "create", "prompt": "x", "operation": "image_to_video"},
                "first_frame_url",
            ),
            ({"task_action": "query", "task_id": "../not-valid"}, "task_id"),
            ({"task_action": "query"}, "task_id"),
        ],
    )
    def test_invalid_input_never_reaches_network(self, inputs, message, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid input must not call the network")

        monkeypatch.setattr("requests.post", fail_network)
        monkeypatch.setattr("requests.get", fail_network)
        monkeypatch.setattr("requests.delete", fail_network)
        result = OfoxVideo().execute(inputs)
        assert result.success is False
        assert message in result.error.lower()

    def test_rejects_bearer_prefix_before_network(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "Bearer fake-ofox-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid API key config must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        result = OfoxVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert "remove the 'Bearer ' prefix" in result.error

    def test_missing_key_reports_install_instructions(self, monkeypatch):
        monkeypatch.delenv("OFOX_API_KEY", raising=False)
        result = OfoxVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert "OFOX_API_KEY not set" in result.error

    def test_errors_redact_api_key(self, monkeypatch):
        api_key = "unit-test-api-key-redaction-marker"
        monkeypatch.setenv("OFOX_API_KEY", api_key)

        def failing_post(*args, **kwargs):
            raise RuntimeError(f"request failed using {api_key}")

        monkeypatch.setattr("requests.post", failing_post)
        result = OfoxVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert api_key not in result.error
        assert "[redacted]" in result.error

    def test_download_errors_redact_signed_url_and_preserve_task_id(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")

        monkeypatch.setattr(
            "requests.post",
            lambda *a, **k: _FakeResponse({"id": "vgen_paid", "status": "pending"}),
        )

        def fake_get(url, **kwargs):
            if url.endswith("/vgen_paid"):
                return _FakeResponse(
                    {
                        "id": "vgen_paid",
                        "status": "completed",
                        "mirror_urls": [
                            "https://cdn.ofox.ai/v/out.mp4?X-Signature=secret-marker"
                        ],
                    }
                )
            raise RuntimeError(f"download failed: {url}")

        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        result = OfoxVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["task_id"] == "vgen_paid"
        assert result.data["recovery_action"] == "query"
        assert "secret-marker" not in result.error
        assert "?[redacted]" in result.error


class TestDryRun:
    def test_dry_run_is_offline_and_never_submits(self, monkeypatch):
        monkeypatch.setenv("OFOX_API_KEY", "fake-ofox-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("dry_run must not call the network")

        monkeypatch.setattr("requests.post", fail_network)
        result = OfoxVideo().dry_run(
            {"prompt": "A paper bird takes flight", "duration": 5, "resolution": "720p"}
        )
        assert result["would_execute"] is False
        assert result["paid_submission"] is False
        assert result["valid"] is True
        assert result["api_contract"] == {
            "create": "POST https://api.ofox.ai/v1/videos",
            "query": "GET https://api.ofox.ai/v1/videos/{id}",
            "cancel": "DELETE https://api.ofox.ai/v1/videos/{id}",
        }
        assert "fake-ofox-key" not in str(result)
        assert "authorization" not in str(result).lower()

    def test_estimated_cost_used_for_budget_reservation(self):
        tool = OfoxVideo()
        assert tool.estimate_cost({"prompt": "x"}) == 0.0
        assert tool.estimate_cost({"prompt": "x", "estimated_cost_usd": 0.4}) == 0.4
        with pytest.raises(ValueError, match="negative"):
            tool.estimate_cost({"prompt": "x", "estimated_cost_usd": -1})
