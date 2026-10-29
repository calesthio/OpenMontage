"""Real-tooling verification for the factory (Master Plan P0.4 / P0.5).

These tests prove — with artifacts, not ``get_status()`` claims — what the
machine can actually do at $0:

- the diagram renderer really writes a file;
- a stock search that finds nothing is reported differently from one that
  could not run;
- the strict zero-cost gate really blocks a paid route;
- TTS availability is reported honestly instead of being assumed.

Network access is blocked by ``tests/conftest.py``; every external behaviour
here is produced by fakes or by local binaries.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from lib.zero_cost_gate import (
    NO_RESULTS,
    ToolFacts,
    classify_failure,
    classify_search_record,
    evaluate_call,
    facts_from_registry,
    search_stats_summary,
)
from tools.tool_registry import registry


@pytest.fixture(scope="module")
def discovered() -> None:
    registry.discover()


def _status(tool_name: str) -> str:
    tool = registry._tools.get(tool_name)
    if tool is None:
        return "missing"
    return str(tool.get_info().get("status"))


# --- diagrams --------------------------------------------------------------


def test_diagram_renderer_really_writes_an_image(tmp_path: Path, discovered) -> None:
    """Master Plan section 7: verify the renderer with an artifact, not a status."""

    from tools.graphics.diagram_gen import DiagramGen

    out = tmp_path / "margin_stack.png"
    result = DiagramGen().execute(
        {
            "diagram_type": "boxes",
            "title": "Where a laundry dollar goes",
            "boxes": [
                {"label": "Route revenue"},
                {"label": "Water"},
                {"label": "Chemicals"},
                {"label": "Labour"},
            ],
            "connections": [{"from": 0, "to": 1}, {"from": 0, "to": 2}, {"from": 0, "to": 3}],
            "output_path": str(out),
        }
    )
    assert result.success, result.error
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_mermaid_cli_presence_is_reported_honestly(discovered) -> None:
    """Mermaid rendering needs the mmdc CLI; without it the Pillow path runs."""

    from tools.graphics.diagram_gen import DiagramGen

    tool = DiagramGen()
    has_mmdc = shutil.which("mmdc") is not None
    assert tool.get_status().value in {"available", "unavailable"}
    if not has_mmdc:
        # The tool must still be usable through the Pillow fallback.
        assert tool._has_pillow() is True


# --- stock search error taxonomy ------------------------------------------


def test_no_results_is_not_an_error() -> None:
    searched = [("archive_org", "industrial laundry conveyor")]
    stats = search_stats_summary(searched, [])
    assert stats["per_class"] == {NO_RESULTS: 1}
    assert stats["error_count"] == 0


def test_a_transport_failure_is_classified_not_hidden() -> None:
    records = [
        {
            "phase": "search",
            "source": "wikimedia",
            "query": "industrial laundry conveyor",
            "error": "ConnectionError: connection reset by peer",
        }
    ]
    stats = search_stats_summary([("wikimedia", "industrial laundry conveyor")], records)
    assert stats["per_class"]["transport_error"] == 1
    assert stats["no_results_count"] == 0


def test_an_auth_failure_is_classified_as_auth() -> None:
    records = [
        {
            "phase": "search",
            "source": "pexels",
            "query": "laundry plant",
            "error": "HTTPError: 401 Client Error: Unauthorized",
        }
    ]
    assert classify_search_record(records[0]) == "auth_error"
    stats = search_stats_summary([("pexels", "laundry plant")], records)
    assert stats["per_class"]["auth_error"] == 1


def test_post_search_phases_can_carry_their_own_class() -> None:
    assert classify_search_record({"class": "license_rejected"}) == "license_rejected"
    assert classify_search_record({"class": "invalid_media"}) == "invalid_media"
    assert classify_search_record({"class": "download_error"}) == "download_error"


def test_mixed_search_log_keeps_every_class_distinct() -> None:
    searched = [
        ("archive_org", "a"),
        ("wikimedia", "b"),
        ("pexels", "c"),
        ("pixabay_video", "d"),
    ]
    records = [
        {"source": "wikimedia", "query": "b", "error": "HTTPError: 429 Too Many Requests"},
        {"source": "pexels", "query": "c", "error": "HTTPError: 401 Unauthorized"},
        {"source": "pixabay_video", "query": "d", "class": "license_rejected"},
    ]
    stats = search_stats_summary(searched, records)
    assert stats["per_class"] == {
        NO_RESULTS: 1,
        "rate_limited": 1,
        "auth_error": 1,
        "license_rejected": 1,
    }
    assert stats["attempted"] == 4


# --- zero-cost gate on real registry tools ---------------------------------


def test_a_local_zero_cost_render_route_is_allowed(discovered) -> None:
    decision = evaluate_call(
        facts_from_registry("video_compose", "render", cost_usd=0.0, route="ffmpeg")
    )
    assert decision.allowed, decision.reason


def test_an_unpriced_cloud_tts_route_is_blocked(discovered) -> None:
    decision = evaluate_call(facts_from_registry("elevenlabs_tts", "synthesize"))
    assert decision.blocked
    # Either the provider is unconfigured (surface it as a setup request) or
    # its pricing is unknown (block, never assume free). Both are stops.
    assert (
        "cost_usd is null" in decision.reason
        or "status is" in decision.reason
    ), decision.reason


def test_a_billed_search_route_is_blocked_without_approval(discovered) -> None:
    decision = evaluate_call(
        ToolFacts(
            tool="direct_clip_search",
            operation="search",
            runtime="api",
            route="https://api.example.com/search",
            cost_usd=0.01,
        )
    )
    assert decision.blocked
    assert "strict zero-cost" in decision.reason


# --- honest capability reporting ------------------------------------------


def test_ffmpeg_presence_matches_the_registry_status(discovered) -> None:
    """The registry must not claim a capability the machine cannot deliver."""

    has_ffmpeg = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    status = _status("video_compose")
    if has_ffmpeg:
        assert status == "available", "ffmpeg is installed but video_compose is not available"
    else:
        assert status == "unavailable", (
            "video_compose reports available without ffmpeg on PATH"
        )


def test_tts_availability_is_reported_not_assumed(discovered) -> None:
    """The narration stage fails closed when no synthesizer is installed.

    This asserts the *policy*: whatever the environment, the gate refuses an
    unpriced narration call, so the stage cannot pretend to have audio.
    """

    assert _status("piper_tts") in {"available", "unavailable", "missing"}
    decision = evaluate_call(facts_from_registry("piper_tts", "synthesize"))
    assert decision.blocked


def test_required_factory_tools_are_the_local_zero_cost_ones(discovered) -> None:
    from lib.pipeline_loader import load_pipeline

    manifest = load_pipeline("business-documentary")
    required: set[str] = set()
    for stage in manifest["stages"]:
        required.update(stage.get("required_tools") or [])
    for name in required:
        info = registry._tools[name].get_info()
        assert info.get("status") == "available", f"{name} must be available"
        assert str(info.get("runtime")).lower() in {"local", "hybrid"}
        assert classify_failure(200, "ok") == "unknown_failure"  # sanity: taxonomy wired
