"""Audio enhancement tool for noise reduction and cleanup.

Provides noise reduction, normalization, and EQ via FFmpeg audio
filters. Optional pedalboard integration for higher-quality
processing when available.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)


PRESETS = {
    "clean_speech": {
        "description": "Noise gate + highpass + compressor + limiter for clean dialogue",
        "af": (
            "highpass=f=80,"
            "lowpass=f=13000,"
            "agate=threshold=0.01:ratio=2:attack=5:release=50,"
            "acompressor=threshold=-20dB:ratio=3:attack=5:release=100,"
            "loudnorm=I=-16:LRA=11:TP=-1.5"
        ),
    },
    "noise_reduce": {
        "description": "Aggressive noise reduction for noisy environments",
        "af": (
            "afftdn=nf=-25:nt=w,"
            "highpass=f=100,"
            "loudnorm=I=-16:LRA=11:TP=-1.5"
        ),
    },
    "normalize_only": {
        "description": "Loudness normalization without other processing",
        "af": "loudnorm=I=-16:LRA=11:TP=-1.5",
    },
    "podcast": {
        "description": "Podcast-style processing: de-ess, compress, normalize",
        "af": (
            "highpass=f=80,"
            "acompressor=threshold=-18dB:ratio=4:attack=5:release=100:makeup=2,"
            "loudnorm=I=-16:LRA=7:TP=-1.5"
        ),
    },
    "broadcast": {
        "description": "Broadcast-standard processing with tight dynamics",
        "af": (
            "highpass=f=80,"
            "lowpass=f=15000,"
            "acompressor=threshold=-24dB:ratio=4:attack=5:release=80:makeup=3,"
            "alimiter=limit=0.95:attack=1:release=10,"
            "loudnorm=I=-24:LRA=7:TP=-2"
        ),
    },
    "voice_clarity": {
        "description": "Boost vocal presence with EQ and light compression",
        "af": (
            "highpass=f=80,"
            "equalizer=f=200:t=q:w=1.5:g=-3,"
            "equalizer=f=3000:t=q:w=1.0:g=3,"
            "equalizer=f=5000:t=q:w=1.5:g=2,"
            "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=100,"
            "loudnorm=I=-16:LRA=11:TP=-1.5"
        ),
    },
}


class AudioEnhance(BaseTool):
    name = "audio_enhance"
    version = "0.1.1"
    tier = ToolTier.CORE
    capability = "audio_processing"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg", "elevenlabs"]

    capabilities = [
        "noise_reduction",
        "normalization",
        "compression",
        "eq",
        "speech_cleanup",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {
                "type": "string",
                "description": (
                    "Explicit output filename. Omitted audio paths select a container for "
                    "AAC, MP3, FLAC, Opus, Vorbis or PCM s16le. WebM video with a "
                    "non-WebM audio codec uses Matroska. Other defaults retain the "
                    "input suffix; provide output_path for other codec/container pairs."
                ),
            },
            "preset": {
                "type": "string",
                "enum": list(PRESETS.keys()),
                "default": "clean_speech",
            },
            "custom_af": {
                "type": "string",
                "description": "Custom FFmpeg audio filter string",
            },
            "audio_codec": {"type": "string", "default": "aac"},
            "audio_bitrate": {"type": "string", "default": "192k"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500)
    idempotency_key_fields = [
        "input_path", "preset", "custom_af", "audio_codec", "audio_bitrate",
    ]
    side_effects = ["writes enhanced audio/video to output_path"]
    user_visible_verification = [
        "Listen to enhanced audio and compare with original",
        "Verify speech is clear without artifacts or pumping",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        audio_codec = inputs.get("audio_codec", "aac")
        is_video = input_path.suffix.lower() in {".mp4", ".mkv", ".avi", ".mov", ".webm"}
        default_output = input_path.with_stem(f"{input_path.stem}_enhanced")
        # Pick a muxable audio container rather than inheriting the source
        # suffix after a codec change. Keep unknown encoders caller-directed.
        audio_suffixes = {
            "aac": ".m4a", "mp3": ".mp3", "libmp3lame": ".mp3",
            "flac": ".flac", "opus": ".ogg", "libopus": ".ogg",
            "vorbis": ".ogg", "libvorbis": ".ogg", "pcm_s16le": ".wav",
        }
        if not is_video and audio_codec in audio_suffixes:
            default_output = default_output.with_suffix(audio_suffixes[audio_codec])
        elif is_video and input_path.suffix.lower() == ".webm" and audio_codec not in {
            "opus", "libopus", "vorbis", "libvorbis",
        }:
            default_output = default_output.with_suffix(".mkv")
        output_path = Path(inputs.get("output_path", str(default_output)))
        audio_bitrate = inputs.get("audio_bitrate", "192k")

        af = inputs.get("custom_af")
        if not af:
            preset_name = inputs.get("preset", "clean_speech")
            preset = PRESETS.get(preset_name)
            if not preset:
                return ToolResult(success=False, error=f"Unknown preset: {preset_name}")
            af = preset["af"]

        start = time.time()

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", af,
        ]
        if is_video:
            cmd.extend(["-c:v", "copy"])
        cmd.extend(["-c:a", audio_codec, "-b:a", audio_bitrate])
        cmd.append(str(output_path))

        try:
            self.run_command(cmd)
        except Exception as e:
            return ToolResult(success=False, error=f"FFmpeg failed: {e}")

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "input": str(input_path),
                "output": str(output_path),
                "preset": inputs.get("preset"),
                "filter": af,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    @staticmethod
    def list_presets() -> dict[str, str]:
        """Return available presets and their descriptions."""
        return {name: p["description"] for name, p in PRESETS.items()}
