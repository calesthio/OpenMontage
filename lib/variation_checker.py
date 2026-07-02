"""Scene plan variation checker.

Analyzes a scene plan for repetitive patterns that make videos feel
like slideshows. Catches problems before asset generation begins.

This is a structural check, not a creative judgment — it flags concrete
patterns that reliably produce generic-feeling output.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# Generic language patterns that signal lazy scene descriptions
GENERIC_PHRASES = {
    "a person", "a beautiful", "modern", "futuristic", "cutting-edge",
    "in today's world", "sleek design", "innovative", "state-of-the-art",
    "next-generation", "revolutionary", "a professional", "dynamic",
    "vibrant", "stunning", "breathtaking", "amazing", "incredible",
    "powerful", "seamless", "elegant solution",
}


def check_scene_variation(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a scene plan for repetitive patterns.

    Returns:
        {
            "score": float (0-5, lower is better),
            "verdict": "strong" | "acceptable" | "revise" | "fail",
            "violations": list of specific issues,
            "suggestions": list of improvement suggestions,
        }
    """
    if not scenes:
        return {"score": 5.0, "verdict": "fail", "violations": ["No scenes to check"], "suggestions": []}

    violations: list[str] = []
    suggestions: list[str] = []

    # --- Check 1: Shot size variety ---
    shot_sizes = [
        s.get("shot_language", {}).get("shot_size", "unspecified")
        for s in scenes
    ]
    size_counts = Counter(shot_sizes)
    if len(scenes) >= 4:
        most_common_size, most_common_count = size_counts.most_common(1)[0]
        if most_common_count / len(scenes) > 0.5:
            violations.append(
                f"Shot size '{most_common_size}' used in {most_common_count}/{len(scenes)} scenes "
                f"({most_common_count/len(scenes):.0%}). Vary shot sizes for visual interest."
            )
            suggestions.append("Mix wide establishing shots with close-ups for visual rhythm.")

    # --- Check 2: Consecutive same-size shots ---
    # Track the longest actual run of identical shot sizes. Summing every equal
    # adjacent pair across the whole plan would count non-consecutive groups
    # (e.g. wide,wide,cu,cu,med,med -> 3 pairs) as a single "3 consecutive" run.
    longest_run = 1 if shot_sizes else 0
    current_run = 1
    for i in range(1, len(shot_sizes)):
        if shot_sizes[i] == shot_sizes[i-1] and shot_sizes[i] != "unspecified":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    if longest_run >= 3:
        violations.append(
            f"{longest_run} consecutive same-size shots. "
            f"Vary shot sizes between scenes for editorial rhythm."
        )

    # --- Check 3: Static shot overuse ---
    movements = [
        s.get("shot_language", {}).get("camera_movement", "unspecified")
        for s in scenes
    ]
    static_count = sum(1 for m in movements if m in ("static", "unspecified"))
    if len(scenes) >= 4 and static_count / len(scenes) > 0.6:
        violations.append(
            f"{static_count}/{len(scenes)} scenes are static or unspecified movement. "
            f"Add intentional camera movement to at least 40% of scenes."
        )
        suggestions.append("Consider dolly_in for emphasis, tracking for energy, or crane for scale.")

    # --- Check 4: Lighting variety ---
    lightings = {
        s.get("shot_language", {}).get("lighting_key")
        for s in scenes
        if s.get("shot_language", {}).get("lighting_key")
    }
    if len(scenes) >= 4 and len(lightings) <= 1:
        violations.append(
            f"Only {len(lightings)} unique lighting setup(s) across {len(scenes)} scenes. "
            f"Vary lighting to create mood shifts."
        )

    # --- Check 5: Hero moment exists and is visually distinct ---
    hero_scenes = [s for s in scenes if s.get("hero_moment")]
    if len(scenes) >= 4 and not hero_scenes:
        violations.append(
            "No hero_moment flagged. Every video should have at least one visual peak."
        )
        suggestions.append("Mark the most impactful scene as hero_moment=true.")

    if hero_scenes:
        for hero in hero_scenes:
            hero_idx = scenes.index(hero)
            hero_size = hero.get("shot_language", {}).get("shot_size")
            # Check neighbors
            for offset in (-1, 1):
                neighbor_idx = hero_idx + offset
                if 0 <= neighbor_idx < len(scenes):
                    neighbor_size = scenes[neighbor_idx].get("shot_language", {}).get("shot_size")
                    if hero_size and neighbor_size and hero_size == neighbor_size:
                        violations.append(
                            f"Hero scene '{hero.get('id')}' has same shot size as neighbor. "
                            f"Hero moments should be visually distinct from surrounding scenes."
                        )

    # --- Check 6: Description specificity ---
    generic_count = 0
    for scene in scenes:
        desc = scene.get("description", "").lower()
        for phrase in GENERIC_PHRASES:
            if phrase in desc:
                generic_count += 1
                break
    if generic_count >= len(scenes) * 0.3:
        violations.append(
            f"{generic_count}/{len(scenes)} scenes use generic language. "
            f"Replace vague descriptions with specific visual details."
        )
        suggestions.append(
            "Instead of 'a beautiful cityscape', try 'rain-slicked Tokyo intersection "
            "at night, neon reflections in puddles, pedestrians with translucent umbrellas'."
        )

    # --- Check 7: Texture keywords presence ---
    textured = sum(1 for s in scenes if s.get("texture_keywords"))
    if len(scenes) >= 4 and textured < len(scenes) * 0.3:
        violations.append(
            f"Only {textured}/{len(scenes)} scenes have texture_keywords. "
            f"Add texture descriptors to visual scenes for richer generation prompts."
        )

    # --- Check 8: Shot intent completeness ---
    intented = sum(1 for s in scenes if s.get("shot_intent"))
    if len(scenes) >= 4 and intented < len(scenes) * 0.5:
        violations.append(
            f"Only {intented}/{len(scenes)} scenes have shot_intent. "
            f"Every scene should explain WHY it exists in the video."
        )

    # --- Score ---
    # Each violation category adds ~0.6 to score
    score = min(5.0, len(violations) * 0.6)

    if score < 2.0:
        verdict = "strong"
    elif score < 3.0:
        verdict = "acceptable"
    elif score < 4.0:
        verdict = "revise"
    else:
        verdict = "fail"

    return {
        "score": round(score, 1),
        "verdict": verdict,
        "violations": violations,
        "suggestions": suggestions,
    }
