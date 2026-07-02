"""Contract tests for capability envelope classification.

Verifies that the classifier correctly identifies passed / degraded / blocked
states based on provider availability and pipeline requirements.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.capability_envelope import classify_capability_envelope


def _make_summary(capabilities: dict[str, tuple[int, int]]) -> dict:
    """Build a provider_menu_summary-like dict from {name: (configured, total)}."""
    return {
        "capabilities": [
            {"name": name, "configured": conf, "total": total}
            for name, (conf, total) in capabilities.items()
        ]
    }


class TestCapabilityEnvelope:
    """Tests for capability envelope classification."""

    def test_all_configured_returns_passed(self):
        """All capabilities configured → passed."""
        summary = _make_summary({
            "tts": (2, 3),
            "image_generation": (1, 5),
            "video_generation": (1, 10),
            "music_generation": (1, 1),
        })
        result = classify_capability_envelope(summary, "animated-explainer")
        assert result["status"] == "passed"
        assert result["recommendation"] == "proceed"
        assert len(result["missing_critical"]) == 0
        assert result["degradation_summary"] is None

    def test_no_image_generation_returns_degraded(self):
        """animated-explainer with no image generation → degraded."""
        summary = _make_summary({
            "tts": (1, 3),
            "image_generation": (0, 5),
            "video_generation": (0, 10),
            "music_generation": (1, 1),
        })
        result = classify_capability_envelope(summary, "animated-explainer")
        assert result["status"] == "degraded"
        assert result["recommendation"] == "proceed_as_draft"
        assert any(m["capability"] == "image_generation" for m in result["missing_quality"])
        assert result["degradation_summary"] is not None
        assert "text cards" in result["degradation_summary"].lower() or "slideshow" in result["degradation_summary"].lower()

    def test_no_image_no_music_returns_degraded(self):
        """animated-explainer with no image + no music → degraded (both are quality-tier)."""
        summary = _make_summary({
            "tts": (1, 3),
            "image_generation": (0, 5),
            "video_generation": (0, 10),
            "music_generation": (0, 1),
        })
        result = classify_capability_envelope(summary, "animated-explainer")
        assert result["status"] == "degraded"
        assert result["recommendation"] == "proceed_as_draft"
        assert len(result["missing_quality"]) == 2

    def test_no_tts_for_explainer_returns_blocked(self):
        """animated-explainer with no TTS → blocked (TTS is required)."""
        summary = _make_summary({
            "tts": (0, 3),
            "image_generation": (1, 5),
            "video_generation": (0, 10),
            "music_generation": (1, 1),
        })
        result = classify_capability_envelope(summary, "animated-explainer")
        assert result["status"] == "blocked"
        assert result["recommendation"] == "setup_first"
        assert any(m["capability"] == "tts" for m in result["missing_critical"])

    def test_cinematic_no_video_returns_blocked(self):
        """cinematic with no video generation → blocked."""
        summary = _make_summary({
            "tts": (1, 3),
            "image_generation": (1, 5),
            "video_generation": (0, 10),
            "music_generation": (1, 1),
        })
        result = classify_capability_envelope(summary, "cinematic")
        assert result["status"] == "blocked"
        assert any(m["capability"] == "video_generation" for m in result["missing_critical"])

    def test_unknown_pipeline_returns_passed(self):
        """Unknown pipeline → passed (can't classify)."""
        summary = _make_summary({"tts": (0, 0)})
        result = classify_capability_envelope(summary, "unknown-pipeline")
        assert result["status"] == "passed"

    def test_impact_strings_are_human_readable(self):
        """Verify impact descriptions are non-empty and descriptive."""
        summary = _make_summary({
            "tts": (1, 3),
            "image_generation": (0, 5),
            "video_generation": (0, 10),
            "music_generation": (0, 1),
        })
        result = classify_capability_envelope(summary, "animated-explainer")
        for missing in result["missing_quality"]:
            assert len(missing["impact"]) > 20  # Substantial description
            assert missing["capability"] in missing["impact"].lower() or "generation" in missing["impact"].lower() or "music" in missing["impact"].lower()

    def test_result_structure(self):
        """Verify result contains all expected fields."""
        summary = _make_summary({"tts": (1, 1)})
        result = classify_capability_envelope(summary, "animated-explainer")
        assert "status" in result
        assert "pipeline_type" in result
        assert "missing_critical" in result
        assert "missing_optional" in result
        assert "available_capabilities" in result
        assert "degradation_summary" in result
        assert "recommendation" in result
        assert result["pipeline_type"] == "animated-explainer"

    def test_screen_demo_minimal_requirements(self):
        """screen-demo with only TTS should pass (everything else is optional/quality)."""
        summary = _make_summary({
            "tts": (1, 3),
        })
        result = classify_capability_envelope(summary, "screen-demo")
        # TTS is quality for screen-demo, and it's configured, so no required missing
        assert result["status"] == "passed" or result["status"] == "degraded"
        assert len(result["missing_critical"]) == 0

    def test_empty_summary(self):
        """Empty provider summary → everything missing."""
        summary = {"capabilities": []}
        result = classify_capability_envelope(summary, "animated-explainer")
        # TTS is required for animated-explainer → blocked
        assert result["status"] == "blocked"
