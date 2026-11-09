"""Sora's end of life.

OpenAI removes the Videos API and the Sora 2 aliases on 2026-09-24. These tests
pin the two things that matter: that nothing changes before that date, and that
afterwards the tool takes itself out of circulation instead of spending requests
on an endpoint that is gone.
"""

from __future__ import annotations

import datetime

import pytest

from tools.base_tool import ToolStatus
from tools.video import sora_video
from tools.video.sora_video import _API_SHUTDOWN, SoraVideo, _api_is_gone


@pytest.fixture()
def frozen(monkeypatch):
    """Pin what the module thinks today is."""

    def _freeze(when: datetime.date) -> None:
        class _Date(datetime.date):
            @classmethod
            def today(cls) -> datetime.date:
                return when

        monkeypatch.setattr(sora_video, "date", _Date)

    return _freeze


@pytest.fixture()
def with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_shutdown_date_is_the_announced_one():
    assert _API_SHUTDOWN == datetime.date(2026, 9, 24)


@pytest.mark.parametrize(
    ("day", "gone"),
    [
        (datetime.date(2026, 8, 28), False),
        (datetime.date(2026, 9, 23), False),
        (datetime.date(2026, 9, 24), True),   # removal day itself counts
        (datetime.date(2026, 9, 25), True),
        (datetime.date(2027, 1, 1), True),
    ],
)
def test_the_boundary_falls_on_the_removal_day(day, gone):
    assert _api_is_gone(day) is gone


def test_nothing_changes_while_the_api_is_alive(frozen, with_key):
    """A working provider must not be retired early — that is a regression."""
    frozen(datetime.date(2026, 9, 1))
    if not SoraVideo()._openai_sdk_supports_videos():
        pytest.skip("installed OpenAI SDK has no Videos API support")
    assert SoraVideo().get_status() is ToolStatus.AVAILABLE


def test_it_reports_unavailable_once_the_api_is_gone(frozen, with_key):
    """UNAVAILABLE, not DEGRADED.

    The registry falls back only to tools reporting AVAILABLE, so UNAVAILABLE is
    what actually stops a chain routing into the dead endpoint.
    """
    frozen(datetime.date(2026, 10, 1))
    assert SoraVideo().get_status() is ToolStatus.UNAVAILABLE


def test_it_refuses_instead_of_calling_a_dead_endpoint(frozen, with_key):
    frozen(datetime.date(2026, 10, 1))
    result = SoraVideo().execute({"prompt": "a cat"})
    assert not result.success
    assert "2026-09-24" in result.error


def test_the_refusal_names_somewhere_else_to_go(frozen, with_key):
    frozen(datetime.date(2026, 10, 1))
    error = SoraVideo().execute({"prompt": "a cat"}).error
    assert any(name in error for name in ("veo_video", "kling_video", "seedance_video"))


def test_preflight_is_warned_while_the_api_still_works(frozen):
    """The date has to reach the operator before they plan around the provider."""
    frozen(datetime.date(2026, 8, 28))
    info = SoraVideo().get_info()
    assert info["end_of_life"] == "2026-09-24"
    note = info["resource_profile_note"]
    assert "2026-09-24" in note
    assert "27 days" in note


def test_the_warning_changes_tense_after_the_date(frozen):
    frozen(datetime.date(2026, 10, 1))
    note = SoraVideo().get_info()["resource_profile_note"]
    assert "removed" in note
    assert "days from now" not in note


def test_the_deprecation_is_visible_without_running_anything():
    """not_good_for is what an agent reads when choosing a provider."""
    assert any("2026-09-24" in entry for entry in SoraVideo().not_good_for)
