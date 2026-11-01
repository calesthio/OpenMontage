"""Regression tests: amix must not scale tracks by 1/N.

ffmpeg's `amix` defaults to `normalize=1`, which divides every input by the
input count. Narration segments are scheduled with `adelay`, so all of them
count as active from t=0: N sequential lines came out 20*log10(N) dB quiet
(-15.6 dB for 6 lines) and the music buried the voice. `duck` halved the
speech the same way, and `mix` silently overrode the per-track `volume` the
caller set. Every amix in `mix`, `duck` and `full_mix` now carries
`normalize=0`; outputs that skip loudnorm end in an `alimiter` so tracks that
overlap cannot hard-clip.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402

LIMITER = "alimiter=limit=1:level=0[out]"


def _stub_tracks(tmp_path, roles):
    tracks = []
    for i, role in enumerate(roles):
        path = tmp_path / f"{role}_{i}.wav"
        path.write_bytes(b"stub")
        tracks.append({"path": str(path), "role": role, "start_seconds": float(i)})
    return tracks


def _build(monkeypatch, inputs):
    """Run the tool with ffmpeg stubbed out; return (filter graph, -map label)."""
    captured = []

    def fake_run(self, cmd, **kwargs):
        captured.append(list(cmd))

        class _R:
            stdout = "10.0\n"
            stderr = ""

        return _R()

    monkeypatch.setattr(AudioMixer, "run_command", fake_run)
    result = AudioMixer().execute(inputs)
    assert result.success, result.error

    ffmpeg_cmds = [c for c in captured if c and c[0] == "ffmpeg"]
    assert ffmpeg_cmds, "no ffmpeg command was built"
    cmd = ffmpeg_cmds[0]
    return cmd[cmd.index("-filter_complex") + 1], cmd[cmd.index("-map") + 1]


def _amix_nodes(graph):
    return [node for node in re.split(r"[;,]", graph) if "amix=" in node]


def _assert_all_amix_unnormalized(graph, expected_count):
    nodes = _amix_nodes(graph)
    assert len(nodes) == expected_count, graph
    for node in nodes:
        assert "normalize=0" in node, f"amix must disable normalize; got: {node}"


# --- Offline: filter graph shape (no ffmpeg needed) -------------------------


def test_mix_amix_disables_normalize(tmp_path, monkeypatch):
    tracks = _stub_tracks(tmp_path, ["speech"] * 6 + ["music"])
    tracks[-1]["volume"] = 0.3
    graph, _ = _build(
        monkeypatch,
        {"operation": "mix", "tracks": tracks, "output_path": str(tmp_path / "out.wav")},
    )
    _assert_all_amix_unnormalized(graph, 1)


def test_full_mix_without_ducking_amix_disables_normalize(tmp_path, monkeypatch):
    tracks = _stub_tracks(tmp_path, ["speech"] * 6 + ["music"])
    graph, _ = _build(
        monkeypatch,
        {
            "operation": "full_mix",
            "tracks": tracks,
            "ducking": {"enabled": False},
            "output_path": str(tmp_path / "out.wav"),
        },
    )
    _assert_all_amix_unnormalized(graph, 1)


def test_full_mix_with_ducking_every_amix_disables_normalize(tmp_path, monkeypatch):
    # speech amix, music amix, speech+music amix, +SFX amix
    tracks = _stub_tracks(tmp_path, ["speech"] * 3 + ["music"] * 2 + ["sfx"])
    graph, _ = _build(
        monkeypatch,
        {
            "operation": "full_mix",
            "tracks": tracks,
            "ducking": {"enabled": True},
            "output_path": str(tmp_path / "out.wav"),
        },
    )
    _assert_all_amix_unnormalized(graph, 4)


def test_duck_amix_disables_normalize(tmp_path, monkeypatch):
    speech, music = tmp_path / "speech.wav", tmp_path / "music.wav"
    speech.write_bytes(b"stub")
    music.write_bytes(b"stub")
    graph, mapped = _build(
        monkeypatch,
        {
            "operation": "duck",
            "primary_audio": str(speech),
            "secondary_audio": str(music),
            "output_path": str(tmp_path / "out.wav"),
        },
    )
    _assert_all_amix_unnormalized(graph, 1)
    # duck has no loudnorm stage, so the summed output must be clip-guarded.
    assert graph.endswith(LIMITER), graph
    assert mapped == "[out]"


@pytest.mark.parametrize("operation", ["mix", "full_mix"])
def test_output_without_loudnorm_ends_in_limiter(tmp_path, monkeypatch, operation):
    tracks = _stub_tracks(tmp_path, ["speech"] * 3)
    graph, mapped = _build(
        monkeypatch,
        {
            "operation": operation,
            "tracks": tracks,
            "normalize": False,
            "target_duration": 5,
            "output_path": str(tmp_path / "out.wav"),
        },
    )
    assert graph.endswith(LIMITER), graph
    assert mapped == "[out]"


@pytest.mark.parametrize("operation", ["mix", "full_mix"])
def test_loudnorm_output_has_no_extra_limiter(tmp_path, monkeypatch, operation):
    tracks = _stub_tracks(tmp_path, ["speech"] * 3)
    graph, mapped = _build(
        monkeypatch,
        {
            "operation": operation,
            "tracks": tracks,
            "normalize": True,
            "output_path": str(tmp_path / "out.wav"),
        },
    )
    # loudnorm's true-peak limiter already caps the summed mix.
    assert "loudnorm=" in graph.rsplit(";", 1)[-1], graph
    assert "alimiter" not in graph
    assert mapped == "[out]"


# --- End-to-end: measured levels (ffmpeg required) --------------------------

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")

STARTS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def _render(path, expr, duration):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d={duration}", str(path)],
        capture_output=True, check=True, timeout=60,
    )


def _tone(path, freq, duration=0.5):
    # 0.5 amplitude (-6 dBFS peak): about as hot as typical TTS output.
    _render(path, f"0.5*sin(2*PI*{freq}*t)", duration)


def _levels(path, ss=None, t=None):
    """Return (max_volume, mean_volume) in dB, as reported by volumedetect."""
    cmd = ["ffmpeg", "-hide_banner"]
    if ss is not None:
        cmd += ["-ss", str(ss), "-t", str(t)]
    cmd += ["-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    # ffmpeg logs UTF-8; decode explicitly so non-ASCII temp paths don't break
    # on Windows locales (e.g. cp1251).
    out = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
    )
    found = {}
    for line in out.stderr.splitlines():
        for key in ("max_volume", "mean_volume"):
            if f"{key}:" in line:
                found[key] = float(line.split(f"{key}:")[1].split("dB")[0])
    assert {"max_volume", "mean_volume"} <= found.keys(), out.stderr
    return found["max_volume"], found["mean_volume"]


@needs_ffmpeg
@pytest.mark.parametrize(
    "operation, ducking",
    [("mix", None), ("full_mix", False), ("full_mix", True)],
    ids=["mix", "full_mix-no-ducking", "full_mix-ducking"],
)
def test_sequential_lines_keep_standalone_peak(tmp_path, operation, ducking):
    """Six narration lines: each line's peak in the mix equals its own peak."""
    lines = []
    for i, start in enumerate(STARTS):
        path = tmp_path / f"line{i}.wav"
        _tone(path, 300 + 100 * i)
        lines.append({"path": str(path), "role": "speech", "start_seconds": start})
    standalone = [_levels(line["path"])[0] for line in lines]

    out = tmp_path / "out.wav"
    inputs = {"operation": operation, "tracks": list(lines), "normalize": False,
              "output_path": str(out)}
    if operation == "full_mix":
        inputs["ducking"] = {"enabled": ducking}
        if ducking:
            # A silent bed drives the whole sidechain graph without adding level.
            bed = tmp_path / "bed.wav"
            _render(bed, "0", 7)
            inputs["tracks"].append({"path": str(bed), "role": "music"})

    result = AudioMixer().execute(inputs)
    assert result.success, result.error

    for start, expected in zip(STARTS, standalone):
        peak, _ = _levels(out, ss=start + 0.1, t=0.3)
        assert peak == pytest.approx(expected, abs=0.2), (
            f"line at {start}s: standalone {expected} dB, in mix {peak} dB"
        )


