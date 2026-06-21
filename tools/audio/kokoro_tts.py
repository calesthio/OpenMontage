"""Kokoro v1.0 local text-to-speech provider tool."""

from __future__ import annotations

import time
import importlib.util
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


class KokoroTTS(BaseTool):
    name = "kokoro_tts"
    version = "1.0.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kokoro"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["pip:kokoro", "pip:soundfile", "pip:torch"]
    install_instructions = (
        "Install Kokoro TTS and dependencies:\n"
        "  pip install kokoro soundfile torch\n"
        "You may also need to install espeak-ng on your system:\n"
        "  Ubuntu: sudo apt-get install espeak-ng\n"
        "  Mac: brew install espeak\n"
        "  Windows: Download from https://github.com/espeak-ng/espeak-ng/releases"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "high-quality offline narration",
        "privacy-sensitive local-only workflows",
        "open-weight AI pipelines",
    ]
    not_good_for = [
        "voice clone matching from custom audio",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {
                "type": "string",
                "default": "af_heart",
                "description": "The voice model to use. Defaults to American female 'af_heart'.",
            },
            "lang_code": {
                "type": "string",
                "default": "a",
                "description": "Language code for the pipeline (e.g., 'a' for American English).",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=200, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "voice", "lang_code"]
    side_effects = ["writes audio file to output_path", "downloads model weights on first run"]
    user_visible_verification = ["Listen to generated audio for intelligibility and quality"]

    def get_status(self) -> ToolStatus:
        if importlib.util.find_spec("kokoro") and importlib.util.find_spec("soundfile") and importlib.util.find_spec("torch"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Local execution costs $0
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Kokoro TTS not available. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Kokoro TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np

        text = inputs["text"]
        voice = inputs.get("voice", "af_heart")
        lang_code = inputs.get("lang_code", "a")
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pipeline = KPipeline(lang_code=lang_code)
        generator = pipeline(text, voice=voice)

        audio_segments = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_segments.append(audio)

        if not audio_segments:
            return ToolResult(success=False, error="Kokoro TTS returned no audio segments.")

        final_audio = np.concatenate(audio_segments)
        sf.write(str(output_path), final_audio, 24000)

        if not output_path.exists():
            return ToolResult(success=False, error=f"Kokoro output file missing: {output_path}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice,
                "lang_code": lang_code,
                "text_length": len(text),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model="kokoro-v1.0",
        )
