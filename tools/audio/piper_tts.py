"""Piper local text-to-speech provider tool."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class PiperTTS(BaseTool):
    name = "piper_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "piper"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:piper"]
    install_instructions = (
        "Install Piper TTS:\n"
        "  pip install piper-tts\n"
        "Then download at least one voice model (required — Piper ships none):\n"
        "  python -m piper.download_voices en_US-lessac-medium\n"
        "The model resolves from the current directory or PIPER_VOICE_DIR."
    )
    default_voice = "en_US-lessac-medium"
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": False,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "offline narration fallback",
        "privacy-sensitive local-only workflows",
    ]
    not_good_for = [
        "best-in-class expressive voice quality",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "model": {
                "type": "string",
                "default": "en_US-lessac-medium",
            },
            "speaker_id": {
                "type": "integer",
                "default": 0,
            },
            "length_scale": {
                "type": "number",
                "default": 1.0,
            },
            "sentence_silence": {
                "type": "number",
                "default": 0.3,
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=200, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "model", "speaker_id", "length_scale"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for intelligibility"]

    @staticmethod
    def _voice_search_dirs() -> list[Path]:
        import os

        dirs = [Path.cwd()]
        env_dir = os.environ.get("PIPER_VOICE_DIR")
        if env_dir:
            dirs.append(Path(env_dir).expanduser())
        dirs += [Path.home() / ".local/share/piper", Path.home() / ".piper/models"]
        return dirs

    def _has_voice_model(self) -> bool:
        """True if any Piper voice model (.onnx + .onnx.json) is discoverable."""
        for d in self._voice_search_dirs():
            if d.is_dir():
                for onnx in d.glob("*.onnx"):
                    if onnx.with_suffix(".onnx.json").is_file():
                        return True
        return False

    def get_status(self) -> ToolStatus:
        installed = shutil.which("piper") is not None
        if not installed:
            try:
                import piper  # noqa: F401
                installed = True
            except ImportError:
                return ToolStatus.UNAVAILABLE
        # Installed but unusable until a voice model is downloaded — report
        # DEGRADED so preflight doesn't claim TTS is ready when it will fail.
        return ToolStatus.AVAILABLE if self._has_voice_model() else ToolStatus.DEGRADED

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        status = self.get_status()
        if status == ToolStatus.UNAVAILABLE:
            return ToolResult(success=False, error="Piper TTS not installed. " + self.install_instructions)
        if status == ToolStatus.DEGRADED:
            return ToolResult(
                success=False,
                error=(
                    "Piper is installed but no voice model was found. Download one:\n"
                    f"  python -m piper.download_voices {self.default_voice}"
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Local TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(
            [
                "piper",
                "--model", inputs.get("model", self.default_voice),
                "--speaker", str(inputs.get("speaker_id", 0)),
                "--length-scale", str(inputs.get("length_scale", 1.0)),
                "--sentence-silence", str(inputs.get("sentence_silence", 0.3)),
                "--output_file", str(output_path),
            ],
            input=inputs["text"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if proc.returncode != 0:
            return ToolResult(success=False, error=f"Piper failed (exit {proc.returncode}): {proc.stderr}")
        if not output_path.exists():
            return ToolResult(success=False, error=f"Piper output file missing: {output_path}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": inputs.get("model", self.default_voice),
                "speaker_id": inputs.get("speaker_id", 0),
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=inputs.get("model", self.default_voice),
        )
