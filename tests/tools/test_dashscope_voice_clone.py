"""Unit tests for the DashScope voice-enrollment (voice cloning) tool.

No network access: ``requests.post`` is patched. Covers status gating, the
four operations, local-file encoding, the DEPLOYING -> OK poll, target-model
validation, prefix normalization, workspace-domain routing, metadata output,
and API-key redaction.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.audio.dashscope_voice_clone import DashscopeVoiceClone
from tools.base_tool import ToolStatus

VOICE_ID = "qwen-audio-3.1-tts-flash-femtest-cd3af4b0d06a44449d58934877dfb8ba"
ENDPOINT = "/services/audio/tts/customization"


class _FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self._payload = {"output": {}, "usage": {"count": 1}} if payload is None else payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self) -> dict:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dashscope-secret")
    return "sk-dashscope-secret"


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)


@pytest.fixture
def no_workspace(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("DASHSCOPE_VOICE_CLONE_BASE_URL", raising=False)


@pytest.fixture
def reference_wav(tmp_path, monkeypatch):
    path = tmp_path / "reference.wav"
    path.write_bytes(b"RIFFfake-wav-bytes")
    monkeypatch.setattr(
        "tools.analysis.audio_probe.probe_duration", lambda _p: 18.5
    )
    return path


def _body(mock_post, index: int = 0):
    return mock_post.call_args_list[index].kwargs["json"]


# ----------------------------------------------------------------------
# Status gating
# ----------------------------------------------------------------------


class TestStatus:
    def test_unavailable_without_key(self, no_api_key):
        assert DashscopeVoiceClone().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, api_key):
        assert DashscopeVoiceClone().get_status() == ToolStatus.AVAILABLE

    def test_execute_fails_without_key(self, no_api_key):
        result = DashscopeVoiceClone().execute({"operation": "list"})
        assert result.success is False
        assert "DASHSCOPE_API_KEY" in result.error

    def test_operation_is_required(self, api_key):
        result = DashscopeVoiceClone().execute({})
        assert result.success is False
        assert "operation must be one of" in result.error

    def test_unknown_operation_rejected(self, api_key):
        result = DashscopeVoiceClone().execute({"operation": "rename"})
        assert result.success is False
        assert "operation" in result.error


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------


class TestCreate:
    def test_local_file_is_inlined_as_data_uri(self, api_key, reference_wav, no_workspace):
        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ) as mock_post:
            result = DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "wait_for_ready": False,
                }
            )

        assert result.success is True, result.error
        assert result.data["voice_id"] == VOICE_ID
        assert result.data["status"] == "DEPLOYING"
        body = _body(mock_post)
        assert body["model"] == "voice-enrollment"
        assert body["input"]["action"] == "create_voice"
        assert body["input"]["target_model"] == "qwen-audio-3.1-tts-flash"
        prefix = "data:audio/wav;base64,"
        assert body["input"]["audio"].startswith(prefix)
        decoded = base64.b64decode(body["input"]["audio"][len(prefix):])
        assert decoded == reference_wav.read_bytes()
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == (
            "Bearer sk-dashscope-secret"
        )
        assert mock_post.call_args.args[0].endswith(ENDPOINT)

    def test_polls_until_status_ok(self, api_key, reference_wav, no_workspace):
        responses = [
            _FakeResponse({"output": {"voice_id": VOICE_ID}}),
            _FakeResponse({"output": {"status": "DEPLOYING"}}),
            _FakeResponse({"output": {"status": "OK"}}),
        ]
        with patch("requests.post", side_effect=responses) as mock_post, patch(
            "tools.audio.dashscope_voice_clone.time.sleep"
        ) as mock_sleep:
            result = DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "poll_interval_seconds": 1,
                }
            )

        assert result.success is True, result.error
        assert result.data["status"] == "OK"
        assert mock_post.call_count == 3
        assert _body(mock_post, 1)["input"]["action"] == "query_voice"
        assert _body(mock_post, 1)["input"]["voice_id"] == VOICE_ID
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args.args[0] == 1

    def test_rejected_enrollment_is_reported(self, api_key, reference_wav, no_workspace):
        responses = [
            _FakeResponse({"output": {"voice_id": VOICE_ID}}),
            _FakeResponse({"output": {"status": "UNDEPLOYED"}}),
        ]
        with patch("requests.post", side_effect=responses):
            result = DashscopeVoiceClone().execute(
                {"operation": "create", "reference_audio": str(reference_wav)}
            )

        assert result.success is False
        assert "UNDEPLOYED" in result.error

    def test_enrollment_options_are_forwarded(self, api_key, reference_wav, no_workspace):
        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ) as mock_post:
            DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "target_model": "qwen-audio-3.0-tts-flash",
                    "prefix": "narr8",
                    "language_hints": ["zh", "en"],
                    "enable_preprocess": True,
                    "enable_volume_normalization": True,
                    "max_prompt_audio_length": 15,
                    "wait_for_ready": False,
                }
            )

        body_input = _body(mock_post)["input"]
        assert body_input["target_model"] == "qwen-audio-3.0-tts-flash"
        assert body_input["prefix"] == "narr8"
        assert body_input["language_hints"] == ["zh"]
        assert body_input["enable_preprocess"] is True
        assert body_input["enable_volume_normalization"] == "true"
        assert body_input["max_prompt_audio_length"] == 15.0

    def test_prefix_is_sanitized_and_defaulted(self, api_key, reference_wav, no_workspace):
        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ) as mock_post:
            DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "prefix": "旁白-voice!!",
                    "wait_for_ready": False,
                }
            )
        assert _body(mock_post)["input"]["prefix"] == "voice"

        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ) as mock_post:
            DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "prefix": "中文",
                    "wait_for_ready": False,
                }
            )
        assert _body(mock_post)["input"]["prefix"] == "omvoice"

    def test_url_reference_is_passed_through(self, api_key, no_workspace):
        url = "https://example.com/voice.wav"
        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ) as mock_post:
            result = DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": url,
                    "wait_for_ready": False,
                }
            )

        assert result.success is True
        assert _body(mock_post)["input"]["audio"] == url
        assert result.data["reference"]["source"] == "url"

    def test_unknown_target_model_rejected(self, api_key, reference_wav):
        result = DashscopeVoiceClone().execute(
            {
                "operation": "create",
                "reference_audio": str(reference_wav),
                "target_model": "qwen3-tts-flash",
            }
        )
        assert result.success is False
        assert "Unknown target_model" in result.error

    def test_missing_reference_is_an_error(self, api_key):
        result = DashscopeVoiceClone().execute({"operation": "create"})
        assert result.success is False
        assert "reference_audio is required" in result.error

    def test_missing_file_is_an_error(self, api_key, tmp_path):
        result = DashscopeVoiceClone().execute(
            {
                "operation": "create",
                "reference_audio": str(tmp_path / "nope.wav"),
            }
        )
        assert result.success is False
        assert "not found" in result.error

    def test_unsupported_extension_rejected(self, api_key, tmp_path):
        path = tmp_path / "reference.ogg"
        path.write_bytes(b"not-really-ogg")
        result = DashscopeVoiceClone().execute(
            {"operation": "create", "reference_audio": str(path)}
        )
        assert result.success is False
        assert "Unsupported reference format" in result.error

    def test_short_reference_rejected(self, api_key, tmp_path, monkeypatch):
        path = tmp_path / "short.wav"
        path.write_bytes(b"tiny")
        monkeypatch.setattr(
            "tools.analysis.audio_probe.probe_duration", lambda _p: 2.0
        )
        result = DashscopeVoiceClone().execute(
            {"operation": "create", "reference_audio": str(path)}
        )
        assert result.success is False
        assert "at least" in result.error

    def test_oversize_reference_rejected(self, api_key, tmp_path, monkeypatch):
        path = tmp_path / "big.wav"
        path.write_bytes(b"x")
        monkeypatch.setattr(
            "tools.analysis.audio_probe.probe_duration", lambda _p: 15.0
        )
        monkeypatch.setattr(
            "tools.audio.dashscope_voice_clone.MAX_REFERENCE_BYTES", 0
        )
        result = DashscopeVoiceClone().execute(
            {"operation": "create", "reference_audio": str(path)}
        )
        assert result.success is False
        assert "10 MB" in result.error

    def test_metadata_record_is_written(self, api_key, reference_wav, no_workspace, tmp_path):
        out = tmp_path / "voice.json"
        with patch(
            "requests.post",
            return_value=_FakeResponse({"output": {"voice_id": VOICE_ID}}),
        ):
            result = DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "wait_for_ready": False,
                    "output_path": str(out),
                }
            )

        assert result.success is True
        assert str(out) in result.artifacts
        record = json.loads(out.read_text(encoding="utf-8"))
        assert record["voice_id"] == VOICE_ID
        assert record["target_model"] == "qwen-audio-3.1-tts-flash"
        assert record["reference"]["source"] == "local_file"
        assert record["reference"]["duration_seconds"] == 18.5

    def test_api_error_surfaces_code_and_message(self, api_key, reference_wav):
        with patch(
            "requests.post",
            return_value=_FakeResponse(
                {"code": "InvalidParameter", "message": "audio too short"},
                status_code=400,
            ),
        ):
            result = DashscopeVoiceClone().execute(
                {
                    "operation": "create",
                    "reference_audio": str(reference_wav),
                    "wait_for_ready": False,
                }
            )

        assert result.success is False
        assert "InvalidParameter" in result.error
        assert "audio too short" in result.error


# ----------------------------------------------------------------------
# Query / list / delete
# ----------------------------------------------------------------------


class TestVoiceManagement:
    def test_query_returns_status_and_target_model(self, api_key, no_workspace):
        payload = {
            "output": {
                "status": "OK",
                "target_model": "qwen-audio-3.1-tts-flash",
                "gmt_create": "2026-10-23 20:14:18",
                "resource_link": "https://example.com/ref.wav",
            }
        }
        with patch("requests.post", return_value=_FakeResponse(payload)) as mock_post:
            result = DashscopeVoiceClone().execute(
                {"operation": "query", "voice_id": VOICE_ID}
            )

        assert result.success is True
        assert result.data["status"] == "OK"
        assert result.data["target_model"] == "qwen-audio-3.1-tts-flash"
        assert _body(mock_post)["input"] == {
            "action": "query_voice",
            "voice_id": VOICE_ID,
        }

    def test_query_requires_voice_id(self, api_key):
        result = DashscopeVoiceClone().execute({"operation": "query"})
        assert result.success is False
        assert "voice_id is required" in result.error

    def test_delete_requires_voice_id(self, api_key):
        result = DashscopeVoiceClone().execute({"operation": "delete"})
        assert result.success is False
        assert "voice_id is required" in result.error

    def test_list_maps_voice_list(self, api_key, no_workspace):
        payload = {
            "output": {
                "voice_list": [
                    {"voice_id": "v1", "status": "OK", "gmt_create": "2026-10-01"},
                    {"voice_id": "v2", "status": "DEPLOYING", "gmt_create": "2026-10-02"},
                ]
            }
        }
        with patch("requests.post", return_value=_FakeResponse(payload)) as mock_post:
            result = DashscopeVoiceClone().execute(
                {"operation": "list", "prefix": "narr", "page_size": 5}
            )

        assert result.success is True
        assert result.data["count"] == 2
        assert [v["voice_id"] for v in result.data["voices"]] == ["v1", "v2"]
        assert _body(mock_post)["input"]["action"] == "list_voice"
        assert _body(mock_post)["input"]["prefix"] == "narr"

    def test_delete_reports_success(self, api_key, no_workspace):
        with patch("requests.post", return_value=_FakeResponse({"output": {}})) as mock_post:
            result = DashscopeVoiceClone().execute(
                {"operation": "delete", "voice_id": VOICE_ID}
            )

        assert result.success is True
        assert result.data["deleted"] is True
        assert _body(mock_post)["input"]["action"] == "delete_voice"


# ----------------------------------------------------------------------
# Endpoint routing
# ----------------------------------------------------------------------


class TestEndpointRouting:
    def test_workspace_env_switches_domain(self, api_key, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "wsp-123")
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            DashscopeVoiceClone().execute({"operation": "list"})

        url = mock_post.call_args.args[0]
        assert url == (
            "https://wsp-123.cn-beijing.maas.aliyuncs.com/api/v1"
            + ENDPOINT
        )

    def test_explicit_base_url_overrides_workspace(self, api_key, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "wsp-123")
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            DashscopeVoiceClone().execute(
                {
                    "operation": "list",
                    "base_url": "https://dashscope-intl.aliyuncs.com/api/v1/",
                }
            )

        url = mock_post.call_args.args[0]
        assert url.startswith("https://dashscope-intl.aliyuncs.com/api/v1/services")


# ----------------------------------------------------------------------
# Safety / registry metadata
# ----------------------------------------------------------------------


class TestSafety:
    def test_error_redacts_key(self, api_key, no_workspace):
        def _boom(*args, **kwargs):
            raise RuntimeError("upstream failed for sk-dashscope-secret")

        with patch("requests.post", side_effect=_boom):
            result = DashscopeVoiceClone().execute({"operation": "list"})

        assert result.success is False
        assert "sk-dashscope-secret" not in result.error
        assert "[redacted]" in result.error

    def test_declares_voice_cloning_capability(self):
        tool = DashscopeVoiceClone()
        assert tool.capability == "voice_cloning"
        assert tool.supports["voice_cloning"] is True

    def test_is_never_billed_for_enrollment(self):
        assert DashscopeVoiceClone().estimate_cost({"operation": "create"}) == 0.0
