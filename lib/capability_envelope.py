"""Capability envelope classifier.

Classifies the provider capability state for a pipeline as
passed / degraded / blocked, with human-readable impact descriptions.

This module is used at preflight and carried through the pipeline so that
the compose stage and final review can surface degradation honestly.
"""

from __future__ import annotations

from typing import Any


# Per-pipeline minimum capability requirements.
# Each entry maps a capability name to its criticality:
#   "required" — pipeline cannot produce its delivery promise without this
#   "quality"  — pipeline works but output quality is significantly degraded
#   "optional" — nice-to-have, output is acceptable without it
_PIPELINE_CAPABILITY_REQUIREMENTS: dict[str, dict[str, str]] = {
    "animated-explainer": {
        "tts": "required",
        "image_generation": "quality",
        "video_generation": "optional",
        "music_generation": "quality",
    },
    "cinematic": {
        "tts": "quality",
        "image_generation": "quality",
        "video_generation": "required",
        "music_generation": "quality",
    },
    "talking-head": {
        "tts": "required",
        "avatar": "required",
        "image_generation": "optional",
        "music_generation": "optional",
    },
    "avatar-spokesperson": {
        "tts": "required",
        "avatar": "required",
        "image_generation": "optional",
        "music_generation": "quality",
    },
    "animation": {
        "tts": "quality",
        "image_generation": "quality",
        "video_generation": "required",
        "music_generation": "quality",
    },
    "screen-demo": {
        "tts": "quality",
        "image_generation": "optional",
        "video_generation": "optional",
        "music_generation": "optional",
    },
    "hybrid": {
        "tts": "quality",
        "image_generation": "quality",
        "video_generation": "quality",
        "music_generation": "optional",
    },
}

# Human-readable impact descriptions when a capability is missing
_IMPACT_DESCRIPTIONS: dict[str, str] = {
    "tts": "No text-to-speech available — narration will use low-quality local Piper TTS or be absent entirely.",
    "image_generation": "No image generation — all visual scenes will fall back to text cards or placeholders. Output will look like an animated slideshow.",
    "video_generation": "No video generation — motion scenes will fall back to still images with Ken Burns or text cards.",
    "music_generation": "No music generation — output will have no background music, reducing production quality.",
    "avatar": "No avatar generation — talking-head or spokesperson scenes cannot be created.",
}


def classify_capability_envelope(
    provider_summary: dict[str, Any],
    pipeline_type: str,
) -> dict[str, Any]:
    """Classify the capability envelope for a pipeline.

    Args:
        provider_summary: Output from registry.provider_menu_summary().
            Expected structure: {"capabilities": [{"name": str, "configured": int, "total": int}, ...]}
        pipeline_type: Pipeline manifest name (e.g. "animated-explainer").

    Returns:
        {
            "status": "passed" | "degraded" | "blocked",
            "pipeline_type": str,
            "missing_critical": [{"capability": str, "criticality": str, "impact": str}],
            "missing_optional": [{"capability": str, "impact": str}],
            "available_capabilities": [str],
            "degradation_summary": str | None,
            "recommendation": "proceed" | "setup_first" | "proceed_as_draft",
        }
    """
    requirements = _PIPELINE_CAPABILITY_REQUIREMENTS.get(pipeline_type, {})
    if not requirements:
        # Unknown pipeline — can't classify, assume passed
        return {
            "status": "passed",
            "pipeline_type": pipeline_type,
            "missing_critical": [],
            "missing_optional": [],
            "available_capabilities": [],
            "degradation_summary": None,
            "recommendation": "proceed",
        }

    # Build capability → configured count lookup from the summary
    cap_configured: dict[str, int] = {}
    for cap in provider_summary.get("capabilities", []):
        name = cap.get("name", "")
        configured = cap.get("configured", 0)
        cap_configured[name] = configured

    missing_critical: list[dict[str, str]] = []
    missing_quality: list[dict[str, str]] = []
    missing_optional: list[dict[str, str]] = []
    available: list[str] = []

    for capability, criticality in requirements.items():
        configured = cap_configured.get(capability, 0)
        if configured > 0:
            available.append(capability)
            continue

        impact = _IMPACT_DESCRIPTIONS.get(capability, f"No {capability} available.")
        entry = {"capability": capability, "criticality": criticality, "impact": impact}

        if criticality == "required":
            missing_critical.append(entry)
        elif criticality == "quality":
            missing_quality.append(entry)
        else:
            missing_optional.append(entry)

    # Determine overall status
    has_required_missing = len(missing_critical) > 0
    has_quality_missing = len(missing_quality) > 0

    if has_required_missing:
        status = "blocked"
    elif has_quality_missing:
        status = "degraded"
    else:
        status = "passed"

    # Build degradation summary
    degradation_summary = None
    if status != "passed":
        all_missing = missing_critical + missing_quality
        impacts = [m["impact"] for m in all_missing]
        degradation_summary = (
            f"Capability envelope is {status} for pipeline '{pipeline_type}'. "
            + " ".join(impacts)
        )

    # Recommendation
    if status == "blocked":
        recommendation = "setup_first"
    elif status == "degraded":
        # Degraded but not blocked — can proceed but output will be low quality
        if len(missing_quality) >= 2:
            recommendation = "proceed_as_draft"
        else:
            recommendation = "proceed_as_draft"
    else:
        recommendation = "proceed"

    return {
        "status": status,
        "pipeline_type": pipeline_type,
        "missing_critical": missing_critical,
        "missing_optional": missing_optional,
        "missing_quality": missing_quality,
        "available_capabilities": available,
        "degradation_summary": degradation_summary,
        "recommendation": recommendation,
    }
