"""Contract tests for scene-type collapse detection.

Verifies that the detector correctly identifies when planned scene types
(e.g., animation, anime_scene) are silently downgraded to simpler types
(e.g., text_card) in the rendered output.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.scene_type_collapse import detect_scene_type_collapse


class TestSceneTypeCollapse:
    """Tests for scene-type collapse detection."""

    def test_exact_match_returns_ok(self):
        """Planned types match rendered types → ok."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"type": "text_card", "id": "s2"},
            {"type": "bar_chart", "id": "s3"},
        ]
        cuts = [
            {"type": "animation", "id": "c1"},
            {"type": "text_card", "id": "c2"},
            {"type": "bar_chart", "id": "c3"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["verdict"] == "ok"
        assert result["collapse_count"] == 0
        assert result["collapse_ratio"] == 0.0

    def test_all_animation_to_text_card_returns_collapsed(self):
        """4 animation + 1 text_card planned, all rendered as text_card → collapsed."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"type": "animation", "id": "s2"},
            {"type": "animation", "id": "s3"},
            {"type": "animation", "id": "s4"},
            {"type": "text_card", "id": "s5"},
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},
            {"type": "text_card", "id": "c2"},
            {"type": "text_card", "id": "c3"},
            {"type": "text_card", "id": "c4"},
            {"type": "text_card", "id": "c5"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["verdict"] == "collapsed"
        assert result["collapse_count"] == 4  # 4 animations → text_card
        assert result["collapse_ratio"] >= 0.5
        # Verify collapsed scene details
        for c in result["collapsed_scenes"]:
            assert c["planned_type"] == "animation"
            assert c["rendered_type"] == "text_card"
            assert c["tier_drop"] > 0

    def test_single_downgrade_returns_degraded(self):
        """1 downgrade out of 5 → degraded."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"type": "text_card", "id": "s2"},
            {"type": "bar_chart", "id": "s3"},
            {"type": "stat_card", "id": "s4"},
            {"type": "text_card", "id": "s5"},
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},  # animation → text_card (downgrade)
            {"type": "text_card", "id": "c2"},
            {"type": "bar_chart", "id": "c3"},
            {"type": "stat_card", "id": "c4"},
            {"type": "text_card", "id": "c5"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["verdict"] == "degraded"
        assert result["collapse_count"] == 1
        assert result["collapsed_scenes"][0]["planned_type"] == "animation"
        assert result["collapsed_scenes"][0]["rendered_type"] == "text_card"

    def test_lateral_move_not_counted_as_collapse(self):
        """Same-tier type change is not a collapse."""
        scenes = [
            {"type": "bar_chart", "id": "s1"},
            {"type": "line_chart", "id": "s2"},
        ]
        cuts = [
            {"type": "pie_chart", "id": "c1"},  # tier 2 → tier 2 = lateral
            {"type": "stat_card", "id": "c2"},  # tier 2 → tier 2 = lateral
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["verdict"] == "ok"
        assert result["collapse_count"] == 0

    def test_upgrade_not_counted_as_collapse(self):
        """Rendered type richer than planned → not a collapse."""
        scenes = [
            {"type": "text_card", "id": "s1"},
            {"type": "stat_card", "id": "s2"},
        ]
        cuts = [
            {"type": "animation", "id": "c1"},  # tier 1 → tier 4 = upgrade
            {"type": "anime_scene", "id": "c2"},  # tier 2 → tier 3 = upgrade
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["verdict"] == "ok"
        assert result["collapse_count"] == 0

    def test_empty_inputs_return_ok(self):
        """Empty lists → ok with zero counts."""
        result = detect_scene_type_collapse([], [])
        assert result["verdict"] == "ok"
        assert result["collapse_count"] == 0

    def test_mismatched_list_lengths(self):
        """Different-length lists → compare up to shorter, total is longer."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"type": "animation", "id": "s2"},
            {"type": "animation", "id": "s3"},
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},
            {"type": "text_card", "id": "c2"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["collapse_count"] == 2
        assert result["total_scenes"] == 3  # max of the two

    def test_collapse_ratio_calculation(self):
        """Verify collapse ratio is computed correctly."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"type": "animation", "id": "s2"},
            {"type": "text_card", "id": "s3"},
            {"type": "text_card", "id": "s4"},
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},
            {"type": "text_card", "id": "c2"},
            {"type": "text_card", "id": "c3"},
            {"type": "text_card", "id": "c4"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["collapse_count"] == 2
        assert result["collapse_ratio"] == 0.5
        assert result["verdict"] == "collapsed"

    def test_missing_type_fields_handled(self):
        """Scenes/cuts with missing type fields are skipped gracefully."""
        scenes = [
            {"type": "animation", "id": "s1"},
            {"id": "s2"},  # no type
            {"type": "", "id": "s3"},  # empty type
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},
            {"type": "text_card", "id": "c2"},
            {"type": "text_card", "id": "c3"},
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        # Only s1 → c1 is a valid comparison with a downgrade
        assert result["collapse_count"] == 1

    def test_tier_drop_reported(self):
        """Verify tier_drop is computed correctly for each collapse."""
        scenes = [
            {"type": "video", "id": "s1"},  # tier 4
            {"type": "anime_scene", "id": "s2"},  # tier 3
        ]
        cuts = [
            {"type": "text_card", "id": "c1"},  # tier 1
            {"type": "text_card", "id": "c2"},  # tier 1
        ]
        result = detect_scene_type_collapse(scenes, cuts)
        assert result["collapse_count"] == 2
        assert result["collapsed_scenes"][0]["tier_drop"] == 3  # 4 → 1
        assert result["collapsed_scenes"][1]["tier_drop"] == 2  # 3 → 1
