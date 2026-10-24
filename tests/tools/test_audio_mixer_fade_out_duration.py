"""Issue #771 regression: N/A duration must raise an actionable error.

Stub run_command so these tests need neither ffprobe nor media files.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools.audio.audio_mixer import AudioMixer


def _mixer_with_duration(value: str) -> AudioMixer:
    mixer = AudioMixer()
    mixer.run_command = lambda *a, **k: SimpleNamespace(stdout=f"{value}\n")
    return mixer


def test_fade_out_on_undeterminable_duration_raises_actionable_error():
    mixer = _mixer_with_duration("N/A")

    with pytest.raises(ValueError) as exc_info:
        mixer._track_filters({"path": "empty.wav", "fade_out_seconds": 0.2})

    message = str(exc_info.value)
    assert "empty.wav" in message
    assert "N/A" in message
    assert "could not convert string to float" not in message


def test_fade_out_with_valid_duration_builds_afade():
    mixer = _mixer_with_duration("3.0")

    filters = mixer._track_filters({"path": "empty.wav", "fade_out_seconds": 0.2})

    assert any(item.startswith("afade=t=out:st=") for item in filters)
