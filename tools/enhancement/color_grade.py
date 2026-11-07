"""Color grading tool wrapping FFmpeg LUT and filter chains.

Applies cinematic color grading profiles to video. Supports both
built-in profile presets and external .cube LUT files.
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


# Built-in grading profiles using FFmpeg colorbalance/curves/eq filters
PROFILES = {
    "cinematic_warm": {
        "description": "Warm cinematic look with lifted shadows and orange highlights",
        "vf": (
            "colorbalance=rs=0.08:gs=0.02:bs=-0.05:rh=0.06:gh=0.02:bh=-0.04,"
            "curves=all='0/0.03 0.25/0.22 0.5/0.50 0.75/0.78 1/0.97',"
            "eq=contrast=1.05:saturation=1.1"
        ),
    },
    "cinematic_cool": {
        "description": "Cool teal-and-orange cinematic grade",
        "vf": (
            "colorbalance=rs=-0.02:gs=-0.03:bs=0.08:rh=0.06:gh=-0.02:bh=-0.06,"
            "curves=all='0/0.02 0.25/0.20 0.5/0.48 0.75/0.78 1/0.98',"
            "eq=contrast=1.08:saturation=1.05"
        ),
    },
    "moody_dark": {
        "description": "Crushed blacks, desaturated midtones, dark atmosphere",
        "vf": (
            "curves=all='0/0.05 0.15/0.12 0.5/0.45 0.85/0.82 1/0.95',"
            "eq=contrast=1.12:saturation=0.8:brightness=-0.03"
        ),
    },
    "bright_clean": {
        "description": "Bright, clean look with lifted shadows and vivid color",
        "vf": (
            "curves=all='0/0.05 0.25/0.30 0.5/0.55 0.75/0.80 1/1.0',"
            "eq=contrast=1.0:saturation=1.15:brightness=0.02"
        ),
    },
    "vintage_film": {
        "description": "Faded film look with grain texture and warm tint",
        "vf": (
            # colorbalance takes per-range channel options — rs/gs/bs (shadows),
            # rm/gm/bm (midtones), rh/gh/bh (highlights). "ms" and "mh" are not
            # options at all, so ffmpeg rejected the whole filter chain with
            # "Error applying option 'ms' to filter 'colorbalance'" and this
            # profile could never render. Warm midtones + cooler highlights keep
            # the intended faded-film tint.
            "colorbalance=rs=0.06:gs=0.03:bs=-0.03:rm=0.03:bh=-0.02,"
            "curves=all='0/0.06 0.25/0.25 0.5/0.50 0.75/0.74 1/0.94',"
            "eq=saturation=0.85:contrast=0.95"
        ),
    },
    "high_contrast": {
        "description": "Punchy high-contrast grade for dynamic content",
        "vf": (
            "curves=all='0/0 0.20/0.12 0.5/0.50 0.80/0.88 1/1',"
            "eq=contrast=1.2:saturation=1.1"
        ),
    },
    "neutral": {
        "description": "Minimal correction — normalize levels and light contrast",
        "vf": "eq=contrast=1.02:saturation=1.02:brightness=0.01",
    },
}


class ColorGrade(BaseTool):
    name = "color_grade"
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
        "grade_preset",
        "grade_lut",
        "grade_custom",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "profile": {
                "type": "string",
                "enum": list(PROFILES.keys()),
                "default": "cinematic_warm",
            },
            "lut_path": {
                "type": "string",
                "description": "Path to external .cube LUT file",
            },
            "intensity": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 1.0,
                "description": "Blend intensity: 0 = original, 1 = full grade",
            },
            "custom_vf": {"type": "string"},
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 20},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=2000)
    idempotency_key_fields = ["input_path", "profile", "lut_path", "intensity"]
    side_effects = ["writes graded video to output_path"]
    user_visible_verification = [
        "Compare graded output with original for color accuracy",
        "Verify skin tones look natural, not oversaturated",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_graded")))
        )
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 20)

        vf = self._build_filter(inputs)
        if not vf:
            return ToolResult(success=False, error="No profile, lut_path, or custom_vf specified")

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
                "profile": inputs.get("profile"),
                "lut": inputs.get("lut_path"),
                "intensity": inputs.get("intensity", 1.0),
                "filter": vf,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _build_filter(self, inputs: dict[str, Any]) -> str:
        if "custom_vf" in inputs:
            return inputs["custom_vf"]

        lut_path = inputs.get("lut_path")
        if lut_path and Path(lut_path).exists():
            safe_path = str(Path(lut_path).resolve()).replace("\\", "/").replace(":", "\\:")
            return f"lut3d='{safe_path}'"

        profile_name = inputs.get("profile", "cinematic_warm")
        profile = PROFILES.get(profile_name)
        if not profile:
            return ""

        vf = profile["vf"]

        # Apply intensity blending if < 1.0
        intensity = inputs.get("intensity", 1.0)
        if 0 < intensity < 1.0:
            # Use split + overlay approach: blend graded with original
            vf = (
                f"split[original][tograde];"
                f"[tograde]{vf}[graded];"
                f"[original][graded]blend=all_mode=normal:all_opacity={intensity}"
            )

        return vf

    @staticmethod
    def list_profiles() -> dict[str, str]:
        """Return available profiles and their descriptions."""
        return {name: p["description"] for name, p in PROFILES.items()}
