"""Regression coverage for first-class Gemini Omni provider discovery and execution."""

from __future__ import annotations

import base64
import json
import sys
import types
from pathlib import Path

import pytest

from tools.base_tool import ToolStatus


class FakeResponse:
    def __init__(self, json_data=None, content=b"", ok=True, status_code=200, headers=None, text=""):
        self._json = json_data
        self.content = content
        self.ok = ok
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text or (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _install_fake_requests(monkeypatch, post_responses, get_responses):
    """Inject a fake requests module; returns the recorded calls."""
    calls = {"post": [], "get": []}

    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, data=None, timeout=None, params=None):
        calls["post"].append({"url": url, "headers": headers, "json": json, "data": data})
        response = post_responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def fake_get(url, headers=None, timeout=None, params=None):
        calls["get"].append({"url": url, "headers": headers, "params": params})
        return get_responses.pop(0)

    fake.post = fake_post
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


@pytest.fixture()
def gemini_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


def test_gemini_omni_is_discovered_as_video_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("gemini_omni_video")
    assert tool is not None
    assert tool.provider == "gemini_omni"
    assert tool.capability == "video_generation"
    # Ranking + selector-filter contract: without these the scorer buries the
    # editing capability and the selector drops it from image_to_video routing.
    assert tool.quality_score == 0.85
    assert tool.supports["image_to_video"] is True
    assert tool.supports["reference_to_video"] is True
    assert tool.supports["conversational_editing"] is True
    assert "gemini-omni" in tool.agent_skills
    assert tool.retry_policy.max_retries == 0
    assert tool.input_schema["properties"]["model"]["enum"] == ["gemini-omni-1.1-flash"]
    assert tool.input_schema["properties"]["resolution"]["enum"] == ["720p"]


def test_gemini_omni_is_routed_by_video_selector():
    from tools.video.video_selector import VideoSelector

    provider_names = [t.name for t in VideoSelector()._providers()]
    assert "gemini_omni_video" in provider_names


def test_gemini_omni_status_tracks_google_api_keys(monkeypatch):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GeminiOmniVideo().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    assert GeminiOmniVideo().get_status() == ToolStatus.AVAILABLE


