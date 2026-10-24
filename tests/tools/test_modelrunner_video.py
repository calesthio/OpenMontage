"""Behavioral tests for the ModelRunner tools with a faked `requests` module.

Covers the submit -> poll -> result -> download cycle for all four
capabilities, the storage-upload path for image-to-video, the auth boundary
(the API key never leaves the first-party hosts), and the error paths
(FAILED, COMPLETED-with-error, HTTP errors, poll timeout on a fake monotonic
clock). No network access and no API key required.

Run: pytest tests/tools/test_modelrunner_video.py -v
"""

from __future__ import annotations

import sys
import types

import pytest

from tools import modelrunner_client
from tools.audio.modelrunner_music import ModelRunnerMusic
from tools.audio.modelrunner_tts import ModelRunnerTTS
from tools.graphics.modelrunner_image import ModelRunnerImage
from tools.video.modelrunner_video import ModelRunnerVideo

REQUEST_ID = "req_ABCDEFGHIJKLMNOPQ"
STATUS_URL = f"https://queue.modelrunner.run/x/y/requests/{REQUEST_ID}/status"
RESPONSE_URL = f"https://queue.modelrunner.run/x/y/requests/{REQUEST_ID}"


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200, text="", headers=None):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code
        self.text = text or str(self._payload)
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def fake_requests(monkeypatch):
    """Install a fake `requests` module, a fake monotonic clock, and call logs.

    Queue items may be FakeResponse objects or Exceptions (raised to simulate
    transport failures). time.sleep advances the fake clock so the poll
    deadline logic is exercised for real.
    """
    calls = {"post": [], "get": [], "put": []}
    queues = {"post": [], "get": [], "put": []}

    def handler(method):
        def call(url, **kwargs):
            body = kwargs.get("data")
            if hasattr(body, "read"):
                # requests consumes streamed bodies; record the actual bytes.
                kwargs["data"] = body.read()
            calls[method].append({"url": url, **kwargs})
            if not queues[method]:
                raise AssertionError(f"Unexpected {method.upper()} to {url}")
            item = queues[method].pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return call

    module = types.ModuleType("requests")
    module.post = handler("post")
    module.get = handler("get")
    module.put = handler("put")
    monkeypatch.setitem(sys.modules, "requests", module)
    monkeypatch.setenv("MODELRUNNER_KEY", "test-key")

    clock = {"now": 0.0}
    monkeypatch.setattr(modelrunner_client.time, "sleep", lambda s: clock.__setitem__("now", clock["now"] + s))
    monkeypatch.setattr(modelrunner_client.time, "monotonic", lambda: clock["now"])

    return types.SimpleNamespace(calls=calls, queues=queues, clock=clock)


SUBMITTED = FakeResponse({
    "status": "IN_QUEUE", "request_id": REQUEST_ID,
    "status_url": STATUS_URL, "response_url": RESPONSE_URL,
    "cancel_url": f"{RESPONSE_URL}/cancel", "logs": [],
})


def in_progress() -> FakeResponse:
    return FakeResponse({"status": "IN_PROGRESS", "request_id": REQUEST_ID,
                         "status_url": STATUS_URL, "response_url": RESPONSE_URL})


def completed_status() -> FakeResponse:
    return FakeResponse({"status": "COMPLETED", "request_id": REQUEST_ID,
                         "status_url": STATUS_URL, "response_url": RESPONSE_URL})


def result(output) -> FakeResponse:
    return FakeResponse({"id": REQUEST_ID, "status": "COMPLETED", "output": output})


# ------------------------------------------------------------------
# Happy paths
# ------------------------------------------------------------------

