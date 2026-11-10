"""Local Talking-Head Presenter Provider with Graceful Degradation."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

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


class LocalTalkingHeadProvider(BaseTool):
    name = "local_talking_head"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    capability = "avatar"
    provider = "local_talking_head"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []
    agent_skills = ["ffmpeg"]

    capabilities = [
        "photo_to_talking_head",
        "presenter_fallback",
        "graceful_degradation",
    ]

    supports = {
        "offline": True,
        "graceful_fallback": True,
        "mps": False,
        "cuda": False,
    }

    best_for = [
        "graceful degradation of presenter scenes on Apple Silicon Mac",
        "hybrid visual-first tutorial production without paid avatar services",
    ]

    input_schema = {
        "type": "object",
        "required": ["audio_path"],
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to face portrait or presenter image",
            },
            "audio_path": {
                "type": "string",
                "description": "Path to driving speech audio file",
            },
            "output_path": {
                "type": "string",
                "description": "Path to output video file",
            },
            "scene_title": {
                "type": "string",
                "description": "Title of the scene for fallback graphic generation",
            },
            "fallback_to_visuals": {
                "type": "boolean",
                "default": True,
                "description": "Whether to gracefully fallback to a visual scene if avatar model is infeasible",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=100, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0)
    idempotency_key_fields = ["image_path", "audio_path", "fallback_to_visuals"]
    side_effects = ["writes fallback visual plan or video"]
    user_visible_verification = [
        "Verify presenter_status is reported clearly (skipped_unavailable)",
        "Check that visual fallback scenes render with proper narration audio and captions",
    ]

    def get_status(self) -> ToolStatus:
        """Always available as a pipeline-safe degradation adapter."""
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        audio_path_str = str(inputs.get("audio_path", "")).strip()
        if not audio_path_str:
            return ToolResult(success=False, error="audio_path must be provided")

        audio_path = Path(audio_path_str)
        if not audio_path.is_file():
            return ToolResult(success=False, error=f"Audio file not found: {audio_path}")

        image_path_str = inputs.get("image_path")
        output_path_str = inputs.get("output_path", "presenter_scene.mp4")
        fallback_to_visuals = bool(inputs.get("fallback_to_visuals", True))

        # Check for genuine local CUDA avatar environment
        has_cuda_env = bool(os.environ.get("SADTALKER_PATH") and os.environ.get("CUDA_VISIBLE_DEVICES"))

        if has_cuda_env:
            # If an explicit CUDA environment is provisioned, attempt genuine generation
            try:
                from tools.avatar.talking_head import TalkingHead
                th = TalkingHead()
                if th.get_status() == ToolStatus.AVAILABLE:
                    return th.execute(inputs)
            except Exception as exc:
                if not fallback_to_visuals:
                    return ToolResult(success=False, error=f"Avatar generation failed: {exc}")

        # Graceful degradation path documented in Phase 4 benchmark
        elapsed = round(time.time() - started, 2)
        return ToolResult(
            success=True,
            data={
                "presenter_status": "skipped_unavailable",
                "reason": (
                    "Apple Silicon M6 local avatar infeasibility documented in Phase 4: "
                    "Local talking head models (SadTalker, MuseTalk, Wav2Lip) require CUDA, "
                    "face3d C++ compilation fails on ARM64 macOS, and checkpoints carry CC BY-NC restrictions. "
                    "Gracefully degraded to narration-led visual scene."
                ),
                "fallback_action": "elevate_visual_scene",
                "recommended_cut_type": "stat_card" if "stat" in str(inputs.get("scene_title", "")).lower() else "text_card",
                "audio_path": str(audio_path),
                "image_path": image_path_str,
                "output_video": None,
            },
            artifacts=[],
            duration_seconds=elapsed,
            cost_usd=0.0,
        )
