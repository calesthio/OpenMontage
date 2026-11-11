"""Contract coverage for the MiniCut CLI video upscaler (Topaz).

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
        self.credits = 12.5
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
                line = (f"minicut gen {words[1]} out.mp4 --yes --max-credits {self.credits} "
                        f"--key {KEY} --quote {HASH}")
                return self._out(argv, 3, {"state": "needs_yes", "credits": self.credits - 0.5,
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
            row.update({"saved": True, "paths": [str(self.saved)]})
            return self._out(argv, 0, {"jobs": [row], "exit": 0})
        return self._out(argv, 6, {"jobs": [row], "exit": 6})

    def sent(self):
        return [c for c in self.calls if c[0] == "gen" and "--yes" in c]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    import tools.minicut_cli as mod

    saved = tmp_path / "library" / "big.mp4"
    saved.parent.mkdir()
    saved.write_bytes(b"fake-upscaled-mp4")
    cli = FakeMiniCut(saved)
    real_which = shutil.which
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(mod.shutil, "which", lambda name: EXE if name == "minicut" else real_which(name))
    monkeypatch.setattr(mod.subprocess, "run", cli)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return cli


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "shot.mp4"
    path.write_bytes(b"small-clip")
    return path


def _tool():
    from tools.enhancement.minicut_upscale import MiniCutUpscale

    return MiniCutUpscale()


def _approved(clip, **extra):
    approval = _tool().dry_run({"input_path": str(clip)})["approval"]
    return {"input_path": str(clip), "approval": approval, **extra}


def test_minicut_upscale_is_found_next_to_local_upscale():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("minicut_upscale")
    assert tool is not None
    assert tool.provider == "minicut"
    assert tool.capability == registry.get("upscale").capability == "enhancement"
    assert tool.dependencies == ["cmd:minicut"]
    assert tool.retry_policy.max_retries == 0
    names = {t.name for t in registry.find_by_capability("video_upscale")}
    assert {"upscale", "minicut_upscale"} <= names
    assert "minicut_upscale" not in {t.name for t in registry.find_by_capability("image_upscale")}


def test_unavailable_without_cli(monkeypatch):
    import tools.minicut_cli as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    assert _tool().get_status() == ToolStatus.UNAVAILABLE


def test_estimate_cost_requires_quote():
    with pytest.raises(PriceQuoteRequired):
        _tool().estimate_cost({"input_path": "shot.mp4"})


def test_dry_run_returns_approval_and_sends_nothing(fake, clip, tmp_path):
    plan = _tool().dry_run({"input_path": str(clip), "scale": 4})

    assert plan["estimated_credits"] == 12.5
    assert plan["approval"] == {"credits": 12.5, "model": "topaz-standard", "key": KEY, "quote": HASH}
    assert plan["would_execute"] is False
    assert fake.sent() == []
    [quote] = fake.calls
    assert quote[:3] == ["gen", "topaz-standard", "shot_upscaled.mp4"]
    assert "--prompt" not in quote
    assert quote[quote.index("--set") + 1] == "upscale-factor=4"
    role, path = quote[quote.index("--in") + 1].split("=", 1)
    assert role == "source"
    assert path.startswith(str(tmp_path / "home" / "cache" / "openmontage"))
    assert open(path, "rb").read() == b"small-clip"
    assert quote[-3:] == ["--target", "prop:openmontage", "--json"]


def test_still_image_is_refused_before_any_cli_call(fake, tmp_path):
    image = tmp_path / "frame.png"
    image.write_bytes(b"png")
    plan = _tool().dry_run({"input_path": str(image)})

    assert "still images" in plan["quote_reason"]
    assert fake.calls == []


def test_execute_without_approval_sends_nothing(fake, clip):
    result = _tool().execute({"input_path": str(clip)})

    assert not result.success
    assert result.data["approval_required"] is True
    assert "12.5 credits" in result.error
    assert fake.sent() == []


def test_approved_job_writes_upscaled_clip_to_output_path(fake, clip, tmp_path):
    out = tmp_path / "renders" / "shot_4k.mp4"
    result = _tool().execute(_approved(clip, output_path=str(out)))

    assert result.success, result.error
    assert result.artifacts == [str(out)]
    assert out.read_bytes() == b"fake-upscaled-mp4"
    assert result.cost_usd is None
    assert result.data["model"] == "topaz-standard"
    assert result.data["job_id"] == "job-1"
    [sent] = fake.sent()
    assert sent[sent.index("--max-credits") + 1] == "12.5"
    assert sent[sent.index("--key") + 1] == KEY
    assert sent[sent.index("--quote") + 1] == HASH


def test_default_output_sits_next_to_the_input(fake, clip):
    result = _tool().execute(_approved(clip))

    assert result.success, result.error
    assert result.artifacts == [str(clip.with_name("shot_upscaled.mp4"))]


def test_same_approval_sent_twice_makes_one_job(fake, clip):
    inputs = _approved(clip)
    first = _tool().execute(inputs)
    fake.job_states = ["done"]
    second = _tool().execute(inputs)

    assert first.success and second.success
    assert first.data["job_id"] == second.data["job_id"] == "job-1"
    assert len(fake.jobs) == 1


def test_price_change_asks_again(fake, clip):
    inputs = _approved(clip)
    fake.credits = 20.0
    result = _tool().execute(inputs)

    assert not result.success
    assert result.data["approval_required"] is True
    assert result.data["approval"]["credits"] == 20.0
    assert fake.jobs == {}


def test_timeout_returns_resume_job_and_resume_does_not_resubmit(fake, clip):
    fake.job_states = ["running"]
    first = _tool().execute(_approved(clip, poll_timeout=0))
    assert not first.success
    assert first.data == {"resume_job": {"job_id": "job-1"}}

    fake.job_states = ["done"]
    second = _tool().execute({"input_path": str(clip), "resume_job": first.data["resume_job"]})
    assert second.success, second.error
    assert len(fake.sent()) == 1
