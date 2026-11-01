"""Contract tests for direct Volcengine Ark Seedance 2.0 video generation.

All HTTP calls are mocked.  This suite must never create a paid task.
"""

from __future__ import annotations

import base64
import wave

import pytest

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.video.seedance_ark import SeedanceArkVideo


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
        assert issubclass(SeedanceArkVideo, BaseTool)
        tool = SeedanceArkVideo()
        assert tool.name == "seedance_ark"
        assert tool.provider == "ark"
        assert tool.capability == "video_generation"
        assert tool.runtime == ToolRuntime.API
        assert tool.supports["text_to_video"] is True
        assert tool.supports["image_to_video"] is True
        assert tool.supports["reference_to_video"] is True
        assert "env:ARK_API_KEY" in tool.dependencies

    def test_status_requires_ark_api_key(self, monkeypatch):
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        assert SeedanceArkVideo().get_status() == ToolStatus.UNAVAILABLE
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        assert SeedanceArkVideo().get_status() == ToolStatus.AVAILABLE

    def test_official_model_ids(self):
        assert SeedanceArkVideo.MODEL_IDS == {
            "2.5": "doubao-seedance-2-5-260628",
            "standard": "doubao-seedance-2-0-260128",
            "fast": "doubao-seedance-2-0-fast-260128",
            "mini": "doubao-seedance-2-0-mini-260615",
        }

    def test_seedance_25_contract_and_limits(self):
        tool = SeedanceArkVideo()
        payload = tool._build_payload(
            {
                "prompt": "A continuous cinematic chase with synchronized sound",
                "model_variant": "2.5",
                "duration": 30,
                "resolution": "720p",
                "aspect_ratio": "16:9",
            }
        )
        assert payload["model"] == "doubao-seedance-2-5-260628"
        assert payload["duration"] == 30
        assert payload["generate_audio"] is True

        with pytest.raises(ValueError, match="custom_price_cny_per_million_tokens"):
            tool.estimate_cost(payload)


