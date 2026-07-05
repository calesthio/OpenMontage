from __future__ import annotations

from tools.base_tool import ToolStatus
from tools.subtitle.doubao_subtitle_polish import DoubaoSubtitlePolish


SCRIPT = (
    "在这些案子上面，我积累了充足的实战经验。"
    "如果你身边刚好缺一位靠谱的律师朋友，今天刷到这条视频，"
    "不妨给徐律师点个赞、留个关注。"
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_status_degraded_without_key_because_dry_run_still_works(monkeypatch):
    monkeypatch.delenv("DOUBAO_SUBTITLE_API_KEY", raising=False)
    monkeypatch.delenv("DOUBAO_VISION_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert DoubaoSubtitlePolish().get_status() == ToolStatus.DEGRADED


def test_dry_run_polishes_subtitles_without_network(monkeypatch):
    def fail_post(*args, **kwargs):
        raise AssertionError("dry_run must not call network")

    monkeypatch.setattr("requests.post", fail_post)

    result = DoubaoSubtitlePolish().execute(
        {
            "text": SCRIPT,
            "start": 0,
            "end": 8,
            "dry_run": True,
            "max_chars_per_line": 12,
        }
    )

    assert result.success, result.error
    assert result.data["provider"] == "doubao"
    assert result.data["mode"] == "dry_run"
    assert result.data["api_called"] is False
    assert result.data["cue_count"] >= 5
    assert all(len(cue["text"].splitlines()) <= 2 for cue in result.data["cues"])
    assert all(
        len(line) <= 12
        for cue in result.data["cues"]
        for line in cue["text"].splitlines()
        if line.strip()
    )
    assert "prompt" in result.data
    assert "只输出 JSON" in result.data["prompt"]


def test_live_mode_posts_text_only_responses_payload(monkeypatch):
    monkeypatch.setenv("DOUBAO_SUBTITLE_API_KEY", "subtitle-key")
    monkeypatch.setenv("DOUBAO_SUBTITLE_MODEL", "doubao-subtitle-test")
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "output_text": (
                    '{"cues":['
                    '{"text":"在这些案子上面，"},'
                    '{"text":"我积累了充足的实战经验。"},'
                    '{"text":"靠谱的律师朋友，"}'
                    '],"notes":["按口播节奏短句显示"]}'
                ),
                "usage": {"total_tokens": 88},
            }
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = DoubaoSubtitlePolish().execute(
        {
            "text": SCRIPT,
            "start": 0,
            "end": 8,
            "dry_run": False,
            "max_chars_per_line": 12,
        }
    )

    assert result.success, result.error
    assert result.data["api_called"] is True
    assert result.data["model"] == "doubao-subtitle-test"
    assert result.data["usage"]["total_tokens"] == 88
    assert result.data["cues"][0]["start"] == 0
    assert result.data["cues"][-1]["end"] == 8
    request = calls[0]
    assert request["url"].endswith("/api/v3/responses")
    assert request["headers"]["Authorization"] == "Bearer subtitle-key"
    assert request["json"]["model"] == "doubao-subtitle-test"
    content = request["json"]["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "不要编造时间戳" in content[0]["text"]


def test_live_mode_returns_clear_error_for_invalid_json(monkeypatch):
    monkeypatch.setenv("DOUBAO_SUBTITLE_API_KEY", "subtitle-key")
    monkeypatch.setenv("DOUBAO_SUBTITLE_MODEL", "doubao-subtitle-test")

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"output_text": "不是 JSON"})

    monkeypatch.setattr("requests.post", fake_post)

    result = DoubaoSubtitlePolish().execute(
        {
            "text": SCRIPT,
            "start": 0,
            "end": 8,
            "dry_run": False,
        }
    )

    assert not result.success
    assert "valid JSON" in result.error
    assert "subtitle-key" not in result.error
