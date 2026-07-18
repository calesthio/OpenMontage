"""Regression: video_stitch.execute() must not KeyError on a missing
"operation" — "stitch" (join clips with transitions) is the overwhelmingly
common call and the only truly obvious default.

Found live across two separate jobs: an agent driving the compose stage
supplied exactly the params _stitch() needs (clips, transitions, output_path)
but omitted "operation", raising a bare KeyError('operation') stringifying to
the cryptic "'operation'" — uninterpretable enough that the agent kept
repeating the same broken call until the stage burned through its entire
turn budget (MAX_TURNS) both times.
"""

from __future__ import annotations

from tools.video.video_stitch import VideoStitch


def test_missing_operation_defaults_to_stitch_not_keyerror():
    vs = VideoStitch()
    result = vs.execute({})   # no "operation" key at all
    # Must route into _stitch() (and fail there on ITS OWN precondition,
    # a normal ToolResult) — never raise/return a bare KeyError.
    assert result.success is False
    assert "clips" in result.error.lower()
    assert "operation" not in result.error.lower()


def test_explicit_operation_still_respected():
    vs = VideoStitch()
    result = vs.execute({"operation": "bogus_op"})
    assert result.success is False
    assert result.error == "Unknown operation: bogus_op"
