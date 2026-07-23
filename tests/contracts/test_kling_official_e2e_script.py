"""Contract tests for the Kling official E2E smoke script."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "kling_official_animated_explainer_e2e.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("kling_official_animated_explainer_e2e", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_status_redacts_secret_values():
    script = _load_script()

    status = script._env_status(
        {
            "KLING_API_KEY": "secret-token",
            "KLING_API_BASE_URL": "https://api-beijing.klingai.com",
            "FAL_KEY": "",
        }
    )

    assert status["KLING_API_KEY"]["present"] is True
    assert status["KLING_API_KEY"]["display"] == "<set:12 chars>"
    assert "secret-token" not in repr(status)
    assert status["KLING_API_BASE_URL"]["display"] == "https://api-beijing.klingai.com"
    assert status["FAL_KEY"]["present"] is False


def test_cli_modes_are_explicit_and_non_paid_by_default():
    script = _load_script()

    assert script._execution_mode(script._parse_args([])) == "dry_run"
    assert script._execution_mode(script._parse_args(["--live-tts"])) == "live_tts"
    assert script._execution_mode(script._parse_args(["--live-full"])) == "live_full"
    assert script._execution_mode(script._parse_args(["--live"])) == "live_full"
    assert script._execution_mode(script._parse_args(["--live-avatar"])) == "live_avatar"
    assert script._execution_mode(script._parse_args(["--live-all"])) == "live_all"


def test_video_duration_aligns_to_narration_within_kling_limits():
    script = _load_script()

    assert script._aligned_video_duration("3", 6.05) == "7"
    assert script._aligned_video_duration("10", 6.05) == "10"
    assert script._aligned_video_duration("3", None) == "3"
    assert script._aligned_video_duration("3", 30.0) == "15"


def test_live_all_combines_core_and_avatar_results(monkeypatch, tmp_path):
    script = _load_script()
    core = {
        "artifacts": {"narration": "narration.mp3", "final": "final.mp4"},
        "ffprobe": {"final": {"duration": 6.0}},
        "estimated_cost_usd": 0.25,
    }
    avatar_suite = {
        "artifacts": {"avatar": "avatar.mp4", "lip_sync": "lip.mp4"},
        "ffprobe": {"avatar": {"duration": 7.0}, "lip_sync": {"duration": 7.0}},
        "estimated_cost_usd": 0.75,
    }
    monkeypatch.setattr(script, "_run_live_full", lambda *args, **kwargs: core)
    monkeypatch.setattr(
        script, "_run_live_avatar_suite", lambda *args, **kwargs: avatar_suite
    )

    result = script._run_live_all(
        tmp_path,
        voice_id="voice-a",
        voice_language="en",
        voice_speed=1.0,
        text="hello",
        timeout_seconds=30,
        poll_interval=1.0,
        include_account_usage=False,
        video_duration="3",
    )

    assert result["core"] is core
    assert result["avatar_suite"] is avatar_suite
    assert result["artifacts"]["final"] == "final.mp4"
    assert result["artifacts"]["lip_sync"] == "lip.mp4"
    assert result["estimated_cost_usd"] == 1.0
