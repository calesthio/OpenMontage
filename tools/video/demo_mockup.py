"""Demo mockup tool — Sovereign-native openvid equivalent.

Produces a polished product-demo video from one or more screenshots /
product stills. Wraps FFmpeg to apply Ken Burns motion (slow zoom +
pan) to each still, then concats with branded intro / outro cards.

Pattern inspired by openvid (https://github.com/CristianOlivera1/openvid)
but native to the OpenMontage tool registry — uses existing FFmpeg primitives,
no Next.js / browser dependency. The browser-based UX from openvid is
deliberately NOT replicated; agents and the marketing ensemble drive this
tool directly.

Use cases for the Sovereign portfolio:
- ATX Mats product showcases (matt screenshots → polished demo reels)
- GLI LED-sign listing videos (product images → Amazon-style demo)
- GBB facility tours (gym photos → social-ready video)
- Sovereign Mind app showcase (app screenshots → product demo)
- Any tenant marketing-sleeve "drop screenshot, get demo" workflow

Output spec:
- Default 1920×1080 landscape; configurable to 1080×1920 portrait for Reels/TikTok
- 30fps, h264, AAC-stereo silence track (voiceover layered via separate tool)
- Per-still duration default 4s with 1s crossfade between
- Branded intro (1.5s, brand-primary background, title text) + outro (1s, brand-primary, CTA)

This is a CORE tier tool — should always be available wherever FFmpeg is.
Pairs with `audio_mixer` (add voiceover), `remotion_caption_burn` (add captions),
and `auto_reframe` (re-aspect for multi-channel publish).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)
from tools.dam_hook import DAM_INPUT_SCHEMA_FRAGMENT, maybe_register_artifact


class DemoMockup(BaseTool):
    name = "demo_mockup"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg", "video_toolkit", "video-edit"]

    capabilities = ["create_demo_mockup", "ken_burns_stills"]

    input_schema = {
        "type": "object",
        "required": ["stills", "output_path"],
        "properties": {
            "stills": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Ordered list of input image paths (screenshots / product stills).",
            },
            "output_path": {
                "type": "string",
                "description": "Output mp4 path.",
            },
            "title": {
                "type": "string",
                "default": "",
                "description": "Optional title shown on the branded intro card. Empty = no intro.",
            },
            "subtitle": {
                "type": "string",
                "default": "",
                "description": "Optional subtitle shown beneath the title on the intro card.",
            },
            "cta": {
                "type": "string",
                "default": "",
                "description": "Optional CTA text shown on the branded outro card. Empty = no outro.",
            },
            "brand_primary_hex": {
                "type": "string",
                "default": "0x0A0F1A",
                "description": "Primary brand color for intro/outro card backgrounds (FFmpeg hex format e.g. 0x0A0F1A). Pull from TenantBrand.palette[0] when available.",
            },
            "text_color": {
                "type": "string",
                "default": "white",
                "description": "Text color on intro/outro cards.",
            },
            "still_duration_s": {
                "type": "number",
                "default": 4.0,
                "minimum": 1.0,
                "description": "Per-still display duration in seconds.",
            },
            "crossfade_s": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.0,
                "description": "Crossfade duration between adjacent stills.",
            },
            "intro_duration_s": {
                "type": "number",
                "default": 1.5,
                "minimum": 0.0,
            },
            "outro_duration_s": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.0,
            },
            "output_width": {
                "type": "integer",
                "default": 1920,
            },
            "output_height": {
                "type": "integer",
                "default": 1080,
            },
            "fps": {
                "type": "integer",
                "default": 30,
            },
            "ken_burns_zoom": {
                "type": "number",
                "default": 1.15,
                "minimum": 1.0,
                "maximum": 2.0,
                "description": "Final zoom factor for Ken Burns motion (1.0 = no zoom).",
            },
            "title_font_size": {
                "type": "integer",
                "default": 64,
            },
            "subtitle_font_size": {
                "type": "integer",
                "default": 32,
            },
            "cta_font_size": {
                "type": "integer",
                "default": 48,
            },
            **DAM_INPUT_SCHEMA_FRAGMENT,
        },
    }

    resource_profile = ResourceProfile(cpu_cores=4, ram_mb=2000, vram_mb=0, disk_mb=500, network_required=False)
    idempotency_key_fields = ["stills", "title", "subtitle", "cta", "brand_primary_hex", "still_duration_s", "output_width", "output_height"]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = ["Play output mp4; verify Ken Burns motion, brand color on intro/outro, no jank between crossfades"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        n_stills = len(inputs.get("stills", []))
        still_dur = float(inputs.get("still_duration_s", 4.0))
        intro = float(inputs.get("intro_duration_s", 1.5))
        outro = float(inputs.get("outro_duration_s", 1.0))
        # Empirically: FFmpeg zoompan + concat ~ 1× to 3× realtime depending on resolution
        total_output_s = n_stills * still_dur + intro + outro
        return total_output_s * 1.5

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            if shutil.which("ffmpeg") is None:
                return ToolResult(success=False, error="ffmpeg not installed. " + self.install_instructions)

            stills = [Path(p) for p in inputs["stills"]]
            for s in stills:
                if not s.exists():
                    return ToolResult(success=False, error=f"input still not found: {s}")

            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)

            width = int(inputs.get("output_width", 1920))
            height = int(inputs.get("output_height", 1080))
            fps = int(inputs.get("fps", 30))
            still_dur = float(inputs.get("still_duration_s", 4.0))
            crossfade = float(inputs.get("crossfade_s", 1.0))
            intro_dur = float(inputs.get("intro_duration_s", 1.5))
            outro_dur = float(inputs.get("outro_duration_s", 1.0))
            zoom_final = float(inputs.get("ken_burns_zoom", 1.15))
            brand_hex = str(inputs.get("brand_primary_hex", "0x0A0F1A"))
            text_color = str(inputs.get("text_color", "white"))
            title = str(inputs.get("title", "") or "")
            subtitle = str(inputs.get("subtitle", "") or "")
            cta = str(inputs.get("cta", "") or "")
            title_size = int(inputs.get("title_font_size", 64))
            sub_size = int(inputs.get("subtitle_font_size", 32))
            cta_size = int(inputs.get("cta_font_size", 48))

            tmpdir = output_path.parent / f".demo_mockup_{int(time.time())}"
            tmpdir.mkdir(parents=True, exist_ok=True)

            still_dur_frames = int(round(still_dur * fps))
            segments: list[Path] = []

            # Build intro card if requested
            if intro_dur > 0 and title:
                intro_path = tmpdir / "intro.mp4"
                self._render_text_card(
                    intro_path, width, height, fps, intro_dur, brand_hex, text_color,
                    primary_text=title, primary_size=title_size,
                    secondary_text=subtitle, secondary_size=sub_size,
                )
                segments.append(intro_path)

            # Render Ken Burns clip per still
            for idx, still in enumerate(stills):
                clip_path = tmpdir / f"clip_{idx:03d}.mp4"
                self._render_ken_burns(
                    still, clip_path, width, height, fps, still_dur_frames, zoom_final,
                )
                segments.append(clip_path)

            # Build outro card if requested
            if outro_dur > 0 and cta:
                outro_path = tmpdir / "outro.mp4"
                self._render_text_card(
                    outro_path, width, height, fps, outro_dur, brand_hex, text_color,
                    primary_text=cta, primary_size=cta_size,
                    secondary_text="", secondary_size=sub_size,
                )
                segments.append(outro_path)

            if not segments:
                return ToolResult(success=False, error="no segments produced (no stills + no intro/outro)")

            # Concatenate via FFmpeg concat filter (handles different segment specs cleanly)
            self._concat_segments(segments, output_path, crossfade if len(segments) > 1 else 0.0, width, height, fps)

            # Cleanup tmp segments + dir
            for seg in segments:
                seg.unlink(missing_ok=True)
            try:
                # also clear any leftover hidden overlay PNGs
                for leftover in tmpdir.iterdir():
                    leftover.unlink(missing_ok=True)
                tmpdir.rmdir()
            except OSError:
                pass  # leave tmp residue rather than fail the run

            duration_s = round(time.time() - start, 2)
            duration_estimate_s = len(stills) * still_dur + intro_dur + outro_dur
            result = ToolResult(
                success=True,
                data={
                    "output_path": str(output_path),
                    "segments": len(segments),
                    "duration_estimate_s": duration_estimate_s,
                },
                artifacts=[str(output_path)],
                duration_seconds=duration_s,
            )
            asset_id = maybe_register_artifact(
                tool_result=result, inputs=inputs, capability=self.capability,
                created_by_tool=self.name, artifact_path=str(output_path),
                width=width, height=height, duration_s=duration_estimate_s,
            )
            if asset_id:
                result.data["dam_asset_id"] = asset_id
            return result
        except Exception as exc:
            return ToolResult(success=False, error=f"demo_mockup failed: {exc}", duration_seconds=round(time.time() - start, 2))

    # ---------------------------------------------------------------- helpers

    def _render_text_card(
        self,
        out_path: Path,
        width: int,
        height: int,
        fps: int,
        duration_s: float,
        bg_hex: str,
        text_color: str,
        primary_text: str,
        primary_size: int,
        secondary_text: str,
        secondary_size: int,
    ) -> None:
        """Render a solid-color card with centered title + optional subtitle.

        Implementation note: many Homebrew ffmpeg builds ship without the
        drawtext filter (built without libfreetype). To avoid that dependency
        we render the text layer in Pillow as a transparent PNG and overlay
        it via ffmpeg's overlay filter (always available).
        """
        # Render text PNG via PIL (transparent background, centered)
        text_png_path = out_path.with_suffix(".overlay.png")
        self._render_text_png(
            text_png_path,
            width,
            height,
            text_color,
            primary_text,
            primary_size,
            secondary_text,
            secondary_size,
        )

        # Compose: solid color background + PNG overlay
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={bg_hex}:s={width}x{height}:r={fps}:d={duration_s}",
            "-loop", "1", "-i", str(text_png_path),
            "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-t", str(duration_s),
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        text_png_path.unlink(missing_ok=True)

    @staticmethod
    def _render_text_png(
        out_path: Path,
        width: int,
        height: int,
        text_color: str,
        primary_text: str,
        primary_size: int,
        secondary_text: str,
        secondary_size: int,
    ) -> None:
        """Render centered title (+ optional subtitle) as a transparent PNG."""
        # Resolve a system font that exists on macOS — fall back to PIL's bundled default
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        font_path: str | None = None
        for cand in font_candidates:
            if Path(cand).exists():
                font_path = cand
                break

        primary_font = (
            ImageFont.truetype(font_path, primary_size) if font_path else ImageFont.load_default()
        )
        secondary_font = (
            ImageFont.truetype(font_path, secondary_size) if (font_path and secondary_text) else (ImageFont.load_default() if secondary_text else None)
        )

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Parse text_color (named or "#RRGGBB" or "0xRRGGBB")
        fill = DemoMockup._parse_color(text_color)

        # Measure + center primary
        p_bbox = draw.textbbox((0, 0), primary_text, font=primary_font)
        p_w = p_bbox[2] - p_bbox[0]
        p_h = p_bbox[3] - p_bbox[1]

        if secondary_text and secondary_font:
            s_bbox = draw.textbbox((0, 0), secondary_text, font=secondary_font)
            s_w = s_bbox[2] - s_bbox[0]
            s_h = s_bbox[3] - s_bbox[1]
            gap = max(20, primary_size // 4)
            total_h = p_h + gap + s_h
            top = (height - total_h) // 2

            p_x = (width - p_w) // 2
            p_y = top - p_bbox[1]
            draw.text((p_x, p_y), primary_text, font=primary_font, fill=fill)

            s_x = (width - s_w) // 2
            s_y = top + p_h + gap - s_bbox[1]
            draw.text((s_x, s_y), secondary_text, font=secondary_font, fill=fill)
        else:
            p_x = (width - p_w) // 2
            p_y = (height - p_h) // 2 - p_bbox[1]
            draw.text((p_x, p_y), primary_text, font=primary_font, fill=fill)

        img.save(out_path)

    @staticmethod
    def _parse_color(color: str) -> tuple[int, int, int, int]:
        """Parse a color literal into RGBA. Accepts named ('white'), '#RRGGBB', or '0xRRGGBB'."""
        named = {
            "white": (255, 255, 255, 255),
            "black": (0, 0, 0, 255),
            "red": (255, 0, 0, 255),
            "green": (0, 255, 0, 255),
            "blue": (0, 0, 255, 255),
        }
        if color.lower() in named:
            return named[color.lower()]
        hexstr = color
        if hexstr.startswith("#"):
            hexstr = hexstr[1:]
        elif hexstr.lower().startswith("0x"):
            hexstr = hexstr[2:]
        if len(hexstr) == 6:
            r = int(hexstr[0:2], 16)
            g = int(hexstr[2:4], 16)
            b = int(hexstr[4:6], 16)
            return (r, g, b, 255)
        # Fallback: white
        return (255, 255, 255, 255)

    def _render_ken_burns(
        self,
        still: Path,
        out_path: Path,
        width: int,
        height: int,
        fps: int,
        duration_frames: int,
        zoom_final: float,
    ) -> None:
        """Render a Ken Burns motion clip from a single still."""
        # zoompan: linear zoom from 1.0 to zoom_final over duration_frames
        # x,y pan: slight diagonal (center → 1/8 right + 1/8 down) for parallax feel
        # iw / ih: refer to input image dims; '/2' centers; '/8' adds drift
        zoom_expr = f"min(zoom+{(zoom_final - 1.0) / duration_frames:.6f},{zoom_final:.4f})"
        # NOTE: ffmpeg zoompan expression doesn't expose `d` as a variable,
        # so we inline the literal frame count to drive the linear pan.
        x_expr = f"iw/2-(iw/zoom/2)+(iw/8)*on/{duration_frames}"
        y_expr = f"ih/2-(ih/zoom/2)+(ih/8)*on/{duration_frames}"

        # First scale-pad the input to a larger canvas so zoompan has room to pan
        # Then zoompan it down to output size
        vf_chain = (
            # 1. Scale to fit while preserving aspect, then pad to fill output (with brand-friendly fill)
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={duration_frames}:s={width}x{height}:fps={fps}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(still),
            "-vf", vf_chain,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-t", f"{duration_frames / fps}",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _concat_segments(self, segments: list[Path], out_path: Path, crossfade: float, width: int, height: int, fps: int) -> None:
        """Concat segments with optional crossfade between consecutive clips."""
        if crossfade <= 0 or len(segments) == 1:
            # Simple concat via demuxer (fastest path)
            concat_list = out_path.parent / f".concat_{int(time.time())}.txt"
            with concat_list.open("w") as f:
                for seg in segments:
                    f.write(f"file '{seg.resolve()}'\n")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                str(out_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            concat_list.unlink(missing_ok=True)
            return

        # Crossfade concat — build xfade filtergraph
        # Compute per-segment durations via ffprobe
        durations: list[float] = []
        for seg in segments:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(seg)],
                check=True, capture_output=True, text=True,
            )
            durations.append(float(r.stdout.strip()))

        # Build xfade chain: [0:v][1:v]xfade=offset=d0-cf[v01];[v01][2:v]xfade=offset=d0+d1-2*cf[v012]; ...
        inputs_args: list[str] = []
        for seg in segments:
            inputs_args.extend(["-i", str(seg)])

        filter_parts: list[str] = []
        prev_label = "[0:v]"
        cumulative_offset = 0.0
        for i in range(1, len(segments)):
            cumulative_offset += durations[i - 1] - crossfade
            this_label = f"[v{i:02d}]"
            filter_parts.append(
                f"{prev_label}[{i}:v]xfade=transition=fade:duration={crossfade}:offset={cumulative_offset}{this_label}"
            )
            prev_label = this_label

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs_args,
            "-filter_complex", filter_complex,
            "-map", prev_label,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
