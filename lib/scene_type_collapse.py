"""Scene-type collapse detector.

Compares planned scene types (from scene_plan) against rendered cut types
(from edit_decisions/resolved_cuts) to catch silent downgrades — e.g.,
animation scenes that were rendered as text_card divs.

This is a governance guard: the pipeline should never silently replace
a promised scene type with a weaker one without surfacing the downgrade.
"""

from __future__ import annotations

from typing import Any


# Scene types ordered roughly by "richness" — richer types collapsing
# to simpler ones is a downgrade. Types at the same level are lateral
# moves, not downgrades.
_RICHNESS_TIERS: dict[str, int] = {
    # Tier 4: real motion / generated video
    "video": 4,
    "animation": 4,
    "avatar": 4,
    # Tier 3: composite / multi-element visual
    "anime_scene": 3,
    "terminal_scene": 3,
    "screenshot_scene": 3,
    "comparison": 3,
    # Tier 2: data-driven visual component
    "bar_chart": 2,
    "line_chart": 2,
    "pie_chart": 2,
    "kpi_grid": 2,
    "progress_bar": 2,
    "stat_card": 2,
    "callout": 2,
    # Tier 1: static text / card
    "text_card": 1,
    "hero_title": 1,
}


def _get_tier(scene_type: str) -> int:
    """Get the richness tier of a scene type. Unknown types default to tier 2."""
    return _RICHNESS_TIERS.get(scene_type, 2)


def detect_scene_type_collapse(
    scene_plan_scenes: list[dict[str, Any]],
    rendered_cuts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare planned scene types against rendered cut types.

    Args:
        scene_plan_scenes: Scenes from the scene_plan artifact. Each should
            have at least a "type" key and ideally an "id" or index.
        rendered_cuts: Cuts from edit_decisions (resolved). Each should
            have a "type" key and an "id" key.

    Returns:
        {
            "collapsed_scenes": [
                {"index": int, "scene_id": str, "planned_type": str,
                 "rendered_type": str, "tier_drop": int},
                ...
            ],
            "collapse_count": int,
            "total_scenes": int,
            "collapse_ratio": float,
            "verdict": "ok" | "degraded" | "collapsed",
        }
    """
    if not scene_plan_scenes or not rendered_cuts:
        return {
            "collapsed_scenes": [],
            "collapse_count": 0,
            "total_scenes": max(len(scene_plan_scenes), len(rendered_cuts)),
            "collapse_ratio": 0.0,
            "verdict": "ok",
        }

    collapsed_scenes: list[dict[str, Any]] = []

    # Match by index (scene_plan[i] → rendered_cuts[i]) since IDs may differ.
    # If the lists have different lengths, compare up to the shorter one.
    compare_count = min(len(scene_plan_scenes), len(rendered_cuts))

    for i in range(compare_count):
        planned = scene_plan_scenes[i]
        rendered = rendered_cuts[i]

        planned_type = (planned.get("type") or "").strip().lower()
        rendered_type = (rendered.get("type") or "").strip().lower()

        if not planned_type or not rendered_type:
            continue

        planned_tier = _get_tier(planned_type)
        rendered_tier = _get_tier(rendered_type)

        # A collapse is when the rendered type is in a lower richness tier
        if rendered_tier < planned_tier:
            collapsed_scenes.append({
                "index": i,
                "scene_id": planned.get("id") or rendered.get("id") or f"scene_{i}",
                "planned_type": planned_type,
                "rendered_type": rendered_type,
                "tier_drop": planned_tier - rendered_tier,
            })

    total = max(len(scene_plan_scenes), len(rendered_cuts))
    collapse_count = len(collapsed_scenes)
    collapse_ratio = collapse_count / total if total > 0 else 0.0

    # Verdicts:
    #   - "ok": no collapses
    #   - "degraded": some scenes collapsed but < 50%
    #   - "collapsed": >= 50% of scenes collapsed — likely a text-slideshow
    if collapse_count == 0:
        verdict = "ok"
    elif collapse_ratio >= 0.5:
        verdict = "collapsed"
    else:
        verdict = "degraded"

    return {
        "collapsed_scenes": collapsed_scenes,
        "collapse_count": collapse_count,
        "total_scenes": total,
        "collapse_ratio": round(collapse_ratio, 3),
        "verdict": verdict,
    }
