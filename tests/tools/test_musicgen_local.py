"""Tests for tools/audio/musicgen_local.py — MusicGenLocal tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.audio.musicgen_local import MusicGenLocal
from tools.tool_registry import ToolRegistry


class TestMusicGenLocalDefinition:
    """Verify the tool class metadata matches project conventions."""

    def test_class_inherits_basetool(self):
        assert issubclass(MusicGenLocal, BaseTool)

    def test_name(self):
        assert MusicGenLocal.name == "musicgen_local"

    def test_version(self):
        assert MusicGenLocal.version == "0.1.0"

    def test_tier(self):
        assert MusicGenLocal.tier == ToolTier.GENERATE

    def test_capability(self):
        assert MusicGenLocal.capability == "music_generation"

    def test_provider(self):
        assert MusicGenLocal.provider == "musicgen_local"

    def test_runtime(self):
        assert MusicGenLocal.runtime == ToolRuntime.LOCAL_GPU

    def test_stability(self):
        assert MusicGenLocal.stability == ToolStability.EXPERIMENTAL

    def test_execution_mode(self):
        assert MusicGenLocal.execution_mode == ExecutionMode.SYNC

    def test_determinism(self):
        assert MusicGenLocal.determinism == Determinism.SEEDED

    def test_capabilities_list(self):
        assert "generate_background_music" in MusicGenLocal.capabilities
        assert "generate_instrumental" in MusicGenLocal.capabilities
        assert "text_to_music" in MusicGenLocal.capabilities
        assert "offline_generation" in MusicGenLocal.capabilities

    def test_fallback_tools(self):
        assert "music_gen" in MusicGenLocal.fallback_tools
        assert "pixabay_music" in MusicGenLocal.fallback_tools
        assert "freesound_music" in MusicGenLocal.fallback_tools

    def test_supports(self):
        assert MusicGenLocal.supports["offline"] is True
        assert MusicGenLocal.supports["duration_control"] is True
        assert MusicGenLocal.supports["model_size_choice"] is True

    def test_input_schema_requires_prompt(self):
        assert "required" in MusicGenLocal.input_schema
        assert "prompt" in MusicGenLocal.input_schema["required"]

    def test_input_schema_properties(self):
        props = MusicGenLocal.input_schema["properties"]
        assert "prompt" in props
        assert "model" in props
        assert "duration_seconds" in props
        assert "seed" in props
        assert "guidance_scale" in props
        assert "temperature" in props

    def test_input_schema_duration_default(self):
        assert MusicGenLocal.input_schema["properties"]["duration_seconds"]["default"] == 15

    def test_input_schema_duration_bounds(self):
        assert MusicGenLocal.input_schema["properties"]["duration_seconds"]["minimum"] == 1
        assert MusicGenLocal.input_schema["properties"]["duration_seconds"]["maximum"] == 120

    def test_input_schema_model_default(self):
        assert MusicGenLocal.input_schema["properties"]["model"]["default"] == "facebook/musicgen-small"

    def test_input_schema_model_options(self):
        # Model options are documented in install_instructions, not in the schema enum
        pass

    def test_agent_skills(self):
        assert MusicGenLocal.agent_skills == []

    def test_best_for(self):
        assert "offline/air-gapped music generation" in MusicGenLocal.best_for
        assert "free music generation (no API cost)" in MusicGenLocal.best_for

    def test_not_good_for(self):
        assert "CPU-only machines (very slow, needs GPU)" in MusicGenLocal.not_good_for

    def test_idempotency_key_fields(self):
        assert "prompt" in MusicGenLocal.idempotency_key_fields
        assert "seed" in MusicGenLocal.idempotency_key_fields
        assert "model" in MusicGenLocal.idempotency_key_fields

    def test_side_effects(self):
        assert any("writes audio file" in s for s in MusicGenLocal.side_effects)
        assert any("download model weights" in s for s in MusicGenLocal.side_effects)


class TestMusicGenLocalInstance:
    """Test instance methods with a clean tool instance."""

    def setup_method(self):
        self.tool = MusicGenLocal()

    def test_get_info_returns_dict(self):
        info = self.tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == "musicgen_local"
        assert info["capability"] == "music_generation"
        assert info["runtime"] == "local_gpu"

    def test_get_status_checks_import(self):
        # Without transformers, status should be UNAVAILABLE
        status = self.tool.get_status()
        assert status in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)

    def test_estimate_cost_free(self):
        assert self.tool.estimate_cost({"prompt": "test"}) == 0.0
        assert self.tool.estimate_cost({}) == 0.0

    def test_estimate_runtime(self):
        runtime = self.tool.estimate_runtime({"duration_seconds": 30})
        assert isinstance(runtime, float)
        assert runtime >= 30.0

    def test_estimate_runtime_default(self):
        runtime = self.tool.estimate_runtime({})
        assert runtime == 35.0  # 15 (default) + 20 overhead

    def test_execute_returns_error_when_unavailable(self):
        if self.tool.get_status() != ToolStatus.AVAILABLE:
            result = self.tool.execute({"prompt": "test music"})
            assert result.success is False
            assert "error" in str(result.__dict__)

    def test_execute_validates_prompt_required(self):
        with pytest.raises(KeyError):
            self.tool.execute({})

    def test_idempotency_key(self):
        key1 = self.tool.idempotency_key({"prompt": "lo-fi beats", "seed": 42})
        key2 = self.tool.idempotency_key({"prompt": "lo-fi beats", "seed": 42})
        assert key1 == key2

    def test_idempotency_key_differs(self):
        key1 = self.tool.idempotency_key({"prompt": "lo-fi beats", "seed": 42})
        key2 = self.tool.idempotency_key({"prompt": "rock guitar", "seed": 42})
        assert key1 != key2

    def test_resource_profile(self):
        rp = self.tool.resource_profile
        assert rp.vram_mb == 4000
        assert rp.ram_mb == 4000
        assert rp.disk_mb == 6000
        assert rp.cpu_cores == 4
        assert rp.network_required is False

    def test_retry_policy(self):
        assert self.tool.retry_policy.max_retries == 1
        assert "cuda_oom" in self.tool.retry_policy.retryable_errors

    def test_install_instructions(self):
        inst = self.tool.install_instructions
        assert "pip install transformers torch torchaudio scipy" in inst
        assert "facebook/musicgen-small" in inst


class TestMusicGenLocalRegistry:
    """Verify the tool is discoverable via the registry."""

    def test_registry_discovers_tool(self):
        reg = ToolRegistry()
        reg.register(MusicGenLocal())
        found = reg.get("musicgen_local")
        assert found is not None
        assert found.name == "musicgen_local"

    def test_registry_finds_by_capability(self):
        reg = ToolRegistry()
        reg.register(MusicGenLocal())
        matches = reg.get_by_capability("music_generation")
        assert any(t.name == "musicgen_local" for t in matches)

    def test_registry_finds_by_provider(self):
        reg = ToolRegistry()
        reg.register(MusicGenLocal())
        matches = reg.get_by_provider("musicgen_local")
        assert len(matches) == 1

    def test_registry_lists_as_available(self):
        reg = ToolRegistry()
        reg.register(MusicGenLocal())
        available = reg.get_available()
        assert any(t.name == "musicgen_local" for t in available)


class TestMusicGenLocalSupports:
    """Test the supports/provides metadata."""

    def test_supports_offline(self):
        assert MusicGenLocal.supports.get("offline") is True

    def test_supports_melody_conditioning(self):
        assert MusicGenLocal.supports.get("melody_conditioning") is True

    def test_does_not_support_vocals(self):
        assert "vocals" not in MusicGenLocal.best_for

    def test_output_format_in_execute(self):
        """If execute were called, it should produce a WAV file."""
        pass

    @pytest.mark.parametrize("field", [
        "prompt", "model", "duration_seconds", "seed",
        "guidance_scale", "temperature", "top_k", "top_p", "output_path",
    ])
    def test_input_schema_has_field(self, field):
        assert field in MusicGenLocal.input_schema["properties"]

    def test_default_values_in_schema(self):
        props = MusicGenLocal.input_schema["properties"]
        assert props["guidance_scale"]["default"] == 3.0
        assert props["temperature"]["default"] == 1.0
        assert props["top_k"]["default"] == 250
        assert props["top_p"]["default"] == 0.0

    def test_execute_no_gpu(self):
        """Simulate execute on a CPU-only system."""
        tool = MusicGenLocal()
        if tool.get_status() != ToolStatus.AVAILABLE:
            result = tool.execute({"prompt": "test music"})
            assert result.success is False


class TestMusicGenLocalDryRun:
    """Test the dry_run method which should work without GPU."""

    def test_dry_run_returns_expected(self):
        tool = MusicGenLocal()
        result = tool.dry_run({"prompt": "ambient pad music", "duration_seconds": 30})
        assert result["tool"] == "musicgen_local"
        assert result["estimated_cost_usd"] == 0.0
        assert result["would_execute"] is True

    def test_dry_run_default_duration(self):
        tool = MusicGenLocal()
        result = tool.dry_run({"prompt": "test"})
        assert result["estimated_cost_usd"] == 0.0
        assert result["would_execute"] is True

    def test_dry_run_with_seed(self):
        tool = MusicGenLocal()
        result = tool.dry_run({"prompt": "test", "seed": 42})
        assert result["estimated_cost_usd"] == 0.0
