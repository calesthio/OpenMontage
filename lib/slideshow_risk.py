"""Slideshow risk scorer.

Scores a video plan across 6 dimensions that reliably predict whether
the output will feel like a slideshow rather than directed video.

Each dimension is scored 0-5 (lower is better):
  - repetition: same layouts/backgrounds/scene grammar recurring
  - decorative_visuals: scenes decorate instead of communicate
  - weak_motion: motion exists but has no narrative purpose
  - weak_shot_intent: no explicit reason for framing or reveal rhythm
  - typography_overreliance: too much of the video is text-first
  - unsupported_cinematic_claims: cinematic label without structure

Verdict:
  < 2.0: strong
  < 3.0: acceptable
  < 4.0: revise
  >= 4.0: fail — should not proceed to compose
"""

from __future__ import annotations

from typing import Any


def _scene_dicts(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [scene for scene in scenes if isinstance(scene, dict)]


def _shot_language(scene: dict[str, Any]) -> dict[str, Any]:
    shot_language = scene.get("shot_language")
    return shot_language if isinstance(shot_language, dict) else {}


def score_slideshow_risk(
    scenes: list[dict[str, Any]],
    edit_decisions: dict[str, Any] | None = None,
    renderer_family: str | None = None,
    render_runtime: str | None = None,
) -> dict[str, Any]:
    """Score slideshow risk across 6 dimensions.

    Args:
        scenes: Scene list from scene_plan artifact.
        edit_decisions: Optional edit_decisions artifact for transition analysis.
        renderer_family: Optional renderer family for cinematic claim verification.
        render_runtime: Optional render runtime (remotion/hyperframes/ffmpeg).
            Passed through so dimension scoring can reason about runtime-specific
            indicators when it's useful. Scoring logic is currently
            runtime-neutral — a text-heavy HyperFrames composition is just as
            slideshow-y as a text-heavy Remotion one — but the parameter is
            part of the contract so callers record runtime alongside family.

    Returns:
        {
            "average": float,
            "verdict": str,
            "dimensions": {dimension_name: {"score": float, "reason": str}},
            "render_runtime": str | None,
        }
    """
    if not scenes:
        return {
            "average": 5.0,
            "verdict": "fail",
            "dimensions": {},
            "render_runtime": render_runtime,
        }

    scenes = _scene_dicts(scenes)
    if not scenes:
        return {
            "average": 5.0,
            "verdict": "fail",
            "dimensions": {},
            "render_runtime": render_runtime,
        }

    dimensions = {
        "repetition": _score_repetition(scenes),
        "decorative_visuals": _score_decorative(scenes),
        "weak_motion": _score_weak_motion(scenes),
        "weak_shot_intent": _score_weak_intent(scenes),
        "typography_overreliance": _score_typography(scenes),
        "unsupported_cinematic_claims": _score_cinematic_claims(scenes, renderer_family),
    }

    scores = [d["score"] for d in dimensions.values()]
    average = sum(scores) / len(scores)

    if average < 2.0:
        verdict = "strong"
    elif average < 3.0:
        verdict = "acceptable"
    elif average < 4.0:
        verdict = "revise"
    else:
        verdict = "fail"

    return {
        "average": round(average, 2),
        "verdict": verdict,
        "dimensions": dimensions,
        "render_runtime": render_runtime,
    }


def _score_repetition(scenes: list[dict]) -> dict[str, Any]:
    """Score visual repetition across scenes."""
    if len(scenes) < 3:
        return {"score": 0.0, "reason": "Too few scenes to assess repetition"}

    # Check for repeated scene types
    from collections import Counter
    types = Counter(s.get("type", "unknown") for s in scenes)
    most_common_type, most_common_count = types.most_common(1)[0]
    type_ratio = most_common_count / len(scenes)

    # Check for repeated descriptions (crude similarity)
    descriptions = [s.get("description", "").lower()[:50] for s in scenes]
    unique_desc_ratio = len(set(descriptions)) / len(descriptions)

    # Check shot size repetition
    sizes = [_shot_language(s).get("shot_size", "none") for s in scenes]
    size_ratio = Counter(sizes).most_common(1)[0][1] / len(scenes)

    score = 0.0
    reasons = []

    if type_ratio > 0.7:
        score += 2.0
        reasons.append(f"Scene type '{most_common_type}' dominates at {type_ratio:.0%}")
    if unique_desc_ratio < 0.6:
        score += 1.5
        reasons.append(f"Only {unique_desc_ratio:.0%} unique descriptions")
    if size_ratio > 0.6:
        score += 1.5
        reasons.append(f"Same shot size in {size_ratio:.0%} of scenes")

    return {"score": min(5.0, score), "reason": "; ".join(reasons) or "Good variety"}


def _score_decorative(scenes: list[dict]) -> dict[str, Any]:
    """Score whether scenes are decorative vs communicative."""
    decorative_count = 0
    for scene in scenes:
        has_info_role = bool(scene.get("information_role"))
        has_narrative_role = bool(scene.get("narrative_role"))
        has_intent = bool(scene.get("shot_intent"))

        # A scene with no role or intent is likely decorative
        if not has_info_role and not has_narrative_role and not has_intent:
            decorative_count += 1

    ratio = decorative_count / len(scenes)
    score = min(5.0, ratio * 5.0)

    if ratio > 0.5:
        reason = f"{decorative_count}/{len(scenes)} scenes have no stated purpose (no information_role, narrative_role, or shot_intent)"
    elif ratio > 0.2:
        reason = f"{decorative_count}/{len(scenes)} scenes lack stated purpose"
    else:
        reason = "Most scenes have clear communicative purpose"

    return {"score": round(score, 1), "reason": reason}


def _score_weak_motion(scenes: list[dict]) -> dict[str, Any]:
    """Score whether camera movement is purposeful."""
    total_moving = 0
    purposeless_moving = 0

    for scene in scenes:
        sl = _shot_language(scene)
        movement = sl.get("camera_movement", "static")
        if movement not in ("static", "unspecified", None):
            total_moving += 1
            # Movement without shot_intent suggests arbitrary motion
            if not scene.get("shot_intent"):
                purposeless_moving += 1

    if total_moving == 0:
        # No movement at all is fine for some styles, but scores moderate
        return {"score": 1.5, "reason": "No camera movement defined (may be intentional for static style)"}

    ratio = purposeless_moving / total_moving
    score = min(5.0, ratio * 4.0)

    if ratio > 0.5:
        reason = f"{purposeless_moving}/{total_moving} moving shots lack shot_intent"
    else:
        reason = "Camera movement appears purposeful"

    return {"score": round(score, 1), "reason": reason}


def _score_weak_intent(scenes: list[dict]) -> dict[str, Any]:
    """Score shot intent completeness."""
    with_intent = sum(1 for s in scenes if s.get("shot_intent"))
    ratio = with_intent / len(scenes)

    # Invert: more intent = lower score
    score = min(5.0, (1.0 - ratio) * 5.0)

    if ratio < 0.3:
        reason = f"Only {with_intent}/{len(scenes)} scenes have shot_intent — most shots lack purpose"
    elif ratio < 0.6:
        reason = f"{with_intent}/{len(scenes)} scenes have shot_intent"
    else:
        reason = "Strong shot intent coverage"

    return {"score": round(score, 1), "reason": reason}


def _score_typography(scenes: list[dict]) -> dict[str, Any]:
    """Score text-first overreliance."""
    text_scenes = sum(
        1 for s in scenes
        if s.get("type") in ("text_card", "stat_card", "kpi_grid")
    )
    ratio = text_scenes / len(scenes)

    if ratio > 0.6:
        score = 4.0
        reason = f"{text_scenes}/{len(scenes)} scenes are text/stat cards — video feels like animated slides"
    elif ratio > 0.4:
        score = 2.5
        reason = f"{text_scenes}/{len(scenes)} scenes are text-based — consider balancing with visual scenes"
    elif ratio > 0.2:
        score = 1.0
        reason = "Balanced text and visual content"
    else:
        score = 0.0
        reason = "Visual-first approach"

    return {"score": score, "reason": reason}


def _score_cinematic_claims(
    scenes: list[dict],
    renderer_family: str | None,
) -> dict[str, Any]:
    """Score whether cinematic claims are backed by cinematic structure."""
    is_cinematic = renderer_family and "cinematic" in renderer_family.lower()

    if not is_cinematic:
        return {"score": 0.0, "reason": "Not claiming cinematic treatment"}

    issues = []

    # Cinematic should have: varied shot sizes, intentional movement, hero moments
    hero_count = sum(1 for s in scenes if s.get("hero_moment"))
    if hero_count == 0:
        issues.append("Claims cinematic but has no hero_moment defined")

    has_movement = sum(
        1 for s in scenes
        if _shot_language(s).get("camera_movement", "static") != "static"
    )
    if has_movement < len(scenes) * 0.3:
        issues.append(f"Claims cinematic but only {has_movement}/{len(scenes)} scenes have camera movement")

    has_lighting = sum(
        1 for s in scenes
        if _shot_language(s).get("lighting_key")
    )
    if has_lighting < len(scenes) * 0.3:
        issues.append(f"Claims cinematic but only {has_lighting}/{len(scenes)} scenes define lighting")

    score = min(5.0, len(issues) * 1.8)
    reason = "; ".join(issues) if issues else "Cinematic claims supported by structure"

    return {"score": round(score, 1), "reason": reason}
