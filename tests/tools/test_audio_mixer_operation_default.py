"""Regression: audio_mixer.execute() must not KeyError on a missing
"operation" — "full_mix" is explicitly documented (in _full_mix's own
docstring) as "the preferred operation for the compose-director skill", the
only one of five operations with a stated default use case.

Found live (third tool in this pattern, after video_compose and video_stitch):
an agent driving the compose stage called this tool with mix-shaped params
(video_path, audio_tracks, output_format) but omitted "operation", raising a
bare KeyError('operation') and burning the stage's entire turn budget.
"""

from __future__ import annotations

from tools.audio.audio_mixer import AudioMixer


def test_missing_operation_defaults_to_full_mix_not_keyerror():
    am = AudioMixer()
    result = am.execute({})   # no "operation" key at all
    # Must route into _full_mix() (and fail there on ITS OWN precondition,
    # a normal ToolResult) — never raise/return a bare KeyError.
    assert result.success is False
    assert "tracks" in result.error.lower()
    assert "operation" not in result.error.lower()


def test_explicit_operation_still_respected():
    am = AudioMixer()
    result = am.execute({"operation": "bogus_op"})
    assert result.success is False
    assert result.error == "Unknown operation: bogus_op"
