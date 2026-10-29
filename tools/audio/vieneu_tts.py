"""VieNeu-TTS local Vietnamese text-to-speech provider.

VieNeu (https://github.com/pnnbao97/VieNeu-TTS) is a 48 kHz Vietnamese TTS with
preset voices and voice cloning. It is heavy (ONNX/torch), so instead of installing it
into OpenMontage's environment this tool shells out to whichever Python has `vieneu`
installed. Set VIENEU_PYTHON to that interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from functools import lru_cache
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

_RUNNER = Path(__file__).with_name("_vieneu_runner.py")
# Cloned voices exported by VieNeu (`save_voices`) and kept in the repo, e.g. assets/voices/vieneu/chang.json.
_VOICES_DIR = Path(__file__).resolve().parents[2] / "assets" / "voices" / "vieneu"
# ponytail: one known install on this machine; VIENEU_PYTHON overrides it anywhere else.
_DEFAULT_PYTHON_CANDIDATES = [r"D:\videoscribe\.venv\Scripts\python.exe"]


def vieneu_python() -> str | None:
    explicit = os.environ.get("VIENEU_PYTHON")
    candidates = [explicit] if explicit else _DEFAULT_PYTHON_CANDIDATES
    return next((c for c in candidates if c and Path(c).exists()), None)


# ponytail: cached for the process lifetime — the probe spawns a Python that imports
# vieneu (seconds, not ms) and registry.discover() calls get_status() often. If vieneu is
# installed/removed mid-session, call _has_vieneu.cache_clear() or restart.
@lru_cache(maxsize=4)
def _has_vieneu(python: str) -> bool:
    try:
        proc = subprocess.run([python, "-c", "import vieneu"], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def split_lines(text: str) -> list[str]:
    """One narration segment per non-empty line; timing is reported per segment."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class VieNeuTTS(BaseTool):
    name = "vieneu_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "vieneu"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["env:VIENEU_PYTHON"]
    install_instructions = (
        "Install VieNeu-TTS in any Python 3.11 venv:\n"
        "  pip install vieneu\n"
        "Then point OpenMontage at that interpreter:\n"
        "  set VIENEU_PYTHON=<venv>\\Scripts\\python.exe\n"
        "First run downloads pnnbao-ump/VieNeu-TTS-v3-Turbo from Hugging Face."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "offline_generation", "vietnamese", "segment_timestamps"]
    supports = {
        "voice_cloning": True,  # via voice_profile exported from VieNeu
        "multilingual": False,
        "languages": ["vi"],
        "offline": True,
        "native_audio": True,
        "word_timestamps": False,
        "segment_timestamps": True,
    }
    best_for = [
        "Vietnamese narration with natural regional voices (Bắc/Trung/Nam)",
        "offline, free, 48 kHz voiceover",
        "cloned Vietnamese voices exported as a VieNeu voice profile",
    ]
    not_good_for = [
        "any language other than Vietnamese",
        "sub-second latency (model load is ~40s per call)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Narration. One line per segment."},
            "voice": {
                "type": "string",
                "default": "Thanh Bình",
                "description": "Preset name, e.g. 'Thanh Bình', 'Minh Đức', 'Ngọc Linh', or a name from voice_profile.",
            },
            "voice_profile": {
                "type": "string",
                "description": "Optional VieNeu voice-profile JSON (cloned voices). Defaults to VIENEU_VOICE_PROFILE.",
            },
            "gap_seconds": {"type": "number", "default": 0.4, "description": "Silence inserted between lines."},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=4, ram_mb=4096, vram_mb=0, disk_mb=2500, network_required=False)
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["text", "voice", "voice_profile", "gap_seconds"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen for mispronounced words; VieNeu reads digits and abbreviations literally"]

    def get_status(self) -> ToolStatus:
        py = vieneu_python()
        return ToolStatus.AVAILABLE if py and _has_vieneu(py) else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        py = vieneu_python()
        if not py or not _has_vieneu(py):
            return ToolResult(success=False, error="VieNeu-TTS not available. " + self.install_instructions)

        lines = split_lines(inputs["text"])
        if not lines:
            return ToolResult(success=False, error="text is empty")

        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        job = {
            "lines": lines,
            "voice": inputs.get("voice", "Thanh Bình"),
            "voice_profile": inputs.get("voice_profile") or os.environ.get("VIENEU_VOICE_PROFILE"),
            "voices_dir": str(_VOICES_DIR) if _VOICES_DIR.is_dir() else None,
            "gap_seconds": inputs.get("gap_seconds", 0.4),
            "output_path": str(output_path),
        }
        start = time.time()
        try:
            proc = subprocess.run(
                [py, str(_RUNNER)],
                input=json.dumps(job, ensure_ascii=False),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=1800,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="VieNeu-TTS timed out after 1800s")

        payload = _last_json_line(proc.stdout)
        if proc.returncode != 0 or not payload or payload.get("error"):
            detail = (payload or {}).get("error") or proc.stderr[-2000:]
            return ToolResult(success=False, error=f"VieNeu-TTS failed (exit {proc.returncode}): {detail}")
        if not output_path.exists():
            return ToolResult(success=False, error=f"VieNeu output file missing: {output_path}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "VieNeu-TTS-v3-Turbo",
                "voice": payload.get("voice"),
                "output": str(output_path),
                "format": "wav",
                "sample_rate": payload.get("sample_rate"),
                "duration_seconds": payload.get("duration_seconds"),
                "segments": payload.get("segments", []),
                "voices_available": payload.get("voices_available", []),
                "text_length": len(inputs["text"]),
            },
            artifacts=[str(output_path)],
            model="VieNeu-TTS-v3-Turbo",
            duration_seconds=round(time.time() - start, 2),
        )


def _last_json_line(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None
