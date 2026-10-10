"""CLI-level narration wiring: argv flags, narrator adapter, pacing warning."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402


class _Client:
    def __init__(self):
        self.calls = []

    def render(self, lang, text, out_path):
        self.calls.append((lang, text, out_path))
        return 1234


def test_client_narrator_delegates(tmp_path):
    c = _Client()
    n = RT.ClientNarrator(c)
    assert n.render("en", "hi", 3, tmp_path / "step_3.wav") == 1234
    assert c.calls == [("en", "hi", str(tmp_path / "step_3.wav"))]


def test_timings_voice_mismatch_warning():
    timings = {"narration": {"backend": "elevenlabs", "voice_id": "A"}}
    assert RT.timings_voice_warning(timings, "elevenlabs", "A") is None
    msg = RT.timings_voice_warning(timings, "elevenlabs", "B")
    assert msg and "A" in msg and "B" in msg and "author_tutorial" in msg
    msg2 = RT.timings_voice_warning(timings, "ttsd", "")
    assert msg2 and "elevenlabs" in msg2 and "ttsd" in msg2
    # Old timings files (no narration block) never warn.
    assert RT.timings_voice_warning({}, "elevenlabs", "B") is None


def test_cli_accepts_backend_and_voice_flags():
    ap = RT.build_arg_parser()
    args = ap.parse_args([
        "--tutorial", "t", "--client-dir", "/c", "--project-id", "p",
        "--narration-backend", "elevenlabs", "--voice-id", "VX",
    ])
    assert args.narration_backend == "elevenlabs" and args.voice_id == "VX"
    args = ap.parse_args(["--tutorial", "t", "--client-dir", "/c", "--project-id", "p"])
    assert args.narration_backend is None and args.voice_id is None
