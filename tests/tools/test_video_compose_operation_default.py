"""Regression: video_compose.execute() must not KeyError on a missing
"operation" — "compose" (assemble the final render) is the overwhelmingly
common call and the only truly obvious default.

Found live: an agent driving the compose stage repeatedly omitted "operation"
(reasonably, since compose is the stage's one obvious action), which raised
a bare KeyError('operation') stringifying to the cryptic "'operation'" —
uninterpretable enough that the agent kept repeating the same broken call
until the stage burned through its entire turn budget (MAX_TURNS) and had to
retry from scratch.
"""

from __future__ import annotations

from tools.video.video_compose import VideoCompose


def test_missing_operation_defaults_to_compose_not_keyerror():
    vc = VideoCompose()
    result = vc.execute({})   # no "operation" key at all
    # Must route into _compose() (and fail there on ITS OWN precondition,
    # a normal ToolResult) — never raise/return a bare KeyError.
    assert result.success is False
    assert "edit_decisions" in result.error
    assert "operation" not in result.error.lower()


def test_explicit_operation_still_respected():
    vc = VideoCompose()
    result = vc.execute({"operation": "bogus_op"})
    assert result.success is False
    assert result.error == "Unknown operation: bogus_op"
