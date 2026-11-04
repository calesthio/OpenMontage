"""Cache the requested audio, including inputs outside the tracks array."""

import math
import shutil
import struct
import subprocess
import wave

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.audio.audio_enhance import AudioEnhance
from tools.audio.audio_mixer import AudioMixer


def _video(path, audio):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", "color=c=black:s=48x32:r=2:d=1", "-i", audio,
        "-c:v", "mpeg4", "-c:a", "pcm_s16le", str(path),
    ], check=True, timeout=10)
    return str(path)


def _active_pcm_window(path):
    with wave.open(str(path), "rb") as audio:
        assert audio.getsampwidth() == 2 and audio.getnchannels() == 1
        rate = audio.getframerate()
        audio.setpos(int(0.1 * rate))
        raw = audio.readframes(int(0.3 * rate))
        return (rate, audio.getnchannels(), audio.getnframes()), struct.unpack("<" + "h" * (len(raw) // 2), raw)


@pytest.fixture
def media(tmp_path, monkeypatch, request):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    reset_default_asset_cache()
    files = {}
    # Keep the simple-duck oracle far from its existing implicit-stream EOF
    # variability without relaxing fresh-render PCM or exact cache-hit checks.
    samples = 64000 if request.node.callspec.params["case"] in ("primary", "secondary", "attenuation") else 16000
    for name, frequency in (("voice", 330), ("other_voice", 110), ("music", 440), ("other_music", 880)):
        path = tmp_path / f"{name}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"".join(
                struct.pack("<h", round(1500 * math.sin(2 * math.pi * frequency * i / 16000)))
                for i in range(samples)
            ))
        files[name] = str(path)
    try:
        yield files
    finally:
        reset_default_asset_cache()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="Native FFmpeg required")
@pytest.mark.parametrize("case", ["primary", "secondary", "attenuation", "normalization", "loudness", "duration", "extract", "segment_music", "segments"])
def test_actual_changed_audio_request_does_not_restore_prior_render(media, tmp_path, monkeypatch, case):
    tracks = [{"path": media["voice"], "role": "speech"}, {"path": media["music"], "role": "music"}]
    first = {"operation": "duck", "primary_audio": media["voice"], "secondary_audio": media["music"]}
    second = dict(first)
    suffix = ".wav"
    if case == "primary":
        second["primary_audio"] = media["other_voice"]
    elif case == "secondary":
        second["secondary_audio"] = media["other_music"]
    elif case == "attenuation":
        first["duck_level"], second["duck_level"] = -3, -20
    elif case == "normalization":
        first = {"operation": "mix", "tracks": tracks, "normalize": False}
        second = {**first, "normalize": True}
    elif case == "loudness":
        first = {"operation": "mix", "tracks": tracks, "loudnorm_target": -16}
        second = {**first, "loudnorm_target": -24}
    elif case == "duration":
        first = {"operation": "full_mix", "tracks": tracks, "normalize": False, "ducking": {"enabled": False}, "target_duration": 1}
        second = {**first, "target_duration": 2}
    elif case == "extract":
        first = {"operation": "extract", "input_path": _video(tmp_path / "voice.avi", media["voice"])}
        second = {**first, "input_path": _video(tmp_path / "other_voice.avi", media["other_voice"])}
    else:
        video = tmp_path / "source.avi"
        _video(video, media["voice"])
        first = {"operation": "segmented_music", "video_path": str(video), "music_path": media["music"], "segments": [{"start": 0, "end": 0.4}], "fade_duration": 0.05}
        second = dict(first)
        if case == "segment_music":
            second["music_path"] = media["other_music"]
        else:
            second["segments"] = [{"start": 0.6, "end": 0.9}]
        suffix = ".mp4"

    tool = AudioMixer()
    first_path, second_path = tmp_path / f"first{suffix}", tmp_path / f"second{suffix}"
    first_result = tool.execute({**first, "output_path": str(first_path)})
    second_result = tool.execute({**second, "output_path": str(second_path)})
    assert first_result.success, first_result.error
    assert second_result.success, second_result.error
    assert not first_result.from_cache
    assert not second_result.from_cache, "A different source or rendered setting reused the first artifact"
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    reference = tmp_path / f"reference{suffix}"
    reference_result = tool.execute({**second, "output_path": str(reference)})
    assert reference_result.success, reference_result.error
    if case in ("primary", "secondary", "attenuation"):
        # Compare the active signal: this existing simple-duck path does not
        # promise whole-wave equality between separate native renders.
        (shape_a, a), (shape_b, b), (shape_reference, expected) = map(_active_pcm_window, (first_path, second_path, reference))
        assert shape_a == shape_b == shape_reference
        assert len(a) == len(b) == len(expected)
        assert math.sqrt(sum((x - y) ** 2 for x, y in zip(a, expected)) / len(a)) > 100
        assert max(abs(x - y) for x, y in zip(b, expected)) <= 1
    else:
        assert first_path.read_bytes() != reference.read_bytes()
        assert second_path.read_bytes() == reference.read_bytes()
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    repeat = tmp_path / f"repeat{suffix}"
    repeated = tool.execute({**second, "output_path": str(repeat)})
    assert repeated.success and repeated.from_cache
    assert repeat.read_bytes() == second_path.read_bytes()


def _audio_packet_hashes(path):
    import json

    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_packets",
        "-show_data_hash", "sha256", "-show_entries", "packet=data_hash",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, timeout=10)
    return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Native FFmpeg required")
@pytest.mark.parametrize("case", ["codec", "bitrate"])
def test_actual_enhancement_encoding_controls_do_not_restore_prior_audio(media, tmp_path, monkeypatch, case):
    first = {"input_path": media["voice"], "custom_af": "anull", "audio_codec": "aac", "audio_bitrate": "32k"}
    second = {**first, **({"audio_codec": "flac"} if case == "codec" else {"audio_bitrate": "64k"})}
    tool = AudioEnhance()
    first_path, second_path = tmp_path / "first.mka", tmp_path / "second.mka"
    a = tool.execute({**first, "output_path": str(first_path)})
    b = tool.execute({**second, "output_path": str(second_path)})
    assert a.success, a.error
    assert b.success, b.error
    assert not a.from_cache and not b.from_cache
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    reference = tmp_path / "reference.mka"
    c = tool.execute({**second, "output_path": str(reference)})
    assert c.success, c.error
    # Matroska container UIDs vary; compare actual encoded audio packets.
    assert _audio_packet_hashes(first_path) != _audio_packet_hashes(reference)
    assert _audio_packet_hashes(second_path) == _audio_packet_hashes(reference)
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    repeated_path = tmp_path / "repeated.mka"
    repeated = tool.execute({**second, "output_path": str(repeated_path)})
    assert repeated.success and repeated.from_cache
    assert repeated_path.read_bytes() == second_path.read_bytes()
