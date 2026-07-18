"""YouTube uploader (roadmap 3.4): availability gating + contract shape.

No network in tests — availability logic and graceful failure only.
"""

from __future__ import annotations

import pytest

from tools.base_tool import ToolStatus
from tools.publishers.youtube_upload import YouTubeUpload


def test_unavailable_without_credentials(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRETS_FILE", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKEN_FILE", raising=False)
    assert YouTubeUpload().get_status() is ToolStatus.UNAVAILABLE


def test_unavailable_when_env_points_at_dead_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS_FILE", str(tmp_path / "nope.json"))
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "nope2.json"))
    assert YouTubeUpload().get_status() is ToolStatus.UNAVAILABLE


def test_execute_fails_gracefully_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRETS_FILE", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKEN_FILE", raising=False)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    result = YouTubeUpload().execute({"video_path": str(video), "title": "t"})
    assert result.success is False
    assert "not configured" in result.error


def test_execute_rejects_missing_video():
    result = YouTubeUpload().execute({"video_path": "/nope/never.mp4", "title": "t"})
    assert result.success is False
    assert "not found" in result.error


def test_registry_discovers_youtube_upload():
    from tools.tool_registry import registry
    registry.ensure_discovered()
    tool = registry.get("youtube_upload")
    assert tool is not None
    assert tool.capability == "publish"
    assert tool.provider == "youtube"
