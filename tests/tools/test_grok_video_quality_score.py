"""Regression for grok_video quality_score (REVIEW §8 #6).

Every premium video provider sets a quality_score (seedance 0.95, runway /
higgsfield 0.9) so the scorer ranks them above stock/local options. grok_video
— which ships native synchronized audio (lip-sync + dialogue + SFX in a single
pass) — had none, so it was ranked only on supports/stability flags and
under-ranked. This pins the field and confirms it surfaces in get_info().
"""

from __future__ import annotations

from tools.video.grok_video import GrokVideo


def test_grok_video_has_quality_score():
    assert GrokVideo.quality_score is not None
    # On par with the other native-audio/premium providers (0.9–0.95).
    assert GrokVideo.quality_score >= 0.9


def test_quality_score_surfaces_in_tool_info():
    info = GrokVideo().get_info()
    assert info["quality_score"] == GrokVideo.quality_score
