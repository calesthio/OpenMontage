"""Background removal tool wrapping rembg.

Removes backgrounds from images using the rembg library (U2Net models).
Outputs transparent PNGs or composites onto a custom background color.
Supports local execution via rembg and optionally cloud APIs.
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
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class BgRemove(BaseTool):
    name = "bg_remove"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "rembg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["python:rembg", "python:PIL"]
    install_instructions = (
        "pip install rembg       # CPU mode\n"
        "pip install rembg[gpu]  # GPU mode (requires CUDA + onnxruntime-gpu)"
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "background_removal",
        "alpha_matte",
        "batch_processing",
        "custom_background",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to image or video frame",
            },
            "output_path": {
                "type": "string",
                "description": "Output path; defaults to {stem}_nobg.png",
            },
            "model": {
                "type": "string",
                "enum": ["u2net", "u2net_human_seg", "isnet-general-use"],
                "default": "u2net",
            },
            "bg_color": {
                "type": "string",
                "description": "Replacement background color hex (e.g. #00FF00). Transparent if not set.",
            },
            "alpha_matting": {
                "type": "boolean",
                "default": False,
                "description": "Use alpha matting for finer edges",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=500
    )

    idempotency_key_fields = ["input_path", "model", "bg_color", "alpha_matting"]
    side_effects = ["writes background-removed image to output_path"]
    user_visible_verification = [
        "Inspect output for clean edges around the subject",
        "Verify transparency or background color is applied correctly",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import rembg  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_nobg").with_suffix(".png")))
        )
        model_name = inputs.get("model", "u2net")
        bg_color = inputs.get("bg_color")
        alpha_matting = inputs.get("alpha_matting", False)

        try:
            import rembg
        except ImportError:
            return ToolResult(
                success=False,
                error="rembg is not installed. Run: pip install rembg",
            )

        try:
            from PIL import Image
        except ImportError:
            return ToolResult(
                success=False,
                error="Pillow is not installed. Run: pip install Pillow",
            )

        start = time.time()

        input_image = Image.open(input_path)

        result_image = rembg.remove(
            input_image,
            session=rembg.new_session(model_name),
            alpha_matting=alpha_matting,
        )

        # Composite onto a colored background if requested
        if bg_color:
            hex_color = bg_color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            background = Image.new("RGBA", result_image.size, (r, g, b, 255))
            background.paste(result_image, mask=result_image.split()[3])
            result_image = background.convert("RGB")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_image.save(str(output_path))

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "input": str(input_path),
                "output": str(output_path),
                "model": model_name,
                "alpha_matting": alpha_matting,
                "bg_color": bg_color,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )
