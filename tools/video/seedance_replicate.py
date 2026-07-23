"""Seedance 2.0 (ByteDance) video generation via Replicate.

Replicate hosts ByteDance's published Seedance 2.0 models:
  - bytedance/seedance-2.0        (standard)
  - bytedance/seedance-2.0-fast   (fast tier)

Same model family as the fal.ai path (tools/video/seedance_video.py) —
if you have both FAL_KEY and REPLICATE_API_TOKEN the scoring engine
deduplicates by provider=seedance and picks whichever registers first.
"""

from __future__ import annotations

import os
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


class SeedanceReplicate(BaseTool):
    name = "seedance_replicate"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "seedance"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set REPLICATE_API_TOKEN to your Replicate API token.\n"
        "  Get one at https://replicate.com/account/api-tokens"
    )
    agent_skills = ["seedance-2-0", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_image": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "lip_sync": True,
        "multi_shot": True,
        "aspect_ratio": True,
        "seed": True,
    }
    best_for = [
        "preferred premium video gen when REPLICATE_API_TOKEN is available",
        "cinematic trailers, teasers, and high-fidelity clips with native synchronized audio",
        "director-level camera control and multi-shot editing in a single generation",
        "lip-sync from quoted dialogue in prompts",
        "consistent character identity across shots",
    ]
    not_good_for = ["offline generation", "budget-constrained projects"]
    fallback_tools = ["seedance_video", "veo_video", "kling_video", "minimax_video"]
    quality_score = 0.95

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": ["standard", "fast"],
                "default": "standard",
                "description": "standard = bytedance/seedance-2.0, fast = bytedance/seedance-2.0-fast",
            },
            "duration": {
                "type": "string",
                "enum": ["auto", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"],
                "default": "5",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p"],
                "default": "720p",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
            },
            "image_url": {
                "type": "string",
                "description": "Start frame image URL for image_to_video",
            },
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration", "seed"]
    side_effects = ["writes video file to output_path", "calls Replicate API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_token(self) -> str | None:
        return os.environ.get("REPLICATE_API_TOKEN")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._get_api_token() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        variant = inputs.get("model_variant", "standard")
        duration = inputs.get("duration", "5")
        secs = 5 if duration == "auto" else int(duration)
        # Replicate bills per-second at roughly the same rate as fal.ai for this model family.
        rate = 0.24 if variant == "fast" else 0.30
        return round(rate * secs, 2)

    def max_cost_usd(self, inputs: dict[str, Any]) -> float | None:
        """Upper bound on a single call's spend.

        duration="auto" lets the MODEL choose the length, so the bound prices
        it at the schema's maximum (15 seconds) instead of the estimate's 5s
        guess. Explicit durations price exactly; the non-fast rate is already
        the dearest and is the estimate's fallback for unknown variants.
        execute() issues one billed request.
        """
        if inputs.get("duration", "5") == "auto":
            return self.estimate_cost({**inputs, "duration": "15"})
        return self.estimate_cost(inputs)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0 if inputs.get("model_variant") == "fast" else 120.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        token = self._get_api_token()
        if not token:
            return ToolResult(
                success=False,
                error="REPLICATE_API_TOKEN not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        variant = inputs.get("model_variant", "standard")
        model_slug = (
            "bytedance/seedance-2.0-fast" if variant == "fast" else "bytedance/seedance-2.0"
        )

        payload_input: dict[str, Any] = {"prompt": inputs["prompt"]}
        if inputs.get("duration") and inputs["duration"] != "auto":
            payload_input["duration"] = int(inputs["duration"])
        if inputs.get("aspect_ratio") and inputs["aspect_ratio"] != "auto":
            payload_input["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload_input["resolution"] = inputs["resolution"]
        if "generate_audio" in inputs:
            payload_input["generate_audio"] = inputs["generate_audio"]
        if inputs.get("seed") is not None:
            payload_input["seed"] = inputs["seed"]
        if inputs.get("operation") == "image_to_video" and inputs.get("image_url"):
            payload_input["image"] = inputs["image_url"]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
        }

        try:
            submit = requests.post(
                f"https://api.replicate.com/v1/models/{model_slug}/predictions",
                headers=headers,
                json={"input": payload_input},
                timeout=90,
            )
            submit.raise_for_status()
            pred = submit.json()

            # Poll until completed (Replicate may return the result synchronously
            # when Prefer: wait is honored, but fall back to polling).
            while pred.get("status") in ("starting", "processing"):
                time.sleep(3)
                get_url = pred.get("urls", {}).get("get")
                if not get_url:
                    return ToolResult(success=False, error="Replicate response missing poll URL")
                poll = requests.get(get_url, headers=headers, timeout=30)
                poll.raise_for_status()
                pred = poll.json()

            status = pred.get("status")
            if status != "succeeded":
                return ToolResult(
                    success=False,
                    error=f"Replicate Seedance 2.0 generation {status}: {pred.get('error')}",
                )

            output = pred.get("output")
            # Replicate returns either a string URL or a list.
            video_url = output[0] if isinstance(output, list) else output
            if not isinstance(video_url, str):
                return ToolResult(success=False, error=f"Unexpected output shape from Replicate: {output!r}")

            video_response = requests.get(video_url, timeout=180)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "seedance_replicate_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Replicate Seedance 2.0 generation failed: {e}",
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "seedance",
                "gateway": "replicate",
                "model": model_slug,
                "prompt": inputs["prompt"],
                "variant": variant,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "resolution": inputs.get("resolution", "720p"),
                "generate_audio": inputs.get("generate_audio", True),
                "seed": pred.get("input", {}).get("seed"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_slug,
        )
