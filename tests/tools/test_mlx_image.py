"""Regression tests for the mlx_image provider.

Locks the contract that ``mlx_image`` is auto-discovered by ``image_selector``
with zero selector edits, advertises the full ControlNet / i2i / LoRA / faceswap
surface (the gap it fills — see docs/REVIEW-story-to-image.md §6.1 and
docs/REVIEW-image-to-video-voice.md §7), and maps inputs to the ``run.py image``
CLI correctly without spawning the runtime.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from tools.graphics.mlx_image import MLXImage, _JSON_SUMMARY_RE
from tools.base_tool import ToolStatus


# --------------------------------------------------------------------------
# Registration + capability surface
# --------------------------------------------------------------------------

def test_registers_as_image_generation_provider():
    tool = MLXImage()
    assert tool.capability == "image_generation"
    assert tool.provider == "mlx"
    assert tool.name == "mlx_image"
    assert tool.runtime.value in ("LOCAL_GPU", "local_gpu")


def test_advertises_full_control_surface():
    """The whole point of mlx_image: cover the surface no other provider does."""
    tool = MLXImage()
    for flag in ("controlnet", "img2img", "reference_image", "faceswap", "lora", "multi_lora"):
        assert tool.supports.get(flag) is True, f"mlx_image must advertise supports.{flag}"


def test_cost_is_zero():
    assert MLXImage().estimate_cost({"prompt": "x"}) == 0.0


def test_agent_skill_bridge_present():
    """The Layer-3 skill dir the orchestrator loads must be declared."""
    assert MLXImage().agent_skills == ["mlx-movie-director"]


# --------------------------------------------------------------------------
# image_selector discovers it with ZERO selector edits
# --------------------------------------------------------------------------

def test_image_selector_discovers_mlx_image():
    from tools.tool_registry import registry
    registry.ensure_discovered()
    selector = next(
        t for t in registry.get_by_capability("image_generation")
        if t.name == "image_selector"
    )
    candidates = selector._providers()
    assert any(t.name == "mlx_image" for t in candidates), (
        "mlx_image must be auto-discovered by image_selector — adding the file "
        "required no selector edit. If this fails, the discovery seam is broken."
    )


def test_mlx_image_survives_edit_mode_filter():
    """An i2i/controlnet/faceswap scene (image_path present) must keep mlx_image."""
    from tools.tool_registry import registry
    registry.ensure_discovered()
    selector = next(
        t for t in registry.get_by_capability("image_generation")
        if t.name == "image_selector"
    )
    candidates = selector._providers()
    filtered = selector._filter_candidates({"prompt": "x", "image_path": "x.png"}, candidates)
    assert any(t.name == "mlx_image" for t in filtered)


# --------------------------------------------------------------------------
# Availability gate (no subprocess — pure filesystem)
# --------------------------------------------------------------------------

def test_status_unavailable_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLX_MOVIE_DIRECTOR_DIR", raising=False)
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXImage._resolve_env()
    assert env["ok"] is False
    assert "MLX_MOVIE_DIRECTOR_DIR" in env["reason"]
    assert MLXImage().get_status() == ToolStatus.UNAVAILABLE


def test_status_unavailable_when_venv_missing(monkeypatch, tmp_path):
    """Env dir + run.py present but venv absent → UNAVAILABLE with recreate hint."""
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXImage._resolve_env()
    assert env["ok"] is False
    assert "venv" in env["reason"].lower()
    assert "uv venv" in env["reason"]


def test_status_available_with_full_env(monkeypatch, tmp_path):
    """arm64 + run.py + venv python + model subdirs → AVAILABLE."""
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
    env = MLXImage._resolve_env()
    assert env["ok"] is True, env.get("reason")
    # arm64 is required — skip the status assertion on non-Apple-Silicon CI.
    if env["arm64"]:
        assert MLXImage().get_status() == ToolStatus.AVAILABLE


# --------------------------------------------------------------------------
# Action routing + CLI argument building (no subprocess)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "inputs, expected_action",
    [
        ({"prompt": "a cat"}, "t2i"),
        ({"prompt": "edit", "image": "x.png"}, "i2i"),
        ({"prompt": "edit", "image_path": "x.png"}, "i2i"),
        ({"prompt": "pose", "image": "x.png", "controlnet_type": "pose"}, "controlnet"),
        ({"prompt": "swap", "image": "body.png", "face": "src.png"}, "faceswap"),
    ],
)
def test_action_routing(inputs, expected_action):
    action, _ = MLXImage._resolve_action(inputs)
    assert action == expected_action


def test_t2i_arg_building():
    args = MLXImage._build_args(
        {"prompt": "a cat", "width": 1024, "height": 768, "seed": 42, "pipeline": "zimage"},
        [],
    )
    assert args == ["--prompt", "a cat", "--width", "1024", "--height", "768",
                    "--seed", "42", "--pipeline", "zimage"]


def test_i2i_uses_input_image_flag():
    """run.py i2i/controlnet read --input-image, not --input."""
    args = MLXImage._build_args(
        {"prompt": "oil", "image": "a.jpg", "denoise_strength": 0.5}, []
    )
    assert "--input-image" in args and "a.jpg" in args
    assert "--input " not in " ".join(args)  # no bare --input for i2i


def test_faceswap_uses_input_and_face_flags():
    args = MLXImage._build_args(
        {"prompt": "p", "image": "body.png", "face": "src.png", "face_mode": "head"}, []
    )
    joined = " ".join(args)
    assert "--input body.png" in joined
    assert "--face src.png" in joined
    assert "--mode head" in joined


def test_lora_paths_paired_with_scales():
    args = MLXImage._build_args(
        {"prompt": "p",
         "lora_path": ["a.safetensors", "b.safetensors"],
         "lora_scale": [0.7, 0.4]},
        [],
    )
    # Each path must be immediately followed by its scale.
    assert args == ["--prompt", "p",
                    "--lora-path", "a.safetensors", "--lora-scale", "0.7",
                    "--lora-path", "b.safetensors", "--lora-scale", "0.4"]


def test_lora_scale_mismatch_rejected():
    from tools.graphics.mlx_image import _BadInput
    with pytest.raises(_BadInput):
        MLXImage._build_args(
            {"prompt": "p",
             "lora_path": ["a.safetensors", "b.safetensors"],
             "lora_scale": [0.7]},  # wrong count
            [],
        )


# --------------------------------------------------------------------------
# execute() — error paths + output parsing (subprocess mocked)
# --------------------------------------------------------------------------

def test_execute_returns_error_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLX_MOVIE_DIRECTOR_DIR", raising=False)
    result = MLXImage().execute({"prompt": "a cat"})
    assert result.success is False
    assert "MLX_MOVIE_DIRECTOR_DIR" in result.error


def test_parse_outputs_prefers_json_summary(monkeypatch, tmp_path):
    img = tmp_path / "out.png"
    img.write_bytes(b"\x89PNG")
    payload = json.dumps({"outputs": [str(img)], "status": "ok"})
    stdout = f"some log\nJSON_SUMMARY:{payload}\n"
    outs = MLXImage._parse_outputs(stdout, str(tmp_path))
    assert outs == [str(img)]


def test_parse_outputs_falls_back_to_dir_scan(tmp_path):
    """If no JSON_SUMMARY line, pick the newest image in the gen-output-dir."""
    import os, time
    older = tmp_path / "a.png"; older.write_bytes(b"x")
    newer = tmp_path / "b.png"; newer.write_bytes(b"x")
    # ensure newer mtime > older mtime
    os.utime(older, (time.time() - 10, time.time() - 10))
    outs = MLXImage._parse_outputs("", str(tmp_path))
    # Returns all images newest-first; the newest (b.png) must lead.
    assert outs and outs[0] == str(newer)
    assert str(older) in outs


def test_execute_success_path(monkeypatch, tmp_path):
    """Full execute() with the run.py subprocess mocked to emit a JSON summary."""
    # Stage a fake but complete MLX env.
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

    if not MLXImage._resolve_env()["arm64"]:
        pytest.skip("Apple-Silicon-only fixture (the gate requires arm64)")

    # The image the fake run.py "produces".
    produced = tmp_path / "generated.png"
    produced.write_bytes(b"\x89PNG")

    fake_proc = types.SimpleNamespace(
        returncode=0,
        stdout=f"JSON_SUMMARY:{json.dumps({'outputs': [str(produced)]})}\n",
        stderr="",
    )

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return fake_proc

    monkeypatch.setattr("tools.graphics.mlx_image.subprocess.run", fake_run)

    out_path = tmp_path / "final" / "result.png"
    result = MLXImage().execute({
        "prompt": "a cat", "seed": 42, "pipeline": "zimage", "output_path": str(out_path),
    })

    assert result.success is True, result.error
    assert result.data["provider"] == "mlx"
    assert result.data["model"] == "mlx-zimage"
    assert result.data["action"] == "t2i"
    assert result.data["seed"] == 42
    assert result.cost_usd == 0.0
    assert out_path.exists()  # copied to the requested output_path
    # The command invoked run.py with the image action + json-summary.
    assert "image" in captured["cmd"] and "t2i" in captured["cmd"]
    assert "--gen-output-dir" in captured["cmd"] and "--json-summary" in captured["cmd"]
    assert "--seed" in captured["cmd"]


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
    if not MLXImage._resolve_env()["arm64"]:
        pytest.skip("Apple-Silicon-only fixture")

    monkeypatch.setattr(
        "tools.graphics.mlx_image.subprocess.run",
        lambda cmd, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    result = MLXImage().execute({"prompt": "a cat"})
    assert result.success is False
    assert "run.py exited 1" in result.error
    assert "boom" in result.error
