"""Focused tests for the MOSS-TTS MLX local TTS tool.

No live inference, no network: mlx_audio is only imported inside the
generation subprocess. Covers the tool contract, registry discovery,
model + codec resolution (including env override and aria2c leftovers),
and execute() guardrails.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.tool_registry import ToolRegistry
from tools.audio import moss_tts as moss_module
from tools.audio.moss_tts import MossTTS


def _make_model_dir(root: Path, with_codec: bool = True) -> Path:
    d = root / "moss-tts-nano"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}")
    (d / "model.safetensors").write_bytes(b"\x00" * 16)
    if with_codec:
        tok = d / "audio_tokenizer"
        tok.mkdir()
        (tok / "config.json").write_text("{}")
        (tok / "model-00001-of-00001.safetensors").write_bytes(b"\x00" * 16)
    return d


@pytest.fixture(autouse=True)
def _no_env_model_dir(monkeypatch):
    monkeypatch.delenv("MOSS_TTS_MODEL_DIR", raising=False)


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    model_dir = _make_model_dir(tmp_path)
    monkeypatch.setattr(moss_module, "_MODEL_DIRS", [model_dir])
    return model_dir


# ---- Contract ----

def test_contract_fields():
    tool = MossTTS()
    assert isinstance(tool, BaseTool)
    assert tool.capability == "tts"
    assert tool.provider == "moss"
    assert tool.runtime is ToolRuntime.LOCAL
    assert tool.input_schema["required"] == ["text", "ref_audio"]
    assert "pip:mlx-audio" in tool.dependencies


def test_registry_discovery():
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("moss_tts") is not None
    tts_tools = [t.name for t in registry.get_by_capability("tts")]
    assert "moss_tts" in tts_tools


# ---- Status / model resolution ----

def test_status_unavailable_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(moss_module, "_MODEL_DIRS", [tmp_path / "nowhere"])
    assert MossTTS().get_status() is ToolStatus.UNAVAILABLE


def test_status_available_with_model_and_codec(fake_model):
    assert MossTTS().get_status() is ToolStatus.AVAILABLE


def test_missing_codec_is_unavailable(tmp_path, monkeypatch):
    model_dir = _make_model_dir(tmp_path, with_codec=False)
    monkeypatch.setattr(moss_module, "_MODEL_DIRS", [model_dir])
    assert MossTTS().get_status() is ToolStatus.UNAVAILABLE


def test_aria2_leftover_is_unavailable(fake_model):
    (fake_model / "model.safetensors.aria2").write_bytes(b"")
    assert MossTTS().get_status() is ToolStatus.UNAVAILABLE


def test_env_override_resolves_model(fake_model, monkeypatch):
    monkeypatch.setattr(moss_module, "_MODEL_DIRS", [])
    monkeypatch.setenv("MOSS_TTS_MODEL_DIR", str(fake_model))
    assert MossTTS().get_status() is ToolStatus.AVAILABLE


# ---- Guardrails ----

def test_execute_refuses_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(moss_module, "_MODEL_DIRS", [tmp_path / "nowhere"])
    result = MossTTS().execute({"text": "merhaba", "ref_audio": "/tmp/x.wav"})
    assert not result.success
    assert "not found locally" in result.error


def test_estimate_cost_is_zero():
    assert MossTTS().estimate_cost({"text": "x"}) == 0.0
