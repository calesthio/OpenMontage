"""Native FFmpeg proof that segment fades never extend music past its window."""
import array
import math
import shutil
import subprocess

import pytest

from tools.audio.audio_mixer import AudioMixer


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
@pytest.mark.parametrize("segment,fade", [((0.5, 0.7), 0.5), ((0.5, 0.7), 0.15), ((0.4, 1.4), 0.1), ((0.5, 0.7), 0)])
def test_segment_music_stays_inside_window(tmp_path, segment, fade):
    video = tmp_path / "silent.mkv"
    music = tmp_path / "tone.wav"
    output = tmp_path / "mixed.mkv"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=16x16:r=25:d=2",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2",
        "-c:v", "ffv1", "-c:a", "pcm_s16le", str(video),
    ], check=True, timeout=30)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        str(music),
    ], check=True, timeout=30)
    start, end = segment
    result = AudioMixer().execute({
        "operation": "segmented_music", "video_path": str(video), "music_path": str(music),
        "output_path": str(output), "segments": [{"start": start, "end": end}],
        "fade_duration": fade,
    })
    assert result.success, result.error
    raw = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(output), "-f", "f32le", "-ac", "1", "-ar", "44100", "-",
    ], check=True, stdout=subprocess.PIPE, timeout=30).stdout
    samples = array.array("f", raw)

    def rms(lo, hi):
        values = samples[int(lo * 44100):int(hi * 44100)]
        return math.sqrt(sum(v * v for v in values) / len(values))

    # Decode the actual AAC output. Allow 240ms for frame granularity and encoder/decoder buffering.
    assert rms(start + .04, end - .04) > .0005
    assert rms(.1, start - .08) < .0001
    assert rms(end + .24, min(end + .34, 1.9)) < .0001
