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

    @staticmethod
    def _piper_installed() -> bool:
        # This tool shells out to the `piper` executable, so execution readiness
        # is gated on the binary being on PATH. The Python `piper` package
        # importing is NOT sufficient — a package-only install still cannot run
        # the subprocess, so preflight must report UNAVAILABLE in that state.
        return shutil.which("piper") is not None

    def _find_voice(self, name: str) -> Path | None:
        """Locate a Piper voice model (.onnx + .onnx.json) by name or path.

        Accepts a direct path to an .onnx file or a bare model name resolved
        against the voice search dirs. Returns the .onnx path if found.
        """
        direct = Path(name).expanduser()
        if direct.suffix == ".onnx" and direct.is_file():
            return direct
        for d in self._voice_search_dirs():
            if d.is_dir():
                cand = d / f"{name}.onnx"
                if cand.is_file() and cand.with_suffix(".onnx.json").is_file():
                    return cand
        return None

    def get_status(self) -> ToolStatus:
        if not self._piper_installed():
            return ToolStatus.UNAVAILABLE
        # Installed, but preflight is only truthful if the default voice — the
        # one execute() uses when no model is specified — is actually present.
        # Report DEGRADED when it is missing so preflight doesn't claim TTS is
        # ready when the default execute path will fail. Callers may still run
        # execute() with an explicitly-provided voice that is installed.
        return (
            ToolStatus.AVAILABLE
            if self._find_voice(self.default_voice)
            else ToolStatus.DEGRADED
        )

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._piper_installed():
            return ToolResult(success=False, error="Piper TTS not installed. " + self.install_instructions)
        # Gate on the specific voice this call will use, not the coarse status —
        # a caller may request an installed voice even when the default is absent.
        model = inputs.get("model", self.default_voice)
        voice_path = self._find_voice(model)
        if voice_path is None:
            searched = ", ".join(str(d) for d in self._voice_search_dirs())
            return ToolResult(
                success=False,
                error=(
                    f"Piper is installed but voice model '{model}' was not found "
                    f"(searched: {searched}). Download it:\n"
                    f"  python -m piper.download_voices {model}"
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, str(voice_path))
        except Exception as exc:
            return ToolResult(success=False, error=f"Local TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any], model_path: str) -> ToolResult:
        # model_path is the resolved .onnx file located by _find_voice(). Piper
        # only searches the current directory for a bare model name, so passing
        # the resolved path is required when the voice lives in PIPER_VOICE_DIR
        # or ~/.piper — otherwise a voice that passed the availability gate would
        # still fail to load at run time from a different cwd.
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(
            [
                "piper",
                "--model", model_path,
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
                "model": model_path,
                "speaker_id": inputs.get("speaker_id", 0),
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=model_path,
        )
