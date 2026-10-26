"""Kokoro-82M local text-to-speech provider tool.

Synthesises narration with hexgrad/Kokoro-82M (Apache-2.0 weights) on CPU via
the ``kokoro`` package, then normalises through ``FinishAudioTool`` so the
emitted wav hits the delivery loudness target (~-15 LUFS / ~-4.3 dBTP with the
default config, per commit 7fd52a4) instead of raw Kokoro output (~-25.5 LUFS).

Fail-closed: if ``kokoro``/``torch``/``misaki`` are not importable, or the
Kokoro-82M weights cannot be loaded, the tool returns ``BLOCKED`` (never silent
success). Voice ``af_heart`` is the default and only voice used here — no silent
voice substitution.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from tools.audio.finish_audio import FinishAudioTool
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

SAMPLE_RATE = 24000  # Kokoro-82M native sample rate
DEFAULT_VOICE = "af_heart"
DEFAULT_LANG = "a"
DEFAULT_SPEED = 1.0


class KokoroTTSTool(BaseTool):
    name = "kokoro_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kokoro"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:kokoro", "python:torch", "python:misaki"]
    install_instructions = (
        "Install the Kokoro TTS stack (CPU, binary wheels on Python 3.14):\n"
        "  pip install --only-binary=:all: torch==2.14.1 --index-url "
        "https://download.pytorch.org/whl/cpu\n"
        "  pip install --only-binary=:all: kokoro==0.2.2 misaki==0.7.4\n"
        "Kokoro-82M weights (kokoro-v1_0.pth, ~313 MB) are cached into HF_HOME\n"
        "on first run from hexgrad/Kokoro-82M (Apache-2.0).\n"
        "Voice license gate: Kokoro-82M is owner-approved for the pilot with "
        "attribution (CC BY Koniwa/SIWIS + synthetic-data caveats) — see "
        "docs/openmontage/VOICE_DECISION.md."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "offline_generation"]
    supports = {
        "voice_cloning": False,
        "multilingual": False,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "local-only narration (no API key, no paid route)",
        "pilot narration voice af_heart",
    ]
    not_good_for = [
        "paid API voices / voice cloning",
        "real-time streaming (CPU RTF 1.58-1.75, slower than real time)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text", "output_path"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "output_path": {"type": "string"},
            "voice": {
                "type": "string",
                "default": DEFAULT_VOICE,
                "description": "Kokoro voice id (default af_heart).",
            },
            "lang_code": {
                "type": "string",
                "default": DEFAULT_LANG,
                "description": "Kokoro language code (default a = American English).",
            },
            "speed": {
                "type": "number",
                "default": DEFAULT_SPEED,
                "minimum": 0.5,
                "maximum": 2.0,
                "description": "Speaking speed multiplier.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=400, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["text", "voice", "lang_code", "speed"]
    side_effects = ["writes normalised narration wav to output_path"]
    user_visible_verification = [
        "Measure output with ebur128: integrated LUFS near -15, true peak <= -4.3 dBTP",
        "Confirm voice used is af_heart (no substitution)",
    ]

    def _synth_raw(self, text: str, voice: str, lang_code: str, speed: float) -> str:
        """Synthesise text to a raw pcm_s16le 24000 Hz wav; return temp path."""
        from kokoro import KPipeline

        pipeline = KPipeline(lang_code=lang_code)
        chunks = []
        for _, _, seg in pipeline(text, voice=voice, speed=speed):
            chunks.append(np.asarray(seg, dtype=np.float32))
        if not chunks:
            raise RuntimeError("Kokoro produced no audio for the given text")
        audio = np.concatenate(chunks)
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="kokoro_raw_")
        os.close(fd)
        sf.write(tmp, audio, SAMPLE_RATE, subtype="PCM_16")
        return tmp

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        text = inputs.get("text")
        output_path = inputs.get("output_path")
        voice = inputs.get("voice", DEFAULT_VOICE)
        lang_code = inputs.get("lang_code", DEFAULT_LANG)
        speed = float(inputs.get("speed", DEFAULT_SPEED))

        if not text:
            return ToolResult(
                success=False,
                error="BLOCKED: text is required",
                data={"verdict": "BLOCKED"},
            )
        if not output_path:
            return ToolResult(
                success=False,
                error="BLOCKED: output_path is required",
                data={"verdict": "BLOCKED"},
            )

        start = time.time()
        raw_tmp = None
        try:
            raw_tmp = self._synth_raw(text, voice, lang_code, speed)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"BLOCKED: Kokoro synthesis failed: {exc}",
                data={"verdict": "BLOCKED"},
            )

        try:
            out_parent = Path(output_path).parent
            if out_parent and not out_parent.exists():
                out_parent.mkdir(parents=True, exist_ok=True)

            fin = FinishAudioTool()
            fin_res = fin.execute({"input_path": raw_tmp, "output_path": output_path})
            if not fin_res.success:
                return ToolResult(
                    success=False,
                    error=f"BLOCKED: finish_audio normalization failed: {fin_res.error}",
                    data={"verdict": "BLOCKED"},
                )
        finally:
            if raw_tmp and Path(raw_tmp).exists():
                try:
                    Path(raw_tmp).unlink()
                except OSError:
                    pass

        data = {
            "provider": self.provider,
            "model": "hexgrad/Kokoro-82M",
            "voice": voice,
            "lang_code": lang_code,
            "speed": speed,
            "text_length": len(text),
            "output": str(output_path),
            "format": "wav",
            "sample_rate": 44100,  # finish_audio emits 44100 Hz pcm_s16le
            "channels": 1,
            "render_seconds": round(time.time() - start, 2),
            "cost_usd": 0.0,
        }
        data.update(fin_res.data or {})
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model="hexgrad/Kokoro-82M",
        )
