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
    # Old timings files (no narration block) were authored by ttsd: warn when
    # the render now uses another backend, stay quiet for ttsd.
    assert RT.timings_voice_warning({}, "ttsd", "") is None
    legacy = RT.timings_voice_warning({}, "elevenlabs", "B")
    assert legacy and "ttsd" in legacy and "elevenlabs" in legacy


def test_cli_accepts_backend_and_voice_flags():
    ap = RT.build_arg_parser()
    args = ap.parse_args([
        "--tutorial", "t", "--client-dir", "/c", "--project-id", "p",
        "--narration-backend", "elevenlabs", "--voice-id", "VX",
    ])
    assert args.narration_backend == "elevenlabs" and args.voice_id == "VX"
    args = ap.parse_args(["--tutorial", "t", "--client-dir", "/c", "--project-id", "p"])
    assert args.narration_backend is None and args.voice_id is None


def _temp_client(tmp_path):
    import json
    d = tmp_path / "cypress" / "e2e-tutorials" / "s"
    d.mkdir(parents=True)
    (d / "tour.tutorial.cy.js").write_text("")
    (d / "tour.tutorial.json").write_text(json.dumps({"title": "Tour", "lang": "de"}))
    return tmp_path


def test_main_fails_before_capture_when_narration_not_ready(tmp_path, monkeypatch, capsys):
    """ElevenLabs config problems must surface before the 5-20 minute Cypress capture."""
    client = _temp_client(tmp_path)
    monkeypatch.setattr(RT.bridge, "run_tutorial_spec",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("capture ran")))
    monkeypatch.setattr(RT, "init_project",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("project created")))
    monkeypatch.setattr(RT, "parse_env_file", lambda path: {})
    # Key present, but no voice for the recipe lang (de) and no override.
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_IDS", "en:V1")
    monkeypatch.delenv("TUTORIAL_VOICE_ID", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "render_tutorial.py", "--tutorial", "tour", "--client-dir", str(client),
        "--project-id", "p", "--base-url", "https://d.example.com",
        "--narration-backend", "elevenlabs",
    ])
    assert RT.main() == 2
    err = capsys.readouterr().err
    assert "'de'" in err and "en" in err  # names the missing lang and the configured ones


def test_main_recipe_pinned_backend_is_checked_before_capture(tmp_path, monkeypatch, capsys):
    import json
    client = _temp_client(tmp_path)
    recipe = client / "cypress" / "e2e-tutorials" / "s" / "tour.tutorial.json"
    recipe.write_text(json.dumps({"title": "Tour", "lang": "en", "narration_backend": "elevenlabs"}))
    monkeypatch.setattr(RT.bridge, "run_tutorial_spec",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("capture ran")))
    monkeypatch.setattr(RT, "parse_env_file", lambda path: {})
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "render_tutorial.py", "--tutorial", "tour", "--client-dir", str(client),
        "--project-id", "p", "--base-url", "https://d.example.com",
    ])
    assert RT.main() == 2
    assert "ELEVENLABS_API_KEY" in capsys.readouterr().err