def test_gemini_omni_cost_estimate_uses_max_output_not_duration_hint(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    tool = GeminiOmniVideo()
    expected = 1.0136015  # 10 * 5,792 * $17.50/M + one input byte at $1.50/M
    assert tool.estimate_cost({"prompt": "x"}) == pytest.approx(expected)
    assert tool.estimate_cost({"prompt": "x", "duration": "3"}) == pytest.approx(expected)
    assert tool.estimate_cost({"prompt": "x", "duration": "30"}) == pytest.approx(expected)


def test_gemini_omni_cost_estimate_includes_available_media_inputs(tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    small_image = tmp_path / "small.png"
    small_image.write_bytes(b"img")
    larger_image = tmp_path / "larger.png"
    larger_image.write_bytes(b"i" * 300)
    input_video = tmp_path / "input.mp4"
    input_video.write_bytes(b"video")

    cost = GeminiOmniVideo().estimate_cost(
        {
            "prompt": "x",
            "reference_image_path": str(small_image),
            "reference_image_paths": [str(larger_image)],
            "input_video_path": str(input_video),
        }
    )

    # One prompt byte + a conservative 258-token image floor + 400 bytes of
    # base64 image data + a max-duration video-token floor, all billed as input.
    assert cost == pytest.approx(1.1014685)


def test_gemini_omni_cost_estimate_includes_prior_video_for_edit(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    cost = GeminiOmniVideo().estimate_cost(
        {
            "prompt": "x",
            "previous_interaction_id": "int_prior",
            "duration": "3",
        }
    )

    assert cost == pytest.approx(1.1004815)


def test_gemini_omni_usage_cost_prices_modalities_remainder_and_thoughts_conservatively():
    from tools.video.gemini_omni_video import GeminiOmniVideo

    cost = GeminiOmniVideo._cost_from_usage(
        {
            "total_input_tokens": 100,
            "total_output_tokens": 1_000,
            "total_thought_tokens": 100,
            "input_tokens_by_modality": [
                {"modality": "text", "tokens": 100}
            ],
            "output_tokens_by_modality": [
                {"modality": "video", "tokens": 400},
                {"modality": "text", "tokens": 300},
                {"modality": "audio", "tokens": 100},
            ],
        }
    )

    assert cost == pytest.approx(0.01685)


def test_gemini_omni_usage_cost_rejects_fractional_token_counts():
    from tools.video.gemini_omni_video import GeminiOmniVideo

    assert (
        GeminiOmniVideo._cost_from_usage(
            {
                "total_input_tokens": 1,
                "total_output_tokens": 0.5,
            }
        )
        is None
    )


def test_gemini_omni_rejects_deprecated_preview_before_paid_call(monkeypatch, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(monkeypatch, post_responses=[], get_responses=[])
    result = GeminiOmniVideo().execute(
        {"prompt": "A cabin shot", "model": "gemini-omni-flash-preview"}
    )

    assert not result.success
    assert "gemini-omni-1.1-flash" in (result.error or "")
    assert calls["post"] == []


def test_gemini_omni_text_to_video_via_uri_delivery(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse({"id": "int_123", "output_video": {"uri": "files/vid-123"}}),
        ],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"fake omni mp4"),
        ],
    )

    output_path = tmp_path / "clip.mp4"
    result = GeminiOmniVideo().execute(
        {
            "prompt": "A marble rolling on a track, single continuous shot.",
            "aspect_ratio": "9:16",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert output_path.read_bytes() == b"fake omni mp4"
    assert result.data["interaction_id"] == "int_123"
    assert result.data["editable"] is True

    payload = calls["post"][0]["json"]
    assert payload["model"] == "gemini-omni-1.1-flash"
    assert result.data["model"] == "gemini-omni-1.1-flash"
    assert payload["input"] == "A marble rolling on a track, single continuous shot."
    assert payload["response_format"] == {
        "type": "video",
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "delivery": "uri",
    }
    assert calls["post"][0]["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert calls["get"][1]["url"].endswith("files/vid-123:download")
    assert calls["get"][1]["params"] == {"alt": "media"}


def test_gemini_omni_success_uses_provider_usage_over_short_duration_hint(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"usage-priced mp4").decode("ascii")
    _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "id": "int_usage",
                    "output_video": {"data": inline},
                    "usage": {
                        "total_input_tokens": 7,
                        "total_output_tokens": 57_920,
                        "total_thought_tokens": 0,
                        "input_tokens_by_modality": [
                            {"modality": "text", "tokens": 7}
                        ],
                        "output_tokens_by_modality": [
                            {"modality": "video", "tokens": 57_920}
                        ],
                    },
                }
            )
        ],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "7 chars",
            "duration": "3",
            "output_path": str(tmp_path / "usage.mp4"),
        }
    )

    assert result.success, result.error
    assert result.cost_usd == pytest.approx(1.0136105)


def test_gemini_omni_malformed_usage_falls_back_conservatively(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"malformed-usage mp4").decode("ascii")
    _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "output_video": {"data": inline},
                    "usage": {
                        "total_input_tokens": 1,
                        "total_output_tokens": 1,
                        "input_tokens_by_modality": [
                            {"modality": "text", "tokens": -1}
                        ],
                    },
                }
            )
        ],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "x",
            "duration": "3",
            "output_path": str(tmp_path / "malformed-usage.mp4"),
        }
    )

    assert result.success, result.error
    assert result.cost_usd == pytest.approx(1.0136015)


def test_gemini_omni_uri_delivery_handles_full_download_url(monkeypatch, tmp_path, gemini_env):
    """The API may return a full .../files/<id>:download?alt=media URL, not just files/<id>."""
    from tools.video.gemini_omni_video import GeminiOmniVideo

    full_url = (
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456:download?alt=media"
    )
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_5", "output_video": {"uri": full_url}})],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"full url mp4"),
        ],
    )

    output_path = tmp_path / "full.mp4"
    result = GeminiOmniVideo().execute({"prompt": "A sunset.", "output_path": str(output_path)})

    assert result.success, result.error
    assert output_path.read_bytes() == b"full url mp4"
    assert calls["get"][0]["url"].endswith("/files/vid-456")
    assert calls["get"][1]["url"].endswith("/files/vid-456:download")


def test_gemini_omni_download_error_preserves_recovery_data_and_cost(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "id": "int_private",
                    "output_video": {"uri": "files/vid-789"},
                    "usage": {
                        "total_input_tokens": 7,
                        "total_output_tokens": 57_920,
                    },
                }
            )
        ],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(ok=False, status_code=500),
        ],
    )

    output_path = tmp_path / "failed.mp4"
    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "output_path": str(output_path)}
    )

    assert not result.success
    assert result.data.get("interaction_id") == "int_private"
    assert result.data.get("output_uri") == "files/vid-789"
    assert result.data.get("resume_download") == {
        "resume_video_uri": "files/vid-789",
        "interaction_id": "int_private",
        "store": True,
    }
    assert result.cost_usd == pytest.approx(1.0136105)
    assert not output_path.exists()


