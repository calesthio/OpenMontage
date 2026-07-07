"""Offline contract tests for the ZapCap captions provider.

All network I/O is mocked at the tool's ``_request`` / ``_download`` boundary —
these tests never touch api.zapcap.ai and require no API key. They cover:

- registry discovery under capability="subtitle"
- get_status() with no key / missing requests / configured key
- local missing-file failure for input_path
- template-name resolution and not-found behavior
- mocked happy path: upload -> create_task -> poll -> download
- a mocked API error path with useful, non-leaky error reporting
"""

from __future__ import annotations

import builtins

import pytest

from tools.base_tool import ToolStatus
from tools.subtitle import zapcap_captions as zc
from tools.subtitle.zapcap_captions import BASE_URL, ZapCapCaptions
from tools.tool_registry import registry

_TEST_KEY = "test-key-do-not-log-1234567890"

# Canned /templates response used across resolution + happy-path tests.
_TEMPLATES = [
    {"id": "a51c5222-47a7-4c37-b052-7b9853d66bf6", "name": "Hormozi 1", "categories": ["animated"]},
    {"id": "46d20d67-255c-4c6a-b971-31fddcfea7f0", "name": "Beast", "categories": ["highlighted"]},
]


def _tool(monkeypatch, *, key: str | None = _TEST_KEY) -> ZapCapCaptions:
    """A ZapCapCaptions instance with a deterministic env key."""
    if key is None:
        monkeypatch.delenv("ZAPCAP_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ZAPCAP_API_KEY", key)
    return ZapCapCaptions()


# --------------------------------------------------------------------------- #
#  Registry discovery + contract metadata
# --------------------------------------------------------------------------- #

def test_registry_discovers_zapcap_under_subtitle():
    registry.discover()
    subtitle_tools = {t.name for t in registry.get_by_capability("subtitle")}
    assert "zapcap_captions" in subtitle_tools

    tool = registry.get("zapcap_captions")
    assert tool is not None
    assert tool.capability == "subtitle"
    assert tool.provider == "zapcap"
    assert tool.runtime.value == "api"
    # Declares the required key as a dependency and links its Layer 3 skill.
    assert "env:ZAPCAP_API_KEY" in tool.dependencies
    assert "zapcap-captions" in tool.agent_skills


def test_base_url_is_production():
    assert BASE_URL == "https://api.zapcap.ai"


# --------------------------------------------------------------------------- #
#  get_status()
# --------------------------------------------------------------------------- #

