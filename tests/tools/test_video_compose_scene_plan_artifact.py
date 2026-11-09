"""The pre-compose slideshow gate must accept the scene_plan artifact as-is.

Agents naturally pass the canonical ``scene_plan`` artifact (``{"version",
"scenes": [...]}``) to ``video_compose``. Before this fix the gate only
understood the bare scene list: the dict was iterated as keys, scoring raised
``'str' object has no attribute 'get'``, the error was swallowed as a log
warning and the slideshow check silently did not run. These tests use the
real scorer (no stubs) so they pin the gate's actual verdicts.
"""

from __future__ import annotations

import logging

import pytest

from tools.video.video_compose import VideoCompose

EDIT_DECISIONS = {"renderer_family": "cinematic-trailer", "render_runtime": "remotion"}

# Six plain video cuts with no shot metadata (what a schema-valid
# edit_decisions carries). Scored on their own they only produce a warning.
VIDEO_CUTS = [
    {"id": f"c{i}", "type": "video", "source": f"v{i}.mp4", "reason": f"beat {i}"}
    for i in range(6)
]

# Five text cards + one video, also without metadata: the gate blocks this
# on cuts alone (slideshow risk 4.0, verdict "fail").
TEXT_CUTS = [
    {"id": f"c{i}", "type": "text_card", "source": "", "reason": f"beat {i}"}
    for i in range(5)
] + [{"id": "c5", "type": "video", "source": "v.mp4", "reason": "x"}]

SLIDESHOW_SCENES = [
    {"id": f"s{i}", "type": "text_card", "description": "title card"}
    for i in range(6)
]

GOOD_SCENES = [
    {
        "id": "s1", "type": "broll", "description": "City wakes at dawn",
        "shot_intent": "establish the world", "narrative_role": "hook",
        "shot_language": {"shot_size": "wide", "camera_movement": "dolly_in"},
    },
    {
        "id": "s2", "type": "broll", "description": "Hands assemble the prototype",
        "shot_intent": "show the craft", "narrative_role": "build",
        "shot_language": {"shot_size": "close_up", "camera_movement": "handheld"},
    },
    {
        "id": "s3", "type": "broll", "description": "Prototype lifts off",
        "shot_intent": "pay off the build", "narrative_role": "climax",
        "hero_moment": True,
        "shot_language": {"shot_size": "medium", "camera_movement": "crane_up"},
    },
]


def _gate(cuts, scene_plan):
    return VideoCompose()._pre_compose_validation(dict(EDIT_DECISIONS), cuts, scene_plan)


def _outcome(result):
    return None if result is None else (result.success, result.error)


@pytest.mark.parametrize(
    "scenes, cuts",
    [(SLIDESHOW_SCENES, VIDEO_CUTS), (GOOD_SCENES, TEXT_CUTS)],
    ids=["slideshow-plan", "good-plan"],
)
def test_artifact_dict_gates_exactly_like_scene_list(scenes, cuts, caplog):
    as_list = _outcome(_gate(cuts, scenes))
    with caplog.at_level(logging.WARNING, logger="video_compose"):
        as_artifact = _outcome(_gate(cuts, {"version": "1.0", "scenes": scenes}))

    assert as_artifact == as_list
    assert "Could not compute slideshow risk" not in caplog.text


def test_slideshow_artifact_blocks_even_with_video_cuts():
    # The plan, not the cuts, decides: a slideshow plan is blocked whether it
    # arrives as the artifact or as its scene list.
    assert _gate(VIDEO_CUTS, None) is None
    result = _gate(VIDEO_CUTS, {"version": "1.0", "scenes": SLIDESHOW_SCENES})
    assert result is not None and not result.success
    assert "Slideshow risk score" in result.error


def test_good_artifact_unblocks_text_heavy_cuts():
    assert _gate(TEXT_CUTS, None) is not None
    assert _gate(TEXT_CUTS, {"version": "1.0", "scenes": GOOD_SCENES}) is None


@pytest.mark.parametrize("artifact", [{"version": "1.0"}, {"version": "1.0", "scenes": []}])
def test_artifact_without_scenes_falls_back_to_cuts(artifact):
    assert _outcome(_gate(TEXT_CUTS, artifact)) == _outcome(_gate(TEXT_CUTS, None))


def test_scene_plan_is_a_declared_input():
    prop = VideoCompose.input_schema["properties"]["scene_plan"]
    assert set(prop["type"]) == {"array", "object"}
