"""cmd_narration must run end-to-end and record a real sentence count.

Regression for a latent NameError: the stage built its manifest with
`len(sentences)` without ever binding `sentences`, so any episode that
actually had to synthesize narration crashed instead of recording it.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

import scripts.run_episode as run_episode
from tools.base_tool import ToolResult

SCRIPT = """# Pilot

## Hook
- Sea ice seals the ocean from the sky. [SE-01]
- Life could still use chemical gradients instead of sunlight. [SE-02]
"""


def _write_wav(path: Path, dur: float = 2.0, sr: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(dur * sr))


@pytest.fixture()
def episode(tmp_path):
    ep = tmp_path / "ep"
    (ep / "artifacts").mkdir(parents=True)
    (ep / "script.md").write_text(SCRIPT, encoding="utf-8")
    return ep


def test_cmd_narration_records_sentence_count(episode, monkeypatch):
    state = {"episode_dir": str(episode), "narration_helper": "torch"}
    helper = episode / "helper.py"
    helper.write_text("# fake helper\n", encoding="utf-8")
    monkeypatch.setitem(run_episode.NARRATION_HELPERS, "torch", helper)
    monkeypatch.setattr(run_episode, "NARRATION_PYTHON", Path("/usr/bin/env"))

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        _write_wav(Path(cmd[-1]), 2.0)

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(run_episode.subprocess, "run", fake_run)

    class FakeFinish:
        def execute(self, params):
            src, dst = Path(params["input_path"]), Path(params["output_path"])
            dst.write_bytes(src.read_bytes())
            return ToolResult(success=True, data={"duration_s": 2.0})

    monkeypatch.setattr("tools.audio.finish_audio.FinishAudioTool", FakeFinish)

    res = run_episode.cmd_narration("se_pilot", state)
    assert res["status"] == "OK", res
    assert (episode / "narration_finished.wav").exists()

    manifest = json.loads(
        (episode / "artifacts" / "narration_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sentences"] == 2
    assert manifest["expected_duration"] == pytest.approx(2.0)


def test_cmd_narration_fails_closed_without_helper(episode, monkeypatch):
    state = {"episode_dir": str(episode), "narration_helper": "torch"}
    monkeypatch.setitem(run_episode.NARRATION_HELPERS, "torch", episode / "missing.py")
    monkeypatch.setattr(run_episode, "NARRATION_PYTHON", Path("/nonexistent/python"))
    res = run_episode.cmd_narration("se_pilot", state)
    assert res["status"] == "BLOCKED"
    assert "helper" in res["error"]


def test_manifest_engine_matches_the_helper_that_ran(episode, monkeypatch):
    """The manifest must not claim the ONNX engine when the torch helper ran."""
    state = {"episode_dir": str(episode), "narration_helper": "torch"}
    helper = episode / "helper.py"
    helper.write_text("# fake helper\n", encoding="utf-8")
    monkeypatch.setitem(run_episode.NARRATION_HELPERS, "torch", helper)
    monkeypatch.setattr(run_episode, "NARRATION_PYTHON", Path("/usr/bin/env"))

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        _write_wav(Path(cmd[-1]), 1.0)

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(run_episode.subprocess, "run", fake_run)

    class FakeFinish:
        def execute(self, params):
            src, dst = Path(params["input_path"]), Path(params["output_path"])
            dst.write_bytes(src.read_bytes())
            return ToolResult(success=True, data={"duration_s": 1.0})

    monkeypatch.setattr("tools.audio.finish_audio.FinishAudioTool", FakeFinish)
    assert run_episode.cmd_narration("se_pilot", state)["status"] == "OK"
    manifest = json.loads(
        (episode / "artifacts" / "narration_manifest.json").read_text(encoding="utf-8"))
    assert manifest["engine"] == "kokoro_82m_torch_cpu"


def test_resumed_narration_rewrites_a_missing_manifest(episode):
    """A resume must not leave QC without a narration manifest."""
    state = {"episode_dir": str(episode)}
    wav = episode / "narration_finished.wav"
    _write_wav(wav, 3.0, sr=44100)
    res = run_episode.cmd_narration("se_pilot", state)
    assert res["status"] == "OK", res
    manifest = json.loads(
        (episode / "artifacts" / "narration_manifest.json").read_text(encoding="utf-8"))
    assert manifest["expected_duration"] == pytest.approx(3.0, abs=0.05)
    assert manifest["sentences"] == 2
    assert manifest["engine"].startswith("kokoro")


# ------------------------------------------------------------------ subtitles
def test_subtitles_use_bullet_script_sentences(episode, monkeypatch):
    """A bullet script must produce a real transcript, not an empty one."""
    state = {"episode_dir": str(episode)}
    wav = episode / "narration_finished.wav"
    _write_wav(wav, 1.0, sr=44100)
    (episode / "scripts").mkdir(exist_ok=True)
    (episode / "scripts" / "z3_subtitles.py").write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(run_episode, "ROOT", episode)
    monkeypatch.setattr(run_episode, "VENV_PY", Path("/usr/bin/env"))
    captured = {}

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        captured["cmd"] = cmd
        Path(cmd[-2]).write_text('{"words": []}', encoding="utf-8")
        Path(cmd[-1]).write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n",
                                 encoding="utf-8")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(run_episode.subprocess, "run", fake_run)
    res = run_episode.cmd_subtitles("se_pilot", state)
    assert res["status"] == "OK", res
    text = captured["cmd"][3]
    assert "Sea ice seals the ocean" in text
    assert "chemical gradients" in text


def test_subtitles_block_instead_of_crashing_when_venv_missing(episode, monkeypatch):
    state = {"episode_dir": str(episode)}
    wav = episode / "narration_finished.wav"
    _write_wav(wav, 1.0, sr=44100)
    monkeypatch.setattr(run_episode, "VENV_PY", Path("/nonexistent/python"))
    res = run_episode.cmd_subtitles("se_pilot", state)
    assert res["status"] == "BLOCKED"
    assert "subtitle" in res["error"].lower()


def test_subtitles_prefer_the_faster_whisper_helper(episode, monkeypatch):
    """stable-ts cannot import here (torchaudio ABI); the CTranslate2 helper
    must be used with the (wav, words, srt) argument order."""
    state = {"episode_dir": str(episode)}
    _write_wav(episode / "narration_finished.wav", 1.0, sr=44100)
    scripts = episode / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "fw_subtitles.py").write_text("# fw\n", encoding="utf-8")
    (scripts / "z3_subtitles.py").write_text("# legacy\n", encoding="utf-8")
    monkeypatch.setattr(run_episode, "ROOT", episode)
    monkeypatch.setattr(run_episode, "VENV_PY", Path("/usr/bin/env"))
    captured = {}

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        captured["cmd"] = cmd
        Path(cmd[-2]).write_text('{"words": []}', encoding="utf-8")
        Path(cmd[-1]).write_text("", encoding="utf-8")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(run_episode.subprocess, "run", fake_run)
    assert run_episode.cmd_subtitles("se_pilot", state)["status"] == "OK"
    assert captured["cmd"][1].endswith("fw_subtitles.py")
    assert len(captured["cmd"]) == 5  # py, helper, wav, words, srt
