"""Hero-tier video super-resolution (and optional interpolation) via fal.ai Topaz.

A NEW enhancement provider for VIDEO, alongside the existing RealESRGAN `upscale`
(which does basic frame-by-frame image/video upscale) — it does not replace it.
Topaz Video (via fal) is the SOTA the quality research named for clean upscaling and
frame-rate conversion; use it on HERO clips only (paid, `quality_tier="hero"`), and
keep RealESRGAN for cheap/bulk.

Reports UNAVAILABLE without FAL_KEY (the key the FLUX/video tools already use), so it
never disturbs existing flows and auto-joins the enhancement menu.

Honest caveats from the research:
  - Video upscaling adds real perceived quality on hero shots.
  - Frame interpolation (`target_fps`) is OPT-IN — its viewer benefit for cinematic AI
    footage is unproven and it risks the "soap-opera effect." Leave it off by default.

Self-hosting the open SeedVR2/FlashVSR super-res models on your own GPU is the future
volume play (cheaper at scale); this paid fal path is the reliable hero-tier option now.
The fal endpoint id and request/response fields are the `ponytail:` calibration knobs.
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

# ponytail: confirm the exact fal Topaz video endpoint + params against your fal account.
_FAL_MODEL = "fal-ai/topaz/upscale/video"


class VideoUpscale(BaseTool):
    name = "video_upscale"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "topaz"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via FAL_KEY
    install_instructions = (
        "Set FAL_KEY to your fal.ai API key (same key the FLUX/video tools use):\n"
        "  export FAL_KEY=your_fal_key\n"
        "Uses fal-ai/topaz/upscale/video for hero-tier video super-resolution."
    )
    agent_skills = ["ffmpeg"]

    capabilities = ["video_upscale", "video_super_resolution", "frame_interpolation"]
    supports = {"upscale": True, "fps_conversion": True}
    best_for = [
        "hero-tier video super-resolution (clean detail on final clips)",
        "upscaling AI-generated hero video for the final render",
    ]
    not_good_for = [
        "bulk/draft video (paid, hero-only — use RealESRGAN upscale for cheap)",
        "defaulting frame interpolation on (soap-opera risk; opt-in only)",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string", "description": "Local video to upload+upscale."},
            "video_url": {"type": "string", "description": "Public video URL (used instead of input_path)."},
            "output_path": {"type": "string"},
            "upscale_factor": {
                "type": "integer",
                "enum": [2, 4],
                "default": 2,
            },
            "target_fps": {
                "type": "integer",
                "description": "OPT-IN frame interpolation to this fps (e.g. 60). Off by default — "
                "risks the soap-opera effect on cinematic footage.",
            },
            "model": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["input_path", "video_url", "upscale_factor", "target_fps"]
    side_effects = ["uploads video to fal", "writes upscaled video to output_path", "calls fal.ai API"]
    user_visible_verification = ["Watch the upscaled clip for real added detail and no temporal artifacts"]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.50  # hero-only paid video upscale (Topaz via fal is per-clip pricey)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0

    @staticmethod
    def _build_payload(video_url: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Pure mapping of tool inputs to the fal Topaz-video request (testable)."""
        payload: dict[str, Any] = {
            "video_url": video_url,
            "upscale_factor": inputs.get("upscale_factor", 2),
        }
        if inputs.get("target_fps"):
            payload["target_fps"] = inputs["target_fps"]
        return payload

    @staticmethod
    def _extract_url(data: dict[str, Any]) -> str:
        """fal returns {'video': {'url'}} or {'videos': [{'url'}]}."""
        if isinstance(data.get("video"), dict) and data["video"].get("url"):
            return data["video"]["url"]
        videos = data.get("videos")
        if videos and isinstance(videos, list) and videos[0].get("url"):
            return videos[0]["url"]
        raise RuntimeError(f"No upscaled video URL in fal response: {data}")

    def _upload_video_fal(self, input_path: str, api_key: str) -> str:
        """Upload a local video to fal storage, return its URL (video content types)."""
        import requests

        path = Path(input_path)
        suffix = path.suffix.lower().lstrip(".")
        content_type = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}.get(
            suffix, "video/mp4"
        )
        init = requests.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json={"content_type": content_type, "file_name": path.name},
            timeout=30,
        )
        init.raise_for_status()
        data = init.json()
        put = requests.put(
            data["upload_url"], headers={"Content-Type": content_type}, data=path.read_bytes(), timeout=300
        )
        put.raise_for_status()
        return data["file_url"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error="Video upscale unavailable. " + self.install_instructions)

        video_url = inputs.get("video_url")
        input_path = inputs.get("input_path")
        if not video_url and not (input_path and Path(input_path).exists()):
            return ToolResult(
                success=False,
                error="video_upscale: provide a valid input_path or a video_url.",
            )

        start = time.time()
        model = inputs.get("model") or _FAL_MODEL
        try:
            if not video_url:
                video_url = self._upload_video_fal(input_path, api_key)
            payload = self._build_payload(video_url, inputs)
            resp = requests.post(
                f"https://fal.run/{model}",
                headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=600,  # video upscale is slow; short clips fit the sync window
            )
            resp.raise_for_status()
            out_url = self._extract_url(resp.json())
            dl = requests.get(out_url, timeout=300)
            dl.raise_for_status()
        except Exception as e:  # noqa: BLE001 - surface fal/network failure to the agent
            return ToolResult(success=False, error=f"Video upscale failed: {e}")

        output_path = Path(inputs.get("output_path", "video_upscaled.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(dl.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "output": str(output_path),
                "upscale_factor": inputs.get("upscale_factor", 2),
                "target_fps": inputs.get("target_fps"),
                "format": "mp4",
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=model,
            duration_seconds=round(time.time() - start, 2),
        )