class TestTaskActions:
    def test_create_uses_official_endpoint_bearer_auth_and_body(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured.update(url=url, headers=headers, json=json, timeout=timeout)
            return _FakeResponse({"id": "cgt-test-123"})

        monkeypatch.setattr("requests.post", fake_post)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "A paper bird takes flight",
                "model_variant": "standard",
                "duration": 5,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "generate_audio": True,
                "watermark": False,
                "return_last_frame": True,
            }
        )

        assert result.success is True
        assert result.data["task_id"] == "cgt-test-123"
        assert result.data["status"] == "submitted"
        assert captured["url"] == (
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        )
        assert captured["headers"]["Authorization"] == "Bearer fake-ark-key"
        assert captured["json"] == {
            "model": "doubao-seedance-2-0-260128",
            "content": [{"type": "text", "text": "A paper bird takes flight"}],
            "duration": 5,
            "ratio": "16:9",
            "resolution": "720p",
            "generate_audio": True,
            "watermark": False,
            "return_last_frame": True,
        }

    def test_query_uses_get_and_returns_task_payload(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        captured = {}

        def fake_get(url, *, headers, timeout):
            captured.update(url=url, headers=headers, timeout=timeout)
            return _FakeResponse(
                {
                    "id": "cgt-test-123",
                    "status": "succeeded",
                    "content": {"video_url": "https://example.com/result.mp4"},
                    "usage": {"completion_tokens": 250000},
                }
            )

        monkeypatch.setattr("requests.get", fake_get)
        result = SeedanceArkVideo().execute(
            {"task_action": "query", "task_id": "cgt-test-123"}
        )

        assert result.success is True
        assert result.data["task"]["status"] == "succeeded"
        assert captured["url"].endswith(
            "/api/v3/contents/generations/tasks/cgt-test-123"
        )
        assert captured["headers"]["Authorization"] == "Bearer fake-ark-key"

    def test_cancel_uses_delete(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        captured = {}

        def fake_delete(url, *, headers, timeout):
            captured.update(url=url, headers=headers, timeout=timeout)
            return _FakeResponse({})

        monkeypatch.setattr("requests.delete", fake_delete)
        result = SeedanceArkVideo().execute(
            {"task_action": "cancel", "task_id": "cgt-test-123"}
        )

        assert result.success is True
        assert result.data == {
            "task_id": "cgt-test-123",
            "status": "cancel_requested",
        }
        assert captured["url"].endswith(
            "/api/v3/contents/generations/tasks/cgt-test-123"
        )

    def test_generate_polls_and_downloads_without_extra_submission(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        calls = {"post": 0, "task_get": 0, "download_get": 0}

        def fake_post(url, *, headers, json, timeout):
            calls["post"] += 1
            return _FakeResponse({"id": "cgt-test-123"})

        def fake_get(url, *, headers=None, timeout):
            if url.endswith("/cgt-test-123"):
                calls["task_get"] += 1
                return _FakeResponse(
                    {
                        "id": "cgt-test-123",
                        "model": "doubao-seedance-2-0-260128",
                        "status": "succeeded",
                        "content": {
                            "video_url": "https://example.com/result.mp4",
                            "last_frame_url": "https://example.com/last.png",
                        },
                        "duration": 5,
                        "resolution": "720p",
                        "ratio": "16:9",
                        "usage": {"completion_tokens": 250000},
                    }
                )
            calls["download_get"] += 1
            return _FakeResponse(content=b"fake-mp4")

        monkeypatch.setattr("requests.post", fake_post)
        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        monkeypatch.setattr(
            "tools.video._shared.probe_output",
            lambda *_: {"duration": 5.0, "width": 1280, "height": 720},
        )

        output = tmp_path / "ark.mp4"
        result = SeedanceArkVideo().execute(
            {
                "prompt": "A paper bird takes flight",
                "poll_interval_seconds": 0,
                "output_path": str(output),
            }
        )

        assert result.success is True
        assert output.read_bytes() == b"fake-mp4"
        assert result.data["task_id"] == "cgt-test-123"
        assert result.data["video_url"] == "https://example.com/result.mp4"
        assert result.data["last_frame_url"] == "https://example.com/last.png"
        assert calls == {"post": 1, "task_get": 1, "download_get": 1}


class TestInputSafety:
    def test_local_first_frame_is_embedded_without_fal_upload(
        self, monkeypatch, tmp_path
    ):
        from PIL import Image

        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        captured = {}
        image = tmp_path / "anchor.png"
        Image.new("RGB", (640, 640), "white").save(image)

        def fail_fal_upload(*args, **kwargs):
            raise AssertionError("Ark local references must never use FAL")

        def fake_post(url, *, headers, json, timeout):
            captured["payload"] = json
            return _FakeResponse({"id": "cgt-test-123"})

        monkeypatch.setattr("tools.video._shared.upload_image_fal", fail_fal_upload)
        monkeypatch.setattr("requests.post", fake_post)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "The bird opens its wings",
                "operation": "image_to_video",
                "reference_image_path": str(image),
            }
        )

        assert result.success is True
        media = captured["payload"]["content"][1]
        assert media["type"] == "image_url"
        assert media["role"] == "first_frame"
        prefix, encoded = media["image_url"]["url"].split(",", 1)
        assert prefix == "data:image/png;base64"
        assert base64.b64decode(encoded) == image.read_bytes()

    def test_reference_media_roles_follow_official_contract(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["payload"] = json
            return _FakeResponse({"id": "cgt-test-123"})

        monkeypatch.setattr("requests.post", fake_post)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "Match the supplied look and rhythm",
                "operation": "reference_to_video",
                "reference_image_urls": ["https://example.com/look.png"],
                "reference_video_urls": ["https://example.com/motion.mp4"],
                "reference_audio_urls": ["https://example.com/voice.mp3"],
            }
        )

        assert result.success is True
        assert captured["payload"]["content"][1:] == [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/look.png"},
                "role": "reference_image",
            },
            {
                "type": "video_url",
                "video_url": {"url": "https://example.com/motion.mp4"},
                "role": "reference_video",
            },
            {
                "type": "audio_url",
                "audio_url": {"url": "https://example.com/voice.mp3"},
                "role": "reference_audio",
            },
        ]

    @pytest.mark.parametrize(
        "inputs, message",
        [
            ({"task_action": "create", "prompt": ""}, "prompt"),
            (
                {
                    "task_action": "create",
                    "prompt": "x",
                    "duration": 3,
                },
                "duration",
            ),
            (
                {
                    "task_action": "create",
                    "prompt": "x",
                    "operation": "image_to_video",
                },
                "reference image",
            ),
            (
                {"task_action": "query", "task_id": "../not-valid"},
                "task_id",
            ),
        ],
    )
    def test_invalid_input_never_reaches_network(self, inputs, message, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid input must not call the network")

        monkeypatch.setattr("requests.post", fail_network)
        monkeypatch.setattr("requests.get", fail_network)
        monkeypatch.setattr("requests.delete", fail_network)
        result = SeedanceArkVideo().execute(inputs)
        assert result.success is False
        assert message in result.error.lower()

    def test_errors_redact_api_key(self, monkeypatch):
        api_key = "unit-test-api-key-redaction-marker"
        monkeypatch.setenv("ARK_API_KEY", api_key)

        def failing_post(*args, **kwargs):
            raise RuntimeError(f"request failed using {api_key}")

        monkeypatch.setattr("requests.post", failing_post)
        result = SeedanceArkVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert api_key not in result.error
        assert "[redacted]" in result.error

    def test_download_errors_redact_signed_url_and_preserve_task_id(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fake_post(*args, **kwargs):
            return _FakeResponse({"id": "cgt-paid-123"})

        def fake_get(url, **kwargs):
            if url.endswith("/cgt-paid-123"):
                return _FakeResponse(
                    {
                        "id": "cgt-paid-123",
                        "status": "succeeded",
                        "content": {
                            "video_url": (
                                "https://cdn.example/video.mp4"
                                "?X-Signature=unit-test-signature-marker"
                            )
                        },
                    }
                )
            raise RuntimeError(f"download failed: {url}")

        monkeypatch.setattr("requests.post", fake_post)
        monkeypatch.setattr("requests.get", fake_get)
        result = SeedanceArkVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["task_id"] == "cgt-paid-123"
        assert result.data["recovery_action"] == "query"
        assert "unit-test-signature-marker" not in result.error
        assert "?[redacted]" in result.error

    def test_terminal_failure_redacts_signed_input_url(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fake_post(*args, **kwargs):
            return _FakeResponse({"id": "cgt-paid-123"})

        def fake_get(*args, **kwargs):
            return _FakeResponse(
                {
                    "id": "cgt-paid-123",
                    "status": "failed",
                    "error": {
                        "code": "InputFetchFailed",
                        "message": (
                            "cannot fetch https://media.example/a.mp4"
                            "?X-Signature=unit-test-signature-marker"
                        ),
                    },
                }
            )

        monkeypatch.setattr("requests.post", fake_post)
        monkeypatch.setattr("requests.get", fake_get)
        result = SeedanceArkVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["task_id"] == "cgt-paid-123"
        assert "unit-test-signature-marker" not in result.error
        assert "?[redacted]" in result.error

    def test_corrupt_or_tiny_local_image_never_reaches_network(
        self, monkeypatch, tmp_path
    ):
        from PIL import Image

        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid local image must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_bytes(b"\x89PNG\r\n\x1a\nmock")
        corrupt_result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "x",
                "operation": "image_to_video",
                "reference_image_path": str(corrupt),
            }
        )
        assert corrupt_result.success is False
        assert "unreadable or corrupt" in corrupt_result.error

        tiny = tmp_path / "tiny.png"
        Image.new("RGB", (1, 1), "white").save(tiny)
        tiny_result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "x",
                "operation": "image_to_video",
                "reference_image_path": str(tiny),
            }
        )
        assert tiny_result.success is False
        assert "300 to 6000" in tiny_result.error

    def test_corrupt_or_tiny_image_data_uri_never_reaches_network(self, monkeypatch):
        from io import BytesIO

        from PIL import Image

        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid image Data URI must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        corrupt = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "x",
                "operation": "image_to_video",
                "reference_image_url": "data:image/png;base64,NOT-BASE64",
            }
        )
        assert corrupt.success is False
        assert "strict base64" in corrupt.error

        buffer = BytesIO()
        Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
        tiny_uri = "data:image/png;base64," + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
        tiny = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "x",
                "operation": "image_to_video",
                "reference_image_url": tiny_uri,
            }
        )
        assert tiny.success is False
        assert "300 to 6000" in tiny.error

    def test_rejects_bearer_prefix_before_network(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "Bearer fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid API Key config must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert "remove the 'Bearer ' prefix" in result.error

    def test_rejects_local_reference_video_before_network(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        video = tmp_path / "reference.mp4"
        video.write_bytes(b"not-a-real-video")

        def fail_network(*args, **kwargs):
            raise AssertionError("local video must not reach the Ark API")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "match this motion",
                "operation": "reference_to_video",
                "reference_video_path": str(video),
            }
        )
        assert result.success is False
        assert "reference_video_path is not supported by ark" in result.error.lower()

    def test_rejects_fast_1080p_before_network(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("unsupported resolution must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "x",
                "model_variant": "fast",
                "resolution": "1080p",
            }
        )
        assert result.success is False
        assert "only 480p or 720p" in result.error

    def test_short_local_audio_never_reaches_network(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        audio = tmp_path / "short.wav"
        with wave.open(str(audio), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(8000)
            writer.writeframes(b"\0\0" * 8000)

        def fail_network(*args, **kwargs):
            raise AssertionError("invalid local audio must not call network")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "match audio1",
                "operation": "reference_to_video",
                "reference_image_urls": ["https://example.com/look.png"],
                "reference_audio_path": str(audio),
            }
        )
        assert result.success is False
        assert "2 to 15 seconds" in result.error

    def test_invalid_exchange_rate_fails_before_paid_post(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        monkeypatch.setenv("ARK_CNY_PER_USD", "not-a-number")

        def fail_network(*args, **kwargs):
            raise AssertionError("local cost config error must precede paid POST")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert result.data == {}

    @pytest.mark.parametrize("exchange_rate", ["nan", "inf", "-inf"])
    def test_non_finite_exchange_rate_never_reaches_paid_post(
        self, monkeypatch, exchange_rate
    ):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        monkeypatch.setenv("ARK_CNY_PER_USD", exchange_rate)

        def fail_network(*args, **kwargs):
            raise AssertionError("non-finite exchange rate reached paid POST")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute({"task_action": "create", "prompt": "x"})
        assert result.success is False
        assert "finite" in result.error

    @pytest.mark.parametrize("exchange_rate", ["nan", "inf", "-inf"])
    def test_non_finite_exchange_rate_never_returns_query_cost(
        self, monkeypatch, exchange_rate
    ):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        monkeypatch.setenv("ARK_CNY_PER_USD", exchange_rate)
        monkeypatch.setattr(
            "requests.get",
            lambda *args, **kwargs: _FakeResponse(
                {
                    "id": "task-query-cost",
                    "status": "succeeded",
                    "model": "doubao-seedance-2-0-260128",
                    "usage": {"completion_tokens": 108_000},
                }
            ),
        )
        result = SeedanceArkVideo().execute(
            {"task_action": "query", "task_id": "task-query-cost"}
        )
        assert result.success is False
        assert "finite" in result.error

    @pytest.mark.parametrize("custom_price", ["nan", "inf", "-inf"])
    def test_non_finite_custom_price_never_returns_query_cost(
        self, monkeypatch, custom_price
    ):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        monkeypatch.setattr(
            "requests.get",
            lambda *args, **kwargs: _FakeResponse(
                {
                    "id": "task-query-custom-cost",
                    "status": "succeeded",
                    "model": "ep-custom-account-pricing",
                    "usage": {"completion_tokens": 108_000},
                }
            ),
        )
        result = SeedanceArkVideo().execute(
            {
                "task_action": "query",
                "task_id": "task-query-custom-cost",
                "custom_price_cny_per_million_tokens": custom_price,
            }
        )
        assert result.success is False
        assert "finite" in result.error

    def test_custom_query_without_price_reports_unknown_not_zero(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        monkeypatch.setattr(
            "requests.get",
            lambda *args, **kwargs: _FakeResponse(
                {
                    "id": "task-query-custom-unknown",
                    "status": "succeeded",
                    "model": "ep-custom-account-pricing",
                    "usage": {"completion_tokens": 100_000},
                }
            ),
        )
        result = SeedanceArkVideo().execute(
            {
                "task_action": "query",
                "task_id": "task-query-custom-unknown",
            }
        )
        assert result.success is True
        assert result.cost_usd is None
        assert (
            result.data["cost_estimate_status"]
            == "unknown_custom_model_or_missing_usage"
        )

    def test_query_retries_transient_server_error(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        calls = {"count": 0}

        def fake_get(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return _FakeResponse(
                    {"error": {"code": "InternalError"}},
                    status_code=503,
                )
            return _FakeResponse({"id": "cgt-test-123", "status": "running"})

        monkeypatch.setattr("requests.get", fake_get)
        monkeypatch.setattr("time.sleep", lambda *_: None)
        result = SeedanceArkVideo().execute(
            {"task_action": "query", "task_id": "cgt-test-123"}
        )
        assert result.success is True
        assert calls["count"] == 2

    def test_dry_run_is_offline_and_never_submits(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("dry_run must not call the network")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().dry_run(
            {
                "prompt": "A paper bird takes flight",
                "duration": 5,
                "resolution": "720p",
            }
        )
        assert result["would_execute"] is False
        assert result["paid_submission"] is False
        assert result["api_contract"] == {
            "create": (
                "POST https://ark.cn-beijing.volces.com/api/v3/"
                "contents/generations/tasks"
            ),
            "query": (
                "GET https://ark.cn-beijing.volces.com/api/v3/"
                "contents/generations/tasks/{task_id}"
            ),
            "cancel": (
                "DELETE https://ark.cn-beijing.volces.com/api/v3/"
                "contents/generations/tasks/{task_id}"
            ),
        }
        assert "authorization" not in str(result).lower()
        assert "fake-ark-key" not in str(result)


class TestOfficialCostFormula:
    def test_standard_720p_five_seconds_without_video(self):
        tool = SeedanceArkVideo()
        inputs = {
            "prompt": "x",
            "model_variant": "standard",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "16:9",
        }
        assert tool.estimate_token_usage(inputs) == 108000
        assert tool.estimate_cost_cny(inputs) == pytest.approx(4.968)

    def test_input_video_duration_uses_video_price(self):
        tool = SeedanceArkVideo()
        inputs = {
            "prompt": "x",
            "operation": "reference_to_video",
            "model_variant": "standard",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "reference_video_urls": ["https://example.com/motion.mp4"],
            "reference_video_durations": [2],
        }
        assert tool.estimate_token_usage(inputs) == 151200
        assert tool.estimate_cost_cny(inputs) == pytest.approx(4.2336)

    def test_missing_video_duration_uses_conservative_fifteen_seconds(self):
        tool = SeedanceArkVideo()
        inputs = {
            "prompt": "x",
            "operation": "reference_to_video",
            "model_variant": "standard",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "reference_video_urls": ["https://example.com/motion.mp4"],
        }
        assert tool.estimate_token_usage(inputs) == 432000
        assert tool.estimate_cost_cny(inputs) == pytest.approx(12.096)

    def test_custom_endpoint_cost_is_unknown_not_standard_price(self):
        tool = SeedanceArkVideo()
        inputs = {
            "prompt": "x",
            "model": "ep-custom-account-pricing",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "16:9",
        }
        with pytest.raises(ValueError, match="pricing is unknown"):
            tool.estimate_cost_cny(inputs)
        dry = tool.dry_run(inputs)
        assert dry["valid"] is False
        assert "pricing is unknown" in dry["error"]

    def test_custom_endpoint_requires_price_before_paid_post(self, monkeypatch):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("unknown custom price must precede paid POST")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "model": "ep-custom-account-pricing",
                "prompt": "x",
            }
        )
        assert result.success is False
        assert "pricing is unknown" in result.error

    def test_custom_endpoint_accepts_explicit_price(self):
        tool = SeedanceArkVideo()
        cost = tool.estimate_cost_cny(
            {
                "model": "ep-custom-account-pricing",
                "prompt": "x",
                "duration": 5,
                "resolution": "720p",
                "aspect_ratio": "16:9",
                "custom_price_cny_per_million_tokens": 50,
            }
        )
        assert cost == pytest.approx(5.4)

    @pytest.mark.parametrize("custom_price", ["nan", "inf", "-inf"])
    def test_non_finite_custom_price_never_reaches_paid_post(
        self, monkeypatch, custom_price
    ):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")

        def fail_network(*args, **kwargs):
            raise AssertionError("non-finite custom price reached paid POST")

        monkeypatch.setattr("requests.post", fail_network)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "model": "ep-custom-account-pricing",
                "custom_price_cny_per_million_tokens": custom_price,
                "prompt": "x",
            }
        )
        assert result.success is False
        assert "finite" in result.error

    def test_valid_audio_data_uri_reaches_mocked_create(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ARK_API_KEY", "fake-ark-key")
        audio = tmp_path / "two-seconds.wav"
        with wave.open(str(audio), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(8_000)
            writer.writeframes(b"\x00\x00" * 16_000)
        audio_uri = "data:audio/wav;base64," + base64.b64encode(
            audio.read_bytes()
        ).decode("ascii")
        observed = {}

        def fake_post(url, **kwargs):
            observed["payload"] = kwargs["json"]
            return _FakeResponse({"id": "task-audio-data-uri"})

        monkeypatch.setattr("requests.post", fake_post)
        result = SeedanceArkVideo().execute(
            {
                "task_action": "create",
                "prompt": "match this audio",
                "operation": "reference_to_video",
                "reference_image_url": "https://example.com/look.png",
                "reference_audio_url": audio_uri,
            }
        )
        assert result.success is True
        audio_items = [
            item
            for item in observed["payload"]["content"]
            if item["type"] == "audio_url"
        ]
        assert audio_items[0]["audio_url"]["url"] == audio_uri
