from pathlib import Path

from tools.audio.audio_mixer import AudioMixer
from tools.base_tool import ToolResult


class _CmdResult:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


def test_full_mix_single_speech_ducking_does_not_emit_dead_speech_dup_pad(
    tmp_path: Path,
    monkeypatch,
) -> None:
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    speech.write_bytes(b"speech")
    music.write_bytes(b"music")

    captured: dict[str, str] = {}

    def fake_run_command(self, cmd):  # noqa: ANN001
        if "-filter_complex" in cmd:
            captured["filter_complex"] = cmd[cmd.index("-filter_complex") + 1]
        return _CmdResult()

    monkeypatch.setattr(AudioMixer, "run_command", fake_run_command, raising=True)

    result = AudioMixer().execute(
        {
            "operation": "full_mix",
            "tracks": [
                {"path": str(speech), "role": "speech"},
                {"path": str(music), "role": "music"},
            ],
            "ducking": {"enabled": True},
            "normalize": False,
            "output_path": str(tmp_path / "out.wav"),
        }
    )

    assert result.success is True
    assert isinstance(result, ToolResult)
    assert "speech_dup" not in captured["filter_complex"]
    assert "[a0]acopy[speech_out]" in captured["filter_complex"]
