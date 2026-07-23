"""Regression tests: segmented_music must not attenuate narration.

`_segmented_music` mixed the video's audio with the shaped music via
`amix=inputs=2`, whose default `normalize=1` divides every input by the input
count (x0.5 / -6 dB). Unlike `_mix` / `_full_mix`, this path has no `loudnorm`
stage afterward, so the narration was permanently attenuated across the whole
timeline — including stretches where the music volume expression is 0. The fix
adds `normalize=0` (music is already scaled by the `volume` expression, so
speech must pass at unity).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402


def test_segmented_music_amix_disables_normalize(tmp_path, monkeypatch):
    """The generated amix must carry normalize=0 (offline, no ffmpeg)."""
    video = tmp_path / "v.mp4"
    music = tmp_path / "m.wav"
    video.write_bytes(b"stub")
    music.write_bytes(b"stub")

    captured = []

    def fake_run(self, cmd, **kwargs):
        captured.append(list(cmd))

        class _R:
            stdout = "10.0\n"
            stderr = ""

        return _R()

    monkeypatch.setattr(AudioMixer, "run_command", fake_run)

    AudioMixer().execute(
        {
            "operation": "segmented_music",
            "video_path": str(video),
            "music_path": str(music),
            "music_volume": 0.2,
            "segments": [{"start": 1.0, "end": 2.0}],
            "output_path": str(tmp_path / "out.mp4"),
        }
    )

    ffmpeg_cmds = [c for c in captured if c and c[0] == "ffmpeg"]
    assert ffmpeg_cmds, "no ffmpeg command was built"
    fc = ffmpeg_cmds[0][ffmpeg_cmds[0].index("-filter_complex") + 1]
    assert "amix=inputs=2" in fc
    assert "normalize=0" in fc, f"amix must disable normalize; got: {fc}"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_segmented_music_preserves_narration_level(tmp_path):
    """End-to-end: narration in a no-music region is not ~6 dB quieter."""

    def _mean_db(path, ss, t):
        out = subprocess.run(
            ["ffmpeg", "-ss", str(ss), "-t", str(t), "-i", str(path),
             "-vn", "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        for line in out.stderr.splitlines():
            if "mean_volume" in line:
                return float(line.split("mean_volume:")[1].strip().split(" ")[0])
        raise AssertionError("no mean_volume in ffmpeg output")

    video = tmp_path / "vspeech.mp4"
    music = tmp_path / "mus.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=5",
         "-f", "lavfi", "-i", "sine=frequency=300:duration=5",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video)],
        capture_output=True, check=True, timeout=60,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=3", str(music)],
        capture_output=True, check=True, timeout=60,
    )

    # Baseline: the same stereo/aac conversion the tool applies, without any mix.
    baseline = tmp_path / "base.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video),
         "-af", "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo",
         "-c:a", "aac", "-b:a", "192k", str(baseline)],
        capture_output=True, check=True, timeout=60,
    )

    out = tmp_path / "out.mp4"
    result = AudioMixer().execute(
        {
            "operation": "segmented_music",
            "video_path": str(video),
            "music_path": str(music),
            "music_volume": 0.2,
            "segments": [{"start": 1.0, "end": 2.0}],  # music only during [1,2]
            "output_path": str(out),
        }
    )
    assert result.success, result.error

    baseline_db = _mean_db(baseline, 3, 1)   # no-music region baseline
    out_db = _mean_db(out, 3, 1)             # no-music region through the tool

    # Narration must track the conversion baseline, not sit ~6 dB below it.
    assert out_db > baseline_db - 2.0, (
        f"narration attenuated: baseline {baseline_db} dB, output {out_db} dB"
    )
