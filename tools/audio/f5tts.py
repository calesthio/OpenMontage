"""F5-TTS local voice-cloning text-to-speech provider tool.

F5-TTS is a flow-matching TTS model with strong few-shot voice cloning. Given a
short reference audio (7-12 seconds with a clean sentence ending) and its
verbatim transcript, it synthesizes new text in the reference voice. Runs on
local GPU; ~2 sec/beat on a 3090 at 24kHz.

Reference: https://github.com/SWivid/F5-TTS
"""

from __future__ import annotations

import os
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


def _patch_torchaudio_for_windows() -> None:
    """Replace torchaudio.load with a soundfile-backed loader.

    torchaudio 2.11 routes audio decoding through torchcodec, which on Windows
    requires FFmpeg shared DLLs that aren't shipped with `pip install torch`.
    soundfile (already a hard dep of f5-tts) covers the WAV/MP3/FLAC F5 needs
    for reference audio.
    """
    import numpy as np  # noqa: F401  (validates the soundfile<-numpy chain)
    import soundfile as sf
    import torch
    import torchaudio

    def _load_via_soundfile(path, **_kw):
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T), sr

    torchaudio.load = _load_via_soundfile


class F5TTS(BaseTool):
    name = "f5tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "f5tts"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:f5_tts", "python:torch", "python:soundfile"]
    install_instructions = (
        "Install F5-TTS:\n"
        "  pip install f5-tts  # also installs torchaudio, soundfile, vocos\n"
        "Requires PyTorch with CUDA. Models download to HF cache on first use\n"
        "(~1.5 GB for F5TTS_v1_Base + Vocos vocoder)."
    )
    fallback = "piper_tts"
    fallback_tools = ["piper_tts", "elevenlabs_tts", "openai_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_cloning",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": False,  # base model is English-focused
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "offline narration with cloned voice continuity across projects",
        "documentary register narration when paired with a clean reference",
        "free local TTS that approaches ElevenLabs quality",
    ]
    not_good_for = [
        "best-in-class expressive ElevenLabs quality (still a gap on inflection)",
        "CPU-only machines (very slow without GPU)",
        "long-form generation (>30s in a single call) — split into beats",
    ]

    input_schema = {
        "type": "object",
        "required": ["text", "ref_audio", "ref_text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to synthesize in the reference voice.",
            },
            "ref_audio": {
                "type": "string",
                "description": (
                    "Path to reference audio. 7-12 seconds, clean sentence ending. "
                    "Reference >12s triggers internal clipping that can leak ref text "
                    "into the output's first words — keep it short and clean."
                ),
            },
            "ref_text": {
                "type": "string",
                "description": "Verbatim transcript of ref_audio.",
            },
            "model": {
                "type": "string",
                "default": "F5TTS_v1_Base",
                "description": "F5-TTS model name (HF: SWivid/F5-TTS).",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "description": (
                    "Pacing multiplier. <1.0 slows speech (use ~0.95-0.97 to match "
                    "ElevenLabs Brian's pacing more closely)."
                ),
            },
            "seed": {"type": "integer", "default": 42},
            "output_path": {
                "type": "string",
                "description": "Where to write the output. Extension drives format (.wav or .mp3).",
            },
            "output_sample_rate": {
                "type": "integer",
                "default": 44100,
                "description": "Resample target for MP3 output. Native F5-TTS sr is 24000.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=4096, vram_mb=6000, disk_mb=2000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["MemoryError"])
    idempotency_key_fields = ["text", "ref_audio", "ref_text", "model", "speed", "seed"]
    side_effects = ["writes audio file to output_path", "may download model weights on first run"]
    user_visible_verification = [
        "Listen to generated audio for voice match and naturalness",
        "Check first 1.0s for ref-text bleed (long refs >12s can leak)",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import f5_tts  # noqa: F401
            import torch
        except ImportError:
            return ToolStatus.UNAVAILABLE
        if not torch.cuda.is_available():
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Empirical: ~2 sec synth per 5 sec of generated speech on a 3090.
        text_len = len(inputs.get("text", ""))
        approx_speech_seconds = max(1.0, text_len / 15.0)  # ~15 chars/sec spoken English
        return approx_speech_seconds * 0.4  # 0.4x real-time on GPU

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() == ToolStatus.UNAVAILABLE:
            return ToolResult(success=False, error="F5-TTS not installed. " + self.install_instructions)

        ref_audio = Path(inputs["ref_audio"])
        if not ref_audio.exists():
            return ToolResult(success=False, error=f"ref_audio not found: {ref_audio}")

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        _patch_torchaudio_for_windows()
        from f5_tts.api import F5TTS as F5API

        start = time.time()
        try:
            tts = F5API(model=inputs.get("model", "F5TTS_v1_Base"))
        except Exception as exc:
            return ToolResult(success=False, error=f"F5-TTS model load failed: {exc}")

        out_path = Path(inputs.get("output_path", "f5tts_output.wav"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        is_mp3 = out_path.suffix.lower() == ".mp3"
        wav_path = out_path.with_suffix(".wav") if is_mp3 else out_path

        try:
            tts.infer(
                ref_file=str(ref_audio),
                ref_text=inputs["ref_text"],
                gen_text=inputs["text"],
                file_wave=str(wav_path),
                speed=inputs.get("speed", 1.0),
                seed=inputs.get("seed", 42),
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"F5-TTS synthesis failed: {exc}")

        if is_mp3:
            sr = inputs.get("output_sample_rate", 44100)
            proc = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(wav_path),
                    "-ar", str(sr), "-ac", "1",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    str(out_path),
                ],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                return ToolResult(success=False, error=f"ffmpeg WAV->MP3 failed: {proc.stderr}")
            wav_path.unlink(missing_ok=True)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": inputs.get("model", "F5TTS_v1_Base"),
                "ref_audio": str(ref_audio),
                "text_length": len(inputs["text"]),
                "output": str(out_path),
                "format": "mp3" if is_mp3 else "wav",
            },
            artifacts=[str(out_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=inputs.get("seed", 42),
            model=inputs.get("model", "F5TTS_v1_Base"),
        )
