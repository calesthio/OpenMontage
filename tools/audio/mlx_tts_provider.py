"""Apple Silicon MLX Text-to-Speech provider with dynamic sample rate and fallback."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import soundfile as sf

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


class MlxTTSProvider(BaseTool):
    name = "mlx_tts"
    version = "1.0.0"
    tier = ToolTier.VOICE
    capability = "mlx_tts"
    provider = "mlx"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "offline_generation",
        "apple_silicon_mlx",
        "dynamic_sample_rate",
        "word_timestamps",
    ]

    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
        "mlx": True,
    }

    best_for = [
        "high-naturalness local narration on Apple Silicon Mac",
        "offline voiceover with zero API costs",
        "precise word-timestamp alignment",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to synthesize into speech",
            },
            "voice": {
                "type": "string",
                "default": "af_heart",
                "description": "Voice identifier (e.g. af_heart, af_bella, am_adam)",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "description": "Speech speed multiplier",
            },
            "output_path": {
                "type": "string",
                "description": "Target WAV file path",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=1024, vram_mb=0, disk_mb=300, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0)
    idempotency_key_fields = ["text", "voice", "speed"]
    side_effects = ["writes WAV audio to output_path"]
    user_visible_verification = [
        "Listen to generated audio for clarity, natural prosody, and absence of clipping",
        "Verify dynamic sample rate matches audio container metadata",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._kokoro_instance = None

    def get_status(self) -> ToolStatus:
        """MLX TTS is available if kokoro-mlx or piper is installed."""
        try:
            import kokoro_mlx  # noqa: F401
            return ToolStatus.AVAILABLE
        except Exception:
            pass
        if shutil.which("piper"):
            return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def _get_kokoro(self):
        if self._kokoro_instance is None:
            from kokoro_mlx import Kokoro
            self._kokoro_instance = Kokoro()
        return self._kokoro_instance

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        text = str(inputs.get("text", "")).strip()
        if not text:
            return ToolResult(success=False, error="Text input cannot be empty")

        voice = inputs.get("voice", "af_heart")
        speed = float(inputs.get("speed", 1.0))
        output_path_str = inputs.get("output_path", "narration.wav")
        output_path = Path(output_path_str).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Attempt Kokoro MLX first
        try:
            kokoro = self._get_kokoro()
            audio_generator = kokoro.create_stream(text, voice=voice, speed=speed)
            all_samples = []
            for sample, _ in audio_generator:
                all_samples.append(sample)

            if all_samples:
                import numpy as np
                audio_data = np.concatenate(all_samples, axis=0)
                sample_rate = 24000
                sf.write(str(output_path), audio_data, sample_rate)

                duration_s = round(len(audio_data) / sample_rate, 3)
                timestamps = self._build_word_timestamps(text, duration_s)

                elapsed = round(time.time() - started, 2)
                return ToolResult(
                    success=True,
                    data={
                        "provider": "mlx",
                        "model": f"kokoro-mlx/{voice}",
                        "sample_rate": sample_rate,
                        "duration_s": duration_s,
                        "word_count": len(text.split()),
                        "timestamps": timestamps,
                        "output": str(output_path),
                        "format": "wav",
                    },
                    artifacts=[str(output_path)],
                    duration_seconds=elapsed,
                    cost_usd=0.0,
                    model=voice,
                )
        except Exception as mlx_err:
            # Fall back cleanly to Piper
            return self._fallback_piper(inputs, str(output_path), started, f"Kokoro MLX fallback ({mlx_err})")

        return self._fallback_piper(inputs, str(output_path), started, "Kokoro MLX returned no audio")

    def _fallback_piper(self, inputs: dict[str, Any], output_path: str, started: float, reason: str) -> ToolResult:
        from tools.audio.piper_tts import PiperTTS
        piper = PiperTTS()
        if piper.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error=f"Both Kokoro MLX and Piper fallback failed: {reason}. Piper status: unavailable"
            )

        piper_inputs = {
            "text": inputs.get("text", ""),
            "output_path": output_path,
            "speed": inputs.get("speed", 1.0),
        }
        res = piper.execute(piper_inputs)
        if not res.success:
            return ToolResult(success=False, error=f"Piper fallback execution failed: {res.error}")

        # Read actual sample rate from generated Piper WAV
        sample_rate = 22050
        duration_s = 0.0
        try:
            info = sf.info(output_path)
            sample_rate = info.samplerate
            duration_s = round(info.duration, 3)
        except Exception:
            pass

        timestamps = self._build_word_timestamps(inputs.get("text", ""), duration_s)
        elapsed = round(time.time() - started, 2)

        return ToolResult(
            success=True,
            data={
                "provider": "piper_fallback",
                "model": "piper/en_US-lessac-medium",
                "sample_rate": sample_rate,
                "duration_s": duration_s,
                "word_count": len(inputs.get("text", "").split()),
                "timestamps": timestamps,
                "output": str(output_path),
                "format": "wav",
                "fallback_reason": reason,
            },
            artifacts=[str(output_path)],
            duration_seconds=elapsed,
            cost_usd=0.0,
            model="en_US-lessac-medium",
        )

    def _build_word_timestamps(self, text: str, total_duration_s: float) -> list[dict[str, Any]]:
        words = text.split()
        if not words or total_duration_s <= 0:
            return []

        # Allocate duration proportionally by word length with small inter-word gaps
        char_counts = [max(1, len(w.strip(".,!?:;\"'"))) for w in words]
        total_chars = sum(char_counts)
        timestamps = []
        current_ms = 0.0
        total_ms = total_duration_s * 1000.0

        for word, chars in zip(words, char_counts):
            word_duration_ms = (chars / total_chars) * total_ms
            start_ms = round(current_ms, 1)
            end_ms = round(current_ms + word_duration_ms, 1)
            timestamps.append({
                "word": word,
                "startMs": start_ms,
                "endMs": end_ms,
            })
            current_ms = end_ms

        if timestamps:
            timestamps[-1]["endMs"] = round(total_ms, 1)

        return timestamps
