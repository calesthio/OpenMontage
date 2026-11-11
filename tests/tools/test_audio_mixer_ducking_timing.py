"""Verify millisecond ducking envelopes through native FFmpeg, not command mocks."""

import math
import shutil
import struct
import subprocess
import wave

import pytest

from tools.audio.audio_mixer import AudioMixer

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
RATE = 16000


def _fixture(path, speech):
    values = [
        (0.5 if 0.2 <= i / RATE < 0.8 else 0.0) if speech else 0.05
        for i in range(2 * RATE)
    ]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(b"".join(struct.pack("<h", round(value * 32767)) for value in values))


def _samples(path):
    with wave.open(str(path), "rb") as audio:
        count = audio.getnframes() * audio.getnchannels()
        samples = struct.unpack("<" + "h" * count, audio.readframes(audio.getnframes()))
        return samples[::audio.getnchannels()], audio.getframerate()


def _rms(samples, rate, start, end):
    window = samples[int(start * rate):int(end * rate)]
    return math.sqrt(sum(value * value for value in window) / len(window))


def _execute(tmp_path, operation, timings):
    speech, music = tmp_path / "speech.wav", tmp_path / "music.wav"
    _fixture(speech, True)
    _fixture(music, False)
    output = tmp_path / "mixed.wav"
    inputs = {
        "operation": operation, "output_path": str(output), "normalize": False,
        "ducking": {"music_volume_during_speech": 0.15, **timings},
    }
    if operation == "duck":
        inputs.update(primary_audio=str(speech), secondary_audio=str(music))
    else:
        inputs["tracks"] = [
            {"path": str(speech), "role": "speech"},
            {"path": str(music), "role": "music"},
        ]
    result = AudioMixer().execute(inputs)
    assert result.success, result.error
    return output, speech, music


@pytest.mark.parametrize("operation", ["duck", "full_mix"])
@pytest.mark.parametrize("timings", [{}, {"attack_ms": 200, "release_ms": 500}])
def test_half_second_release_retains_ducking_after_speech(tmp_path, operation, timings):
    output, _, _ = _execute(tmp_path, operation, timings)
    samples, rate = _samples(output)
    # The voice has been silent for 100ms, but a 500ms release still holds
    # audible attenuation. The former 0.5ms release was already recovered.
    early = _rms(samples, rate, 0.90, 1.0)
    unducked = _rms(samples, rate, 0.05, 0.15)
    assert unducked > 0
    assert early < 0.8 * unducked


@pytest.mark.parametrize("operation", ["duck", "full_mix"])
def test_short_release_recovers_before_the_measurement_window(tmp_path, operation):
    output, _, _ = _execute(tmp_path, operation, {"attack_ms": 20, "release_ms": 20})
    samples, rate = _samples(output)
    assert _rms(samples, rate, 0.90, 1.0) > 0.9 * _rms(samples, rate, 0.05, 0.15)


def test_full_mix_matches_independent_millisecond_ffmpeg_reference(tmp_path):
    output, speech, music = _execute(tmp_path, "full_mix", {"attack_ms": 200, "release_ms": 500})
    reference = tmp_path / "reference.wav"
    # Explicit native sidechain inputs, with the requested millisecond values.
    graph = (
        "[0:a]asplit=2[voice][key];"
        "[1:a][key]sidechaincompress=threshold=0.02:ratio=9:attack=200:release=500:"
        "level_sc=1:mix=0.9,volume=0.45[bed];"
        "[voice][bed]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=1:level=0[out]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(speech), "-i", str(music), "-filter_complex", graph,
         "-map", "[out]", str(reference)],
        capture_output=True, check=True, timeout=15,
    )
    actual, rate = _samples(output)
    expected, reference_rate = _samples(reference)
    assert rate == reference_rate
    assert len(actual) == len(expected)
    # Compare the attack and early-release envelope while both inputs are
    # active, independently of sidechain EOF/tail behavior.
    start, end = int(0.05 * rate), int(1.1 * rate)
    assert max(abs(a - b) for a, b in zip(actual[start:end], expected[start:end])) <= 1
