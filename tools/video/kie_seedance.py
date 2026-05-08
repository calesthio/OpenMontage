"""Seedance 2 / Seedance 2 Fast video generation via KIE.AI.

Alternative gateway to the existing fal.ai-based `seedance_video` tool.
Uses KIE_AI_API_KEY instead of FAL_KEY.

Reference: ~/.claude/projects/-Users-abalioglu/memory/reference_kieai_models.md
- bytedance/seedance-2 — duration 4-15s, aspect 9:16/16:9/1:1/adaptive,
  first_frame_url (i2v), reference_image_urls (max 9), generate_audio,
  web_search (must be false)
- bytedance/seedance-2-fast — same params, faster/cheaper, for tests/sample renders

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


class KIESeedance(BaseTool):
    name = "kie_seedance"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kie:bytedance_seedance"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set KIE_AI_API_KEY (https://kie.ai)."
    agent_skills = ["seedance-2-0", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "native_audio": True,
        "multi_shot": True,
        "lip_sync_from_quoted_dialogue": True,
        "character_identity_consistency": True,
    }
    best_for = [
        "premium cinematic clips with multi-shot identity persistence",
        "trailer/teaser/hype-edit beats",
        "lip-sync from prompt-quoted dialogue (`Character says: \"...\"` pattern)",
        "reference-conditioned generation — up to 9 ref images",
    ]
    not_good_for = [
        "cheap b-roll (use kling_video or pexels_video for cost)",
        "4+ simultaneous actions in one shot (split to multi-shot)",
        "readable text/logos inside the clip (handle text in Remotion overlay)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "200-400 words for hero shots; 80-150 for inserts"},
            "model": {
                "type": "string",
                "enum": ["bytedance/seedance-2", "bytedance/seedance-2-fast"],
                "default": "bytedance/seedance-2-fast",
                "description": "Use fast for samples/previews/cost-capped; standard for hero/multi-shot/camera-heavy.",
            },
            "duration": {"type": "integer", "default": 5, "minimum": 4, "maximum": 15},
            "aspect_ratio": {
                "type": "string",
                "enum": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                "default": "9:16",
            },
            "resolution": {"type": "string", "enum": ["480p", "720p"], "default": "720p"},
            "first_frame_url": {
                "type": "string",
                "description": "i2v starting frame (URL or local path — local auto-uploaded). Mutually exclusive with reference_image_urls.",
            },
            "last_frame_url": {"type": "string", "description": "Optional last-frame anchor."},
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 9,
                "description": "Multi-ref mode (up to 9). Mutually exclusive with first_frame_url.",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "seed": {"type": "integer"},
            "output_path": {"type": "string", "default": "seedance_output.mp4"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=200, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "5xx"])
    idempotency_key_fields = [
        "prompt", "model", "duration", "aspect_ratio", "resolution",
        "first_frame_url", "last_frame_url", "reference_image_urls", "seed",
    ]
    side_effects = ["calls KIE.AI", "writes video file to output_path"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if kie_client.is_configured() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # KIE pricing approximations (2026):
        #   seedance-2 standard: ~$0.30/s
        #   seedance-2-fast:     ~$0.24/s
        model = inputs.get("model", "bytedance/seedance-2-fast")
        duration = float(inputs.get("duration", 5))
        rate = 0.30 if model == "bytedance/seedance-2" else 0.24
        return round(rate * duration, 3)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="KIE_AI_API_KEY not set. " + self.install_instructions)

        start = time.time()
        try:
            output_path = Path(inputs.get("output_path", "seedance_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            payload: dict[str, Any] = {
                "prompt": inputs["prompt"],
                "duration": int(inputs.get("duration", 5)),
                "aspect_ratio": inputs.get("aspect_ratio", "9:16"),
                "resolution": inputs.get("resolution", "720p"),
                "generate_audio": bool(inputs.get("generate_audio", True)),
                "web_search": False,  # mandatory for KIE — see memory/reference_kieai_models.md
            }
            if "seed" in inputs:
                payload["seed"] = int(inputs["seed"])

            # Resolve i2v / multi-ref (mutually exclusive)
            first_frame = inputs.get("first_frame_url")
            ref_imgs = inputs.get("reference_image_urls") or []
            if first_frame and ref_imgs:
                return ToolResult(
                    success=False,
                    error="seedance: first_frame_url and reference_image_urls are mutually exclusive — pick one",
                )
            if first_frame:
                payload["first_frame_url"] = kie_client.maybe_upload(first_frame)
                if inputs.get("last_frame_url"):
                    payload["last_frame_url"] = kie_client.maybe_upload(inputs["last_frame_url"])
            elif ref_imgs:
                payload["reference_image_urls"] = [kie_client.maybe_upload(u) for u in ref_imgs[:9]]

            model = inputs.get("model", "bytedance/seedance-2-fast")
            record = kie_client.run_unified(model, payload, max_wait_s=900)  # 15min for full quality
            urls = kie_client.extract_result_urls(record)
            if not urls:
                return ToolResult(success=False, error=f"Seedance returned no result URLs: {record}")

            kie_client.download_to(urls[0], output_path)

            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "duration_s": payload["duration"],
                    "aspect_ratio": payload["aspect_ratio"],
                    "resolution": payload["resolution"],
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
            return ToolResult(success=False, error=f"KIE Seedance: {exc}", duration_seconds=round(time.time() - start, 2))
        except Exception as exc:
            return ToolResult(success=False, error=f"KIE Seedance unexpected: {exc}", duration_seconds=round(time.time() - start, 2))
