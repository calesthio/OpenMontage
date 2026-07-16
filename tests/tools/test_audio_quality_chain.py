"""Wave-1 audio chain quality (audit 2026-07-16, ①).

Covers: the deterministic envelope duck (music genuinely recovers between
narration segments), amix normalize=0, and two-pass loudness normalization
to -14 LUFS.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402
from tools.audio import loudness  # noqa: E402

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg required"
)


# ---------------------------------------------------------------------------
# Pure unit tests — no ffmpeg
# ---------------------------------------------------------------------------

class TestDuckEnvelopeExpr:
    def test_single_interval_shape(self):
        expr = AudioMixer._duck_envelope_expr([(2.0, 5.0)], 0.15, 0.2, 0.8)
        # Gain formula: 1 - (1-duck) * min(1, sum(envelopes))
        assert expr.startswith("1-0.85*min(1,")
        # Attack ramp begins at speech start, release extends past speech end.
        assert "lt(t,2.0)" in expr
        assert "lt(t,2.2)" in expr      # 2.0 + attack
        assert "lt(t,5.8)" in expr      # 5.0 + release

    def test_multiple_intervals_are_summed(self):
        expr = AudioMixer._duck_envelope_expr(
            [(0.0, 3.0), (10.0, 12.5)], 0.2, 0.2, 0.8
        )
        assert expr.count("if(lt(t,") == 8  # 4 branches × 2 intervals
        assert "+" in expr

    def test_zero_attack_release_guarded(self):
        # Division by zero must be impossible.
        expr = AudioMixer._duck_envelope_expr([(0.0, 1.0)], 0.15, 0.0, 0.0)
        assert "/0.01" in expr and "/0)" not in expr


class TestLoudnormFilter:
    def test_second_pass_uses_measured_values_linear(self):
        measured = {
            "input_i": "-23.5", "input_tp": "-5.1",
            "input_lra": "6.0", "input_thresh": "-33.7",
            "target_offset": "0.3",
        }
        f = loudness.loudnorm_filter(measured)
        assert "I=-14.0" in f and "TP=-1.5" in f
        assert "measured_I=-23.5" in f and "linear=true" in f

    def test_fallback_without_measurement_is_plain_loudnorm(self):
        f = loudness.loudnorm_filter(None)
        assert f == "loudnorm=I=-14.0:TP=-1.5:LRA=11.0"


# ---------------------------------------------------------------------------
# Integration — real ffmpeg
# ---------------------------------------------------------------------------

def _sine(path: Path, freq: int, dur: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency={freq}:duration={dur}", str(path)],
        capture_output=True, check=True, timeout=30,
    )


@ffmpeg_required
def test_full_mix_uses_envelope_duck_and_normalizes_to_minus_14(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _sine(speech, 440, 2)
    _sine(music, 220, 6)
    out = tmp_path / "mixed.wav"

    result = AudioMixer().execute({
        "operation": "full_mix",
        "tracks": [
            {"path": str(speech), "role": "speech", "start_seconds": 0},
            {"path": str(music), "role": "music", "volume": 0.3},
        ],
        "ducking": {"enabled": True},
        "output_path": str(out),
    })

    assert result.success is True, result.error
    assert out.exists()
    assert result.data["duck_mode"] == "envelope"
    assert result.data["normalized"] is True

    # The deliverable must sit at the -14 LUFS target (±1 LU tolerance —
    # loudnorm's own precision on short synthetic material).
    measured = loudness.measure_loudness(out)
    assert measured is not None
    assert abs(float(measured["input_i"]) - (-14.0)) <= 1.0


@ffmpeg_required
def test_full_mix_music_recovers_after_speech_ends(tmp_path):
    # 2s of speech, 8s of music: with the envelope duck the music's tail
    # (after speech + release) must be genuinely louder than during speech.
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _sine(speech, 440, 2)
    _sine(music, 220, 8)
    out = tmp_path / "mixed.wav"

    result = AudioMixer().execute({
        "operation": "full_mix",
        "tracks": [
            {"path": str(speech), "role": "speech", "start_seconds": 0},
            {"path": str(music), "role": "music", "volume": 0.4},
        ],
        "ducking": {"enabled": True, "music_volume_during_speech": 0.1},
        "normalize": False,  # inspect the raw duck, not the normalized result
        "output_path": str(out),
    })
    assert result.success is True, result.error

    def rms_of_window(start: float, dur: float) -> float:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats",
             "-ss", str(start), "-t", str(dur), "-i", str(out),
             "-af", "astats=metadata=1:measure_overall=RMS_level",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        import re
        m = re.findall(r"RMS level dB:\s*(-?[\d.]+)", proc.stderr)
        return float(m[-1])

    # lavfi sine is NOT full-scale, so absolute dBFS thresholds are
    # meaningless. Assert the strong deterministic property instead: in the
    # tail window (4.0s — past speech end 2.0s + release 0.8s) the gain
    # envelope must be fully recovered, i.e. the tail RMS equals the
    # un-ducked music bed (source RMS + 20*log10(volume 0.4)) within
    # tolerance. Before the fix it measured at the duck floor, 20 dB lower.
    def rms_of_file(path: Path) -> float:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
             "-af", "astats=metadata=1:measure_overall=RMS_level",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        import re
        return float(re.findall(r"RMS level dB:\s*(-?[\d.]+)", proc.stderr)[-1])

    import math
    source_rms = rms_of_file(music)
    expected_tail = source_rms + 20 * math.log10(0.4)  # bed volume, gain recovered to 1.0
    expected_ducked = expected_tail + 20 * math.log10(0.1)  # duck floor

    after = rms_of_window(4.0, 1.0)
    assert abs(after - expected_tail) <= 1.5, (
        f"music tail {after} dBFS != recovered bed {expected_tail:.1f} dBFS "
        f"(ducked floor would be {expected_ducked:.1f})"
    )


@ffmpeg_required
def test_normalize_media_loudness_video_copy(tmp_path):
    # A tiny 2s test video with a quiet tone — after normalization the
    # integrated loudness must be pulled up to the target.
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-af", "volume=0.05",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         str(src)],
        capture_output=True, check=True, timeout=60,
    )
    dst = tmp_path / "normalized.mp4"
    assert loudness.normalize_media_loudness(src, dst, video_copy=True) is True
    measured = loudness.measure_loudness(dst)
    assert measured is not None
    assert abs(float(measured["input_i"]) - (-14.0)) <= 1.5
