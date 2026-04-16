"""ComfyUI image generation via a local or remote ComfyUI server.

Default workflow: FLUX 2 Dev (NVFP4) with Mistral text encoder.
Supports custom workflows via the ``workflow_json`` input.
"""

from __future__ import annotations

import json
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
from tools._comfyui.client import ComfyUIClient, ComfyUIError

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"


class ComfyUIImage(BaseTool):
    name = "comfyui_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked at runtime via server health
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "See https://github.com/comfyanonymous/ComfyUI for setup."
    )
    agent_skills = []

    capabilities = ["text_to_image"]
    supports = {
        "seed": True,
        "custom_size": True,
        "custom_workflow": True,
        "offline": True,
    }
    best_for = [
        "local GPU generation without API costs",
        "Blackwell / DGX Spark hardware where diffusers is unsupported",
        "full control over sampling via custom ComfyUI workflows",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "CPU-only machines",
    ]
    fallback = "flux_image"
    fallback_tools = ["flux_image", "local_diffusion", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt for image generation"},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "steps": {"type": "integer", "default": 20},
            "guidance": {"type": "number", "default": 3.5},
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the image"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON (overrides default)",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "steps", "seed"]
    side_effects = ["writes image file to output_path"]
    user_visible_verification = ["Inspect generated image for quality and prompt adherence"]

    def __init__(self) -> None:
        self._client = ComfyUIClient()

    def get_status(self) -> ToolStatus:
        if self._client.is_available():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("steps", 20)) * 1.5

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._client.is_available():
            return ToolResult(
                success=False,
                error="ComfyUI server not reachable. " + self.install_instructions,
            )

        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)
        steps = inputs.get("steps", 20)
        guidance = inputs.get("guidance", 3.5)
        output_path = Path(inputs.get("output_path", f"comfyui_image_{seed}.png"))

        try:
            if inputs.get("workflow_json"):
                workflow = json.loads(inputs["workflow_json"])
            else:
                workflow = ComfyUIClient.load_workflow(_WORKFLOWS / "flux2-txt2img.json")
                workflow = ComfyUIClient.patch_workflow(workflow, {
                    "4": {"text": inputs["prompt"]},
                    "5": {"guidance": guidance},
                    "6": {"width": width, "height": height, "batch_size": 1},
                    "7": {"noise_seed": seed},
                    "10": {"steps": steps, "width": width, "height": height},
                    "13": {"filename_prefix": output_path.stem},
                })

            paths = self._client.generate(
                workflow, output_node="13", dest=output_path, timeout=600,
            )

        except ComfyUIError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"ComfyUI image generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": "flux2-dev-nvfp4",
                "prompt": inputs["prompt"],
                "width": width,
                "height": height,
                "steps": steps,
                "guidance": guidance,
                "output": str(paths[0]),
                "format": "png",
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model="flux2-dev-nvfp4",
        )