def test_status_unavailable_without_key(monkeypatch):
    tool = _tool(monkeypatch, key=None)
    assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_status_unavailable_when_requests_missing(monkeypatch):
    tool = _tool(monkeypatch)  # key present
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ImportError("simulated: requests not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_status_available_with_key_and_requests(monkeypatch):
    tool = _tool(monkeypatch)
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_execute_without_key_returns_error(monkeypatch):
    tool = _tool(monkeypatch, key=None)
    result = tool.execute({"action": "list_templates"})
    assert result.success is False
    assert "ZAPCAP_API_KEY" in result.error


# --------------------------------------------------------------------------- #
#  Local missing-file failure
# --------------------------------------------------------------------------- #

def test_caption_missing_input_file_fails_cleanly(monkeypatch, tmp_path):
    tool = _tool(monkeypatch)
    missing = tmp_path / "nope.mp4"

    # Guard: no network call should ever happen for a missing local file.
    def boom(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("network was called for a missing local file")

    monkeypatch.setattr(tool, "_request", boom)

    result = tool.execute(
        {"action": "caption", "input_path": str(missing), "template_id": _TEMPLATES[0]["id"]}
    )
    assert result.success is False
    assert "not found" in result.error.lower()
    assert str(missing) in result.error


# --------------------------------------------------------------------------- #
#  Template-name resolution
# --------------------------------------------------------------------------- #

def test_resolve_template_id_by_name_case_insensitive(monkeypatch):
    tool = _tool(monkeypatch)
    monkeypatch.setattr(tool, "_list_templates", lambda: _TEMPLATES)
    # Case-insensitive name match returns the id.
    assert tool._resolve_template_id(None, "hormozi 1") == _TEMPLATES[0]["id"]
    # Explicit id passes through untouched (no lookup needed).
    assert tool._resolve_template_id("explicit-id", None) == "explicit-id"


def test_resolve_template_id_unknown_name_raises_with_options(monkeypatch):
    tool = _tool(monkeypatch)
    monkeypatch.setattr(tool, "_list_templates", lambda: _TEMPLATES)
    with pytest.raises(ValueError) as exc:
        tool._resolve_template_id(None, "Nonexistent Template")
    msg = str(exc.value)
    assert "Nonexistent Template" in msg
    # The error lists the available names to guide the caller.
    assert "Hormozi 1" in msg and "Beast" in msg


def test_resolve_template_id_requires_id_or_name(monkeypatch):
    tool = _tool(monkeypatch)
    with pytest.raises(ValueError):
        tool._resolve_template_id(None, None)


# --------------------------------------------------------------------------- #
#  Mocked happy path: upload -> create_task -> poll -> download
# --------------------------------------------------------------------------- #

def test_caption_happy_path(monkeypatch, tmp_path):
    tool = _tool(monkeypatch)

    src = tmp_path / "in.mp4"
    src.write_bytes(b"\x00\x00fake-mp4-bytes")
    out = tmp_path / "out" / "captioned.mp4"

    # Task goes transcribing -> completed across two polls.
    task_states = [
        {"id": "task-abc", "status": "transcribing", "downloadUrl": None, "transcript": None},
        {
            "id": "task-abc",
            "status": "completed",
            "downloadUrl": "https://cdn.example/out.mp4",
            "transcript": "https://cdn.example/words.json",
        },
    ]
    calls: list[tuple[str, str]] = []

    def fake_request(method, path, *, json_body=None, params=None, files=None, timeout=120):
        calls.append((method, path))
        if method == "POST" and path == "/videos":
            return {"id": "vid-123", "status": "uploaded"}
        if method == "POST" and path == "/videos/vid-123/task":
            assert json_body["templateId"] == _TEMPLATES[0]["id"]
            assert json_body["autoApprove"] is True  # default
            return {"taskId": "task-abc"}
        if method == "GET" and path == "/videos/vid-123/task/task-abc":
            return task_states.pop(0) if len(task_states) > 1 else task_states[0]
        raise AssertionError(f"unexpected request: {method} {path}")

    downloaded: dict[str, str] = {}

    def fake_download(url, output_path):
        downloaded["url"] = url
        from pathlib import Path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"captioned-bytes")
        return output_path

    monkeypatch.setattr(tool, "_request", fake_request)
    monkeypatch.setattr(tool, "_download", fake_download)

    result = tool.execute(
        {
            "action": "caption",
            "input_path": str(src),
            "template_id": _TEMPLATES[0]["id"],
            "output_path": str(out),
            "poll_interval_seconds": 0,  # no real sleeping
            "timeout_seconds": 30,
        }
    )

    assert result.success is True, result.error
    assert result.data["videoId"] == "vid-123"
    assert result.data["taskId"] == "task-abc"
    assert result.data["templateId"] == _TEMPLATES[0]["id"]
    assert result.data["status"] == "completed"
    assert result.data["output"] == str(out)
    assert result.artifacts == [str(out)]
    assert out.exists() and out.read_bytes() == b"captioned-bytes"
    assert downloaded["url"] == "https://cdn.example/out.mp4"
    # Confirms the full lifecycle ran: upload, task, and at least two polls.
    assert ("POST", "/videos") in calls
    assert ("POST", "/videos/vid-123/task") in calls
    assert calls.count(("GET", "/videos/vid-123/task/task-abc")) >= 2


# --------------------------------------------------------------------------- #
#  Mocked API error path — useful message, no secret leak
# --------------------------------------------------------------------------- #

def test_caption_api_error_is_reported_without_leaking_key(monkeypatch, tmp_path):
    tool = _tool(monkeypatch)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")

    def failing_request(method, path, *, json_body=None, params=None, files=None, timeout=120):
        # Mirrors how _request surfaces a non-2xx response (body message only).
        raise RuntimeError("ZapCap POST /videos -> 401 Unauthorized: invalid api key")

    monkeypatch.setattr(tool, "_request", failing_request)

    result = tool.execute(
        {"action": "caption", "input_path": str(src), "template_id": _TEMPLATES[0]["id"]}
    )
    assert result.success is False
    # Error is actionable (names the action + upstream status).
    assert "caption" in result.error
    assert "401" in result.error
    # The API key must never appear in surfaced errors.
    assert _TEST_KEY not in result.error


def test_task_failed_status_surfaces_error(monkeypatch, tmp_path):
    tool = _tool(monkeypatch)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")

    def fake_request(method, path, *, json_body=None, params=None, files=None, timeout=120):
        if method == "POST" and path == "/videos":
            return {"id": "vid-9", "status": "uploaded"}
        if path.endswith("/task"):
            return {"taskId": "task-9"}
        # GET task status -> failed
        return {"id": "task-9", "status": "failed", "error": "no speech detected"}

    monkeypatch.setattr(tool, "_request", fake_request)

    result = tool.execute(
        {
            "action": "caption",
            "input_path": str(src),
            "template_id": _TEMPLATES[0]["id"],
            "poll_interval_seconds": 0,
        }
    )
    assert result.success is False
    assert "no speech detected" in result.error
