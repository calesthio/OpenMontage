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

_DEFAULT_WINDOWS_PIPER_DIR = Path("C:/piper")
_DEFAULT_MODEL_NAME = "en_US-lessac-medium"


def _resolve_piper_executable() -> Path | None:
    """Return a Piper binary path if one is configured or discoverable."""
    override = os.environ.get("PIPER_EXECUTABLE")
    if override:
        path = Path(override)
        if path.is_file():
            return path

    found = shutil.which("piper")
    if found:
        return Path(found)

    # Windows: piper-tts pip wheels can break on non-ASCII profile paths.
    # The standalone release at C:\piper is the recommended local install.
    if os.name == "nt":
        for candidate in (
            _DEFAULT_WINDOWS_PIPER_DIR / "piper.exe",
            Path.home() / ".local" / "piper" / "piper" / "piper.exe",
        ):
            if candidate.is_file():
                return candidate
    return None


def _model_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("PIPER_MODEL_DIR")
    if override:
        dirs.append(Path(override))
    dirs.extend(
        [
            _DEFAULT_WINDOWS_PIPER_DIR,
            Path.home() / ".piper" / "models",
            Path.home() / ".local" / "piper" / "piper",
        ]
    )
    seen: set[Path] = set()
    unique: list[Path] = []
    for directory in dirs:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(directory)
    return unique


def _resolve_model_path(model: str) -> Path:
    """Map a voice id or .onnx path to an on-disk model file."""
    candidate = Path(model)
    if candidate.suffix == ".onnx" and candidate.is_file():
        return candidate

    name = model if model.endswith(".onnx") else f"{model}.onnx"
    for directory in _model_search_dirs():
        path = directory / name
        if path.is_file():
            return path

    raise FileNotFoundError(
        f"Piper voice model not found for {model!r}. "
        f"Download en_US-lessac-medium.onnx (+ .json) into one of: "
        f"{', '.join(str(d) for d in _model_search_dirs())}"
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
        "Install Piper TTS (Windows recommended path: C:\\piper — ASCII only):\n"
        "  1. Download https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip\n"
        "  2. Extract to C:\\piper (avoid user-profile paths with non-ASCII characters)\n"
        "  3. Download voice files into the same folder:\n"
        "     en_US-lessac-medium.onnx + en_US-lessac-medium.onnx.json\n"
        "     (hf-mirror: rhasspy/piper-voices/.../lessac/medium)\n"
        "  4. Optional env vars: PIPER_EXECUTABLE, PIPER_MODEL_DIR\n"
        "Linux/macOS: pip install piper-tts OR use the release binary; then:\n"
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
        if _resolve_piper_executable() is not None:
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
        piper_exe = _resolve_piper_executable()
        if piper_exe is None:
            return ToolResult(success=False, error="Piper executable not found")

        model_name = inputs.get("model", _DEFAULT_MODEL_NAME)
        try:
            model_path = _resolve_model_path(model_name)
        except FileNotFoundError as exc:
            return ToolResult(success=False, error=str(exc))

        output_path = Path(inputs.get("output_path", "tts_output.wav")).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(
            [
                str(piper_exe),
                "--model",
                str(model_path),
                "--speaker",
                str(inputs.get("speaker_id", 0)),
                "--length-scale",
                str(inputs.get("length_scale", 1.0)),
                "--sentence-silence",
                str(inputs.get("sentence_silence", 0.3)),
                "--output_file",
                str(output_path),
            ],
            input=inputs["text"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(piper_exe.parent),
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