def test_gemini_omni_accepted_response_without_video_preserves_usage_cost(
    monkeypatch, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "id": "int_no_video",
                    "usage": {
                        "total_input_tokens": 7,
                        "total_output_tokens": 57_920,
                    },
                }
            )
        ],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute({"prompt": "x", "duration": "3"})

    assert not result.success
    assert result.data == {"interaction_id": "int_no_video"}
    assert result.cost_usd == pytest.approx(1.0136105)


def test_gemini_omni_resume_download_uses_get_only(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"recovered omni mp4"),
        ],
    )

    output_path = tmp_path / "recovered.mp4"
    result = GeminiOmniVideo().execute(
        {
            "resume_video_uri": "files/vid-789",
            "interaction_id": "int_private",
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert calls["post"] == []
    assert len(calls["get"]) == 2
    assert output_path.read_bytes() == b"recovered omni mp4"
    assert result.data["operation"] == "resume_download"
    assert result.data["interaction_id"] == "int_private"
    assert result.cost_usd == 0.0


def test_gemini_omni_recovery_payload_without_interaction_id_is_schema_valid(
    monkeypatch, tmp_path, gemini_env
):
    from jsonschema import Draft202012Validator

    from tools.video.gemini_omni_video import GeminiOmniVideo

    _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"output_video": {"uri": "files/vid-no-id"}})],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(ok=False, status_code=500),
        ],
    )

    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "output_path": str(tmp_path / "failed.mp4")}
    )

    assert not result.success
    resume = result.data["resume_download"]
    assert "interaction_id" not in resume
    Draft202012Validator(GeminiOmniVideo.input_schema).validate(resume)


def test_gemini_omni_canonical_rest_steps_video_is_downloaded(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "id": "int_steps",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "video",
                                    "mime_type": "video/mp4",
                                    "uri": "files/vid-steps",
                                }
                            ]
                        }
                    ],
                }
            )
        ],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"steps mp4"),
        ],
    )

    output_path = tmp_path / "steps.mp4"
    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "output_path": str(output_path)}
    )

    assert result.success, result.error
    assert len(calls["post"]) == 1
    assert output_path.read_bytes() == b"steps mp4"
    assert result.data["interaction_id"] == "int_steps"


def test_gemini_omni_steps_ignore_user_input_inline_image(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    user_image = base64.b64encode(b"not a video").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(
                {
                    "id": "int_steps",
                    "steps": [
                        {
                            "type": "user_input",
                            "content": [
                                {
                                    "type": "image",
                                    "data": user_image,
                                    "mime_type": "image/png",
                                }
                            ],
                        },
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "video",
                                    "uri": "files/vid-output",
                                    "mime_type": "video/mp4",
                                }
                            ],
                        },
                    ],
                }
            )
        ],
        get_responses=[
            FakeResponse({"state": "ACTIVE"}),
            FakeResponse(content=b"model output mp4"),
        ],
    )

    output_path = tmp_path / "model-output.mp4"
    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "output_path": str(output_path)}
    )

    assert result.success, result.error
    assert output_path.read_bytes() == b"model output mp4"
    assert len(calls["get"]) == 2


def test_gemini_omni_retryable_http_error_is_not_replayed(monkeypatch, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse(ok=False, status_code=503, text="temporarily unavailable")],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute({"prompt": "A sunset."})

    assert not result.success
    assert "503" in (result.error or "")
    assert len(calls["post"]) == 1


