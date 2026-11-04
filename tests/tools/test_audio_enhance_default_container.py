"""Default AAC enhancement must produce an actual compatible media container."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.audio.audio_enhance import AudioEnhance

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")


def _audio(path, codec):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:sample_rate=48000:duration=0.4", "-c:a", codec, str(path)],
        capture_output=True, check=True, timeout=15,
    )


def _probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=10,
    )
    info = json.loads(result.stdout)
    assert 0.3 <= float(info["format"]["duration"]) <= 0.7
    return info


@pytest.mark.parametrize("suffix,codec", [("mp3", "libmp3lame"), ("flac", "flac"), ("ogg", "libopus")])
def test_default_aac_audio_has_a_compatible_container(tmp_path, suffix, codec):
    source = tmp_path / f"voice.{suffix}"
    _audio(source, codec)
    result = AudioEnhance().execute({"input_path": str(source), "preset": "normalize_only"})
    assert result.success, result.error
    output = Path(result.data["output"])
    assert output == tmp_path / "voice_enhanced.m4a"
    info = _probe(output)
    assert [s["codec_name"] for s in info["streams"]] == ["aac"]
    assert "m4a" in info["format"]["format_name"]
    assert source.exists()


def test_default_aac_webm_preserves_video_in_matroska(tmp_path):
    source = tmp_path / "clip.webm"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=10:duration=0.4",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4",
         "-c:v", "libvpx-vp9", "-c:a", "libopus", "-shortest", str(source)],
        capture_output=True, check=True, timeout=15,
    )
    original = _probe(source)
    result = AudioEnhance().execute({"input_path": str(source), "preset": "normalize_only"})
    assert result.success, result.error
    output = Path(result.data["output"])
    assert output == tmp_path / "clip_enhanced.mkv"
    info = _probe(output)
    assert {s["codec_type"]: s["codec_name"] for s in info["streams"]} == {"video": "vp9", "audio": "aac"}
    old_video = next(s for s in original["streams"] if s["codec_type"] == "video")
    new_video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (new_video["width"], new_video["height"]) == (old_video["width"], old_video["height"])
    def video_packets(path):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets",
             "-show_data_hash", "sha256", "-show_entries", "packet=data_hash", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]
    assert video_packets(output) == video_packets(source)


def test_explicit_container_path_is_preserved(tmp_path):
    source, output = tmp_path / "voice.mp3", tmp_path / "chosen.mka"
    _audio(source, "libmp3lame")
    result = AudioEnhance().execute({"input_path": str(source), "output_path": str(output), "preset": "normalize_only"})
    assert result.success, result.error
    assert result.data["output"] == str(output)
    assert [s["codec_name"] for s in _probe(output)["streams"]] == ["aac"]


def test_custom_pcm_codec_preserves_wav_default(tmp_path):
    source = tmp_path / "voice.wav"
    _audio(source, "pcm_s16le")
    result = AudioEnhance().execute({"input_path": str(source), "audio_codec": "pcm_s16le", "preset": "normalize_only"})
    assert result.success, result.error
    output = Path(result.data["output"])
    assert output == tmp_path / "voice_enhanced.wav"
    assert [s["codec_name"] for s in _probe(output)["streams"]] == ["pcm_s16le"]


@pytest.mark.parametrize("codec,suffix,expected", [
    ("flac", "flac", "flac"), ("libopus", "ogg", "opus"),
    ("libvorbis", "ogg", "vorbis"), ("pcm_s16le", "wav", "pcm_s16le"),
    ("libmp3lame", "mp3", "mp3"),
])
def test_custom_audio_codec_selects_a_compatible_default(tmp_path, codec, suffix, expected):
    source = tmp_path / "voice.mp3"
    _audio(source, "libmp3lame")
    result = AudioEnhance().execute({
        "input_path": str(source), "audio_codec": codec, "custom_af": "anull",
    })
    assert result.success, result.error
    output = Path(result.data["output"])
    assert output == tmp_path / f"voice_enhanced.{suffix}"
    assert [s["codec_name"] for s in _probe(output)["streams"]] == [expected]
