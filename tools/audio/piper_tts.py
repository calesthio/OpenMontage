"""Piper local text-to-speech provider tool."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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

_DEFAULT_VOICE = "en_US-lessac-medium"


def _piper_executable() -> str | None:
    """Return the ``piper`` command: on PATH, or next to the running interpreter.

    ``make setup`` installs piper-tts into the project venv, and tools are run
    with ``.venv/bin/python`` without activating it, so PATH alone misses it.
    """
    found = shutil.which("piper")
    if found:
        return found
    name = "piper.exe" if os.name == "nt" else "piper"
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.is_file() else None


def _data_dir() -> Path:
    """Folder the voice models are kept in (``PIPER_DATA_DIR`` overrides it)."""
    override = os.environ.get("PIPER_DATA_DIR")
    return Path(override).expanduser() if override else Path.home() / ".piper" / "models"


def _installed_voices(data_dir: Path) -> list[str]:
    """Voices in *data_dir*: a ``<name>.onnx`` with its ``<name>.onnx.json``."""
    if not data_dir.is_dir():
        return []
    return sorted(
        model.stem
        for model in data_dir.glob("*.onnx")
        if model.with_name(f"{model.name}.json").is_file()
    )


def _download_hint(voice: str, data_dir: Path) -> str:
    return (
        f'"{sys.executable}" -m piper.download_voices {voice} --data-dir "{data_dir}"'
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
        "Then download a voice model into ~/.piper/models (PIPER_DATA_DIR "
        "overrides the folder):\n"
        "  python -m piper.download_voices en_US-lessac-medium --data-dir ~/.piper/models"
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
                "default": _DEFAULT_VOICE,
                "description": (
                    "Installed voice name, or a path to a .onnx voice file. When "
                    "omitted, the default voice is used if it is installed, "
                    "otherwise the first installed voice."
                ),
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

    def vouches_for_model(self, model: str) -> bool:
        """True when `piper --model <model>` (as _generate invokes it) finds a voice.

        Mirrors piper's own lookup: an existing file path (absolute or relative),
        else `<name>.onnx` in the cwd or the configured home voice directory.
        False means "can't confirm", not "unsupported":
        provider_routing then applies its generic free-form-model policy.
        """
        return Path(model).is_file() or any(
            (directory / f"{model}.onnx").is_file()
            for directory in (Path.cwd(), self._voice_data_dir())
        )

    @staticmethod
    def _voice_data_dir() -> Path:
        return _data_dir()

    def get_status(self) -> ToolStatus:
        if not _piper_executable():
            return ToolStatus.UNAVAILABLE
        # The command without a voice cannot speak: say so before a run does.
        if not _installed_voices(_data_dir()):
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        data_dir = _data_dir()
        info["data_dir"] = str(data_dir)
        info["installed_voices"] = _installed_voices(data_dir)
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        executable = _piper_executable()
        if not executable:
            return ToolResult(success=False, error="Piper TTS not available. " + self.install_instructions)

        data_dir = _data_dir()
        model, problem = self._resolve_model(inputs.get("model"), data_dir)
        if model is None:
            return ToolResult(success=False, error=problem)

        start = time.time()
        try:
            result = self._generate(inputs, executable, model, data_dir)
        except Exception as exc:
            return ToolResult(success=False, error=f"Local TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _resolve_model(self, requested: Any, data_dir: Path) -> tuple[str | None, str | None]:
        """Return ``(model argument for piper, None)`` or ``(None, error)``.

        An explicit voice must be installed, be a path to a model file, or be
        one ``vouches_for_model`` confirms (the routing witness and this check
        must not disagree). With none given, the default voice wins when
        installed, else the first installed voice.
        """
        installed = _installed_voices(data_dir)
        listing = ", ".join(installed) or "none"
        if requested:
            requested = str(requested)
            if (
                requested in installed
                or Path(requested).expanduser().is_file()
                or self.vouches_for_model(requested)
            ):
                return requested, None
            return None, (
                f"Piper voice {requested!r} is not installed in {data_dir} "
                f"(installed: {listing}). Download it with:\n"
                f"  {_download_hint(requested, data_dir)}"
            )
        if _DEFAULT_VOICE in installed:
            return _DEFAULT_VOICE, None
        if installed:
            return installed[0], None
        return None, (
            f"No Piper voice is installed in {data_dir}. Download one with:\n"
            f"  {_download_hint(_DEFAULT_VOICE, data_dir)}"
        )

    def _generate(
        self,
        inputs: dict[str, Any],
        executable: str | None = None,
        model: str | None = None,
        data_dir: Path | None = None,
    ) -> ToolResult:
        # execute() passes what it resolved; a direct call gets the same
        # command, voice and folder a plain `piper` run would use.
        executable = executable or _piper_executable() or "piper"
        model = str(model or inputs.get("model") or _DEFAULT_VOICE)
        data_dir = data_dir or self._voice_data_dir()
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(
            [
                executable,
                "--model", model,
                "--data-dir", str(data_dir),
                "--speaker", str(inputs.get("speaker_id", 0)),
                "--length-scale", str(inputs.get("length_scale", 1.0)),
                "--sentence-silence", str(inputs.get("sentence_silence", 0.3)),
                "--output_file", str(output_path),
            ],
            input=inputs["text"],
            capture_output=True,
            text=True,
            # Both sides UTF-8: the Windows default (cp1252) turns accented text
            # into input piper can't decode, which yields an empty WAV.
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
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
                "model": model,
                "speaker_id": inputs.get("speaker_id", 0),
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=model,
        )
