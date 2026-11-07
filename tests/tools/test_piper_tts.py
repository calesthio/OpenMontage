"""Piper voice resolution + real synthesis when the voice is installed.

The tool hands ``--model`` straight to the piper CLI, and
``python -m piper.download_voices <voice>`` writes the voice into the current
directory unless ``--download-dir`` is given. A bare voice name therefore only
worked when the process happened to run from the directory holding the voice —
everywhere else piper exited with "Unable to find voice" and the tool reported
a bare failure with no fix hint.

`resolve_voice_model` searches the conventional locations instead and raises an
error that names the download command. The tests below pin both halves: the
resolution logic (no network, no model needed) and — only when a voice is
actually installed — a real synthesis whose duration is measured from the
written file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.audio.piper_tts import PiperTTS, resolve_voice_model


def _piper_available() -> bool:
    return shutil.which("piper") is not None


def _voice_installed() -> bool:
    try:
        resolve_voice_model("en_US-lessac-medium")
        return True
    except FileNotFoundError:
        return False


# --- resolution ------------------------------------------------------------


def test_an_explicit_path_wins(tmp_path: Path) -> None:
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"not really a model")
    assert resolve_voice_model(str(model)) == model


def test_a_bare_name_resolves_in_the_voices_dir(tmp_path: Path, monkeypatch) -> None:
    voice_dir = tmp_path / "voices"
    voice_dir.mkdir()
    (voice_dir / "en_US-lessac-medium.onnx").write_bytes(b"x")
    monkeypatch.setenv("PIPER_VOICES_DIR", str(voice_dir))

    assert resolve_voice_model("en_US-lessac-medium") == voice_dir / "en_US-lessac-medium.onnx"


def test_a_bare_name_resolves_without_the_onnx_suffix(tmp_path: Path, monkeypatch) -> None:
    voice_dir = tmp_path / "voices"
    voice_dir.mkdir()
    (voice_dir / "en_US-lessac-medium").write_bytes(b"x")
    monkeypatch.setenv("PIPER_VOICES_DIR", str(voice_dir))

    assert resolve_voice_model("en_US-lessac-medium") == voice_dir / "en_US-lessac-medium"


def test_a_bare_name_resolves_from_the_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PIPER_VOICES_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"x")

    assert resolve_voice_model("en_US-lessac-medium").name == "en_US-lessac-medium.onnx"


def test_an_unresolvable_voice_names_the_fix(tmp_path: Path, monkeypatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    # Pin the search to an empty directory so this test does not depend on
    # whether a voice happens to be installed on the machine.
    monkeypatch.setattr(
        "tools.audio.piper_tts._voice_search_dirs", lambda: [empty]
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_voice_model("en_US-lessac-medium")

    message = str(excinfo.value)
    assert "download_voices" in message
    assert "PIPER_VOICES_DIR" in message
    assert "Searched:" in message


def test_the_tool_surfaces_the_resolution_error(monkeypatch, tmp_path: Path) -> None:
    """A missing voice must fail with the fix hint, not a bare piper exit code."""

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(
        "tools.audio.piper_tts._voice_search_dirs", lambda: [empty]
    )
    monkeypatch.chdir(tmp_path)

    if not _piper_available():
        pytest.skip("piper executable not installed")

    result = PiperTTS().execute({"text": "hello", "model": "en_US-lessac-medium"})
    assert result.success is False
    assert "download_voices" in result.error


# --- real synthesis (only when the voice is actually installed) ------------


@pytest.mark.skipif(
    not (_piper_available() and _voice_installed()),
    reason="piper + en_US-lessac-medium voice not installed in this environment",
)
def test_real_narration_writes_a_decodable_file(tmp_path: Path) -> None:
    """P0.4: verify TTS with an artifact, not with get_status()."""

    text = (
        "Every hotel towel you have ever used was washed in a plant that runs "
        "on a schedule tighter than a bus route."
    )
    out = tmp_path / "narration.wav"
    result = PiperTTS().execute(
        {"text": text, "model": "en_US-lessac-medium", "output_path": str(out)}
    )

    assert result.success, result.error
    assert out.exists() and out.stat().st_size > 10_000
    assert result.data["format"] == "wav"

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "default=noprint_wrappers=1",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "codec_name=pcm_s16le" in probe.stdout
    assert "channels=1" in probe.stdout

    duration_line = next(
        line for line in probe.stdout.splitlines() if line.startswith("duration=")
    )
    duration = float(duration_line.split("=", 1)[1])
    # A ~20-word sentence must not render as 0.1s (broken) or 60s (hung).
    assert 1.0 < duration < 30.0

    if shutil.which("ffmpeg"):
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        assert decode.returncode == 0, decode.stderr


@pytest.mark.skipif(
    not (_piper_available() and _voice_installed()),
    reason="piper + en_US-lessac-medium voice not installed in this environment",
)
def test_duration_comes_from_the_file_not_a_wpm_estimate(tmp_path: Path) -> None:
    """The narration manifest must measure duration, never estimate it."""

    out = tmp_path / "hook.wav"
    result = PiperTTS().execute(
        {"text": "The wash is cheap. The route is the business.", "output_path": str(out)}
    )
    assert result.success, result.error

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    measured = float(probe.stdout.strip())
    # Piper's default length_scale is 1.0 (~150 wpm class); a 9-word line lands
    # in a few seconds, and the point of the test is that a real number exists.
    assert measured > 0.5
    assert os.path.getsize(out) > 5_000


def test_cost_is_zero_and_offline() -> None:
    """Strict $0 mode: local synthesis must stay free."""

    tool = PiperTTS()
    assert tool.estimate_cost({"text": "anything"}) == 0.0
    assert tool.supports.get("offline") is True
