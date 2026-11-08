"""Contract coverage for the MiniCut CLI image, voice and music providers.

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
HASH = "b" * 64
CREDITS = 2.5


class FakeMiniCut:
    """Answers like the minicut CLI: quote, paid send (one job per key), then jobs --get."""

    def __init__(self, saved):
        self.calls: list[list[str]] = []
        self.jobs: dict[str, str] = {}
        self.job_states = ["running", "done"]
        self.saved = saved

    @staticmethod
    def _out(argv, code, data):
        return subprocess.CompletedProcess(argv, code, json.dumps(data) + "\n", "")

    def __call__(self, argv, **kwargs):
        words = argv[1:]
        self.calls.append(words)
        if words[0] == "gen":
            if "--yes" not in words:
                line = f"minicut gen {words[1]} out --yes --max-credits {CREDITS} --key {KEY} --quote {HASH}"
                return self._out(argv, 3, {"state": "needs_yes", "credits": CREDITS, "max_credits": CREDITS,
                                           "model": words[1], "next_step": line})
            key = words[words.index("--key") + 1]
            self.jobs.setdefault(key, f"job-{len(self.jobs) + 1}")
            return self._out(argv, 0, {"job_id": self.jobs[key], "state": "queued", "replayed": False})
        state = self.job_states.pop(0) if self.job_states else "running"
        row = {"job_id": words[2], "state": state}
        if state == "done":
            row.update(saved=True, paths=[str(self.saved)])
            return self._out(argv, 0, {"jobs": [row], "exit": 0})
        return self._out(argv, 6, {"jobs": [row], "exit": 6})

    def sent(self):
        return [c for c in self.calls if c[0] == "gen" and "--yes" in c]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    import tools.minicut_cli as mod

    saved = tmp_path / "library" / "track.wav"
    saved.parent.mkdir()
    saved.write_bytes(b"fake-audio")
    cli = FakeMiniCut(saved)
    real_which = shutil.which
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(mod.shutil, "which", lambda name: EXE if name == "minicut" else real_which(name))
    monkeypatch.setattr(mod.subprocess, "run", cli)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return cli


def _tools():
    from tools.audio.minicut_music import MiniCutMusic
    from tools.audio.minicut_tts import MiniCutTTS
    from tools.graphics.minicut_image import MiniCutImage

    return {"image": MiniCutImage(), "tts": MiniCutTTS(), "music": MiniCutMusic()}


def test_each_capability_is_discovered_under_one_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    found = {t.name: t.capability for t in registry.get_by_provider("minicut")}
    assert found["minicut_image"] == "image_generation"
    assert found["minicut_tts"] == "tts"
    assert found["minicut_music"] == "music_generation"
    assert registry.get("minicut_tool") is None  # the shared base is not a tool
    for name in ("minicut_image", "minicut_tts", "minicut_music"):
        tool = registry.get(name)
        assert tool.dependencies == ["cmd:minicut"]
        assert tool.retry_policy.max_retries == 0


def test_unavailable_without_cli_and_cost_needs_a_quote(monkeypatch):
    import tools.minicut_cli as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    for tool in _tools().values():
        assert tool.get_status() == ToolStatus.UNAVAILABLE
        with pytest.raises(PriceQuoteRequired):
            tool.estimate_cost({})


def test_image_quote_sends_quality_and_staged_references(fake, tmp_path):
    ref = tmp_path / "face.png"
    ref.write_bytes(b"png")
    plan = _tools()["image"].dry_run({"prompt": "a red kite", "image_paths": [str(ref)]})

    assert plan["approval"] == {"credits": CREDITS, "model": "gpt-image-2", "key": KEY, "quote": HASH}
    assert fake.sent() == []
    quote = fake.calls[0]
    assert quote[:4] == ["gen", "gpt-image-2", "minicut_image.png", "--prompt"]
    assert "quality=medium" in quote
    role, path = quote[quote.index("--in") + 1].split("=", 1)
    assert role == "image_ref[0]"
    assert path.startswith(str(tmp_path / "home" / "cache" / "openmontage"))


def test_tts_quote_sends_text_and_the_selector_voice(fake):
    _tools()["tts"].dry_run({"text": "Hello there.", "voice_id": "Rachel"})
    quote = fake.calls[0]
    assert quote[:5] == ["gen", "elevenlabs-v3", "minicut_voice.mp3", "--prompt", "Hello there."]
    assert "voice=Rachel" in quote

    _tools()["tts"].dry_run({"text": "Hi."})
    assert not any(w.startswith("voice=") for w in fake.calls[1])


def test_music_quote_sends_prompt_and_negative_prompt(fake):
    _tools()["music"].dry_run({"prompt": "calm piano, instrumental", "negative_prompt": "drums"})
    quote = fake.calls[0]
    assert quote[:2] == ["gen", "lyria-3-5"]
    assert "negative-prompt=drums" in quote
    assert quote[-3:] == ["--target", "prop:openmontage", "--json"]


def test_execute_without_approval_sends_nothing(fake, tmp_path):
    for tool, inputs in zip(_tools().values(), ({"prompt": "x"}, {"text": "x"}, {"prompt": "x"})):
        result = tool.execute({**inputs, "output_path": str(tmp_path / "out")})
        assert not result.success
        assert result.data["approval_required"] is True
        assert f"{CREDITS} credits" in result.error
    assert fake.sent() == []


def test_approved_job_writes_output_once_and_keeps_the_returned_file_type(fake, tmp_path):
    music = _tools()["music"]
    approval = music.dry_run({"prompt": "calm piano"})["approval"]
    inputs = {"prompt": "calm piano", "approval": approval, "output_path": str(tmp_path / "audio" / "bed.mp3")}

    first = music.execute(inputs)
    fake.job_states = ["done"]
    second = music.execute(inputs)

    assert first.success, first.error
    out = tmp_path / "audio" / "bed.wav"
    assert first.artifacts == [str(out)]
    assert out.read_bytes() == b"fake-audio"
    assert first.data["format"] == "wav"
    assert first.cost_usd is None
    assert first.data["job_id"] == second.data["job_id"] == "job-1"
    assert len(fake.jobs) == 1


def test_timeout_returns_resume_job_and_resume_does_not_resubmit(fake, tmp_path):
    tts = _tools()["tts"]
    approval = tts.dry_run({"text": "Hello."})["approval"]
    fake.job_states = ["running"]
    first = tts.execute({"text": "Hello.", "approval": approval, "poll_timeout": 0,
                         "output_path": str(tmp_path / "vo.mp3")})
    assert first.data == {"resume_job": {"job_id": "job-1"}}

    fake.job_states = ["done"]
    second = tts.execute({"text": "Hello.", "resume_job": first.data["resume_job"],
                          "output_path": str(tmp_path / "vo.mp3")})
    assert second.success, second.error
    assert len(fake.sent()) == 1


def test_selectors_route_to_minicut(fake, tmp_path):
    from tools.audio.tts_selector import TTSSelector
    from tools.graphics.image_selector import ImageSelector

    ranked = ImageSelector().execute({"prompt": "a red kite", "operation": "rank"})
    assert "minicut_image" in [r["tool_name"] for r in ranked.data["rankings"]]

    result = TTSSelector().execute({"text": "Hello.", "preferred_provider": "minicut",
                                    "voice_id": "Rachel", "output_path": str(tmp_path / "vo.mp3")})
    assert result.data["approval_required"] is True
    assert fake.calls[-1][1] == "elevenlabs-v3"
