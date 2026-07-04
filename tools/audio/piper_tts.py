"""Piper local text-to-speech provider tool."""

from __future__ import annotations

import os
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
        "Or download from https://github.com/rhasspy/piper/releases\n"
        "Then download a voice model:\n"
        "  python -m piper.download_voices en_US-lessac-medium"
    )
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

    def get_status(self) -> ToolStatus:
        if not shutil.which("piper"):
            return ToolStatus.UNAVAILABLE
        if self._resolve_model_arg(self.input_schema["properties"]["model"]["default"]):
            return ToolStatus.AVAILABLE
        return ToolStatus.DEGRADED

    def _candidate_model_paths(self, model: str) -> list[Path]:
        raw = Path(model).expanduser()
        candidates = [raw]
        if raw.suffix != ".onnx":
            candidates.append(raw.with_suffix(".onnx"))

        voice_roots = [
            Path.home() / ".piper" / "models",
            Path.home() / ".local" / "share" / "piper" / "voices",
            Path.home() / ".cache" / "piper" / "voices",
            Path.cwd(),
        ]
        if "APPDATA" in os.environ:
            voice_roots.append(Path(os.environ["APPDATA"]) / "piper" / "voices")

        for root in voice_roots:
            candidates.append(root / raw.name)
            if raw.suffix != ".onnx":
                candidates.append(root / f"{model}.onnx")
                candidates.append(root / model / f"{model}.onnx")

        # Preserve order, drop duplicates.
        seen: set[str] = set()
        unique: list[Path] = []
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def _resolve_model_arg(self, model: str) -> str | None:
        for candidate in self._candidate_model_paths(model):
            if candidate.exists():
                return str(candidate)
        return None

    def _missing_model_error(self, model: str) -> str:
        return (
            f"Piper executable found, but voice model {model!r} is not installed. "
            f"Download it with `python -m piper.download_voices {model}` or pass "
            "an explicit local `.onnx` model path."
        )

    def _status_error(self, model: str) -> str:
        status = self.get_status()
        if status == ToolStatus.UNAVAILABLE:
            return "Piper TTS not available. " + self.install_instructions
        if self._resolve_model_arg(model):
            return ""
        return self._missing_model_error(model)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        model = inputs.get("model", "en_US-lessac-medium")
        status_error = self._status_error(model)
        if status_error:
            return ToolResult(success=False, error=status_error)

        inputs = dict(inputs)
        inputs["model"] = self._resolve_model_arg(model) or model
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
                "--model", inputs.get("model", "en_US-lessac-medium"),
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
                "model": inputs.get("model", "en_US-lessac-medium"),
                "speaker_id": inputs.get("speaker_id", 0),
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=inputs.get("model", "en_US-lessac-medium"),
        )
