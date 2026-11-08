"""Contract coverage for the MiniCut CLI sound effects tool (ElevenLabs Sound Effects v2).

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
PROMPT = "a heavy wooden door slams shut"


class FakeMiniCut:
    """Answers like the minicut CLI: quote, paid send (one job per key), then jobs --get."""

    def __init__(self, saved):
        self.real_run = subprocess.run
        self.calls: list[list[str]] = []
        self.credits = 0.5
        self.jobs: dict[str, str] = {}
        self.job_states = ["running", "done"]
        self.saved = saved

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
                line = (f"minicut gen {words[1]} out.mp3 --yes --max-credits {self.credits} "
                        f"--key {KEY} --quote {HASH}")
                return self._out(argv, 3, {"state": "needs_yes", "credits": self.credits,
                                           "max_credits": self.credits, "model": words[1],
                                           "next_step": line})
            key = words[words.index("--key") + 1]
            replayed = key in self.jobs
            self.jobs.setdefault(key, f"job-{len(self.jobs) + 1}")
            return self._out(argv, 0, {"job_id": self.jobs[key], "state": "queued", "replayed": replayed})
        job_id = words[2]
        state = self.job_states.pop(0) if self.job_states else "running"
        row = {"job_id": job_id, "state": state}
        if state == "done":
            row.update(saved=True, paths=[str(self.saved)])
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

    saved = tmp_path / "library" / "door.mp3"
    saved.parent.mkdir()
    saved.write_bytes(b"fake-mp3")
    cli = FakeMiniCut(saved)
    real_which = shutil.which
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(mod.shutil, "which", lambda name: EXE if name == "minicut" else real_which(name))
    monkeypatch.setattr(mod.subprocess, "run", cli)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return cli


def _tool():
    from tools.audio.minicut_sfx import MiniCutSfx

    return MiniCutSfx()


def _approved(tmp_path, **extra):
    approval = _tool().dry_run({"prompt": PROMPT})["approval"]
    return {"prompt": PROMPT, "approval": approval,
            "output_path": str(tmp_path / "sfx" / "door.mp3"), **extra}


def _set(words):
    return [words[i + 1] for i, w in enumerate(words) if w == "--set"]


def test_minicut_sfx_is_discovered_as_sound_effects_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("minicut_sfx")
    assert tool is not None
    assert tool.provider == "minicut"
    assert tool.capability == "sound_effects"
    assert tool in registry.get_by_capability("sound_effects")
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
    plan = _tool().dry_run(
        {"prompt": PROMPT, "duration_seconds": 2.5, "prompt_influence": 0.6, "loop": True}
    )

    assert plan["estimated_credits"] == 0.5
    assert plan["approval"] == {"credits": 0.5, "model": "elevenlabs-sfx-v2", "key": KEY, "quote": HASH}
    assert plan["would_execute"] is False
    assert fake.sent() == []
    quote = fake.calls[0]
    assert quote[:2] == ["gen", "elevenlabs-sfx-v2"]
    assert quote[quote.index("--prompt") + 1] == PROMPT
    assert _set(quote) == ["duration-seconds=2.5", "prompt-influence=0.6", "loop=true"]
    assert "--in" not in quote
    assert quote[-3:] == ["--target", "prop:openmontage", "--json"]


def test_settings_left_out_are_not_sent(fake):
    _tool().dry_run({"prompt": PROMPT})
    assert _set(fake.calls[0]) == []


def test_execute_without_approval_sends_nothing(fake, tmp_path):
    result = _tool().execute({"prompt": PROMPT, "output_path": str(tmp_path / "out.mp3")})

    assert not result.success
    assert result.data["approval_required"] is True
    assert "0.5 credits" in result.error
    assert result.cost_usd == 0.0
    assert fake.sent() == []


def test_approved_job_sends_the_approved_line_and_writes_output(fake, tmp_path):
    result = _tool().execute(_approved(tmp_path))

    assert result.success, result.error
    out = tmp_path / "sfx" / "door.mp3"
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"fake-mp3"
    assert result.data["format"] == "mp3"
    assert result.data["job_id"] == "job-1"
    assert result.cost_usd is None
    [sent] = fake.sent()
    assert sent[sent.index("--max-credits") + 1] == "0.5"
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
    fake.credits = 0.75
    result = _tool().execute(inputs)

    assert not result.success
    assert result.data["approval"]["credits"] == 0.75
    assert fake.jobs == {}


def test_refused_job_reports_why_and_charge(fake, tmp_path):
    fake.job_states = ["failed"]
    result = _tool().execute(_approved(tmp_path))

    assert not result.success
    assert "Why: a real person's name" in result.error
    assert "Change: remove the name" in result.error
    assert result.data["credits_charged"] == 0


def test_timeout_returns_resume_job_and_resume_does_not_resubmit(fake, tmp_path):
    fake.job_states = ["running"]
    first = _tool().execute(_approved(tmp_path, poll_timeout=0))
    assert not first.success
    assert first.data == {"resume_job": {"job_id": "job-1"}}

    fake.job_states = ["done"]
    second = _tool().execute(
        {"prompt": PROMPT, "resume_job": first.data["resume_job"],
         "output_path": str(tmp_path / "out.mp3")}
    )
    assert second.success, second.error
    assert len(fake.sent()) == 1
