import shutil
import subprocess
import math
import struct
import wave
from pathlib import Path

import pytest

from tools.audio.audio_mixer import AudioMixer


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)


def _tone(path: Path, frequency: int, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={frequency}:duration={duration}", str(path),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )


def _duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def _tail_rms(path: Path, start_seconds: float, end_seconds: float) -> float:
    with wave.open(str(path), "rb") as handle:
        sample_width = handle.getsampwidth()
        assert sample_width == 2
        frame_rate = handle.getframerate()
        handle.setpos(int(start_seconds * frame_rate))
        raw = handle.readframes(int((end_seconds - start_seconds) * frame_rate))
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def test_full_mix_can_pin_the_composition_length(tmp_path) -> None:
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    output = tmp_path / "mix.wav"
    _tone(speech, 440, 1)
    _tone(music, 220, 3)

    result = AudioMixer().execute({
        "operation": "full_mix",
        "tracks": [
            {"path": str(speech), "role": "speech"},
            {"path": str(music), "role": "music"},
        ],
        "ducking": {"enabled": True},
        "normalize": False,
        "target_duration": 3,
        "output_path": str(output),
    })

    assert result.success, result.error
    assert result.data["target_duration"] == 3
    assert _duration(output) == pytest.approx(3.0, abs=0.15)
    assert _tail_rms(output, 2.0, 2.5) > 100


@pytest.mark.parametrize("target", [0, -1, "not-a-number"])
def test_full_mix_rejects_invalid_target_duration(tmp_path, target) -> None:
    tone = tmp_path / "tone.wav"
    _tone(tone, 440, 0.25)

    result = AudioMixer().execute({
        "operation": "full_mix",
        "tracks": [{"path": str(tone), "role": "speech"}],
        "target_duration": target,
        "output_path": str(tmp_path / "mix.wav"),
    })

    assert result.success is False
    assert "target_duration" in result.error
