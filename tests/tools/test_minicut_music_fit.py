"""Contract coverage for minicut_music_fit: music written to the cut, played by the MiniCut CLI.

A fake ``minicut`` stands in for the CLI, so no test needs the CLI, its samples or a sign-in.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from tools.base_tool import ToolStatus

EXE = "/usr/local/bin/minicut"
needs_ffprobe = pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not installed")


def _wav(path: Path, seconds: float, rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * round(seconds * rate))


class FakeMiniCut:
    """Answers `minicut music check` and `minicut music render` like the CLI (plain text, exit code)."""

    def __init__(self):
        self.real_run = subprocess.run
        self.calls: list[list[str]] = []
        self.check_problems: list[str] = []
        self.render_extra_s = 0.0

    def __call__(self, argv, **kwargs):
        if argv[0] != EXE:  # ffprobe runs for real
            return self.real_run(argv, **kwargs)
        words = argv[1:]
        self.calls.append(words)
        song_path = Path(words[2])
        song = json.loads(song_path.read_text(encoding="utf-8"))
        if words[1] == "check":
            if self.check_problems:
                out = "\n".join(self.check_problems) + f"\nFAIL: {len(self.check_problems)} problem(s)."
                return subprocess.CompletedProcess(argv, 5, out + "\n", "")
            return subprocess.CompletedProcess(argv, 0, f"PASS: {song['length_s']} s\n", "")
        stem = song_path.name.replace(".song.json", "")
        _wav(song_path.with_name(stem + ".wav"), song["length_s"] + self.render_extra_s)
        report = {"length_s": song["length_s"], "notes": sum(len(t["notes"]) for t in song["tracks"]),
                  "integrated_lufs": -16.1, "true_peak_dbtp": -1.2}
        song_path.with_name(stem + ".report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "render: done\n", "")


@pytest.fixture
def fake(monkeypatch, tmp_path):
    import tools.minicut_cli as mod

    cli = FakeMiniCut()
    real_which = shutil.which
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(mod.shutil, "which", lambda name: EXE if name == "minicut" else real_which(name))
    monkeypatch.setattr(mod.subprocess, "run", cli)
    return cli


def _tool():
    from tools.audio.minicut_music_fit import MiniCutMusicFit

    return MiniCutMusicFit()


CUTS = [
    {"id": "a", "source": "a.mp4", "in_seconds": 2.0, "out_seconds": 5.5},
    {"id": "logo", "source": "logo.png", "in_seconds": 0, "out_seconds": 9, "layer": "overlay"},
    {"id": "b", "source": "b.mp4", "in_seconds": 0, "out_seconds": 8.0, "speed": 2.0},
    {"id": "c", "source": "c.mp4", "in_seconds": 1.0, "out_seconds": 3.25},
]


def test_minicut_music_is_discovered_as_free_local_music_provider():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("minicut_music_fit")
    assert tool is not None
    assert tool.provider == "minicut"
    assert tool.capability == "music_generation"
    assert tool.runtime.value == "local"
    assert tool.dependencies == ["cmd:minicut"]
    assert tool.estimate_cost({"duration_seconds": 30}) == 0.0


def test_unavailable_without_cli(monkeypatch):
    import tools.minicut_cli as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    assert _tool().get_status() == ToolStatus.UNAVAILABLE


def test_timeline_follows_edit_decisions_cuts():
    from tools.audio.minicut_music_fit import timeline

    # 3.5 s, then 8 s at double speed (4 s), then 2.25 s; the overlay is not a cut.
    assert timeline({"cuts": CUTS}) == (9.75, [3.5, 7.5])
    assert timeline({"duration_seconds": 12, "cut_times": [4, 0, 12, 8, 4]}) == (12.0, [4.0, 8.0])
    with pytest.raises(ValueError):
        timeline({"cut_times": [1, 2]})


def test_song_changes_chord_and_hits_on_every_cut():
    from tools.audio.minicut_music_fit import write_song

    song = write_song(9.75, [3.5, 7.5], key="D", mode="minor", bpm=90)
    tracks = {t["name"]: t for t in song["tracks"]}

    assert song["format"] == "minicut-song/1"
    assert song["length_s"] == 9.75
    assert [n[1] for n in tracks["cut hits"]["notes"]] == [3.5, 7.5]
    assert [n[1] for n in tracks["cello"]["notes"]] == [0.0, 3.5, 7.5]
    assert [n[0] for n in tracks["cello"]["notes"]] == [38, 46, 41]  # D2, Bb2, F2: i VI III
    assert max(n[1] for t in song["tracks"] for n in t["notes"]) < 9.75
    assert 3.5 in [n[1] for n in tracks["piano"]["notes"]]  # the pulse restarts on the cut
    assert write_song(9.75, [3.5, 7.5]) == song  # same cuts in, same song out
    with pytest.raises(ValueError):
        write_song(9.75, [], key="H")


@needs_ffprobe
def test_execute_checks_then_renders_and_writes_wav_of_cut_length(fake, tmp_path):
    out = tmp_path / "audio" / "score.wav"
    result = _tool().execute({"cuts": CUTS, "output_path": str(out)})

    assert result.success, result.error
    assert [c[:2] for c in fake.calls] == [["music", "check"], ["music", "render"]]
    assert fake.calls[1][-1] == "--no-mp3"
    song_path = Path(fake.calls[0][2])
    assert song_path.parent == tmp_path / "home" / "cache" / "openmontage" / "music"
    assert result.artifacts == [str(out)]
    assert result.cost_usd == 0.0
    assert result.data["target_seconds"] == 9.75
    assert abs(result.data["duration_seconds"] - 9.75) < 0.001
    assert result.data["cut_times"] == [3.5, 7.5]
    assert result.data["integrated_lufs"] == -16.1


def test_check_failure_is_reported_and_nothing_is_rendered(fake, tmp_path):
    fake.check_problems = ["tracks[0].instrument: \"kazoo\" is not an instrument id."]
    song = {"format": "minicut-song/1", "length_s": 4,
            "tracks": [{"name": "x", "instrument": "kazoo", "notes": [[60, 0, 1, 80]]}]}
    result = _tool().execute({"song": song, "output_path": str(tmp_path / "x.wav")})

    assert not result.success
    assert "kazoo" in result.error
    assert result.cost_usd == 0.0
    assert [c[1] for c in fake.calls] == ["check"]


@needs_ffprobe
def test_agent_written_song_is_played_as_given(fake, tmp_path):
    song = {"format": "minicut-song/1", "length_s": 6.0, "markers": [{"t": 2.5, "name": "drop"}],
            "tracks": [{"name": "hit", "instrument": "timpani", "notes": [["low", 2.5, 1, 110]]}]}
    result = _tool().execute({"song": song, "output_path": str(tmp_path / "own.wav")})

    assert result.success, result.error
    assert json.loads(Path(fake.calls[1][2]).read_text(encoding="utf-8")) == song
    assert result.data["cut_times"] == [2.5]


@needs_ffprobe
def test_render_of_wrong_length_fails(fake, tmp_path):
    fake.render_extra_s = 0.5
    result = _tool().execute({"duration_seconds": 5, "cut_times": [2], "output_path": str(tmp_path / "m.wav")})

    assert not result.success
    assert "5.500 s" in result.error and "5.000 s" in result.error


def test_output_must_be_wav(fake, tmp_path):
    result = _tool().execute({"duration_seconds": 5, "output_path": str(tmp_path / "m.mp3")})

    assert not result.success
    assert fake.calls == []
