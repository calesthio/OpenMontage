"""Behavioral tests for the Atlas Cloud tools with a faked `requests` module.

Covers the submit -> poll -> download cycle, the media-upload path for
image-to-video, and the error paths (failed prediction, HTTP error, timeout).
No network access and no API key required.

Run: pytest tests/tools/test_atlas_video.py -v
"""

from __future__ import annotations

import sys
import types

import pytest

from tools import atlas_client
from tools.graphics.atlas_image import AtlasImage
from tools.video.atlas_video import AtlasVideo


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200, text=""):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code
        self.text = text or str(self._payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def fake_requests(monkeypatch):
    """Install a fake `requests` module and record every call made through it."""
    calls = {"post": [], "get": []}
    queues = {"post": [], "get": []}

    def fake_post(url, **kwargs):
        calls["post"].append({"url": url, **kwargs})
        if not queues["post"]:
            raise AssertionError(f"Unexpected POST to {url}")
        return queues["post"].pop(0)

    def fake_get(url, **kwargs):
        calls["get"].append({"url": url, **kwargs})
        if not queues["get"]:
            raise AssertionError(f"Unexpected GET to {url}")
        return queues["get"].pop(0)

    module = types.ModuleType("requests")
    module.post = fake_post
    module.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", module)
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    # Keep polling instantaneous.
    monkeypatch.setattr(atlas_client.time, "sleep", lambda _s: None)

    return types.SimpleNamespace(calls=calls, queues=queues)


SUBMITTED = FakeResponse({"code": 200, "data": {"id": "pred_abc123", "status": "processing"}})


def completed(url: str) -> FakeResponse:
    return FakeResponse({"code": 200, "data": {"id": "pred_abc123", "status": "completed", "outputs": [url]}})


# ------------------------------------------------------------------
# Happy paths
# ------------------------------------------------------------------

class TestAtlasVideoExecute:

    def test_text_to_video_round_trip(self, fake_requests, tmp_path):
        out = tmp_path / "clip.mp4"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {"status": "processing"}}),
            completed("https://storage.atlascloud.ai/outputs/clip.mp4"),
            FakeResponse(content=b"MP4DATA"),  # download
        ]

        result = AtlasVideo().execute({
            "prompt": "a rocket launching",
            "duration": 5,
            "output_path": str(out),
        })

        assert result.success is True, result.error
        assert out.read_bytes() == b"MP4DATA"
        assert result.data["prediction_id"] == "pred_abc123"
        assert result.data["provider"] == "atlascloud"
        assert result.cost_usd == pytest.approx(0.67)  # Seedance 2.5, 5s

        body = fake_requests.calls["post"][0]["json"]
        assert body["model"] == "bytedance/seedance-2.5/text-to-video"
        assert body["prompt"] == "a rocket launching"
        assert body["duration"] == 5
        assert body["ratio"] == "adaptive"
        assert body["resolution"] == "720p"

    def test_succeeded_status_is_treated_as_success(self, fake_requests, tmp_path):
        """Atlas documents both `completed` and `succeeded` as terminal success."""
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {"status": "succeeded", "outputs": ["https://x/c.mp4"]}}),
            FakeResponse(content=b"MP4"),
        ]
        result = AtlasVideo().execute({"prompt": "p", "output_path": str(tmp_path / "c.mp4")})
        assert result.success is True, result.error

    def test_image_to_video_uploads_local_file(self, fake_requests, tmp_path):
        source = tmp_path / "frame.png"
        source.write_bytes(b"PNGDATA")

        fake_requests.queues["post"] = [
            FakeResponse({"data": {"download_url": "https://storage.atlascloud.ai/uploads/frame.png"}}),
            SUBMITTED,
        ]
        fake_requests.queues["get"] = [
            completed("https://storage.atlascloud.ai/outputs/clip.mp4"),
            FakeResponse(content=b"MP4"),
        ]

        result = AtlasVideo().execute({
            "prompt": "the scene comes alive",
            "operation": "image_to_video",
            "image_path": str(source),
            "output_path": str(tmp_path / "out.mp4"),
        })

        assert result.success is True, result.error
        upload_call, generate_call = fake_requests.calls["post"]
        assert upload_call["url"].endswith("/model/uploadMedia")
        assert "files" in upload_call
        # The task suffix must have been rewritten to match the operation.
        assert generate_call["json"]["model"] == "bytedance/seedance-2.5/image-to-video"
        assert generate_call["json"]["image"] == "https://storage.atlascloud.ai/uploads/frame.png"

    def test_upload_accepts_bare_url_response_shape(self, fake_requests, tmp_path):
        """Older Atlas docs return {"url": ...} instead of {"data": {"download_url": ...}}."""
        source = tmp_path / "frame.png"
        source.write_bytes(b"PNG")

        fake_requests.queues["post"] = [
            FakeResponse({"url": "https://storage.atlascloud.ai/uploads/legacy.png"}),
            SUBMITTED,
        ]
        fake_requests.queues["get"] = [completed("https://x/c.mp4"), FakeResponse(content=b"MP4")]

        result = AtlasVideo().execute({
            "prompt": "p",
            "operation": "image_to_video",
            "reference_image_path": str(source),
            "output_path": str(tmp_path / "out.mp4"),
        })
        assert result.success is True, result.error
        assert fake_requests.calls["post"][1]["json"]["image"].endswith("legacy.png")


