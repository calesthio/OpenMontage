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


def test_author_and_render_forward_flags_only_from_cli_args(capsys):
    # Explicit tutorialctl flags become CLI flags (beat the recipe)...
    cfg = {**TC.DEFAULTS, "narration_backend": "elevenlabs", "voice_id": "VX", "base_url": ""}
    cli = dict(narration_backend="elevenlabs", voice_id="VX")
    TC.cmd_author(SimpleNamespace(name="t", manifest=None, dry_run=True, **cli), cfg)
    TC.cmd_render(_render_args(**cli), cfg)
    out = capsys.readouterr().out
    assert out.count("--narration-backend elevenlabs") == 2
    assert out.count("--voice-id VX") == 2

    # ...while config-file/env values stay out of argv (they travel as env vars).
    TC.cmd_author(SimpleNamespace(name="t", manifest=None, dry_run=True), cfg)
    TC.cmd_render(_render_args(), cfg)
    out = capsys.readouterr().out
    assert "--narration-backend" not in out and "--voice-id" not in out
    env = TC._env_for(cfg)
    assert env["TUTORIAL_NARRATION_BACKEND"] == "elevenlabs" and env["TUTORIAL_VOICE_ID"] == "VX"


def test_env_for_passes_env_file_keys_to_subprocess(tmp_path, monkeypatch):
    f = tmp_path / "other.env"
    f.write_text("ELEVENLABS_API_KEY=sk_file\nELEVENLABS_VOICE_IDS=en:V1\n")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_IDS", raising=False)
    cfg = {**TC.DEFAULTS, "env_file": str(f), "narration_backend": "elevenlabs"}
    env = TC._env_for(cfg)
    assert env["ELEVENLABS_API_KEY"] == "sk_file" and env["ELEVENLABS_VOICE_IDS"] == "en:V1"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_shell")
    assert TC._env_for(cfg)["ELEVENLABS_API_KEY"] == "sk_shell"  # shell wins


def test_common_parser_accepts_flags():
    p = TC.build_parser()
    ns = p.parse_args(["doctor", "--narration-backend", "elevenlabs", "--voice-id", "VX"])
    assert ns.narration_backend == "elevenlabs" and ns.voice_id == "VX"


def test_env_for_withholds_elevenlabs_keys_when_backend_is_ttsd(tmp_path, monkeypatch):
    f = tmp_path / "other.env"
    f.write_text("ELEVENLABS_API_KEY=sk_file\n")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    cfg = {**TC.DEFAULTS, "env_file": str(f), "narration_backend": "ttsd"}
    assert "ELEVENLABS_API_KEY" not in TC._env_for(cfg)
    # Unset backend: the recipe may still pin elevenlabs, so the key is passed.
    cfg["narration_backend"] = ""
    assert TC._env_for(cfg)["ELEVENLABS_API_KEY"] == "sk_file"
