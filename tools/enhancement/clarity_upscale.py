"""Hero-tier image refinement/upscaling via fal.ai Clarity (diffusion img2img).

A NEW enhancement provider alongside the existing RealESRGAN `upscale` — it does not
replace it. Clarity is a tiled Stable-Diffusion img2img upscaler: unlike the
feed-forward RealESRGAN it *synthesizes* perceptual detail, which looks best on
AI-generated hero shots but can hallucinate. So:

  - Use this for HERO images only (paid, quality_tier="hero").
  - Keep RealESRGAN (`upscale`) for fidelity-critical / text / architectural / bulk work.
  - Default `creativity` (denoise) is kept LOW (0.35) — the research-backed setting that
    adds detail without inventing content. Raise it only when you want reinterpretation.

Backed by the same fal.ai account the app already uses; reports UNAVAILABLE without
FAL_KEY, so it never disturbs existing flows and auto-joins the enhancement menu.
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

_FAL_MODEL = "fal-ai/clarity-upscaler"


class ClarityUpscale(BaseTool):
    name = "clarity_upscale"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "clarity"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC  # diffusion refine — seed-controllable
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via FAL_KEY
    install_instructions = (
        "Set FAL_KEY to your fal.ai API key (same key the FLUX/video tools use):\n"
        "  export FAL_KEY=your_fal_key\n"
        "Uses the fal-ai/clarity-upscaler diffusion upscaler."
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["image_upscale", "image_refine", "detail_enhance"]
    supports = {"seed": True, "creativity_control": True}
    best_for = [
        "hero-tier image refinement (adds perceptual detail beyond RealESRGAN)",
        "polishing AI-generated stills for the final render",
        "diffusion detail synthesis on portraits and textured scenes",
    ]
    not_good_for = [
        "fidelity-critical images with text, logos, or architectural lines (use RealESRGAN)",
        "bulk/draft work — this is paid and hero-only",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "upscale_factor": {
                "type": "number",
                "minimum": 1,
                "maximum": 4,
                "default": 2,
            },
            "creativity": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.35,
                "description": "Denoise strength. Low (~0.35) adds detail faithfully; "
                "high reinterprets and risks hallucination.",
            },
            "resemblance": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 3.0,
                "default": 0.6,
                "description": "How strongly to hold to the source structure.",
            },
            "prompt": {
                "type": "string",
                "default": "",
                "description": "Optional guidance for the refine pass, e.g. 'sharp, detailed, film still'.",
            },
            "seed": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["input_path", "upscale_factor", "creativity", "resemblance", "seed"]
    side_effects = ["uploads image to fal", "writes upscaled image to output_path", "calls fal.ai API"]
    user_visible_verification = [
        "Compare refined output with the original — confirm added detail is faithful, not invented",
    ]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.05  # hero-only paid refine; fal clarity-upscaler ~$0.03-0.05/image

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0

    @staticmethod
    def _build_payload(image_url: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Pure mapping of tool inputs to the fal clarity-upscaler request (testable)."""
        payload: dict[str, Any] = {
            "image_url": image_url,
            "upscale_factor": inputs.get("upscale_factor", 2),
            "creativity": inputs.get("creativity", 0.35),
            "resemblance": inputs.get("resemblance", 0.6),
            "prompt": inputs.get("prompt", ""),
        }
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        return payload

    @staticmethod
    def _extract_url(data: dict[str, Any]) -> str:
        """fal returns either {'image': {'url'}} or {'images': [{'url'}]}."""
        if isinstance(data.get("image"), dict) and data["image"].get("url"):
            return data["image"]["url"]
        images = data.get("images")
        if images and isinstance(images, list) and images[0].get("url"):
            return images[0]["url"]
        raise RuntimeError(f"No upscaled image URL in fal response: {data}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        from tools.video._shared import upload_image_fal

        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error="Clarity upscale unavailable. " + self.install_instructions)

        input_path = inputs.get("input_path")
        if not input_path or not Path(input_path).exists():
            return ToolResult(success=False, error=f"clarity_upscale: input_path not found: {input_path}")

        start = time.time()
        try:
            image_url = upload_image_fal(input_path)
            payload = self._build_payload(image_url, inputs)
            resp = requests.post(
                f"https://fal.run/{_FAL_MODEL}",
                headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            out_url = self._extract_url(resp.json())
            img = requests.get(out_url, timeout=120)
            img.raise_for_status()

            output_path = Path(inputs.get("output_path", "clarity_upscaled.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img.content)
        except Exception as e:  # noqa: BLE001 - surface fal/network failure to the agent
            return ToolResult(success=False, error=f"Clarity upscale failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": _FAL_MODEL,
                "input": str(input_path),
                "output": str(output_path),
                "upscale_factor": inputs.get("upscale_factor", 2),
                "creativity": inputs.get("creativity", 0.35),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            seed=inputs.get("seed"),
            model=_FAL_MODEL,
            duration_seconds=round(time.time() - start, 2),
        )
