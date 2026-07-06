"""Regression tests: HyperFrames style bridge reads the playbook's real keys.

Two defects, both silently dropping a schema-valid style choice back to the
built-in fallback:

  1. Heading font was read from ``typography.heading`` (singular). The playbook
     schema defines ``typography.headings`` (plural, ``additionalProperties:
     false``), so the singular key never existed and every composition fell back
     to the default "Inter" heading font. ``body`` / ``code`` used the correct
     keys, which isolates this to a key typo rather than a general failure.

  2. Motion pace was read from ``motion.pace``. The schema puts ``pace`` under
     ``identity`` (enum: slow/deliberate/moderate/fast/rapid); ``motion`` has
     ``additionalProperties: false`` and no ``pace``. So the fast/slow branches
     were dead and every playbook rendered the moderate default. The fix also
     covers every enum value — previously even a correctly-placed
     ``deliberate`` / ``rapid`` would have collapsed to moderate.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.hyperframes_style_bridge import style_bridge  # noqa: E402


def _playbook(pace: str) -> dict:
    return {
        "name": "test-playbook",
        "identity": {"pace": pace},
        "typography": {
            "headings": {"font": "Montserrat", "weight": 700},
            "body": {"font": "Lora", "weight": 400},
            "code": {"font": "Fira Code"},
        },
        "motion": {"animation_style": "smooth"},
    }


def test_heading_font_read_from_plural_key():
    css, _ = style_bridge(_playbook("moderate"))
    assert css["--font-heading"] == "Montserrat"
    # body/code use their real keys and must keep working.
    assert css["--font-body"] == "Lora"
    assert css["--font-mono"] == "Fira Code"


def test_pace_read_from_identity_block():
    fast, _ = style_bridge(_playbook("fast"))
    slow, _ = style_bridge(_playbook("slow"))
    assert fast["--duration-entrance"] == "0.4s"
    assert slow["--duration-entrance"] == "0.9s"
    assert fast["--duration-entrance"] != slow["--duration-entrance"]


def test_all_enum_paces_are_distinct_and_covered():
    # Every schema enum value must map to its own motion profile — none may
    # silently collapse to the moderate default.
    durations = {
        pace: style_bridge(_playbook(pace))[0]["--duration-entrance"]
        for pace in ("slow", "deliberate", "moderate", "fast", "rapid")
    }
    assert durations["rapid"] == "0.3s"
    assert durations["fast"] == "0.4s"
    assert durations["moderate"] == "0.6s"
    assert durations["deliberate"] == "0.8s"
    assert durations["slow"] == "0.9s"
    # deliberate and rapid must not be the moderate default.
    assert durations["deliberate"] != durations["moderate"]
    assert durations["rapid"] != durations["moderate"]


def test_missing_or_unknown_pace_falls_back_to_moderate():
    for playbook in ({"identity": {}}, {"identity": {"pace": "bogus"}}, {}):
        css, _ = style_bridge(playbook)
        assert css["--duration-entrance"] == "0.6s"


def test_empty_playbook_still_renders_fallback():
    css, design_md = style_bridge(None)
    assert css["--font-heading"] == "Inter"
    assert css["--duration-entrance"] == "0.6s"
    assert "# DESIGN" in design_md
