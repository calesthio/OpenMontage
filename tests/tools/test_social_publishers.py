"""Tests for the networked publishers (youtube_publish, tiktok_publish).

All HTTP is mocked — no network, no credentials needed.
"""

import sys
from pathlib import Path
from unittest import mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import ToolStatus, ToolTier
from tools.publishers import _social
from tools.publishers.tiktok_publish import CHUNK, TikTokPublish
from tools.publishers.youtube_publish import YouTubePublish
from tools.tool_registry import ToolRegistry


class FakeResp:
    def __init__(self, status=200, json_data=None, headers=None, text=""):
        self.status_code = status
        self._json = json_data or {}
        self.headers = headers or {}
        self.text = text or str(json_data)

    def json(self):
        return self._json


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 2048)
    return p


@pytest.fixture
def yt_env(monkeypatch):
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "test")


@pytest.fixture
def tt_env(monkeypatch):
    for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "test")
    monkeypatch.setattr("tools.publishers.tiktok_publish.time.sleep", lambda s: None)


# ---- shared helpers ----

def test_clean_text_strips_controls_brackets_and_limits():
    assert _social.clean_text("Hi <script>\x07 there", 100) == "Hi script there"
    assert len(_social.clean_text("a" * 500, 100)) == 100


def test_clean_tags_dedupes_and_caps():
    tags = _social.clean_tags(["#AI", "ai", "cyber, security", "x" * 70], total_limit=40)
    assert tags[0] == "AI" and "ai" not in tags
    assert "cyber security" in tags
    assert sum(len(t) + 1 for t in tags) <= 40


# ---- contract / registry ----

@pytest.mark.parametrize("cls,name,provider", [
    (YouTubePublish, "youtube_publish", "youtube"),
    (TikTokPublish, "tiktok_publish", "tiktok"),
])
def test_contract(cls, name, provider, monkeypatch):
    for k in cls.dependencies:
        monkeypatch.delenv(k[4:], raising=False)
    tool = cls()
    info = tool.get_info()
    assert info["name"] == name
    assert info["capability"] == "publish"
    assert info["provider"] == provider
    assert info["tier"] == ToolTier.PUBLISH.value
    assert tool.retry_policy.max_retries == 0  # uploads must never auto-retry
    assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_registry_discovers_publishers():
    reg = ToolRegistry()
    reg.discover()
    names = {t.name for t in reg.get_by_capability("publish")}
    assert {"export_bundle", "youtube_publish", "tiktok_publish"} <= names


# ---- YouTube ----

def test_youtube_dry_run_builds_private_body(video):
    res = YouTubePublish().execute({
        "video_path": str(video), "title": "Passkeys <explained>", "description": "Why passwords die.",
        "tags": ["passkeys", "security"], "hashtags": ["Shorts", "#cybersecurity"], "dry_run": True,
    })
    assert res.success
    body = res.data["request_body"]
    assert body["snippet"]["title"] == "Passkeys explained"
    assert "#Shorts #cybersecurity" in body["snippet"]["description"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["containsSyntheticMedia"] is True


def test_youtube_missing_video(tmp_path):
    res = YouTubePublish().execute({"video_path": str(tmp_path / "nope.mp4"), "title": "x"})
    assert not res.success and "not found" in res.error


def test_youtube_upload_success(video, yt_env):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        if "oauth2" in url:
            return FakeResp(json_data={"access_token": "tok"})
        return FakeResp(headers={"Location": "https://upload.example/session"})

    with mock.patch("tools.publishers.youtube_publish.requests.post", side_effect=fake_post), \
         mock.patch("tools.publishers.youtube_publish.requests.put",
                    return_value=FakeResp(json_data={"id": "abc123"})):
        res = YouTubePublish().execute({"video_path": str(video), "title": "Test"})

    assert res.success, res.error
    assert res.data["url"] == "https://www.youtube.com/shorts/abc123"
    entry = res.data["publish_log"]["entries"][0]
    assert entry["status"] == "pending_review" and entry["visibility"] == "private"


def test_youtube_failure_returns_failed_log(video, yt_env):
    with mock.patch("tools.publishers.youtube_publish.requests.post",
                    return_value=FakeResp(status=401, json_data={"error": "invalid_grant"})):
        res = YouTubePublish().execute({"video_path": str(video), "title": "Test"})
    assert not res.success
    assert res.data["publish_log"]["entries"][0]["status"] == "failed"


# ---- TikTok ----

def test_tiktok_chunk_plan():
    assert TikTokPublish.chunk_plan(1000) == (1000, 1)
    assert TikTokPublish.chunk_plan(CHUNK * 2 + 5) == (CHUNK, 2)


def _tiktok_post_factory(final_status):
    def fake_post(url, **kw):
        if url.endswith("/oauth/token/"):
            return FakeResp(json_data={"access_token": "tok"})
        if url.endswith("/creator_info/query/"):
            return FakeResp(json_data={"data": {"privacy_level_options": ["SELF_ONLY"]}, "error": {"code": "ok"}})
        if url.endswith("/init/"):
            return FakeResp(json_data={"data": {"publish_id": "p1", "upload_url": "https://up.example"},
                                       "error": {"code": "ok"}})
        if url.endswith("/status/fetch/"):
            return FakeResp(json_data={"data": {"status": final_status}, "error": {"code": "ok"}})
        raise AssertionError(url)
    return fake_post


def test_tiktok_draft_mode(video, tt_env):
    with mock.patch("tools.publishers.tiktok_publish.requests.post",
                    side_effect=_tiktok_post_factory("SEND_TO_USER_INBOX")) as post, \
         mock.patch("tools.publishers.tiktok_publish.requests.put", return_value=FakeResp(status=201)):
        res = TikTokPublish().execute({"video_path": str(video), "caption": "hi #ai"})
    assert res.success, res.error
    assert any("/inbox/video/init/" in c.args[0] for c in post.call_args_list)
    assert res.data["publish_log"]["entries"][0]["status"] == "draft"


def test_tiktok_direct_unaudited_is_private(video, tt_env):
    with mock.patch("tools.publishers.tiktok_publish.requests.post",
                    side_effect=_tiktok_post_factory("PUBLISH_COMPLETE")), \
         mock.patch("tools.publishers.tiktok_publish.requests.put", return_value=FakeResp(status=201)):
        res = TikTokPublish().execute({"video_path": str(video), "caption": "hi", "mode": "direct"})
    entry = res.data["publish_log"]["entries"][0]
    assert entry["status"] == "pending_review" and entry["visibility"] == "private"