def test_gemini_omni_post_transport_error_marks_submission_unknown(
    monkeypatch, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[TimeoutError("read timed out")],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute({"prompt": "A sunset.", "duration": "3"})

    assert not result.success
    assert result.data == {
        "submission_outcome": "unknown",
        "retry_safe": False,
    }
    assert result.error == (
        "Gemini Omni submission outcome is unknown after transport failure: read timed out. "
        "Do not retry or resubmit; the request may have been accepted and charged."
    )
    assert result.cost_usd == pytest.approx(1.0136135)
    assert len(calls["post"]) == 1
    assert calls["post"][0]["url"].endswith("/interactions")
    assert calls["get"] == []


@pytest.mark.parametrize(
    "uri",
    [
        "files/vid-456",
        "files/vid-456/",
        "v1beta/files/vid-456",
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456",
        "https://generativelanguage.googleapis.com/v1beta/files/vid-456:download?alt=media",
    ],
)
def test_gemini_omni_file_id_extraction_covers_documented_uri_shapes(uri):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    assert GeminiOmniVideo._file_id_from_uri(uri) == "vid-456"


def test_gemini_omni_inline_data_response_is_handled(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"inline mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_9", "output_video": {"data": inline}})],
        get_responses=[],
    )

    output_path = tmp_path / "inline.mp4"
    result = GeminiOmniVideo().execute({"prompt": "A sunset.", "output_path": str(output_path)})

    assert result.success, result.error
    assert output_path.read_bytes() == b"inline mp4"
    assert calls["get"] == []


def test_gemini_omni_edit_turn_sends_previous_interaction_id(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"edited mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_2", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "Make the violin invisible. Keep everything else the same.",
            "operation": "edit_video",
            "previous_interaction_id": "int_1",
            "output_path": str(tmp_path / "edit.mp4"),
        }
    )

    assert result.success, result.error
    assert calls["post"][0]["json"]["previous_interaction_id"] == "int_1"


def test_gemini_omni_uploaded_video_uses_video_input_part(
    monkeypatch, tmp_path, gemini_env
):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    input_video = tmp_path / "input.mp4"
    input_video.write_bytes(b"input mp4")
    inline = base64.b64encode(b"edited mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            FakeResponse(headers={"X-Goog-Upload-URL": "https://upload.example/session"}),
            FakeResponse(
                {
                    "file": {
                        "name": "files/input-video",
                        "state": "ACTIVE",
                        "uri": "files/input-video",
                    }
                }
            ),
            FakeResponse({"id": "int_upload_edit", "output_video": {"data": inline}}),
        ],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "Make it anime.",
            "operation": "edit_video",
            "input_video_path": str(input_video),
            "output_path": str(tmp_path / "edited.mp4"),
        }
    )

    assert result.success, result.error
    assert len(calls["post"]) == 3
    interaction_input = calls["post"][2]["json"]["input"]
    assert interaction_input[0] == {"type": "video", "uri": "files/input-video"}
    assert interaction_input[1] == {"type": "text", "text": "Make it anime."}


def test_gemini_omni_edit_without_source_is_rejected(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    result = GeminiOmniVideo().execute({"prompt": "Make it anime", "operation": "edit_video"})
    assert not result.success
    assert "previous_interaction_id" in result.error


def test_gemini_omni_image_to_video_sends_typed_parts(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    ref = tmp_path / "cat.png"
    ref.write_bytes(b"png bytes")
    inline = base64.b64encode(b"cat mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_3", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {
            "prompt": "A cat <IMAGE_REF_0> playfully batting at yarn.",
            "operation": "image_to_video",
            "reference_image_path": str(ref),
            "output_path": str(tmp_path / "cat.mp4"),
        }
    )

    assert result.success, result.error
    parts = calls["post"][0]["json"]["input"]
    assert parts[0]["type"] == "image"
    assert parts[0]["mime_type"] == "image/png"
    assert parts[0]["data"] == base64.b64encode(b"png bytes").decode("ascii")
    assert parts[-1] == {"type": "text", "text": "A cat <IMAGE_REF_0> playfully batting at yarn."}


def test_gemini_omni_image_to_video_requires_reference(gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    result = GeminiOmniVideo().execute({"prompt": "x", "operation": "image_to_video"})
    assert not result.success
    assert "reference_image_path" in result.error


def test_gemini_omni_store_false_marks_result_not_editable(monkeypatch, tmp_path, gemini_env):
    from tools.video.gemini_omni_video import GeminiOmniVideo

    inline = base64.b64encode(b"oneshot mp4").decode("ascii")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[FakeResponse({"id": "int_4", "output_video": {"data": inline}})],
        get_responses=[],
    )

    result = GeminiOmniVideo().execute(
        {"prompt": "A sunset.", "store": False, "output_path": str(tmp_path / "s.mp4")}
    )

    assert result.success, result.error
    assert result.data["editable"] is False
    assert calls["post"][0]["json"]["store"] is False
    assert calls["post"][0]["json"]["response_format"]["delivery"] == "uri"
