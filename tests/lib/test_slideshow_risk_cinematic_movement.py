"""Cinematic-claim scoring must not count unspecified camera movement as movement."""

from __future__ import annotations

import pytest

from lib.slideshow_risk import score_slideshow_risk


def _scenes(movement, *, key_present: bool = True) -> list[dict]:
    scenes = []
    for i in range(5):
        shot_language = {"lighting_key": "low_key"}
        if key_present:
            shot_language["camera_movement"] = movement
        scenes.append(
            {
                "id": f"s{i}",
                "description": f"scene {i}",
                "hero_moment": i == 0,
                "shot_language": shot_language,
            }
        )
    return scenes


def _claims(scenes: list[dict]) -> dict:
    result = score_slideshow_risk(scenes, renderer_family="cinematic-trailer")
    return result["dimensions"]["unsupported_cinematic_claims"]


@pytest.mark.parametrize("movement", ["unspecified", None, "static"])
def test_non_moving_scenes_do_not_support_cinematic_claim(movement):
    claim = _claims(_scenes(movement))
    assert "only 0/5 scenes have camera movement" in claim["reason"]
    assert claim["score"] > 0


def test_missing_movement_key_is_still_static():
    claim = _claims(_scenes(None, key_present=False))
    assert "only 0/5 scenes have camera movement" in claim["reason"]


def test_real_movement_supports_cinematic_claim():
    claim = _claims(_scenes("dolly_in"))
    assert claim["score"] == 0.0
