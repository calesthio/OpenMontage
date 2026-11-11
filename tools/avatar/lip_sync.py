"""Lip-sync tool for dubbing and localization.

Syncs lip movements in a video to match a different audio track using
Wav2Lip or MuseTalk models. Primary use case: replace original speech
with translated audio and make the speaker's lips match.
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
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# Model checkpoint filenames by variant
MODEL_CHECKPOINTS = {
    "wav2lip": "wav2lip.pth",
    "wav2lip_gan": "wav2lip_gan.pth",
}


class LipSync(BaseTool):
    name = "lip_sync"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "wav2lip"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:torch", "cmd:ffmpeg"]
    install_instructions = (
        "Option 1: pip install wav2lip (if available)\n"
        "Option 2: Clone https://github.com/Rudrabha/Wav2Lip and set WAV2LIP_PATH env var\n"
        "Requires: PyTorch with CUDA, ffmpeg"
    )

    agent_skills = ["ffmpeg"]

    capabilities = [
        "lip_sync",
        "audio_video_alignment",
        "dubbing_support",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "audio_path"],
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Path to source video with face",
            },
            "audio_path": {
                "type": "string",
                "description": "Path to audio track to sync lips to",
            },
            "output_path": {
                "type": "string",
                "description": "Output video path (defaults to {stem}_lipsync.mp4)",
            },
            "model": {
                "type": "string",
                "enum": ["wav2lip", "wav2lip_gan"],
                "default": "wav2lip",
                "description": "Model variant (gan = higher quality but slower)",
            },
            "face_padding": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 4,
                "maxItems": 4,
                "default": [0, 10, 0, 0],
                "description": "Padding around face crop: [top, bottom, left, right]",
            },
            "resize_factor": {
                "type": "integer",
                "default": 1,
                "description": "Downscale factor for faster processing",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=4096, vram_mb=4096, disk_mb=2000
    )
    idempotency_key_fields = ["video_path", "audio_path", "model", "face_padding", "resize_factor"]
    side_effects = ["writes lip-synced video to output_path"]
    user_visible_verification = [
        "Watch output video to verify lip movements match the new audio",
        "Check face region for visual artifacts or jitter",
    ]

    def get_status(self) -> ToolStatus:
        """Check Wav2Lip availability via env var or Python import."""
        # Check WAV2LIP_PATH environment variable
        wav2lip_path = os.environ.get("WAV2LIP_PATH")
        if wav2lip_path and Path(wav2lip_path).is_dir():
            return ToolStatus.AVAILABLE

        # Fallback: try importing wav2lip as a Python package
        try:
            import wav2lip  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            pass

        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local GPU, free

    def _resolve_wav2lip_dir(self) -> Path | None:
        """Locate the Wav2Lip installation directory."""
        wav2lip_path = os.environ.get("WAV2LIP_PATH")
        if wav2lip_path:
            p = Path(wav2lip_path)
            if p.is_dir():
                return p

        # Fallback: check if wav2lip is importable and find its location
        try:
            import wav2lip
            return Path(wav2lip.__file__).parent
        except (ImportError, AttributeError):
            pass

        return None

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="Wav2Lip not available. " + self.install_instructions,
            )

        video_path = Path(inputs["video_path"]).resolve()
        audio_path = Path(inputs["audio_path"]).resolve()

        if not video_path.exists():
            return ToolResult(success=False, error=f"Video not found: {video_path}")
        if not audio_path.exists():
            return ToolResult(success=False, error=f"Audio not found: {audio_path}")

        output_path = Path(
            inputs.get("output_path", str(video_path.with_stem(f"{video_path.stem}_lipsync")))
        ).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        model_variant = inputs.get("model", "wav2lip")
        face_padding = inputs.get("face_padding", [0, 10, 0, 0])
        resize_factor = inputs.get("resize_factor", 1)

        wav2lip_dir = self._resolve_wav2lip_dir()
        if wav2lip_dir is None:
            return ToolResult(
                success=False,
                error="Could not locate Wav2Lip directory. " + self.install_instructions,
            )

        checkpoint = wav2lip_dir / "checkpoints" / MODEL_CHECKPOINTS[model_variant]
        if not checkpoint.exists():
            return ToolResult(
                success=False,
                error=f"Model checkpoint not found: {checkpoint}",
            )

        inference_script = wav2lip_dir / "inference.py"
        if not inference_script.exists():
            return ToolResult(
                success=False,
                error=f"Inference script not found: {inference_script}",
            )

        start = time.time()

        cmd = [
            "python", str(inference_script),
            "--checkpoint_path", str(checkpoint),
            "--face", str(video_path),
            "--audio", str(audio_path),
            "--outfile", str(output_path),
            "--pads", *[str(p) for p in face_padding],
            "--resize_factor", str(resize_factor),
        ]

        try:
            self.run_command(cmd, timeout=600, cwd=wav2lip_dir)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Lip-sync timed out after 600 seconds")
        except Exception as e:
            return ToolResult(success=False, error=f"Wav2Lip inference failed: {e}")

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"Inference completed but output file missing: {output_path}",
            )

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "video_input": str(video_path),
                "audio_input": str(audio_path),
                "output": str(output_path),
                "model": model_variant,
                "resize_factor": resize_factor,
                "face_padding": face_padding,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
            model=model_variant,
        )
