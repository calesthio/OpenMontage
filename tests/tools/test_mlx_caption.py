"""Regression tests for the mlx_caption provider.

Locks the contract that ``mlx_caption`` is the analysis-tier analog of
``mlx_image`` / ``mlx_video`` — the local-VLM (LM Studio) understanding path —
and that it maps inputs to the ``run.py caption`` CLI correctly without spawning
the runtime or requiring LM Studio to be up.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.analysis.mlx_caption import MLXCaption, _BadInput
from tools.base_tool import ToolStatus


# --------------------------------------------------------------------------
# Registration + capability surface
# --------------------------------------------------------------------------

def test_registers_as_analysis_provider():
    tool = MLXCaption()
    assert tool.capability == "analysis"
    assert tool.provider == "mlx"
    assert tool.name == "mlx_caption"
    assert tool.tier.value == "analyze"
    assert tool.runtime.value in ("LOCAL_GPU", "local_gpu")


def test_advertises_vision_surface():
    """The point of mlx_caption: local LM-Studio vision understanding."""
    tool = MLXCaption()
    for flag in ("vision", "image_understanding", "video_understanding", "offline", "local"):
        assert tool.supports.get(flag) is True, f"mlx_caption must advertise supports.{flag}"


def test_cost_is_zero():
    assert MLXCaption().estimate_cost({"image": "x.png"}) == 0.0


def test_agent_skill_bridge_present():
    assert MLXCaption().agent_skills == ["mlx-movie-director"]


def test_fallback_targets_analysis_peers():
    """When MLX/LM Studio is down, fall back to other local/cloud vision tools."""
    fallbacks = {MLXCaption().fallback, *MLXCaption().fallback_tools}
    assert "video_understand" in fallbacks


# --------------------------------------------------------------------------
# Availability gate (no subprocess — pure filesystem + socket probe)
# --------------------------------------------------------------------------

def test_status_unavailable_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLX_MOVIE_DIRECTOR_DIR", raising=False)
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXCaption._resolve_env()
    assert env["ok"] is False
    assert "MLX_MOVIE_DIRECTOR_DIR" in env["reason"]
    assert MLXCaption().get_status() == ToolStatus.UNAVAILABLE


def test_status_unavailable_when_venv_missing(monkeypatch, tmp_path):
    """Env dir + run.py present but venv absent → UNAVAILABLE with recreate hint."""
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    env = MLXCaption._resolve_env()
    assert env["ok"] is False
    assert "venv" in env["reason"].lower()
    assert "uv venv" in env["reason"]


def test_status_unavailable_when_lm_studio_down(monkeypatch, tmp_path):
    """Full MLX env but LM Studio not reachable → UNAVAILABLE with LM Studio hint.

    mlx_caption does NOT require the mlx-models generation stack (need_models=False)
    — the gate is MLX runtime + LM Studio, not model files.
    """
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    # Force the socket probe to fail without touching the network.
    monkeypatch.setattr("tools._mlx.env.lm_studio_reachable", lambda **_: False)
    env = MLXCaption._resolve_env()
    assert env["ok"] is False
    assert "LM Studio" in env["reason"]
    assert MLXCaption().get_status() == ToolStatus.UNAVAILABLE


def test_status_available_with_full_env_and_lm_studio(monkeypatch, tmp_path):
    """MLX runtime + LM Studio reachable → AVAILABLE (no model-dir requirement)."""
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    monkeypatch.setattr("tools._mlx.env.lm_studio_reachable", lambda **_: True)
    # NOTE: no mlx-models/transformer+vae staged — caption must NOT require them.
    env = MLXCaption._resolve_env()
    assert env["ok"] is True, env.get("reason")


def test_caption_does_not_require_generation_models(monkeypatch, tmp_path):
    """need_models=False: an env that would FAIL mlx_image (no models) is fine here."""
    mlx_dir = tmp_path / "mlx_repo"
    (mlx_dir / "python" / "mlx-movie-director").mkdir(parents=True)
    (mlx_dir / "python" / "mlx-movie-director" / "run.py").write_text("# stub")
    venv_py = mlx_dir / "python" / "venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\nexit 0\n")
    venv_py.chmod(0o755)
    monkeypatch.setenv("MLX_MOVIE_DIRECTOR_DIR", str(mlx_dir))
    monkeypatch.delenv("MLX_VENV_PYTHON", raising=False)
    monkeypatch.setattr("tools._mlx.env.lm_studio_reachable", lambda **_: True)
    # mlx_image would be UNAVAILABLE (no transformer/vae staged); caption is fine.
    from tools.graphics.mlx_image import MLXImage
    assert MLXImage._resolve_env()["ok"] is False
    assert MLXCaption._resolve_env()["ok"] is True


# --------------------------------------------------------------------------
# CLI argument building (no subprocess)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "inputs, expected_flags",
    [
        ({}, ["--style", "photography", "--lang", "en"]),
        ({"style": "score"}, ["--style", "score", "--lang", "en"]),
        ({"style": ["photography", "t2i"]}, ["--style", "photography", "t2i", "--lang", "en"]),
        ({"lang": "zh_TW"}, ["--style", "photography", "--lang", "zh_TW"]),
        (
            {"style": "video_analysis", "lang": "en", "model": "qwen3-vl-4b"},
            ["--style", "video_analysis", "--lang", "en", "--model", "qwen3-vl-4b"],
        ),
        (
            {"style": "score", "api_url": "http://host:8080/v1"},
            ["--style", "score", "--lang", "en", "--api-url", "http://host:8080/v1"],
        ),
    ],
)
def test_build_args(inputs, expected_flags):
    assert MLXCaption._build_args(inputs) == expected_flags


def test_build_args_rejects_non_string_style():
    with pytest.raises(_BadInput):
        MLXCaption._build_args({"style": 123})


# --------------------------------------------------------------------------
# Output parsing (no subprocess)
# --------------------------------------------------------------------------

def test_parse_output_styles_map_shape():
    """run.py writes {styles: {<style>: <text>}}; we surface the map + joined text."""
    payload = {"styles": {"photography": "cinematic, warm light", "score": 8.5}}
    tmp = Path(_write_tmp(payload))
    styles_map, text = MLXCaption._parse_output(str(tmp))
    tmp.unlink()
    assert styles_map["photography"] == "cinematic, warm light"
    assert styles_map["score"] == 8.5
    assert text == "cinematic, warm light"  # numeric-score style excluded from text join


def test_parse_output_flat_legacy_shape():
    """Older caption files may be a flat {<style>: <text>} dict."""
    tmp = Path(_write_tmp({"t2i": "a red cube on a table"}))
    styles_map, text = MLXCaption._parse_output(str(tmp))
    tmp.unlink()
    assert styles_map == {"t2i": "a red cube on a table"}
    assert text == "a red cube on a table"


def test_parse_output_dict_value_with_text_field():
    payload = {"styles": {"review": {"text": "good composition", "score": 9}}}
    tmp = Path(_write_tmp(payload))
    styles_map, text = MLXCaption._parse_output(str(tmp))
    tmp.unlink()
    assert text == "good composition"


def test_parse_output_missing_file_returns_empty(tmp_path):
    styles_map, text = MLXCaption._parse_output(str(tmp_path / "nope.json"))
    assert styles_map == {} and text == ""


def _write_tmp(payload: dict) -> str:
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(payload, fh)
    return path
