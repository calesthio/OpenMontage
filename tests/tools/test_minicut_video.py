"""Contract coverage for the MiniCut CLI video provider (Kling 4, Kling 4 Edit).

A fake ``minicut`` stands in for the CLI, so no test signs in or spends.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tools.base_tool import ToolStatus
from tools.provider_pricing import PriceQuoteRequired

EXE = "/usr/local/bin/minicut"
KEY = "3f1c2b9a-8d4e-4f6a-9b2c-1d2e3f4a5b6c"
HASH = "a" * 64


class FakeMiniCut:
    """Answers like the minicut CLI: quote, paid send (one job per key), then jobs --get."""

    def __init__(self, saved):
        self.real_run = subprocess.run
        self.calls: list[list[str]] = []
        self.credits = 60.45
        self.send_exit = 0
        self.jobs: dict[str, str] = {}
        self.job_states = ["running", "done"]
        self.saved = saved
        self.done_row = None

    @staticmethod
    def _out(argv, code, data):
        return subprocess.CompletedProcess(argv, code, json.dumps(data) + "\n", "")

    def __call__(self, argv, **kwargs):
        if argv[0] != EXE:  # ffprobe and anything else run for real
            return self.real_run(argv, **kwargs)
        words = argv[1:]
        self.calls.append(words)
        if words[0] == "gen":
            if "--yes" not in words or words[words.index("--max-credits") + 1] != str(self.credits):
                line = (f"minicut gen {words[1]} out.mp4 --yes --max-credits {self.credits} "
                        f"--key {KEY} --quote {HASH}")
                return self._out(argv, 3, {"state": "needs_yes", "credits": self.credits - 0.4,
                                           "max_credits": self.credits, "model": words[1],
                                           "next_step": line})
            if self.send_exit:
                return self._out(argv, self.send_exit, {"error": {"code": "offline", "message": "minicut.ai did not answer."}})
            key = words[words.index("--key") + 1]
            replayed = key in self.jobs
            self.jobs.setdefault(key, f"job-{len(self.jobs) + 1}")
            return self._out(argv, 0, {"job_id": self.jobs[key], "state": "queued", "replayed": replayed})
        job_id = words[2]
        state = self.job_states.pop(0) if self.job_states else "running"
        row = {"job_id": job_id, "state": state}
        if state == "done":
            row.update(self.done_row or {"saved": True, "paths": [str(self.saved)]})
            return self._out(argv, 0, {"jobs": [row], "exit": 0})
        if state == "failed":
            row.update(credits_charged=0, error={"code": "output_blocked", "message": "Refused.",
                                                 "reason": "a real person's name", "change": "remove the name"})
            return self._out(argv, 5, {"jobs": [row], "exit": 5})
        return self._out(argv, 6, {"jobs": [row], "exit": 6})

    def sent(self):
        return [c for c in self.calls if c[0] == "gen" and "--yes" in c]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    import tools.minicut_cli as mod

    saved = tmp_path / "library" / "clip.mp4"
    saved.parent.mkdir()
    saved.write_bytes(b"fake-mp4")
    cli = FakeMiniCut(saved)
    real_which = shutil.which
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(mod.shutil, "which", lambda name: EXE if name == "minicut" else real_which(name))
    monkeypatch.setattr(mod.subprocess, "run", cli)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return cli


def _tool():
    from tools.video.minicut_video import MiniCutVideo

    return MiniCutVideo()


def _approved(tmp_path, **extra):
    approval = _tool().dry_run({"prompt": "a lighthouse at dusk"})["approval"]
    return {"prompt": "a lighthouse at dusk", "approval": approval,
            "output_path": str(tmp_path / "scenes" / "s1.mp4"), **extra}


def test_minicut_video_is_discovered_as_video_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("minicut_video")
    assert tool is not None
    assert tool.provider == "minicut"
    assert tool.capability == "video_generation"
    assert tool.dependencies == ["cmd:minicut"]
    assert tool.retry_policy.max_retries == 0


def test_unavailable_without_cli(monkeypatch):
    import tools.minicut_cli as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    assert _tool().get_status() == ToolStatus.UNAVAILABLE


def test_estimate_cost_requires_quote():
    with pytest.raises(PriceQuoteRequired):
        _tool().estimate_cost({"prompt": "x"})


def test_dry_run_returns_approval_and_sends_nothing(fake):
    plan = _tool().dry_run({"prompt": "a lighthouse at dusk", "seconds": 5})

    assert plan["estimated_credits"] == 60.45
    assert plan["approval"] == {"credits": 60.45, "model": "kling-4", "key": KEY, "quote": HASH}
    assert plan["would_execute"] is False
    assert fake.sent() == []
    quote = fake.calls[0]
    assert quote[:2] == ["gen", "kling-4"]
    assert "seconds=5" in quote and "resolution=720p" in quote
    assert quote[-3:] == ["--target", "prop:openmontage", "--json"]


def test_execute_without_approval_sends_nothing(fake, tmp_path):
    result = _tool().execute({"prompt": "x", "output_path": str(tmp_path / "out.mp4")})

    assert not result.success
    assert result.data["approval_required"] is True
    assert result.data["approval"]["credits"] == 60.45
    assert "60.45 credits" in result.error
    assert fake.sent() == []


def test_approved_job_sends_the_approved_line_and_writes_output(fake, tmp_path):
    inputs = _approved(tmp_path)
    result = _tool().execute(inputs)

    assert result.success, result.error
    out = tmp_path / "scenes" / "s1.mp4"
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"fake-mp4"
    assert result.cost_usd is None
    assert result.data["job_id"] == "job-1"
    [sent] = fake.sent()
    assert sent[sent.index("--max-credits") + 1] == "60.45"
    assert sent[sent.index("--key") + 1] == KEY
    assert sent[sent.index("--quote") + 1] == HASH


def test_same_approval_sent_twice_makes_one_job(fake, tmp_path):
    inputs = _approved(tmp_path)
    first = _tool().execute(inputs)
    fake.job_states = ["done"]
    second = _tool().execute(inputs)

    assert first.success and second.success
    assert first.data["job_id"] == second.data["job_id"] == "job-1"
    assert len(fake.jobs) == 1


def test_price_change_asks_again(fake, tmp_path):
    inputs = _approved(tmp_path)
    fake.credits = 75.0
    result = _tool().execute(inputs)

    assert not result.success
    assert result.data["approval_required"] is True
    assert result.data["approval"]["credits"] == 75.0
    assert fake.jobs == {}


def test_offline_send_keeps_approval_for_a_free_resend(fake, tmp_path):
    inputs = _approved(tmp_path)
    fake.send_exit = 7
    result = _tool().execute(inputs)

    assert not result.success
    assert "did not answer" in result.error
    assert result.data["approval"] == inputs["approval"]
    assert result.cost_usd is None


def test_refused_job_reports_why_and_charge(fake, tmp_path):
    fake.job_states = ["failed"]
    result = _tool().execute(_approved(tmp_path))

    assert not result.success
    assert "Why: a real person's name" in result.error
    assert "Change: remove the name" in result.error
    assert result.data["credits_charged"] == 0
    assert result.cost_usd is None


def test_done_but_not_saved_here_stops_polling(fake, tmp_path):
    fake.job_states = ["done"]
    fake.done_row = {"saved": False, "here": False}
    result = _tool().execute(_approved(tmp_path))

    assert not result.success
    assert "not saved here" in result.error
    assert result.data == {"resume_job": {"job_id": "job-1"}}


def test_timeout_returns_resume_job_and_resume_does_not_resubmit(fake, tmp_path):
    fake.job_states = ["running"]
    first = _tool().execute(_approved(tmp_path, poll_timeout=0))
    assert not first.success
    assert first.data == {"resume_job": {"job_id": "job-1"}}

    fake.job_states = ["done"]
    second = _tool().execute(
        {"prompt": "a lighthouse at dusk", "resume_job": first.data["resume_job"],
         "output_path": str(tmp_path / "out.mp4")}
    )
    assert second.success, second.error
    assert len(fake.sent()) == 1


def test_edit_needs_a_clip(fake):
    plan = _tool().dry_run({"prompt": "make it night", "model": "kling-4-edit"})
    assert "video_path" in plan["quote_reason"]
    assert fake.calls == []


def test_edit_clip_is_staged_in_minicut_cache(fake, tmp_path):
    clip = tmp_path / "shot.mp4"
    clip.write_bytes(b"clip")
    _tool().dry_run({"prompt": "make it night", "model": "kling-4-edit", "video_path": str(clip)})

    quote = fake.calls[0]
    role, path = quote[quote.index("--in") + 1].split("=", 1)
    assert role == "video_ref[0]"
    assert path.startswith(str(tmp_path / "home" / "cache" / "openmontage"))
    assert open(path, "rb").read() == b"clip"