@needs_ffmpeg
def test_duck_keeps_speech_at_unity(tmp_path):
    speech, music = tmp_path / "speech.wav", tmp_path / "music.wav"
    _tone(speech, 440, duration=2)
    _render(music, "0", 3)
    out = tmp_path / "out.wav"

    result = AudioMixer().execute(
        {
            "operation": "duck",
            "primary_audio": str(speech),
            "secondary_audio": str(music),
            "output_path": str(out),
        }
    )
    assert result.success, result.error

    peak, _ = _levels(out, ss=0.5, t=1)
    assert peak == pytest.approx(_levels(speech)[0], abs=0.2)


@needs_ffmpeg
@pytest.mark.parametrize("operation", ["mix", "full_mix"])
def test_overlapping_tracks_are_limited_not_clipped(tmp_path, operation):
    """Six in-phase -6 dBFS tones at t=0 sum to +9.5 dBFS without normalize."""
    tracks = []
    for i in range(6):
        path = tmp_path / f"t{i}.wav"
        _tone(path, 440, duration=1)
        tracks.append({"path": str(path), "role": "speech"})

    out = tmp_path / "out.wav"
    inputs = {"operation": operation, "tracks": tracks, "normalize": False,
              "output_path": str(out)}
    if operation == "full_mix":
        inputs["ducking"] = {"enabled": False}
    result = AudioMixer().execute(inputs)
    assert result.success, result.error

    peak, mean = _levels(out, ss=0.2, t=0.6)
    # Hard clipping squares the sine off (peak-to-RMS near 0 dB); the limiter
    # keeps a sine's ~3 dB crest factor.
    assert peak - mean > 2.0, f"output clipped: peak {peak} dB, mean {mean} dB"
