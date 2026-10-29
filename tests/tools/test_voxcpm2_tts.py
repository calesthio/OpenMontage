"""Focused tests for the VoxCPM2 MLX local TTS tool.

No live inference, no network: mlx_audio is only imported inside the
generation subprocess. Covers the tool contract, registry discovery,
model-dir resolution (including env override and incomplete downloads),
and execute() guardrails.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.tool_registry import ToolRegistry
from tools.audio import voxcpm2_tts as voxcpm2_module
from tools.audio.voxcpm2_tts import VoxCPM2TTS


def _make_model_dir(root: Path, complete: bool = True) -> Path:
    d = root / "VoxCPM2-4bit"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}")
    (d / "model.safetensors").write_bytes(b"\x00" * 16)
    if not complete:
        (d / "model.safetensors.aria2").write_bytes(b"")
    return d


@pytest.fixture(autouse=True)
def _no_env_model_dir(monkeypatch):
    monkeypatch.delenv("VOXCPM2_MODEL_DIR", raising=False)


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    model_dir = _make_model_dir(tmp_path)
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [model_dir])
    return model_dir


# ---- Contract ----

def test_contract_fields():
    tool = VoxCPM2TTS()
    assert isinstance(tool, BaseTool)
    assert tool.capability == "tts"
    assert tool.provider == "voxcpm"
    assert tool.runtime is ToolRuntime.LOCAL
    assert tool.input_schema["required"] == ["text"]
    assert "pip:mlx-audio" in tool.dependencies


def test_registry_discovery():
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("voxcpm2_tts") is not None
    tts_tools = [t.name for t in registry.get_by_capability("tts")]
    assert "voxcpm2_tts" in tts_tools


# ---- Status / model resolution ----

def test_status_unavailable_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [tmp_path / "nowhere"])
    assert VoxCPM2TTS().get_status() is ToolStatus.UNAVAILABLE


def test_status_available_with_complete_model(fake_model):
    assert VoxCPM2TTS().get_status() is ToolStatus.AVAILABLE


def test_incomplete_download_is_unavailable(tmp_path, monkeypatch):
    model_dir = _make_model_dir(tmp_path, complete=False)
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [model_dir])
    assert VoxCPM2TTS().get_status() is ToolStatus.UNAVAILABLE


def test_env_override_resolves_model(fake_model, monkeypatch):
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [])
    monkeypatch.setenv("VOXCPM2_MODEL_DIR", str(fake_model))
    assert VoxCPM2TTS().get_status() is ToolStatus.AVAILABLE


def test_sharded_model_needs_index(tmp_path, monkeypatch):
    d = tmp_path / "VoxCPM2-bf16"
    d.mkdir()
    (d / "config.json").write_text("{}")
    (d / "model-00001-of-00002.safetensors").write_bytes(b"\x00" * 16)
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [d])
    # No model.safetensors.index.json -> treated as incomplete
    assert VoxCPM2TTS().get_status() is ToolStatus.UNAVAILABLE


# ---- Guardrails ----

def test_execute_refuses_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(voxcpm2_module, "_MODEL_DIRS", [tmp_path / "nowhere"])
    result = VoxCPM2TTS().execute({"text": "merhaba"})
    assert not result.success
    assert "not found locally" in result.error


def test_estimate_cost_is_zero():
    assert VoxCPM2TTS().estimate_cost({"text": "x"}) == 0.0
