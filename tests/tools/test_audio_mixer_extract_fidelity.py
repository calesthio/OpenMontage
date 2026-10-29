"""`extract` must not resample every source to 16 kHz mono.

`_extract` hardcoded `-acodec pcm_s16le -ar 16000 -ac 1`, a speech/STT preset,
on an operation the schema documents only as "extract audio from video file".
Extracting a music or effects bed for mixing silently lost half the spectrum
and the stereo image. The same hardcoded PCM codec also made any container but
WAV fail outright: `Could not find tag for codec pcm_s16le in stream #0`.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402


def _captured_extract(tmp_path, monkeypatch, out_name):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"stub")
    captured = []

    def fake_run(self, cmd, **kwargs):
        captured.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"stub")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(AudioMixer, "run_command", fake_run, raising=False)
    result = AudioMixer().execute({
        "operation": "extract",
        "input_path": str(video),
        "output_path": str(tmp_path / out_name),
    })
    assert result.success, result.error
    return captured[0]


def test_extract_preserves_source_rate_and_channels(tmp_path, monkeypatch) -> None:
    cmd = _captured_extract(tmp_path, monkeypatch, "out.wav")
    assert "-ar" not in cmd, f"extract still forces a sample rate: {cmd}"
    assert "-ac" not in cmd, f"extract still forces a channel count: {cmd}"


def test_extract_does_not_force_pcm_into_every_container(tmp_path, monkeypatch) -> None:
    cmd = _captured_extract(tmp_path, monkeypatch, "out.m4a")
    assert "pcm_s16le" not in cmd, f"pcm_s16le cannot be muxed into m4a: {cmd}"
