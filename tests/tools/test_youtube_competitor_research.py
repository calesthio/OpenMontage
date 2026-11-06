"""Tests for YouTubeCompetitorResearch."""

import json
from unittest.mock import patch, MagicMock

from tools.analysis.youtube_competitor_research import YouTubeCompetitorResearch


def test_status_available():
    tool = YouTubeCompetitorResearch()
    # yt-dlp is installed in this environment
    assert tool.get_status().value in ("available", "unavailable")


def test_normalize():
    tool = YouTubeCompetitorResearch()
    raw = {"id": "abc123", "title": "T", "uploader": "Ch", "view_count": 10, "duration": 120, "upload_date": "20240101", "description": "d" * 600}
    out = tool._normalize(raw)
    assert out["video_id"] == "abc123"
    assert len(out["description"]) == 500


def test_execute_parses_ytdlp_output():
    tool = YouTubeCompetitorResearch()
    fake_line = json.dumps({"id": "vid1", "title": "Title", "uploader": "Chan", "view_count": 5, "duration": 60, "upload_date": "20240101", "description": "desc"})
    fake_proc = MagicMock()
    fake_proc.stdout = fake_line + "\n"
    fake_proc.returncode = 0
    with patch("subprocess.run", return_value=fake_proc):
        res = tool.execute({"query": "ocean planet", "max_results": 3, "fetch_transcripts": False})
    assert res.success is True
    assert res.data["result_count"] == 1
    assert res.data["results"][0]["video_id"] == "vid1"


def test_execute_handles_failure():
    tool = YouTubeCompetitorResearch()
    with patch("subprocess.run", side_effect=Exception("boom")):
        res = tool.execute({"query": "x"})
    assert res.success is False
    assert "boom" in res.error