class TestVideoExecute:

    def test_text_to_video_round_trip(self, fake_requests, tmp_path):
        out = tmp_path / "clip.mp4"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            in_progress(),
            completed_status(),
            result("https://media.modelrunner.ai/abc.mp4"),
            FakeResponse(content=b"MP4DATA"),  # download
        ]

        tool_result = ModelRunnerVideo().execute({
            "prompt": "a rocket launching",
            "duration": 5,
            "output_path": str(out),
        })

        assert tool_result.success is True, tool_result.error
        assert out.read_bytes() == b"MP4DATA"
        assert tool_result.data["request_id"] == REQUEST_ID
        assert tool_result.data["provider"] == "modelrunner"
        assert tool_result.cost_usd == pytest.approx(0.50)  # wan 2.7, 720P default, 5s

        submit = fake_requests.calls["post"][0]
        assert submit["url"] == "https://queue.modelrunner.run/wan-video/wan/v2.7/text-to-video"
        assert submit["headers"]["Authorization"] == "Key test-key"
        body = submit["json"]
        assert body == {
            "prompt": "a rocket launching", "duration": 5,
            "resolution": "720P", "aspect_ratio": "16:9",
        }

    def test_download_carries_no_auth_header(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/abc.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "c.mp4")})

        status_call, result_call, download_call = fake_requests.calls["get"]
        assert status_call["headers"]["Authorization"] == "Key test-key"
        assert result_call["headers"]["Authorization"] == "Key test-key"
        assert "Authorization" not in download_call.get("headers", {})

    def test_image_to_video_uploads_local_file(self, fake_requests, tmp_path):
        source = tmp_path / "frame.png"
        source.write_bytes(b"PNGDATA")

        fake_requests.queues["post"] = [
            FakeResponse({
                "upload_url": "https://storage.example-s3.com/presigned/frame.png",
                "file_url": "https://media.modelrunner.ai/frame.png",
            }),
            SUBMITTED,
        ]
        fake_requests.queues["put"] = [FakeResponse()]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/clip.mp4"),
            FakeResponse(content=b"MP4"),
        ]

        tool_result = ModelRunnerVideo().execute({
            "prompt": "the scene comes alive",
            "operation": "image_to_video",
            "image_path": str(source),
            "output_path": str(tmp_path / "out.mp4"),
        })

        assert tool_result.success is True, tool_result.error
        initiate, submit = fake_requests.calls["post"]
        assert initiate["url"].endswith("/storage/upload/initiate")
        assert initiate["json"]["content_type"] == "image/png"
        assert initiate["json"]["file_name"] == "frame.png"
        # The presigned PUT reuses the exact Content-Type and carries no auth.
        put = fake_requests.calls["put"][0]
        assert put["headers"] == {"Content-Type": "image/png"}
        assert put["data"] == b"PNGDATA"
        # The task suffix was rewritten to match the operation.
        assert submit["url"].endswith("/wan-video/wan/v2.7/image-to-video")
        assert submit["json"]["start_image_url"] == "https://media.modelrunner.ai/frame.png"
        assert "aspect_ratio" not in submit["json"]

    def test_remote_image_passes_through_without_upload(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/clip.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "operation": "image_to_video",
            "image_url": "https://cdn.example.com/hosted.png",
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is True, tool_result.error
        uploads = [c for c in fake_requests.calls["post"] if "upload" in c["url"]]
        assert not uploads


class TestImageExecute:

    def test_text_to_image_round_trip_with_multi_output_naming(self, fake_requests, tmp_path):
        out = tmp_path / "img.jpeg"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result([
                "https://media.modelrunner.ai/a.jpeg",
                "https://media.modelrunner.ai/b.jpeg",
            ]),
            FakeResponse(content=b"IMG1"),
            FakeResponse(content=b"IMG2"),
        ]

        tool_result = ModelRunnerImage().execute({
            "prompt": "a japanese garden",
            "output_path": str(out),
        })

        assert tool_result.success is True, tool_result.error
        assert out.read_bytes() == b"IMG1"
        assert (tmp_path / "img_2.jpeg").read_bytes() == b"IMG2"
        assert tool_result.artifacts == [str(out), str(tmp_path / "img_2.jpeg")]
        assert tool_result.cost_usd == pytest.approx(0.035)

        body = fake_requests.calls["post"][0]["json"]
        assert body["size"] == "2048x2048"  # seedream lite default


class TestTTSExecute:

    def test_kokoro_round_trip(self, fake_requests, tmp_path):
        out = tmp_path / "line.wav"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/line.wav"),
            FakeResponse(content=b"WAV"),
        ]

        tool_result = ModelRunnerTTS().execute({
            "text": "Welcome to the show.",
            "voice": "af_bella",
            "output_path": str(out),
        })

        assert tool_result.success is True, tool_result.error
        assert out.read_bytes() == b"WAV"
        submit = fake_requests.calls["post"][0]
        assert submit["url"].endswith("/hexgrad/kokoro-82m")
        assert submit["json"] == {"text": "Welcome to the show.", "voice": "af_bella"}


