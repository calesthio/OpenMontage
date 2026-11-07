"""Offline coverage for the authenticated Higgsfield CLI adapter."""

import json
import subprocess

import tools.video.higgsfield_video as higgsfield_video
from tools.base_tool import ToolStatus
from tools.video.higgsfield_video import HiggsFieldVideo


class _FakeResponse:
    def __init__(self, content: bytes = b""):
        self.content = content

    def raise_for_status(self):
        return None

    def close(self):
        return None


def test_cli_auth_makes_provider_available_without_api_keys(monkeypatch):
    monkeypatch.delenv("HIGGSFIELD_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_SECRET", raising=False)
    monkeypatch.setattr(
        HiggsFieldVideo,
        "_has_authenticated_cli",
        classmethod(lambda cls: True),
    )

    assert HiggsFieldVideo().get_status() == ToolStatus.AVAILABLE


def test_cli_command_translates_legacy_model_and_reference():
    command = HiggsFieldVideo._build_cli_command(
        "/usr/local/bin/higgsfield",
        {
            "prompt": "slow camera push-in",
            "model": "seedance_2.0",
            "operation": "image_to_video",
            "duration": "5",
            "aspect_ratio": "16:9",
        },
        "/tmp/reference.png",
    )

    assert command == [
        "/usr/local/bin/higgsfield",
        "generate",
        "create",
        "seedance_2_0",
        "--prompt",
        "slow camera push-in",
        "--duration",
        "5",
        "--aspect_ratio",
        "16:9",
        "--start-image",
        "/tmp/reference.png",
        "--wait",
        "--json",
    ]


def test_cli_response_parser_finds_result_url_and_job_id():
    payload = [{"id": "job-123", "result_url": "https://cdn.example.test/clip.mp4"}]

    parsed, url = HiggsFieldVideo._parse_cli_response(json.dumps(payload))

    assert parsed == payload
    assert url == "https://cdn.example.test/clip.mp4"
    assert HiggsFieldVideo._find_job_id(parsed) == "job-123"


def test_execute_uses_cli_and_downloads_result(monkeypatch, tmp_path):
    tool = HiggsFieldVideo()
    output_path = tmp_path / "clip.mp4"
    observed = {}

    monkeypatch.delenv("HIGGSFIELD_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_SECRET", raising=False)
    monkeypatch.setattr(
        higgsfield_video.shutil,
        "which",
        lambda name: "/usr/local/bin/higgsfield" if name == "higgsfield" else None,
    )

    def fake_run(command, *, timeout=None, cwd=None):
        observed["command"] = command
        observed["timeout"] = timeout
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps([{"id": "job-123", "result_url": "https://cdn.example.test/clip.mp4"}]),
            stderr="",
        )

    monkeypatch.setattr(tool, "run_command", fake_run)
    monkeypatch.setattr(
        higgsfield_video.requests,
        "get",
        lambda url, timeout: _FakeResponse(b"fake-mp4"),
    )
    monkeypatch.setattr(
        "tools.video._shared.probe_output",
        lambda path: {"duration_seconds": 5.0},
    )

    result = tool.execute(
        {
            "prompt": "a cinematic test shot",
            "model": "seedance_2.0",
            "duration": "5",
            "aspect_ratio": "16:9",
            "output_path": str(output_path),
        }
    )

    assert result.success is True
    assert result.data["auth_method"] == "oauth_cli"
    assert result.data["cli_model"] == "seedance_2_0"
    assert output_path.read_bytes() == b"fake-mp4"
    assert observed["command"][0] == "/usr/local/bin/higgsfield"
    assert observed["command"][3] == "seedance_2_0"
    assert observed["timeout"] == 900
