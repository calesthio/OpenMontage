"""Regression tests for the mlx_video provider.

Locks the contract that ``mlx_video`` is auto-discovered by ``video_selector``
with zero selector edits, advertises an HONEST surface (free local default —
no premium ``cinematic_quality`` / ``lip_sync`` / ``multi_shot`` flags), routes
to the right ``run.py video`` action, and parses outputs without spawning the
runtime. See docs/REVIEW-image-to-video-voice.md §7.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from tools.video.mlx_video import MLXVideo, _VIDEO_EXTS
from tools.base_tool import ToolStatus


# --------------------------------------------------------------------------
# Registration + capability surface
# --------------------------------------------------------------------------

def test_registers_as_video_generation_provider():
    tool = MLXVideo()
    assert tool.capability == "video_generation"
    assert tool.provider == "mlx"
    assert tool.name == "mlx_video"
    assert tool.runtime.value in ("LOCAL_GPU", "local_gpu")


def test_advertises_honest_surface():
    """mlx_video is a free local default — it must NOT claim premium flags."""
    tool = MLXVideo()
    for flag in ("text_to_video", "image_to_video", "reference_image", "offline", "local_gpu", "seed"):
        assert tool.supports.get(flag) is True, f"mlx_video must advertise supports.{flag}"
    # Premium cinema/audio flags belong to seedance/veo/kling — NOT to LTX-2.3 local.
    for flag in ("cinematic_quality", "lip_sync", "multi_shot", "native_audio", "dialogue_generation"):
        assert not tool.supports.get(flag), f"mlx_video must NOT advertise supports.{flag} (honest best_for)"


def test_cost_is_zero():
    assert MLXVideo().estimate_cost({"prompt": "x"}) == 0.0


def test_agent_skill_bridge_present():
    assert MLXVideo().agent_skills == ["mlx-movie-director"]


def test_fallback_does_not_include_image_selector():
    """Motion-required governance: mlx_video must never degrade to a still image."""
    assert "image_selector" not in MLXVideo().fallback_tools


# --------------------------------------------------------------------------
# video_selector discovers it with ZERO selector edits
# --------------------------------------------------------------------------

def test_video_selector_discovers_mlx_video():
    from tools.tool_registry import registry
    registry.ensure_discovered()
    selector = next(t for t in registry.get_by_capability("video_generation") if t.name == "video_selector")
    candidates = selector._providers()
    assert any(t.name == "mlx_video" for t in candidates), (
        "mlx_video must be auto-discovered by video_selector — zero selector edits. "
        "If this fails, the discovery seam is broken."
    )


def test_mlx_video_survives_i2v_filter():
    """An image_to_video request must keep mlx_video as a candidate."""
    from tools.tool_registry import registry
    registry.ensure_discovered()
    selector = next(t for t in registry.get_by_capability("video_generation") if t.name == "video_selector")
    candidates = selector._providers()
    filtered = selector._filter_candidates(
        {"prompt": "animate", "operation": "image_to_video", "reference_image": "x.png"},
        candidates,
    )
    assert any(t.name == "mlx_video" for t in filtered)


# --------------------------------------------------------------------------
# Availability gate (mirrors mlx_image — pure filesystem)
# --------------------------------------------------------------------------

def test_status_unavailable_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLX_MOVIE_DIRECTOR_DIR", raising=False)
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXVideo._resolve_env()
    assert env["ok"] is False
    assert "MLX_MOVIE_DIRECTOR_DIR" in env["reason"]
    assert MLXVideo().get_status() == ToolStatus.UNAVAILABLE


def test_status_unavailable_when_venv_missing(monkeypatch, tmp_path):
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXVideo._resolve_env()
    assert env["ok"] is False
    assert "venv" in env["reason"].lower() and "uv venv" in env["reason"]


def test_status_available_with_full_env(monkeypatch, tmp_path):
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    for sub in ("transformer", "vae"):
        (mlx_dir / "mlx-models" / sub).mkdir(parents=True)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    # Mock Apple Silicon so the full available-path (incl. the arch guard in
    # resolve_mlx_env) runs on ANY CI host, not just native arm64 reviewers.
    monkeypatch.setattr("tools._mlx.env.platform.machine", lambda: "arm64")
    env = MLXVideo._resolve_env()
    assert env["ok"] is True, env.get("reason")
    assert env["arm64"] is True
    assert MLXVideo().get_status() == ToolStatus.AVAILABLE


# --------------------------------------------------------------------------
# Action routing + CLI argument building (no subprocess)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "inputs, expected_action, expected_mode",
    [
        ({"prompt": "a dog running"}, "t2i2v", "t2v"),                  # prompt-only → rich 3-stage
        ({"prompt": "animate", "image_path": "x.png"}, "generate", "i2v"),  # image present → I2V
        ({"prompt": "animate", "reference_image": "x.png"}, "generate", "i2v"),
        ({"prompt": "x", "action": "generate"}, "generate", "t2v"),     # explicit generate, no image → T2V
        ({"prompt": "x", "action": "t2i2v"}, "t2i2v", "t2v"),           # explicit t2i2v
    ],
)
def test_action_routing(inputs, expected_action, expected_mode):
    action = MLXVideo._resolve_action(inputs)
    assert action == expected_action
    mode = "i2v" if MLXVideo._has_reference_image(inputs) else "t2v"
    assert mode == expected_mode


def test_t2v_arg_building():
    args = MLXVideo._build_args({"prompt": "a dog", "num_frames": 49, "seed": 7, "fps": 24.0}, "generate")
    # _build_args emits in a fixed field order (frames → fps → seed), not call order.
    assert args == ["--prompt", "a dog", "--frames", "49", "--fps", "24.0", "--seed", "7"]


def test_i2v_passes_input_image():
    args = MLXVideo._build_args(
        {"prompt": "animate", "image_path": "still.png", "num_frames": 41}, "generate"
    )
    joined = " ".join(args)
    assert "--input-image still.png" in joined
    assert "--frames 41" in joined


def test_t2i2v_with_optional_input_image():
    """t2i2v may animate a specific still; otherwise generates the keyframe first."""
    args_no_img = MLXVideo._build_args({"prompt": "a scene"}, "t2i2v")
    assert "--input-image" not in args_no_img
    args_with_img = MLXVideo._build_args({"prompt": "a scene", "reference_image": "k.png"}, "t2i2v")
    assert "--input-image k.png" in " ".join(args_with_img)


def test_cfg_and_transformer_passed_through():
    args = MLXVideo._build_args(
        {"prompt": "x", "cfg_scale": 3.0, "transformer": "dasiwa", "stage1_steps": 30}, "t2i2v"
    )
    joined = " ".join(args)
    assert "--cfg-scale 3.0" in joined
    assert "--transformer dasiwa" in joined
    assert "--stage1-steps 30" in joined


# --------------------------------------------------------------------------
# Output parsing
# --------------------------------------------------------------------------

def test_parse_outputs_prefers_json_summary(tmp_path):
    clip = tmp_path / "out.mp4"
    clip.write_bytes(b"\x00\x00\x00")  # not a real mp4; existence is all _parse_outputs checks
    payload = json.dumps({"outputs": [str(clip)], "status": "ok"})
    outs = MLXVideo._parse_outputs(f"JSON_SUMMARY:{payload}\n", str(tmp_path))
    assert outs == [str(clip)]


def test_parse_outputs_falls_back_to_dir_scan(tmp_path):
    """No JSON_SUMMARY → newest video file in the gen-output-dir."""
    import os, time
    older = tmp_path / "a.mp4"; older.write_bytes(b"x")
    newer = tmp_path / "b.mp4"; newer.write_bytes(b"x")
    os.utime(older, (time.time() - 10, time.time() - 10))
    outs = MLXVideo._parse_outputs("", str(tmp_path))
    assert outs and outs[0] == str(newer)


def test_video_output_extensions_covered():
    exts = " ".join(_VIDEO_EXTS)
    for e in ("mp4", "mov", "webm", "gif"):
        assert e in exts


# --------------------------------------------------------------------------
# execute() — error path + mocked success (no real run.py spawn)
# --------------------------------------------------------------------------

def test_execute_returns_error_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLX_MOVIE_DIRECTOR_DIR", raising=False)
    result = MLXVideo().execute({"prompt": "a dog"})
    assert result.success is False
    assert "MLX_MOVIE_DIRECTOR_DIR" in result.error


def test_execute_success_path(monkeypatch, tmp_path):
    mlx_dir = tmp_path / "mlx_repo"
    run_py = mlx_dir / "python" / "mlx-movie-director" / "run.py"
    run_py.parent.mkdir(parents=True)
    run_py.write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    (mlx_dir / "mlx-models" / "transformer").mkdir(parents=True)
    (mlx_dir / "mlx-models" / "vae").mkdir(parents=True)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    if not MLXVideo._resolve_env()["arm64"]:
        pytest.skip("Apple-Silicon-only fixture")

    produced = tmp_path / "clip.mp4"
    produced.write_bytes(b"\x00\x00\x00")
    fake_proc = types.SimpleNamespace(
        returncode=0,
        stdout=f"JSON_SUMMARY:{json.dumps({'outputs': [str(produced)]})}\n",
        stderr="",
    )
    captured: dict = {}
    monkeypatch.setattr("tools.video.mlx_video.subprocess.run", lambda cmd, **k: (captured.__setitem__("cmd", cmd), fake_proc)[1])

    out_path = tmp_path / "final" / "result.mp4"
    result = MLXVideo().execute({
        "prompt": "a dog running", "seed": 7, "num_frames": 49,
        "image_path": "still.png", "output_path": str(out_path),
    })
    assert result.success is True, result.error
    assert result.data["provider"] == "mlx"
    assert result.data["action"] == "generate"  # image present → generate (I2V)
    assert result.data["mode"] == "i2v"
    assert result.data["seed"] == 7
    assert result.cost_usd == 0.0
    assert out_path.exists()
    cmd = captured["cmd"]
    assert "video" in cmd and "generate" in cmd
    assert "--gen-output-dir" in cmd
    # --json-summary is intentionally NOT passed (video subparser doesn't register it).
    assert "--json-summary" not in cmd
    assert "--input-image" in cmd


def test_execute_nonzero_exit_returns_failure(monkeypatch, tmp_path):
    mlx_dir = tmp_path / "mlx_repo"
    run_py = mlx_dir / "python" / "mlx-movie-director" / "run.py"
    run_py.parent.mkdir(parents=True)
    run_py.write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    (mlx_dir / "mlx-models" / "transformer").mkdir(parents=True)
    (mlx_dir / "mlx-models" / "vae").mkdir(parents=True)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    if not MLXVideo._resolve_env()["arm64"]:
        pytest.skip("Apple-Silicon-only fixture")
    monkeypatch.setattr(
        "tools.video.mlx_video.subprocess.run",
        lambda cmd, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="gpu oom"),
    )
    result = MLXVideo().execute({"prompt": "a dog"})
    assert result.success is False
    assert "run.py exited 1" in result.error and "gpu oom" in result.error
