"""Regression tests for classify_from_brief motion_required derivation.

motion_required was computed from promise_type BEFORE the has_footage branch
could reclassify promise_type to SOURCE_LED, so a source-led production (e.g.
talking-head + user footage) inherited motion_required=True and then tripped
validate_cuts' motion-ratio floor against a legitimate user-footage edit.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.delivery_promise import PromiseType, classify_from_brief  # noqa: E402


def test_source_led_via_footage_is_not_motion_required():
    p = classify_from_brief("talking-head", {"has_footage": True})
    assert p.promise_type is PromiseType.SOURCE_LED
    assert p.motion_required is False


def test_explicit_motion_required_still_wins_with_footage():
    p = classify_from_brief("talking-head", {"has_footage": True, "motion_required": True})
    assert p.promise_type is PromiseType.SOURCE_LED
    assert p.motion_required is True


def test_avatar_presenter_without_footage_stays_motion_required():
    p = classify_from_brief("talking-head", {})
    assert p.promise_type is PromiseType.AVATAR_PRESENTER
    assert p.motion_required is True


def test_motion_led_pipeline_unaffected():
    p = classify_from_brief("cinematic", {})
    assert p.promise_type is PromiseType.MOTION_LED
    assert p.motion_required is True
