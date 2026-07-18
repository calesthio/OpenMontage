"""Tests for Remotion render debuggability in video_compose (issue #217).

Two creator-facing gaps:
  1. A failed `npx remotion render` surfaced only "returned non-zero exit
     status 1"; the useful Remotion diagnostics in stderr were dropped.
  2. There was no pass-through for Remotion's `--timeout`, so a slow headless
     browser setup failed opaquely with no way to raise the limit.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_render_failure_surfaces_remotion_stderr_tail(tool, tmp_path, monkeypatch):
    stderr = "some npm noise\nError: Delayed render timed out\nRemotion actual cause here"

    def fake_run_command(cmd, *a, **k):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, output="", stderr=stderr)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "exit 1" in result.error
    assert "Remotion actual cause here" in result.error


def test_timeout_expired_gives_actionable_message(tool, tmp_path, monkeypatch):
    def fake_run_command(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=600)

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert result.success is False
    assert "timed out" in result.error.lower()
    assert "remotion_timeout_ms" in result.error


def test_remotion_timeout_ms_is_passed_through(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None  # output file intentionally absent

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {
            "composition_data": {"cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
            "remotion_timeout_ms": 120000,
        }
    )

    assert "--timeout=120000" in seen["cmd"]
    # subprocess timeout widened past the 120s render budget so run_command
    # does not kill Remotion before its own timeout fires.
    assert seen["timeout"] >= 180


def test_high_level_render_forwards_timeout_to_remotion(tool, tmp_path, monkeypatch):
    # The gap in the first cut: execute(operation="render") -> _render() builds a
    # fresh remotion_inputs dict, so the option must be forwarded there, not only
    # on a direct _remotion_render() call.
    captured = {}
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *a, **k: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda *a, **k: True)

    def fake_remotion_render(inputs):
        captured.update(inputs)
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_remotion_render)
    monkeypatch.setattr(tool, "_run_final_review", lambda *a, **k: {})

    tool._render(
        {
            "edit_decisions": {
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "cuts": [{"id": "c1", "source": "a1", "in_seconds": 0, "out_seconds": 2}],
            },
            "asset_manifest": {"assets": [{"id": "a1", "path": "/tmp/a1.mp4"}]},
            "output_path": str(tmp_path / "out.mp4"),
            "remotion_timeout_ms": 120000,
        }
    )

    assert captured.get("remotion_timeout_ms") == 120000


def test_no_timeout_flag_when_not_requested(tool, tmp_path, monkeypatch):
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        seen["timeout"] = k.get("timeout")
        return None

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {"composition_data": {"cuts": []}, "output_path": str(tmp_path / "out.mp4")}
    )

    assert not any(str(c).startswith("--timeout") for c in seen["cmd"])
    assert seen["timeout"] == 600


# ── Composition/prop-shape mismatch: fail loud instead of a hollow render ──
#
# Confirmed live (a full paid end-to-end run, cinematic pipeline): renderer_
# family="cinematic-trailer" resolved to CinematicRenderer, but the generic
# (non-atelier) edit_decisions the edit-director skill produced only ever
# has cuts[] (Explainer's field) — CinematicRenderer reads scenes[], which
# was never populated. video_compose passed edit_decisions through as props
# verbatim with no per-composition transform, so the render "succeeded" with
# only the background/theme layer and AIGC label — no clips, no audio,
# 30 real seconds of silent black video, after ~¥28 of real generation.

def test_cinematic_renderer_without_scenes_fails_loud(tool, tmp_path, monkeypatch):
    called = {"ran": False}
    monkeypatch.setattr(tool, "run_command", lambda *a, **k: called.__setitem__("ran", True))
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "cuts": [{"id": "c1", "source": "a1", "in_seconds": 0, "out_seconds": 2}],
            },
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert result.success is False
    assert "CinematicRenderer" in result.error
    assert "scenes" in result.error
    assert "atelier" in result.error.lower()
    # Must fail before ever shelling out to npx/Remotion.
    assert called["ran"] is False


def test_talking_head_without_video_src_fails_loud(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "run_command", lambda *a, **k: pytest.fail("should not render"))
    result = tool._remotion_render(
        {
            "composition_data": {"renderer_family": "presenter", "cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert result.success is False
    assert "TalkingHead" in result.error
    assert "videoSrc" in result.error


def test_cinematic_renderer_with_scenes_present_proceeds(tool, tmp_path, monkeypatch):
    # Presence, not truthiness: an empty scenes[] still means the caller
    # intended CinematicRenderer's real shape — let it through to render
    # (and produce whatever an empty scene list actually renders as, which
    # is a separate concern from the shape-mismatch this guard targets).
    seen = {}
    monkeypatch.setattr(tool, "run_command", lambda cmd, *a, **k: seen.setdefault("cmd", cmd))
    result = tool._remotion_render(
        {
            "composition_data": {"renderer_family": "cinematic-trailer", "scenes": []},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert "cmd" in seen
    assert "CinematicRenderer" in seen["cmd"]


def test_explainer_family_unaffected_by_composition_guard(tool, tmp_path, monkeypatch):
    # The default/most common path (explainer-data -> Explainer, cuts[])
    # must be completely unaffected by this guard.
    seen = {}
    monkeypatch.setattr(tool, "run_command", lambda cmd, *a, **k: seen.setdefault("cmd", cmd))
    result = tool._remotion_render(
        {
            "composition_data": {"renderer_family": "explainer-data", "cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert "cmd" in seen
    assert "Explainer" in seen["cmd"]