class TestMusicExecute:

    def test_lyria2_round_trip(self, fake_requests, tmp_path):
        out = tmp_path / "bed.wav"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/bed.wav"),
            FakeResponse(content=b"WAV"),
        ]

        tool_result = ModelRunnerMusic().execute({
            "prompt": "calm ambient piano",
            "output_path": str(out),
        })

        assert tool_result.success is True, tool_result.error
        assert tool_result.cost_usd == pytest.approx(0.06)
        assert fake_requests.calls["post"][0]["url"].endswith("/google/lyria2")


# ------------------------------------------------------------------
# Error paths
# ------------------------------------------------------------------

class TestErrorHandling:

    def test_failed_status_surfaces_provider_error(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"status": "FAILED", "request_id": REQUEST_ID,
                          "status_url": STATUS_URL, "response_url": RESPONSE_URL,
                          "error": "resolution not supported by this model"}),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "resolution not supported" in tool_result.error
        assert tool_result.data["request_id"] == REQUEST_ID
        assert tool_result.cost_usd == 0.0

    def test_completed_with_error_is_a_failure(self, fake_requests, tmp_path):
        """A normalized provider failure: COMPLETED status, non-empty error."""
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            FakeResponse({"id": REQUEST_ID, "status": "COMPLETED", "output": {},
                          "error": "upstream provider rejected the request"},
                         status_code=422),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "upstream provider rejected" in tool_result.error

    def test_http_error_at_submit_includes_api_message(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [
            FakeResponse({"error": "Payment Required", "message": "Insufficient balance",
                          "statusCode": 402}, status_code=402)
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "402" in tool_result.error
        assert "Insufficient balance" in tool_result.error
        assert tool_result.data == {}  # nothing was submitted, nothing to recover

    def test_poll_timeout_reports_recovery_urls_and_billing_caveat(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [in_progress() for _ in range(5)]
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "poll_interval": 1,
            "poll_timeout": 3,
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "IN_PROGRESS" in tool_result.error
        assert tool_result.data["billing_status"] == "possibly_billed"
        assert tool_result.data["request_id"] == REQUEST_ID
        assert tool_result.data["status_url"] == STATUS_URL
        assert tool_result.cost_usd == 0.0

    def test_transient_transport_errors_are_tolerated(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            ConnectionError("reset"),
            ConnectionError("reset"),
            completed_status(),
            result("https://media.modelrunner.ai/c.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "c.mp4")})
        assert tool_result.success is True, tool_result.error

    def test_missing_upload_file_fails_before_any_request(self, fake_requests, tmp_path):
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "operation": "image_to_video",
            "image_path": str(tmp_path / "nope.png"),
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "file not found" in tool_result.error
        assert not fake_requests.calls["post"], "must fail before spending an API call"

    def test_invalid_duration_fails_before_any_request(self, fake_requests, tmp_path):
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p", "duration": 99, "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "duration" in tool_result.error
        assert not fake_requests.calls["post"]


class TestAuthBoundary:

    def test_key_never_sent_to_off_host_status_url(self, fake_requests, tmp_path):
        """A queue envelope pointing off-host must be refused outright."""
        fake_requests.queues["post"] = [
            FakeResponse({
                "status": "IN_QUEUE", "request_id": REQUEST_ID,
                "status_url": f"https://evil.example.com/requests/{REQUEST_ID}/status",
                "response_url": RESPONSE_URL,
            })
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "refusing" in tool_result.error.lower()
        assert not fake_requests.calls["get"], "no request may reach the off-host URL"
        # The POST was accepted, so the job may exist server-side — the
        # request_id must survive for billing provenance.
        assert tool_result.data["request_id"] == REQUEST_ID
        assert tool_result.data["billing_status"] == "possibly_billed"

    def test_non_https_output_url_is_rejected(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("http://media.modelrunner.ai/abc.mp4"),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "https" in tool_result.error

    def test_private_address_output_url_is_rejected(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://192.168.1.10/abc.mp4"),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "private" in tool_result.error

    def test_authenticated_calls_refuse_redirects(self, fake_requests, tmp_path):
        """A redirect on an authenticated endpoint is an error, never followed."""
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse(status_code=302, headers={"location": "https://elsewhere.example.com/x"}),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "redirect" in tool_result.error.lower()
        assert len(fake_requests.calls["get"]) == 1, "the redirect target must never be requested"
        for call in fake_requests.calls["get"]:
            assert call.get("allow_redirects") is False

    def test_submit_sends_allow_redirects_false(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/a.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert fake_requests.calls["post"][0].get("allow_redirects") is False

    def test_download_redirect_hops_are_validated(self, fake_requests, tmp_path):
        """A same-class https redirect is followed; each hop is re-validated."""
        out = tmp_path / "o.mp4"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/a.mp4"),
            FakeResponse(status_code=302, headers={"location": "https://cdn.modelrunner.ai/a.mp4"}),
            FakeResponse(content=b"MP4DATA"),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(out)})
        assert tool_result.success is True, tool_result.error
        assert out.read_bytes() == b"MP4DATA"
        assert fake_requests.calls["get"][-1]["url"] == "https://cdn.modelrunner.ai/a.mp4"

    def test_download_redirect_to_private_host_is_rejected(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/a.mp4"),
            FakeResponse(status_code=302, headers={"location": "https://192.168.1.10/a.mp4"}),
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "private" in tool_result.error
        assert len(fake_requests.calls["get"]) == 3, "the private redirect target must never be requested"

    def test_incomplete_queue_envelope_keeps_request_id_provenance(self, fake_requests, tmp_path):
        """POST accepted but the envelope is unusable: the job may exist and
        bill — the failure must still carry the request_id."""
        fake_requests.queues["post"] = [
            FakeResponse({"status": "IN_QUEUE", "request_id": REQUEST_ID})  # no URLs
        ]
        tool_result = ModelRunnerVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert tool_result.success is False
        assert "incomplete queue envelope" in tool_result.error
        assert tool_result.data["request_id"] == REQUEST_ID
        assert tool_result.data["billing_status"] == "possibly_billed"
        assert tool_result.cost_usd == 0.0


class TestFailBeforeBilling:

    def test_pinned_i2v_endpoint_is_never_rewritten_to_text_sibling(self, fake_requests, tmp_path):
        """An explicitly pinned image-to-video endpoint with no image must fail
        — not silently submit a paid text-to-video job on the sibling route."""
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "model": "wan-video/wan/v2.7/image-to-video",
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "image" in tool_result.error
        assert not fake_requests.calls["post"], "no paid submission may happen"

    def test_pinned_i2v_endpoint_with_image_submits_to_that_route(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/c.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "model": "bytedance/seedance-v2-mini/image-to-video",
            "image_url": "https://cdn.example.com/hosted.png",
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is True, tool_result.error
        submit = fake_requests.calls["post"][0]
        assert submit["url"].endswith("/bytedance/seedance-v2-mini/image-to-video")

    def test_extra_params_cannot_override_validated_fields(self, fake_requests, tmp_path):
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "duration": 5,
            "extra_params": {"duration": 999, "resolution": "8K"},
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "extra_params" in tool_result.error
        assert not fake_requests.calls["post"]

    def test_extra_params_passthrough_of_new_keys_still_works(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed_status(),
            result("https://media.modelrunner.ai/c.mp4"),
            FakeResponse(content=b"MP4"),
        ]
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "extra_params": {"experimental_flag": True},
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is True, tool_result.error
        assert fake_requests.calls["post"][0]["json"]["experimental_flag"] is True

    def test_malformed_poll_controls_fail_before_any_request(self, fake_requests, tmp_path):
        for bad in ({"poll_timeout": "soon"}, {"poll_interval": -1}):
            tool_result = ModelRunnerVideo().execute({
                "prompt": "p", "output_path": str(tmp_path / "o.mp4"), **bad,
            })
            assert tool_result.success is False
            assert "poll" in tool_result.error
            assert tool_result.data == {}, "nothing was submitted"
        assert not fake_requests.calls["post"]

    def test_invalid_payload_fails_before_media_upload(self, fake_requests, tmp_path):
        """Payload validation runs before the storage upload, so an invalid
        call never leaves an orphaned upload behind."""
        source = tmp_path / "frame.png"
        source.write_bytes(b"PNGDATA")
        tool_result = ModelRunnerVideo().execute({
            "prompt": "p",
            "operation": "image_to_video",
            "image_path": str(source),
            "duration": 99,
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert tool_result.success is False
        assert "duration" in tool_result.error
        assert not fake_requests.calls["post"], "no upload initiate, no submission"
        assert not fake_requests.calls["put"]
