"""Regression tests for scoring tokenization vs. punctuation.

Two related defects:
  1. `_tokenize_text` swallowed trailing punctuation ("cinematic." -> "cinematic.")
     because the regex allowed a token to end on '. _ - +'.
  2. The premium-cinematic bonus in score_provider used a raw str.split() (unlike
     every other call site), so a comma-adjacent signal word ("cinematic,") was
     never stripped.

Together these meant an intent whose only cinematic-signal word carried adjacent
punctuation silently lost the premium-provider bonus and could be out-ranked.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib import scoring  # noqa: E402


def test_tokenizer_strips_trailing_punctuation():
    assert scoring._tokenize_text("cinematic.") == ["cinematic"]
    assert scoring._tokenize_text("epic, dramatic") == ["epic", "dramatic"]
    assert scoring._tokenize_text("a trailer!") == ["a", "trailer"]


def test_tokenizer_preserves_model_name_tokens():
    # Internal punctuation must survive so model-name-like tokens still match.
    assert scoring._tokenize_text("gpt-4.1") == ["gpt-4.1"]
    assert scoring._tokenize_text("film-noir") == ["film-noir"]
    assert scoring._tokenize_text("multi_shot") == ["multi_shot"]
    assert scoring._tokenize_text("v1.5.") == ["v1.5"]


class _FakeStatus:
    value = "available"


class _FakeTool:
    def get_status(self):
        return _FakeStatus()

    def get_info(self):
        return {
            "name": "premium_video",
            "provider": "premium",
            "capability": "video_generation",
            "best_for": ["cinematic trailer"],
            "stability": "production",
            "supports": {
                "native_audio": True,
                "multi_shot": True,
                "camera_direction": True,
                "lip_sync": True,
            },
        }


def _fit(intent):
    return scoring.score_provider(
        _FakeTool(), {"asset_type": "video", "intent": intent}
    ).task_fit


def test_cinematic_bonus_ignores_adjacent_punctuation():
    baseline = _fit("make it cinematic and fast")
    assert _fit("make it cinematic, and fast") == baseline  # comma-adjacent
    assert _fit("make it cinematic.") == baseline           # trailing period
