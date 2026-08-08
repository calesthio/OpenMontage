"""Green screen composite tool for talking-head pipeline.

Composites a keyed speaker (dark/solid background) over a Remotion
background video with layout presets. Supports news anchor, full behind,
picture-in-picture, and split layouts.

Uses PIL/numpy for frame-level alpha compositing and FFmpeg for
frame extraction, encoding, and audio muxing.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolTier,
)


class GreenScreenComposite(BaseTool):
    name = "green_screen_composite"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "python:numpy", "python:PIL"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html — "
        "pip install numpy Pillow"
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "green_screen_composite",
        "speaker_overlay",
        "layout_preset",
        "alpha_composite",
    ]

    input_schema = {
        "type": "object",
        "required": ["speaker_path", "background_path", "output_path"],
        "properties": {
            "speaker_path": {
                "type": "string",
                "description": "Path to keyed speaker video (dark bg, from green_screen_processor)",
            },
            "background_path": {
                "type": "string",
                "description": "Path to Remotion background video",
            },
            "output_path": {
                "type": "string",
                "description": "Output composite video path",
            },
            "original_audio_path": {
                "type": "string",
                "description": "Path to original footage to extract audio from",
            },
            "layout": {
                "type": "string",
                "enum": ["news_anchor", "full_behind", "pip", "split"],
                "default": "news_anchor",
                "description": (
                    "news_anchor=speaker bottom-center over shifted bg, "
                    "full_behind=speaker full-frame on bg, "
                    "pip=speaker 30% bottom-right, "
                    "split=speaker left 50% bg right 50%"
                ),
            },
            "speaker_scale": {
                "type": "number",
                "default": 0.65,
                "description": "Scale factor for speaker layer",
            },
            "bg_shift_up": {
                "type": "integer",
                "default": 300,
                "description": "Pixels to shift background content upward",
            },
            "bg_color_hex": {
                "type": "string",
                "default": "#0E172A",
                "description": "The keyed speaker's background color for alpha creation",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=4096, vram_mb=0, disk_mb=8000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["FFmpeg error"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = [
        "speaker_path", "background_path", "layout",
        "speaker_scale", "bg_shift_up", "bg_color_hex",
    ]
    side_effects = ["writes composite video to output_path"]
    user_visible_verification = [
        "Watch output — speaker should be cleanly composited without color fringing",
        "Check layout positioning matches the chosen preset",
        "Verify audio is synced if original_audio_path was provided",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        speaker_path = Path(inputs["speaker_path"])
        background_path = Path(inputs["background_path"])
        output_path = Path(inputs["output_path"])
        original_audio_path = inputs.get("original_audio_path")
        layout = inputs.get("layout", "news_anchor")
        speaker_scale = inputs.get("speaker_scale", 0.65)
        bg_shift_up = inputs.get("bg_shift_up", 300)
        bg_color_hex = inputs.get("bg_color_hex", "#0E172A")

        if not speaker_path.exists():
            return ToolResult(success=False, error=f"Speaker video not found: {speaker_path}")
        if not background_path.exists():
            return ToolResult(success=False, error=f"Background video not found: {background_path}")
        if original_audio_path and not Path(original_audio_path).exists():
            return ToolResult(success=False, error=f"Audio source not found: {original_audio_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()

        # Parse bg color
        bg_color = self._parse_hex_color(bg_color_hex)

        # Step 1: Probe both videos
        speaker_info = self._probe_video(speaker_path)
        bg_info = self._probe_video(background_path)

        if not speaker_info or not bg_info:
            return ToolResult(
                success=False,
                error="Failed to probe one or both input videos",
            )

        # Step 2: Use the LOWER fps (typically 15fps from speaker)
        target_fps = min(speaker_info["fps"], bg_info["fps"])
        if target_fps <= 0:
            target_fps = 15.0

        # Determine output dimensions from background
        out_w = bg_info["width"]
        out_h = bg_info["height"]

        # Use shorter duration
        duration = min(speaker_info["duration"], bg_info["duration"])

        # Step 3: Extract frames from both videos
        temp_dir = output_path.parent / ".greenscreen_composite_tmp"
        speaker_frames_dir = temp_dir / "speaker"
        bg_frames_dir = temp_dir / "bg"
        comp_frames_dir = temp_dir / "composite"

        for d in [speaker_frames_dir, bg_frames_dir, comp_frames_dir]:
            d.mkdir(parents=True, exist_ok=True)

        try:
            self._extract_frames(speaker_path, speaker_frames_dir, target_fps)
            self._extract_frames(background_path, bg_frames_dir, target_fps)

            # Get sorted frame lists
            speaker_frames = sorted(speaker_frames_dir.glob("*.png"))
            bg_frames = sorted(bg_frames_dir.glob("*.png"))

            if not speaker_frames or not bg_frames:
                return ToolResult(
                    success=False,
                    error="Frame extraction produced no frames",
                )

            frame_count = min(len(speaker_frames), len(bg_frames))
            log_interval = max(1, frame_count // 10)

            # Step 4: Composite each frame pair
            for i in range(frame_count):
                if i % log_interval == 0:
                    print(f"[green_screen_composite] Compositing frame {i + 1}/{frame_count}")

                speaker_img = Image.open(speaker_frames[i]).convert("RGB")
                bg_img = Image.open(bg_frames[i]).convert("RGB")

                comp = self._composite_frame(
                    speaker_img, bg_img, bg_color,
                    layout=layout,
                    speaker_scale=speaker_scale,
                    bg_shift_up=bg_shift_up,
                    out_w=out_w,
                    out_h=out_h,
                )
                comp.save(comp_frames_dir / f"frame_{i:06d}.png")

            print(f"[green_screen_composite] All {frame_count} frames composited")

            # Step 5: Encode composite frames to video
            no_audio_path = output_path if not original_audio_path else temp_dir / "no_audio.mp4"
            self._encode_frames(comp_frames_dir, no_audio_path, target_fps, out_w, out_h)

            # Step 6: Mux audio if provided
            if original_audio_path:
                self._mux_audio(no_audio_path, Path(original_audio_path), output_path, duration)

            if not output_path.exists() or output_path.stat().st_size == 0:
                return ToolResult(success=False, error="Output video was not created")

            elapsed = time.time() - start

            return ToolResult(
                success=True,
                data={
                    "output": str(output_path),
                    "layout": layout,
                    "fps": target_fps,
                    "frame_count": frame_count,
                    "duration": round(duration, 2),
                    "dimensions": f"{out_w}x{out_h}",
                    "speaker_scale": speaker_scale,
                    "has_audio": bool(original_audio_path),
                },
                artifacts=[str(output_path)],
                duration_seconds=round(elapsed, 2),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Composite failed: {e}")
        finally:
            # Step 7: Clean up temp directories
            self._cleanup_temp(temp_dir)

    def _parse_hex_color(self, hex_str: str) -> np.ndarray:
        """Parse a hex color string like '#0E172A' to an RGB numpy array."""
        import numpy as np

        hex_str = hex_str.lstrip("#")
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return np.array([r, g, b])

    def _probe_video(self, path: Path) -> dict[str, Any] | None:
        """Probe a video for fps, duration, and dimensions."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ]
        try:
            result = self.run_command(cmd, timeout=30)
            data = json.loads(result.stdout)
        except Exception:
            return None

        # Find video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            return None

        # Parse fps from r_frame_rate (e.g., "30/1" or "15000/1001")
        fps_str = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = fps_str.split("/")
            fps = float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        duration = float(data.get("format", {}).get("duration", 0))

        return {
            "fps": fps,
            "duration": duration,
            "width": int(video_stream.get("width", 1920)),
            "height": int(video_stream.get("height", 1080)),
        }

    def _extract_frames(self, video_path: Path, output_dir: Path, fps: float) -> None:
        """Extract frames from a video at the given fps."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            str(output_dir / "frame_%06d.png"),
        ]
        self.run_command(cmd, timeout=600)

    def _composite_frame(
        self,
        speaker_img: Image.Image,
        bg_img: Image.Image,
        bg_color: np.ndarray,
        *,
        layout: str,
        speaker_scale: float,
        bg_shift_up: int,
        out_w: int,
        out_h: int,
    ) -> Image.Image:
        """Composite a single speaker frame over a background frame using the given layout."""
        import numpy as np

        # Create alpha mask from speaker frame
        speaker_arr = np.array(speaker_img).astype(float)
        dist = np.sqrt(np.sum((speaker_arr - bg_color.astype(float)) ** 2, axis=2))
        threshold = 35
        alpha = np.clip((dist - threshold) * 8, 0, 255).astype(np.uint8)

        speaker_rgba = Image.new("RGBA", speaker_img.size)
        speaker_rgba.paste(speaker_img, (0, 0))
        speaker_rgba.putalpha(Image.fromarray(alpha))

        # Prepare background canvas at output size
        canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 255))

        if layout == "news_anchor":
            # Background shifted up so graphics appear above speaker's head
            bg_resized = bg_img.resize((out_w, out_h), Image.LANCZOS).convert("RGBA")
            # Shift background up: paste it higher so bottom content scrolls up
            shifted_bg = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 255))
            shifted_bg.paste(bg_resized, (0, -bg_shift_up))
            canvas = shifted_bg

            # Scale speaker and place at bottom center
            sp_w = int(speaker_rgba.width * speaker_scale)
            sp_h = int(speaker_rgba.height * speaker_scale)
            speaker_scaled = speaker_rgba.resize((sp_w, sp_h), Image.LANCZOS)
            x = (out_w - sp_w) // 2
            y = out_h - sp_h
            canvas.paste(speaker_scaled, (x, y), speaker_scaled)

        elif layout == "full_behind":
            # Speaker full-frame on background, no scaling, no shifting
            bg_resized = bg_img.resize((out_w, out_h), Image.LANCZOS).convert("RGBA")
            canvas = bg_resized

            # Resize speaker to match output
            speaker_full = speaker_rgba.resize((out_w, out_h), Image.LANCZOS)
            canvas.paste(speaker_full, (0, 0), speaker_full)

        elif layout == "pip":
            # Background full-frame, speaker 30% in bottom-right
            bg_resized = bg_img.resize((out_w, out_h), Image.LANCZOS).convert("RGBA")
            canvas = bg_resized

            pip_scale = 0.30
            sp_w = int(out_w * pip_scale)
            sp_h = int(out_h * pip_scale)
            speaker_pip = speaker_rgba.resize((sp_w, sp_h), Image.LANCZOS)
            margin = 20
            x = out_w - sp_w - margin
            y = out_h - sp_h - margin
            canvas.paste(speaker_pip, (x, y), speaker_pip)

        elif layout == "split":
            # Speaker on left 50%, background on right 50%
            half_w = out_w // 2

            # Left side: speaker resized to fill left half
            speaker_left = speaker_rgba.resize((half_w, out_h), Image.LANCZOS)
            # Right side: background cropped/resized to fill right half
            bg_right = bg_img.resize((half_w, out_h), Image.LANCZOS).convert("RGBA")

            canvas.paste(speaker_left, (0, 0), speaker_left)
            canvas.paste(bg_right, (half_w, 0), bg_right)

        # Convert to RGB for output
        return canvas.convert("RGB")

    def _encode_frames(
        self, frames_dir: Path, output_path: Path, fps: float, width: int, height: int
    ) -> None:
        """Encode PNG frames to an MP4 video."""
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%06d.png"),
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={width}:{height}",
            str(output_path),
        ]
        self.run_command(cmd, timeout=600)

    def _mux_audio(
        self, video_path: Path, audio_source: Path, output_path: Path, duration: float
    ) -> None:
        """Mux audio from the original source into the composite video."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_source),
            "-t", f"{duration:.3f}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            str(output_path),
        ]
        self.run_command(cmd, timeout=300)

    def _cleanup_temp(self, temp_dir: Path) -> None:
        """Remove temporary frame directories."""
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                # Best-effort cleanup; log but don't fail
                print(f"[green_screen_composite] Warning: could not fully clean {temp_dir}")

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0
