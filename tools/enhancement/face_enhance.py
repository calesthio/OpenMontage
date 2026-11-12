"""Face enhancement tool wrapping FFmpeg filters.

Applies skin smoothing, sharpening, and lighting correction presets
to talking-head footage. All presets are FFmpeg filter chains — no GPU
or external models required.
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


# Named presets mapping to FFmpeg filter chains
PRESETS = {
    "soft_skin": {
        "description": "Gentle skin smoothing while preserving edges",
        "vf": "smartblur=lr=1.0:ls=-0.5:lt=-3.0:cr=0.5:cs=-0.5:ct=-3.0",
    },
    "sharpen": {
        "description": "Edge sharpening for crisp detail",
        "vf": "unsharp=5:5:1.0:5:5:0.0",
    },
    "sharpen_light": {
        "description": "Subtle sharpening for soft cameras",
        "vf": "unsharp=3:3:0.5:3:3:0.0",
    },
    "brighten": {
        "description": "Lift shadows and midtones for poorly lit footage",
        "vf": "curves=all='0/0 0.25/0.35 0.5/0.55 0.75/0.8 1/1'",
    },
    "contrast_boost": {
        "description": "Add punch with an S-curve contrast adjustment",
        "vf": "curves=all='0/0 0.25/0.20 0.5/0.5 0.75/0.80 1/1'",
    },
    "warm": {
        "description": "Warm skin tones — slight orange shift",
        "vf": "colorbalance=rs=0.05:gs=0.0:bs=-0.05:rm=0.05:gm=0.0:bm=-0.03",
    },
    "cool": {
        "description": "Cool tones — slight blue shift",
        "vf": "colorbalance=rs=-0.03:gs=0.0:bs=0.05:rm=-0.02:gm=0.0:bm=0.03",
    },
    "denoise": {
        "description": "Temporal noise reduction for grainy footage",
        "vf": "hqdn3d=4:3:6:4",
    },
    "talking_head_standard": {
        "description": "Combined preset: skin smoothing + sharpen edges + warm skin tones",
        "vf": (
            "smartblur=lr=1.0:ls=-0.5:lt=-3.0:cr=0.5:cs=-0.5:ct=-3.0,"
            "unsharp=5:5:0.6:5:5:0.0,"
            "colorbalance=rs=0.06:gs=0.01:bs=-0.04:rm=0.04:gm=0.01:bm=-0.03"
        ),
    },
}


class FaceEnhance(BaseTool):
    name = "face_enhance"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "enhancement"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg"]

    capabilities = [
        "skin_smoothing",
        "sharpening",
        "lighting_correction",
        "color_balance",
        "denoise",
        "preset_chain",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "preset": {
                "type": "string",
                "enum": list(PRESETS.keys()),
                "default": "talking_head_standard",
            },
            "presets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Apply multiple presets in sequence",
            },
            "custom_vf": {
                "type": "string",
                "description": "Custom FFmpeg video filter string (advanced)",
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 20},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=2000)
    idempotency_key_fields = [
        "input_path", "preset", "presets", "custom_vf",
        "codec", "crf",
    ]
    side_effects = ["writes enhanced video to output_path"]
    user_visible_verification = [
        "Compare enhanced output with original side-by-side",
        "Verify skin texture is natural, not plastic",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_enhanced")))
        )
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 20)

        # Build filter chain
        vf = self._build_filter(inputs)
        if not vf:
            return ToolResult(success=False, error="No preset, presets, or custom_vf specified")

        start = time.time()

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "copy",
            str(output_path),
        ]

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
                "filter": vf,
                "preset": inputs.get("preset"),
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _build_filter(self, inputs: dict[str, Any]) -> str:
        if "custom_vf" in inputs:
            return inputs["custom_vf"]

        if "presets" in inputs:
            chains = []
            for name in inputs["presets"]:
                if name not in PRESETS:
                    continue
                chains.append(PRESETS[name]["vf"])
            return ",".join(chains)

        preset_name = inputs.get("preset", "talking_head_standard")
        preset = PRESETS.get(preset_name)
        if preset:
            return preset["vf"]
        return ""

    @staticmethod
    def list_presets() -> dict[str, str]:
        """Return available presets and their descriptions."""
        return {name: p["description"] for name, p in PRESETS.items()}
