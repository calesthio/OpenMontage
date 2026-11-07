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


def _voice_search_dirs() -> list[Path]:
    """Directories a bare voice name is resolved against, in order."""

    dirs: list[Path] = []
    env_dir = os.environ.get("PIPER_VOICES_DIR")
    if env_dir:
        dirs.append(Path(env_dir).expanduser())
    dirs.append(Path.home() / ".local" / "share" / "piper" / "voices")
    dirs.append(Path.cwd())
    return dirs


def resolve_voice_model(model: str) -> Path:
    """Resolve a piper voice argument to an existing ``.onnx`` file.

    ``python -m piper.download_voices <voice>`` drops the voice into the
    current directory unless ``--download-dir`` is given, so a bare voice
    name like ``en_US-lessac-medium`` only works when it happens to sit in
    the process cwd. This resolves the name against ``PIPER_VOICES_DIR``,
    the conventional user voice directory and the cwd, and raises a clear
    error naming the fix when nothing matches.
    """

    candidate = Path(model).expanduser()
    if candidate.exists():
        return candidate

    for base in _voice_search_dirs():
        for suffix in ("", ".onnx"):
            resolved = base / f"{model}{suffix}"
            if resolved.exists():
                return resolved

    searched = ", ".join(str(d) for d in _voice_search_dirs())
    raise FileNotFoundError(
        f"Piper voice {model!r} not found. Download it with "
        f"`python -m piper.download_voices {model}` (optionally with "
        f"--download-dir), or set PIPER_VOICES_DIR. Searched: {searched}"
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
        "  piper --download-dir ~/.local/share/piper/voices --model en_US-lessac-medium\n"
        "Or: python -m piper.download_voices --download-dir ~/.local/share/piper/voices en_US-lessac-medium\n"
        "A bare voice name is resolved against $PIPER_VOICES_DIR, then\n"
        "~/.local/share/piper/voices, then the current directory."
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
                "description": "Voice name or path to an .onnx voice. A bare name is resolved against $PIPER_VOICES_DIR, ~/.local/share/piper/voices and the cwd.",
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
        if shutil.which("piper"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Piper TTS not available. " + self.install_instructions)

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
                "--model", str(resolve_voice_model(inputs.get("model", "en_US-lessac-medium"))),
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
