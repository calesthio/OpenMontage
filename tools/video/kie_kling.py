"""Kling 3.0 / 2.6 video generation via KIE.AI.

Alternative gateway to the existing fal.ai-based `kling_video` tool.
Uses KIE_AI_API_KEY instead of FAL_KEY.

Reference: ~/.claude/projects/-Users-abalioglu/memory/reference_kieai_models.md
- kling-2.6/image-to-video — duration "5"/"10", sound true/false
- kling-3.0/video — duration 3-15s, multi_shots, multi_prompt

Best for cinematic B-roll, fluid camera, mid-tier UGC product replacement.
Cheaper than Seedance (~$0.08/s vs $0.24-0.30/s).

User added 2026-05-07.
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
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from lib import kie_client


class KIEKling(BaseTool):
    name = "kie_kling"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kie:kling"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set KIE_AI_API_KEY (https://kie.ai)."
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
        "multi_shot": True,        # kling-3.0 only
        "multi_prompt": True,      # kling-3.0 only
    }
    best_for = [
        "cost-effective UGC b-roll and product replacement (~$0.08/s)",
        "fluid camera motion, smooth dolly/push-in shots",
        "mid-tier cinematic where Seedance is overkill",
    ]
    not_good_for = [
        "lip-sync from quoted dialogue (use Seedance or talking-head pipeline)",
        "complex multi-shot identity persistence (Seedance is stronger here)",
        "anamorphic / film grain aesthetics (forbidden words in Kling — see model-cheatsheet.md)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "≤150 words. Avoid: anamorphic, film grain, halation."},
            "model": {
                "type": "string",
                "enum": [
                    "kling-3.0/video",
                    "kling-3.0/image-to-video",
                    "kling-2.6/image-to-video",
                    "kling-2.6/text-to-video",
                ],
                "default": "kling-3.0/video",
            },
            "duration": {
                "type": ["integer", "string"],
                "default": 5,
                "description": "kling-3.0: integer 3-15s. kling-2.6: string '5' or '10'.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["9:16", "16:9", "1:1"],
                "default": "9:16",
            },
            "image_url": {
                "type": "string",
                "description": "i2v start frame (URL or local — local auto-uploaded). Required for image-to-video models.",
            },
            "sound": {"type": "boolean", "default": True, "description": "kling-2.6 only — sound:true/false"},
            "multi_shots": {
                "type": "boolean",
                "default": False,
                "description": "kling-3.0 only — enable multi-shot interpretation",
            },
            "multi_prompt": {
                "type": "array",
                "items": {"type": "string"},
                "description": "kling-3.0 only — sequential prompts for multi-shot beats",
            },
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            "output_path": {"type": "string", "default": "kling_output.mp4"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=200, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "5xx"])
    idempotency_key_fields = [
        "prompt", "model", "duration", "aspect_ratio", "image_url",
        "multi_shots", "multi_prompt", "negative_prompt", "seed",
    ]
    side_effects = ["calls KIE.AI", "writes video file to output_path"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.is_configured() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # KIE Kling pricing ~$0.08/s for 3.0, slightly less for 2.6
        duration = inputs.get("duration", 5)
        try:
            duration_int = int(str(duration))
        except ValueError:
            duration_int = 5
        rate = 0.08 if "3.0" in inputs.get("model", "kling-3.0/video") else 0.07
        return round(rate * duration_int, 3)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="KIE_AI_API_KEY not set. " + self.install_instructions)

        start = time.time()
        try:
            output_path = Path(inputs.get("output_path", "kling_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            model = inputs.get("model", "kling-3.0/video")

            payload: dict[str, Any] = {
                "prompt": inputs["prompt"],
                "duration": inputs.get("duration", 5),
                "aspect_ratio": inputs.get("aspect_ratio", "9:16"),
            }
            if "negative_prompt" in inputs:
                payload["negative_prompt"] = inputs["negative_prompt"]
            if "seed" in inputs:
                payload["seed"] = int(inputs["seed"])

            # Image-to-video models need image_url
            if "image-to-video" in model or "i2v" in model:
                if not inputs.get("image_url"):
                    return ToolResult(success=False, error=f"{model} requires image_url")
                payload["image_url"] = kie_client.maybe_upload(inputs["image_url"])

            # kling-2.6-specific
            if "2.6" in model:
                payload["sound"] = bool(inputs.get("sound", True))
                # 2.6 wants string duration
                payload["duration"] = str(payload["duration"])

            # kling-3.0-specific
            if "3.0" in model:
                if inputs.get("multi_shots"):
                    payload["multi_shots"] = True
                if inputs.get("multi_prompt"):
                    payload["multi_prompt"] = inputs["multi_prompt"]

            record = kie_client.run_unified(model, payload, max_wait_s=900)
            urls = kie_client.extract_result_urls(record)
            if not urls:
                return ToolResult(success=False, error=f"Kling returned no result URLs: {record}")

            kie_client.download_to(urls[0], output_path)

            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "duration": payload["duration"],
                    "aspect_ratio": payload["aspect_ratio"],
                    "output": str(output_path),
                    "all_urls": urls,
                    "format": "mp4",
                },
                artifacts=[str(output_path)],
                model=model,
                cost_usd=self.estimate_cost(inputs),
                duration_seconds=round(time.time() - start, 2),
            )
        except kie_client.KIEError as exc:
            return ToolResult(success=False, error=f"KIE Kling: {exc}", duration_seconds=round(time.time() - start, 2))
        except Exception as exc:
            return ToolResult(success=False, error=f"KIE Kling unexpected: {exc}", duration_seconds=round(time.time() - start, 2))
