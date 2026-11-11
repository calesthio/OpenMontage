"""The character composition fills the HyperFrames canvas it is mounted in.

It used to be a fixed 1280x720 box with a 920px SVG, mounted in a canvas
sized by the media profile (1920x1080 by default, 1080x1920 for shorts), so
the scene sat in the top-left corner and the figure's feet were cut off.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.character.character_animation import (
    ActionTimelineCompiler,
    CharacterRigRenderer,
    CharacterSpecGenerator,
    PoseLibraryBuilder,
    SvgRigBuilder,
)
from tools.video.hyperframes_compose import HyperFramesCompose


def _render(tmp_path: Path, ids: tuple[str, ...] = ("lead",), **extra):
    design = CharacterSpecGenerator().execute(
        {"characters": [{"id": cid, "role": "lead", "body_type": "round"} for cid in ids]}
    ).data["character_design"]
    rig_plan = SvgRigBuilder().execute({"character_design": design}).data["rig_plan"]
    pose_library = PoseLibraryBuilder().execute({"rig_plan": rig_plan}).data["pose_library"]
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "character_scene",
                "description": "Lead waves.",
                "start_seconds": 0,
                "end_seconds": 2,
                "character_actions": [
                    {"character_id": "lead", "emotion": "happy", "action_sequence": ["perform"]}
                ],
            }
        ],
    }
    timeline = ActionTimelineCompiler().execute(
        {"scene_plan": scene_plan, "character_ids": list(ids)}
    ).data["action_timeline"]
    result = CharacterRigRenderer().execute(
        {
            "rig_plan": rig_plan,
            "pose_library": pose_library,
            "action_timeline": timeline,
            "output_path": str(tmp_path / "preview.html"),
            **extra,
        }
    )
    assert result.success, result.error
    return result


def _root_size(composition: str) -> tuple[int, int]:
    match = re.search(
        r'data-composition-id="character-scene"[^>]*data-width="(\d+)" data-height="(\d+)"', composition
    )
    assert match, "composition root has no data-width/data-height"
    return int(match.group(1)), int(match.group(2))


@pytest.mark.parametrize(
    ("profile", "size"),
    [(None, (1920, 1080)), ("youtube_shorts", (1080, 1920)), ("instagram_feed", (1080, 1080))],
)
def test_composition_matches_the_scaffold_canvas(tmp_path, profile, size):
    extra = {"profile": profile} if profile else {}
    result = _render(tmp_path, **extra)
    composition = Path(result.data["composition_path"]).read_text(encoding="utf-8")
    assert _root_size(composition) == size
    width, height, _ = HyperFramesCompose._resolve_dimensions(profile, 30)
    assert (width, height) == size
    assert result.data["canvas"] == {"width": size[0], "height": size[1], "profile": profile}


def test_composition_layout_scales_with_its_slot(tmp_path):
    composition = Path(_render(tmp_path).data["composition_path"]).read_text(encoding="utf-8")
    assert "1280px" not in composition
    assert "920px" not in composition
    assert "width: 100%; height: 100%" in composition
    # The square viewBox is fitted inside the slot (preserveAspectRatio "meet"),
    # so the whole figure, feet and shadow included, stays on screen.
    assert re.search(r"svg \{\{?[^}]*width: 90%; height: 90%", composition)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_figures_stay_inside_the_viewbox_and_on_the_ground(tmp_path, count):
    """Figures are drawn around x=320 with arms reaching x=180..475, feet at y=560."""
    ids = tuple(f"c{i}" for i in range(count))
    composition = Path(_render(tmp_path, ids=ids).data["composition_path"]).read_text(encoding="utf-8")
    placements = re.findall(
        r'<g transform="translate\(([-\d.]+) ([-\d.]+)\) scale\(([\d.]+)\)">\s*<g class="character"',
        composition,
    )
    assert len(placements) == count
    centres = []
    for tx, ty, s in placements:
        tx, ty, s = float(tx), float(ty), float(s)
        assert tx + 180 * s >= 0
        assert tx + 475 * s <= 640
        assert abs(ty + 560 * s - 560) < 0.2  # scaled about the feet
        centres.append(tx + 320 * s)
    assert abs(sum(centres) / count - 320) < 0.2  # the group is centred
    # GSAP animates the .character group; its placement must not live there.
    assert not re.search(r'<g class="character"[^>]*transform=', composition)
