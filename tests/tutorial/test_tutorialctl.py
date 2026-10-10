"""tutorialctl forwards narration backend/voice to the author and render CLIs."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import tutorialctl as TC  # noqa: E402


def _render_args(**over):
    base = dict(name="t", project_id=None, offline=False, music=None, capture=None,
                manifest=None, intro_seconds=None, outro_seconds=None, dry_run=True)
    base.update(over)
    return SimpleNamespace(**base)


def test_defaults_have_narration_keys():
    assert TC.DEFAULTS["narration_backend"] == "" and TC.DEFAULTS["voice_id"] == ""
    assert TC.ENV_MAP["narration_backend"] == "TUTORIAL_NARRATION_BACKEND"
    assert TC.ENV_MAP["voice_id"] == "TUTORIAL_VOICE_ID"


def test_author_and_render_forward_flags_only_when_set(capsys):
    cfg = {**TC.DEFAULTS, "narration_backend": "elevenlabs", "voice_id": "VX", "base_url": ""}
    TC.cmd_author(SimpleNamespace(name="t", manifest=None, dry_run=True), cfg)
    TC.cmd_render(_render_args(), cfg)
    out = capsys.readouterr().out
    assert out.count("--narration-backend elevenlabs") == 2
    assert out.count("--voice-id VX") == 2

    cfg = {**TC.DEFAULTS, "base_url": ""}
    TC.cmd_author(SimpleNamespace(name="t", manifest=None, dry_run=True), cfg)
    TC.cmd_render(_render_args(), cfg)
    out = capsys.readouterr().out
    assert "--narration-backend" not in out and "--voice-id" not in out


def test_common_parser_accepts_flags():
    p = TC.build_parser()
    ns = p.parse_args(["doctor", "--narration-backend", "elevenlabs", "--voice-id", "VX"])
    assert ns.narration_backend == "elevenlabs" and ns.voice_id == "VX"
