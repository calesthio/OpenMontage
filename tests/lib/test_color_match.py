"""Unit tests for lib/color_match.py (scene-aware color grading).

Pure logic: profile selection is tested without FFmpeg.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.color_match import (  # noqa: E402
    ARCH_BRIGHT, ARCH_DEEP, ARCH_DEFAULT, ARCH_PROFILES, AI_COOL, AI_DEFAULT, AI_PROFILES,
    profile_for,
)


def test_profile_for_archival_dark_space():
    assert profile_for("archival", "S027") == ARCH_PROFILES["deep"]


def test_profile_for_archival_bright_ice():
    assert profile_for("archival", "S016") == ARCH_PROFILES["bright"]


def test_profile_for_archival_deep_sea():
    assert profile_for("archival", "S007") == ARCH_PROFILES["default"]


def test_profile_for_archival_unknown_scene_defaults():
    assert profile_for("archival", "S999") == ARCH_PROFILES["default"]


def test_profile_for_ai_bright_ice_cool():
    assert profile_for("ai_generated", "S016") == AI_PROFILES["cool"]


def test_profile_for_ai_default():
    assert profile_for("ai_generated", "S027") == AI_PROFILES["default"]


def test_profile_for_custom_scene_sets():
    """Custom scene sets override the pilot defaults."""
    assert profile_for("archival", "X1", dark_space={"X1"}, bright_ice=set(), deep_sea=set()) == ARCH_PROFILES["deep"]
    assert profile_for("archival", "X2", dark_space=set(), bright_ice={"X2"}, deep_sea=set()) == ARCH_PROFILES["bright"]


def test_profiles_are_distinct_filters():
    """Archival and AI profiles must differ so hybrid cuts don't clash."""
    assert ARCH_DEFAULT != AI_DEFAULT
    assert ARCH_DEEP != ARCH_BRIGHT
    assert AI_DEFAULT != AI_COOL
