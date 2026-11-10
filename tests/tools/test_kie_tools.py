"""Behavioral tests for the KIE AI tools (kie_video, kie_image, kie_tts, kie_music)
with a faked `requests` module. No network access and no API key required.

Covers the paid-job lifecycle the PR #777 review flagged:
- submit-once: createTask is called exactly once per fresh execute() call
- timeout: a poll timeout surfaces task_id in the failed ToolResult so the
  caller can recover instead of blindly resubmitting
- interrupted download: a download failure after a successful poll also
  surfaces task_id (the job succeeded and may be billed -- don't resubmit)
- resume: passing resume_task_id skips createTask entirely and only polls

Run: pytest tests/tools/test_kie_tools.py -v
"""

from __future__ import annotations

import sys
import types

import pytest

from tools import kie_client
from tools.audio.kie_music import KieMusic
from tools.audio.kie_tts import KieTTS
from tools.graphics.kie_image import KieImage
from tools.video.kie_video import KieVideo


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200, text=""):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code
        self.text = text or str(self._payload)

    def json(self):
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
    monkeypatch.setenv("KIE_API_KEY", "test-key")
    monkeypatch.delenv("KIEAI_API_KEY", raising=False)
    monkeypatch.setattr(kie_client.time, "sleep", lambda _s: None)

    return types.SimpleNamespace(calls=calls, queues=queues)


SUBMITTED = FakeResponse({"code": 200, "data": {"taskId": "task_abc123"}})


def success_poll(result_urls):
    return FakeResponse({
        "code": 200,
        "data": {"taskId": "task_abc123", "state": "success", "resultJson": f'{{"resultUrls": {result_urls!r}}}'.replace("'", '"')},
    })


def generating_poll():
    return FakeResponse({"code": 200, "data": {"taskId": "task_abc123", "state": "generating"}})


# ---------------------------------------------------------------------------
# submit-once: a fresh execute() creates exactly one task
# ---------------------------------------------------------------------------

class TestSubmitOnce:
    def test_video_creates_exactly_one_task(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [success_poll(["https://x/clip.mp4"])]
        fake_requests.queues["get"].append(FakeResponse(content=b"MP4DATA"))

        result = KieVideo().execute({
            "prompt": "a rocket launching",
            "output_path": str(tmp_path / "clip.mp4"),
        })

        assert result.success is True, result.error
        assert len(fake_requests.calls["post"]) == 1
        assert fake_requests.calls["post"][0]["url"] == kie_client.CREATE_TASK_ENDPOINT
        assert result.data["task_id"] == "task_abc123"

    def test_image_creates_exactly_one_task(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [success_poll(["https://x/img.png"]), FakeResponse(content=b"PNGDATA")]

        result = KieImage().execute({"prompt": "a japanese garden", "output_path": str(tmp_path / "img.png")})

        assert result.success is True, result.error
        assert len(fake_requests.calls["post"]) == 1

    def test_tts_creates_exactly_one_task(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [success_poll(["https://x/out.wav"]), FakeResponse(content=b"WAVDATA")]

        result = KieTTS().execute({"text": "Xin chao", "output_path": str(tmp_path / "out.wav")})

        assert result.success is True, result.error
        assert len(fake_requests.calls["post"]) == 1
        body = fake_requests.calls["post"][0]["json"]
        assert body["model"] == "google/gemini-3-8-flash-tts"


# ---------------------------------------------------------------------------
# timeout: task_id must survive a poll timeout so the caller can recover
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_poll_timeout_surfaces_task_id_and_resume_hint(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [generating_poll() for _ in range(5)]

        result = KieVideo().execute({
            "prompt": "p",
            "poll_interval": 1,
            "poll_timeout": 3,
            "output_path": str(tmp_path / "o.mp4"),
        })

        assert result.success is False
        assert result.data.get("task_id") == "task_abc123"
        assert "task_abc123" in result.error
        assert "resume_task_id" in result.error

    def test_timeout_is_not_in_retryable_errors(self):
        """createTask is not idempotent on KIE's side -- a retry executor must not
        blindly resubmit after a timeout. See docs/PROVIDERS.md 'KIE AI'."""
        for cls in (KieVideo, KieImage, KieTTS, KieMusic):
            assert "timeout" not in cls.retry_policy.retryable_errors, cls.name


# ---------------------------------------------------------------------------
# interrupted download: poll succeeded (job billed), download failed
# ---------------------------------------------------------------------------

class TestInterruptedDownload:
    def test_download_failure_after_success_keeps_task_id(self, fake_requests, tmp_path, monkeypatch):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [success_poll(["https://x/img.png"])]

        def broken_get(url, **kwargs):
            if url == "https://x/img.png":
                raise ConnectionError("connection reset")
            fake_requests.calls["get"].append({"url": url, **kwargs})
            if not fake_requests.queues["get"]:
                raise AssertionError(f"Unexpected GET to {url}")
            return fake_requests.queues["get"].pop(0)

        monkeypatch.setattr(sys.modules["requests"], "get", broken_get)

        result = KieImage().execute({"prompt": "p", "output_path": str(tmp_path / "img.png")})

        assert result.success is False
        assert result.data.get("task_id") == "task_abc123"
        assert "task_abc123" in result.error
        assert "do NOT resubmit" in result.error
        # The one and only createTask call already happened -- must not be repeated.
        assert len(fake_requests.calls["post"]) == 1


# ---------------------------------------------------------------------------
# resume: resume_task_id must skip createTask entirely
# ---------------------------------------------------------------------------

class TestResume:
    def test_resume_never_calls_create_task(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = []  # any POST is a bug -- fail loudly
        fake_requests.queues["get"] = [success_poll(["https://x/clip.mp4"]), FakeResponse(content=b"MP4DATA")]

        result = KieVideo().execute({
            "resume_task_id": "task_abc123",
            "output_path": str(tmp_path / "clip.mp4"),
        })

        assert result.success is True, result.error
        assert fake_requests.calls["post"] == []
        assert result.data["task_id"] == "task_abc123"
        out = tmp_path / "clip.mp4"
        assert out.read_bytes() == b"MP4DATA"

    def test_resume_after_timeout_round_trips(self, fake_requests, tmp_path):
        """The realistic recovery flow: first call times out, second call with
        resume_task_id finishes the same job without a second createTask."""
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [generating_poll()]
        first = KieImage().execute({
            "prompt": "p",
            "poll_interval": 1,
            "poll_timeout": 1,
            "output_path": str(tmp_path / "img.png"),
        })
        assert first.success is False
        task_id = first.data["task_id"]

        fake_requests.queues["get"] = [success_poll(["https://x/img.png"]), FakeResponse(content=b"PNGDATA")]
        second = KieImage().execute({"resume_task_id": task_id, "output_path": str(tmp_path / "img.png")})

        assert second.success is True, second.error
        assert len(fake_requests.calls["post"]) == 1  # only the original submission, ever
        assert second.data["task_id"] == task_id


# ---------------------------------------------------------------------------
# submission failure before a task_id is known
# ---------------------------------------------------------------------------

class TestSubmissionFailure:
    def test_transport_error_on_submit_has_no_task_id(self, fake_requests, tmp_path):
        """A network error on createTask itself means the outcome is genuinely
        unknown -- there is no task_id to report or resume with."""

        def raising_post(url, **kwargs):
            raise ConnectionError("network unreachable")

        fake_requests.calls["post"] = []
        import sys as _sys
        monkeypatch_module = _sys.modules["requests"]
        monkeypatch_module.post = raising_post

        result = KieVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False
        assert "task_id" not in result.data
        assert "kie.ai/logs" in result.error
