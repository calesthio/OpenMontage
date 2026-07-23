"""Showcase card tool wrapping FFmpeg.

Creates a presentation-ready 9:16 card from a source video: letterboxes
the content, adds a bold title at the top, a subtitle description at the
bottom, and a dark background.  Designed for Instagram Reels / TikTok
showcase segments.
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


class ShowcaseCard(BaseTool):
    name = "showcase_card"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg", "video-toolkit"]

    capabilities = ["create_showcase_card"]

    input_schema = {
        "type": "object",
        "required": ["input_path", "output_path", "title"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to the source video.",
            },
            "output_path": {
                "type": "string",
                "description": "Path for the output showcase card video.",
            },
            "title": {
                "type": "string",
                "description": "Bold title text displayed at the top of the card.",
            },
            "subtitle": {
                "type": "string",
                "default": "",
                "description": "Subtitle text displayed at the bottom of the card.",
            },
            "output_width": {
                "type": "integer",
                "default": 1080,
                "description": "Output width in pixels.",
            },
            "output_height": {
                "type": "integer",
                "default": 1920,
                "description": "Output height in pixels.",
            },
            "background_color": {
                "type": "string",
                "default": "0x0A0F1A",
                "description": "Background color in hex (FFmpeg format, e.g. 0x0A0F1A).",
            },
            "title_font": {
                "type": "string",
                "default": "segoeuib.ttf",
                "description": "Font file for the title. Uses system font lookup.",
            },
            "title_font_size": {
                "type": "integer",
                "default": 52,
                "description": "Font size for the title.",
            },
            "subtitle_font_size": {
                "type": "integer",
                "default": 28,
                "description": "Font size for the subtitle.",
            },
            "title_color": {
                "type": "string",
                "default": "white",
                "description": "Title text color.",
            },
            "watermark": {
                "type": "string",
                "default": "",
                "description": "Optional watermark text overlaid on the video (e.g. brand name).",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["input_path", "title", "subtitle"]
    side_effects = ["writes showcase card video to output_path"]
    user_visible_verification = [
        "Play output and verify title, subtitle, and video are positioned correctly",
        "Verify the video content is fully visible (not cropped)",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = inputs["input_path"]
        output_path = inputs["output_path"]
        title = inputs["title"]
        subtitle = inputs.get("subtitle", "")
        out_w = inputs.get("output_width", 1080)
        out_h = inputs.get("output_height", 1920)
        bg_color = inputs.get("background_color", "0x0A0F1A")
        title_font = inputs.get("title_font", "segoeuib.ttf")
        title_font_size = inputs.get("title_font_size", 52)
        subtitle_font_size = inputs.get("subtitle_font_size", 28)
        title_color = inputs.get("title_color", "white")
        watermark = inputs.get("watermark", "")

        if not Path(input_path).exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        start = time.time()

        # Get source dimensions
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            input_path,
        ]
        probe_out = self.run_command(probe_cmd).stdout.strip()
        src_w, src_h = [int(x.strip()) for x in probe_out.split(",")[:2]]

        # Calculate letterbox dimensions — fit source into output width,
        # center vertically in the frame.
        scale_factor = out_w / src_w
        scaled_h = int(src_h * scale_factor)
        # Ensure even dimensions
        scaled_h = scaled_h if scaled_h % 2 == 0 else scaled_h + 1
        pad_y = (out_h - scaled_h) // 2

        # Build filter chain
        filters = [
            f"scale={out_w}:{scaled_h}",
            f"pad={out_w}:{out_h}:0:{pad_y}:color={bg_color}",
        ]

        # Title text at top
        title_escaped = title.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{title_escaped}'"
            f":fontfile='{title_font}'"
            f":fontsize={title_font_size}"
            f":fontcolor={title_color}"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=60"
        )

        # Subtitle text at bottom
        if subtitle:
            sub_escaped = subtitle.replace("'", "\\'").replace(":", "\\:")
            filters.append(
                f"drawtext=text='{sub_escaped}'"
                f":fontfile='segoeui.ttf'"
                f":fontsize={subtitle_font_size}"
                f":fontcolor=white@0.85"
                f":x=(w-text_w)/2:y=h-100"
            )

        # Watermark centered on video
        if watermark:
            wm_escaped = watermark.replace("'", "\\'").replace(":", "\\:")
            filters.append(
                f"drawtext=text='{wm_escaped}'"
                f":fontfile='segoeui.ttf'"
                f":fontsize=36"
                f":fontcolor=white@0.3"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
            )

        vf = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]

        try:
            self.run_command(cmd)
        except Exception as e:
            return ToolResult(success=False, error=f"FFmpeg failed: {e}")

        if not Path(output_path).exists():
            return ToolResult(success=False, error="No output produced")

        elapsed = round(time.time() - start, 2)

        return ToolResult(
            success=True,
            data={
                "output": output_path,
                "source_resolution": f"{src_w}x{src_h}",
                "output_resolution": f"{out_w}x{out_h}",
                "title": title,
                "subtitle": subtitle,
                "letterbox_y_offset": pad_y,
            },
            artifacts=[output_path],
            duration_seconds=elapsed,
        )
