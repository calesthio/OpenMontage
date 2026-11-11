"""final_review.audio_spotcheck.music_present must reflect a declared music bed.

The 2026-11-11 end-to-end audit run rendered narration only, yet final_review
reported `music_present: True`, because the flag was set from the mix's mean
volume alone (> -50 dB), which narration by itself always exceeds.
"""

from __future__ import annotations

import pytest

from tools.video.video_compose import _music_declared


@pytest.mark.parametrize(
    "edit_decisions",
    [
        None,
        {},
        {"audio": {}},
        {"audio": {"narration": {"src": "narration.wav"}}},
        {"audio": {"music": {}}},
        {"audio": {"music": {"volume": 0.2}}},
        {"music": {"volume": 0.2}},
    ],
    ids=["none", "empty", "empty-audio", "narration-only", "empty-music", "music-without-source", "legacy-without-asset"],
)
def test_no_declared_music(edit_decisions) -> None:
    assert _music_declared(edit_decisions) is False


@pytest.mark.parametrize(
    "edit_decisions",
    [
        {"audio": {"music": {"asset_id": "music-bg"}}},
        {"audio": {"music": {"src": "music/bed.mp3"}}},
        {"music": {"asset_id": "music-bg"}},
    ],
    ids=["canonical-asset", "remotion-src", "legacy-asset"],
)
def test_declared_music(edit_decisions) -> None:
    assert _music_declared(edit_decisions) is True