class TestReferenceToVideo:
    """The 12-asset multimodal path: @image1 / @audio1 style references."""

    def test_local_references_are_uploaded_and_remote_ones_pass_through(self, fake_requests, tmp_path):
        portrait = tmp_path / "cowgirl.png"
        portrait.write_bytes(b"PNG")
        track = tmp_path / "beat.mp3"
        track.write_bytes(b"MP3")

        fake_requests.queues["post"] = [
            FakeResponse({"data": {"download_url": "https://storage.atlascloud.ai/u/cowgirl.png"}}),
            FakeResponse({"data": {"download_url": "https://storage.atlascloud.ai/u/beat.mp3"}}),
            SUBMITTED,
        ]
        fake_requests.queues["get"] = [completed("https://x/c.mp4"), FakeResponse(content=b"MP4")]

        result = AtlasVideo().execute({
            "prompt": "@image1 raps the vocal in @audio1",
            "model": "bytedance/seedance-2.0/reference-to-video",
            "operation": "reference_to_video",
            "reference_images": [str(portrait), "https://cdn.example.com/already-hosted.png"],
            "reference_audios": [str(track)],
            "duration": 15,
            "output_path": str(tmp_path / "out.mp4"),
        })

        assert result.success is True, result.error
        body = fake_requests.calls["post"][-1]["json"]
        # Local file uploaded, hosted URL untouched, order preserved (@image1 = first).
        assert body["reference_images"] == [
            "https://storage.atlascloud.ai/u/cowgirl.png",
            "https://cdn.example.com/already-hosted.png",
        ]
        assert body["reference_audios"] == ["https://storage.atlascloud.ai/u/beat.mp3"]
        assert body["model"] == "bytedance/seedance-2.0/reference-to-video"
        # Only the two local files were uploaded, not the hosted one.
        uploads = [c for c in fake_requests.calls["post"] if c["url"].endswith("/uploadMedia")]
        assert len(uploads) == 2

    def test_reference_to_video_without_any_asset_is_rejected(self, fake_requests, tmp_path):
        result = AtlasVideo().execute({
            "prompt": "p",
            "operation": "reference_to_video",
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success is False
        assert "requires supported reference media" in result.error

    def test_reference_image_alone_satisfies_reference_to_video(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [completed("https://x/c.mp4"), FakeResponse(content=b"MP4")]
        result = AtlasVideo().execute({
            "prompt": "@image1 walks",
            "operation": "reference_to_video",
            "reference_images": ["https://cdn.example.com/a.png"],
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success is True, result.error

    def test_too_many_references_rejected_before_calling_api(self, fake_requests, tmp_path):
        result = AtlasVideo().execute({
            "prompt": "p",
            "model": "bytedance/seedance-2.0/reference-to-video",
            "operation": "reference_to_video",
            "reference_images": [f"https://x/{i}.png" for i in range(10)],
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success is False
        assert "at most 9" in result.error
        assert not fake_requests.calls["post"], "must fail before spending an API call"


class TestAtlasImageExecute:

    def test_text_to_image_round_trip(self, fake_requests, tmp_path):
        out = tmp_path / "img.png"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            completed("https://storage.atlascloud.ai/outputs/img.png"),
            FakeResponse(content=b"PNGDATA"),
        ]

        result = AtlasImage().execute({
            "prompt": "a japanese garden",
            "width": 2048,
            "height": 1152,
            "output_path": str(out),
        })

        assert result.success is True, result.error
        assert out.read_bytes() == b"PNGDATA"
        assert result.cost_usd == pytest.approx(0.045)

        body = fake_requests.calls["post"][0]["json"]
        assert body["model"] == "bytedance/seedream-v5.0-pro/text-to-image"
        assert body["size"] == "2048*1152"

    def test_auth_header_is_bearer(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [completed("https://x/i.png"), FakeResponse(content=b"P")]
        AtlasImage().execute({"prompt": "p", "output_path": str(tmp_path / "i.png")})
        assert fake_requests.calls["post"][0]["headers"]["Authorization"] == "Bearer test-key"


# ------------------------------------------------------------------
# Error paths
# ------------------------------------------------------------------

class TestErrorHandling:

    def test_failed_prediction_surfaces_error_message(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {
                "status": "failed",
                "error": "Invalid parameter: resolution not supported by this model",
            }}),
        ]
        result = AtlasVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False
        assert "resolution not supported" in result.error

    def test_http_error_includes_body(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [
            FakeResponse({"error": "insufficient balance"}, status_code=402, text="insufficient balance")
        ]
        result = AtlasVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False
        assert "402" in result.error
        assert "insufficient balance" in result.error

    def test_non_200_envelope_code_is_an_error(self, fake_requests, tmp_path):
        """Atlas can return a failure code inside an HTTP 200 envelope."""
        fake_requests.queues["post"] = [FakeResponse({"code": 400, "message": "unknown model"})]
        result = AtlasVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False
        assert "unknown model" in result.error

    def test_missing_prediction_id_is_an_error(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [FakeResponse({"code": 200, "data": {"status": "processing"}})]
        result = AtlasImage().execute({"prompt": "p", "output_path": str(tmp_path / "i.png")})
        assert result.success is False
        assert "prediction id" in result.error

    def test_poll_timeout_reports_prediction_id(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {"status": "processing"}}) for _ in range(5)
        ]
        result = AtlasVideo().execute({
            "prompt": "p",
            "poll_interval": 1,
            "poll_timeout": 3,
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success is False
        assert "pred_abc123" in result.error

    def test_completed_with_no_outputs_is_an_error(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {"status": "completed", "outputs": []}}),
        ]
        result = AtlasImage().execute({"prompt": "p", "output_path": str(tmp_path / "i.png")})
        assert result.success is False
        assert "no outputs" in result.error

    def test_missing_upload_file_is_an_error(self, fake_requests, tmp_path):
        result = AtlasVideo().execute({
            "prompt": "p",
            "operation": "image_to_video",
            "image_path": str(tmp_path / "nope.png"),
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success is False
        assert "file not found" in result.error
