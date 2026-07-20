"""Regression test for check_scene_variation consecutive-run counting.

The "consecutive same-size shots" check summed every equal adjacent pair across
the whole plan instead of measuring the longest actual run, so an editorially
varied plan of separate 2-shot groups (wide,wide,cu,cu,med,med) falsely tripped
a "3 consecutive same-size shots" violation.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.variation_checker import check_scene_variation  # noqa: E402


def _scenes(sizes):
    return [{"shot_language": {"shot_size": s}} for s in sizes]


def test_non_consecutive_same_size_pairs_do_not_trip_run_check():
    # Three separate 2-shot groups — longest run is 2, not 3.
    res = check_scene_variation(_scenes(["wide", "wide", "cu", "cu", "medium", "medium"]))
    assert not any("consecutive same-size" in v for v in res["violations"])


def test_true_run_of_three_is_flagged():
    res = check_scene_variation(_scenes(["wide", "wide", "wide", "cu", "medium"]))
    assert any("3 consecutive same-size" in v for v in res["violations"])


def test_unspecified_shots_do_not_form_a_run():
    res = check_scene_variation(
        _scenes(["unspecified", "unspecified", "unspecified", "unspecified"])
    )
    assert not any("consecutive same-size" in v for v in res["violations"])
