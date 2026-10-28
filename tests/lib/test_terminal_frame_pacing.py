"""Narration pacing must follow the actual TerminalScene frame cursor."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.verify_scene_pacing import step_duration, trace, assert_alignment


@pytest.mark.parametrize("fps", [24, 25, 30, 60])
def test_fractional_holds_are_rounded_to_frames(fps):
    step = {"kind": "out", "text": "ready", "holdSeconds": 0.15}
    assert step_duration(step, fps) == (max(2, math.ceil(0.08 * fps)) + math.ceil(0.15 * fps)) / fps


def test_fractional_pause_is_a_whole_frame():
    assert step_duration({"kind": "pause", "seconds": 0.01}, 30) == 1 / 30


def test_astral_command_uses_javascript_string_length():
    # JS text.length counts UTF-16 units: this command has 3, not 2.
    assert step_duration({"kind": "cmd", "text": "🌍!", "typeSpeed": 1, "holdSeconds": 0}, 30) == 3


def test_many_output_lines_do_not_accumulate_false_narration_alignment():
    steps = [{"kind": "out", "text": str(i)} for i in range(90)]
    # TerminalScene advances 8 frames per output at 30fps: final line at 712/30.
    assert trace(steps, quiet=True)[-1].video_time == 23.73
    assert_alignment(steps, 0, 24, [(712 / 30, "last line")], tolerance=0.05)


def test_trace_matches_the_actual_terminal_scene_cursor():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable; pure Python frame regressions still run")
    source = (Path(__file__).parents[2] / "remotion-composer/src/components/TerminalScene.tsx").read_text()
    layout = source.split("// Lay out timing in frames", 1)[1].split("// Only render lines", 1)[0]
    layout = layout.replace(": RenderedLine[]", "").replace(": RenderedPill[]", "")
    steps = [
        {"kind": "cmd", "text": "🌍!", "typeSpeed": 0.035, "holdSeconds": 0.013},
        {"kind": "out", "text": "done", "holdSeconds": 0.15},
        {"kind": "pause", "seconds": 0.011},
        {"kind": "pill", "text": "ready"},
    ]
    # Execute the production cursor loop, including its ceil and JS text.length.
    script = "const steps=" + json.dumps(steps) + "; const fps=30; const accentColor='blue';" + layout + "console.log(JSON.stringify({lines,pills,cursorFrame}));"
    rendered = json.loads(subprocess.check_output([node, "-e", script], text=True))
    actual_starts = [line["startFrame"] for line in rendered["lines"]] + [rendered["pills"][0]["startFrame"]]
    assert [lm.video_time for lm in trace(steps, quiet=True)] == [round(frame / 30, 2) for frame in actual_starts]
    assert sum(step_duration(step, 30) for step in steps) == pytest.approx(rendered["cursorFrame"] / 30)
