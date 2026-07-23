"""Green screen keying processor.

Removes green/blue screen backgrounds from footage using either FFmpeg
chromakey filtering or rembg AI segmentation. Supports automatic method
detection by analyzing frame color histograms.

Methods:
  - auto: Analyze frames to pick the best method (chromakey vs rembg)
  - chromakey: FFmpeg chromakey filter (fast, works well on clean screens)
  - rembg: AI background removal via rembg/u2net (slower, handles any bg)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any

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


class GreenScreenProcessor(BaseTool):
    name = "green_screen_processor"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html  "
        "For rembg method: pip install rembg[gpu] onnxruntime"
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "green_screen_keying",
        "chromakey",
        "background_removal",
        "rembg_segmentation",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path", "output_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to raw green screen footage",
            },
            "output_path": {
                "type": "string",
                "description": "Path for keyed output video",
            },
            "method": {
                "type": "string",
                "enum": ["auto", "chromakey", "rembg"],
                "default": "auto",
                "description": "Keying method: auto detects best approach, chromakey uses FFmpeg, rembg uses AI segmentation",
            },
            "fps": {
                "type": "integer",
                "default": 15,
                "description": "Output frames per second",
            },
            "bg_color": {
                "type": "string",
                "default": "#0E172A",
                "description": "Hex color for output background",
            },
            "max_frames": {
                "type": "integer",
                "default": 0,
                "description": "Limit frames to process (0 = all)",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=4096, vram_mb=0, disk_mb=8000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["FFmpeg error"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = [
        "input_path", "method", "fps", "bg_color", "max_frames",
    ]
    side_effects = ["writes keyed video to output_path"]
    user_visible_verification = [
        "Check output for green fringing around subject edges",
        "Verify background is cleanly replaced with target color",
        "Look for flickering or inconsistent keying between frames",
    ]

    # Platform-specific null device
    _null_device = "NUL" if platform.system() == "Windows" else "/dev/null"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        output_path = Path(inputs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        method = inputs.get("method", "auto")
        fps = inputs.get("fps", 15)
        bg_color = inputs.get("bg_color", "#0E172A")
        max_frames = inputs.get("max_frames", 0)
        start = time.time()

        # Step 1: Probe input video
        probe = self._probe_video(input_path)
        if not probe:
            return ToolResult(success=False, error="Failed to probe input video")

        duration = probe["duration"]
        width = probe["width"]
        height = probe["height"]
        src_fps = probe["fps"]

        # Step 2: Determine method
        if method == "auto":
            method = self._auto_detect_method(input_path, duration, width, height)

        # Step 3: Set up temp directory for frame processing
        temp_dir = output_path.parent / f".gs_tmp_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 4: Extract frames at target fps
            frames_dir = temp_dir / "frames"
            frames_dir.mkdir(exist_ok=True)
            frame_count = self._extract_frames(
                input_path, frames_dir, fps, max_frames
            )
            if frame_count == 0:
                return ToolResult(
                    success=False, error="No frames extracted from input"
                )

            # Step 5: Process frames
            processed_dir = temp_dir / "processed"
            processed_dir.mkdir(exist_ok=True)

            if method == "chromakey":
                ok = self._process_chromakey(
                    frames_dir, processed_dir, bg_color, frame_count, width, height
                )
            else:
                ok = self._process_rembg(
                    frames_dir, processed_dir, bg_color, frame_count
                )

            if not ok:
                return ToolResult(
                    success=False,
                    error=f"Frame processing failed with method={method}",
                )

            # Step 6: Reconstruct video from processed frames
            self._reconstruct_video(processed_dir, output_path, fps, width, height)

            if not output_path.exists() or output_path.stat().st_size == 0:
                return ToolResult(
                    success=False, error="Output video was not created"
                )

            elapsed = time.time() - start

            return ToolResult(
                success=True,
                data={
                    "method_used": method,
                    "frame_count": frame_count,
                    "duration": round(duration, 2),
                    "output_path": str(output_path),
                    "resolution": f"{width}x{height}",
                    "fps": fps,
                    "bg_color": bg_color,
                },
                artifacts=[str(output_path)],
                duration_seconds=round(elapsed, 2),
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Green screen processing failed: {e}")
        finally:
            # Clean up temp directory
            self._cleanup_dir(temp_dir)

    def _probe_video(self, input_path: Path) -> dict[str, Any] | None:
        """Probe video for duration, dimensions, and fps."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate",
            "-select_streams", "v:0",
            "-of", "json",
            str(input_path),
        ]
        try:
            result = self.run_command(cmd, timeout=30)
            data = json.loads(result.stdout)

            duration = float(data.get("format", {}).get("duration", 0))

            stream = data.get("streams", [{}])[0]
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))

            # Parse r_frame_rate like "30/1" or "30000/1001"
            fps_str = stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps_val = float(num) / float(den) if float(den) != 0 else 30.0
            else:
                fps_val = float(fps_str)

            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps_val,
            }
        except Exception:
            return None

    def _auto_detect_method(
        self, input_path: Path, duration: float, width: int, height: int
    ) -> str:
        """Analyze sample frames to decide between chromakey and rembg.

        Extracts 5 evenly-spaced frames, checks color histograms for
        green/blue screen presence, then tests chromakey quality on a sample.
        """
        temp_dir = input_path.parent / f".gs_detect_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract 5 sample frames evenly spaced
            interval = max(duration / 6, 0.1)
            sample_paths = []
            for i in range(5):
                ts = interval * (i + 1)
                out = temp_dir / f"sample_{i}.png"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{ts:.3f}",
                    "-i", str(input_path),
                    "-frames:v", "1",
                    str(out),
                ]
                try:
                    self.run_command(cmd, timeout=30)
                    if out.exists():
                        sample_paths.append(out)
                except Exception:
                    continue

            if not sample_paths:
                return "rembg"  # fallback if we can't extract samples

            # Analyze color histograms for green/blue screen presence
            has_green_screen = self._detect_green_screen_histogram(sample_paths)

            if not has_green_screen:
                # No obvious green/blue screen detected, use rembg
                return "rembg"

            # Test chromakey on a sample frame and check quality
            test_frame = sample_paths[len(sample_paths) // 2]
            chromakey_quality = self._test_chromakey_quality(test_frame, temp_dir)

            if chromakey_quality > 80:
                return "chromakey"
            else:
                return "rembg"

        finally:
            self._cleanup_dir(temp_dir)

    def _detect_green_screen_histogram(self, sample_paths: list[Path]) -> bool:
        """Analyze frames for dominant green or blue channel presence.

        Uses FFmpeg signalstats to measure average hue. A strong green
        screen typically has a large area of similar green/blue hue.
        """
        green_votes = 0
        for sample in sample_paths:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(sample),
                "-vf", "signalstats=stat=tout+vrep+brng,metadata=mode=print",
                "-frames:v", "1",
                "-f", "null", self._null_device,
            ]
            try:
                result = self.run_command(cmd, timeout=15)
                # Check stderr for color stats
                output = result.stderr or ""

                # Alternative: use FFmpeg to count green-ish pixels
                # Run a simpler hue check with colorchannelmixer
                cmd2 = [
                    "ffmpeg", "-y",
                    "-i", str(sample),
                    "-vf", (
                        "split[a][b];"
                        "[a]colorchannelmixer=rr=0:gg=1:bb=0,"
                        "threshold=threshold=0.3:similarity=0.3[mask];"
                        "[mask]blackframe=amount=0:threshold=32"
                    ),
                    "-frames:v", "1",
                    "-f", "null", self._null_device,
                ]
                # This is complex; use a simpler approach: check raw pixels
                # via a green-range filter
                cmd_green = [
                    "ffmpeg", "-y",
                    "-i", str(sample),
                    "-vf", (
                        "colorkey=color=0x00FF00:similarity=0.4:blend=0.0,"
                        "alphaextract,"
                        "blackframe=amount=0:threshold=128"
                    ),
                    "-frames:v", "1",
                    "-f", "null", self._null_device,
                ]
                try:
                    result2 = self.run_command(cmd_green, timeout=15)
                    stderr = result2.stderr or ""
                    # blackframe reports percentage of black pixels
                    # If many pixels became transparent (black in alpha), there's green
                    if "pblack:" in stderr:
                        import re
                        pblack_matches = re.findall(r"pblack:(\d+)", stderr)
                        if pblack_matches:
                            pblack = int(pblack_matches[0])
                            if pblack >= 20:
                                green_votes += 1
                except Exception:
                    pass

            except Exception:
                continue

        # If majority of frames show green screen
        return green_votes >= len(sample_paths) // 2

    def _test_chromakey_quality(self, test_frame: Path, temp_dir: Path) -> float:
        """Run chromakey on a test frame and estimate quality percentage.

        Returns a score 0-100 indicating what percentage of the expected
        background was successfully keyed out.
        """
        keyed_out = temp_dir / "chromakey_test.png"

        # Apply chromakey and output with alpha
        cmd = [
            "ffmpeg", "-y",
            "-i", str(test_frame),
            "-vf", "chromakey=color=0x00FF00:similarity=0.3:blend=0.08",
            str(keyed_out),
        ]
        try:
            self.run_command(cmd, timeout=15)
        except Exception:
            return 0.0

        if not keyed_out.exists():
            return 0.0

        # Count transparent pixels via alphaextract + blackframe
        cmd2 = [
            "ffmpeg", "-y",
            "-i", str(keyed_out),
            "-vf", "alphaextract,blackframe=amount=0:threshold=32",
            "-frames:v", "1",
            "-f", "null", self._null_device,
        ]
        try:
            result = self.run_command(cmd2, timeout=15)
            stderr = result.stderr or ""
            import re
            pblack_matches = re.findall(r"pblack:(\d+)", stderr)
            if pblack_matches:
                # pblack = percentage of black pixels in alpha = transparent pixels
                return float(pblack_matches[0])
        except Exception:
            pass

        return 0.0

    def _extract_frames(
        self, input_path: Path, frames_dir: Path, fps: int, max_frames: int
    ) -> int:
        """Extract frames from video at target fps."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps={fps}",
            str(frames_dir / "frame_%06d.png"),
        ]

        if max_frames > 0:
            cmd.insert(-1, "-frames:v")
            cmd.insert(-1, str(max_frames))

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            # ffmpeg may return non-zero but still produce frames
            pass

        # Count extracted frames
        frame_files = sorted(frames_dir.glob("frame_*.png"))
        count = len(frame_files)

        if count > 0:
            # Log progress for large frame counts
            if count > 100:
                print(f"[green_screen_processor] Extracted {count} frames")

        return count

    def _process_chromakey(
        self,
        frames_dir: Path,
        processed_dir: Path,
        bg_color: str,
        frame_count: int,
        width: int,
        height: int,
    ) -> bool:
        """Process frames using FFmpeg chromakey filter.

        Applies chromakey to remove green, then composites onto bg_color.
        """
        bg_hex = bg_color.lstrip("#")
        # Convert hex to FFmpeg color format
        ffmpeg_bg = f"0x{bg_hex}"

        frame_files = sorted(frames_dir.glob("frame_*.png"))
        processed = 0

        for i, frame in enumerate(frame_files):
            out_path = processed_dir / frame.name
            cmd = [
                "ffmpeg", "-y",
                # Background sized to the frame up front. The old code used a 1x1
                # color source and `[0:v]scale=iw:ih` — a no-op (iw/ih were the
                # 1x1 source's own size) — and overlay takes the size of its
                # FIRST input, so every frame was clipped to a single pixel and
                # the whole video came out a solid color with the subject gone.
                "-f", "lavfi", "-i", f"color=c={ffmpeg_bg}:size={width}x{height}",
                "-i", str(frame),
                "-filter_complex",
                (
                    # Force an explicit alpha format after chromakey so the keyed
                    # transparency survives filter negotiation on every FFmpeg
                    # build — without it, some Linux builds carry the keyed frame
                    # forward without an alpha plane and overlay draws opaque
                    # green over the background instead of compositing.
                    f"[1:v]chromakey=color=0x00FF00:similarity=0.3:blend=0.08,"
                    f"format=yuva420p[fg];"
                    f"[0:v][fg]overlay=0:0:format=auto,format=yuv420p"
                ),
                "-frames:v", "1",
                str(out_path),
            ]
            try:
                self.run_command(cmd, timeout=30)
                if out_path.exists():
                    processed += 1
            except Exception:
                # Try with the frame size explicitly to fix scale
                try:
                    cmd_retry = [
                        "ffmpeg", "-y",
                        "-i", str(frame),
                        "-vf",
                        f"chromakey=color=0x00FF00:similarity=0.3:blend=0.08,"
                        f"split[fg][alpha];"
                        f"[alpha]alphaextract[a];"
                        f"color=c={ffmpeg_bg}[bg];"
                        f"[bg][fg][a]maskedmerge",
                        "-frames:v", "1",
                        str(out_path),
                    ]
                    # Simpler fallback: just apply chromakey without compositing
                    cmd_simple = [
                        "ffmpeg", "-y",
                        "-i", str(frame),
                        "-vf", f"chromakey=color=0x00FF00:similarity=0.3:blend=0.08",
                        str(out_path),
                    ]
                    self.run_command(cmd_simple, timeout=30)
                    if out_path.exists():
                        processed += 1
                except Exception:
                    continue

            if frame_count > 100 and (i + 1) % 50 == 0:
                print(
                    f"[green_screen_processor] Chromakey: {i + 1}/{frame_count} frames"
                )

        return processed > 0

    def _process_rembg(
        self,
        frames_dir: Path,
        processed_dir: Path,
        bg_color: str,
        frame_count: int,
    ) -> bool:
        """Process frames using rembg AI segmentation.

        Removes background with u2net_human_seg model, then composites
        the subject onto bg_color background.
        """
        try:
            import rembg
            from PIL import Image
        except ImportError:
            return False

        # Parse bg_color hex to RGB
        bg_hex = bg_color.lstrip("#")
        bg_r = int(bg_hex[0:2], 16)
        bg_g = int(bg_hex[2:4], 16)
        bg_b = int(bg_hex[4:6], 16)

        session = rembg.new_session("u2net_human_seg")

        frame_files = sorted(frames_dir.glob("frame_*.png"))
        processed = 0

        for i, frame in enumerate(frame_files):
            try:
                img = Image.open(frame).convert("RGB")
                import numpy as np

                # Remove background (returns RGBA)
                result = rembg.remove(
                    np.array(img),
                    session=session,
                )
                result_img = Image.fromarray(result)

                # Composite onto bg_color background
                bg = Image.new("RGBA", result_img.size, (bg_r, bg_g, bg_b, 255))
                bg.paste(result_img, (0, 0), result_img)

                # Save as RGB
                out_path = processed_dir / frame.name
                bg.convert("RGB").save(out_path)
                processed += 1

            except Exception:
                continue

            if frame_count > 100 and (i + 1) % 50 == 0:
                print(
                    f"[green_screen_processor] rembg: {i + 1}/{frame_count} frames"
                )

        return processed > 0

    def _reconstruct_video(
        self,
        frames_dir: Path,
        output_path: Path,
        fps: int,
        width: int,
        height: int,
    ) -> None:
        """Reconstruct video from processed frames using FFmpeg."""
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%06d.png"),
            "-vf", f"scale={width}:{height}:flags=lanczos",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        self.run_command(cmd, timeout=600)

    @staticmethod
    def _cleanup_dir(dir_path: Path) -> None:
        """Recursively remove a temp directory."""
        if not dir_path.exists():
            return
        try:
            shutil.rmtree(dir_path)
        except OSError:
            # Best-effort cleanup; individual file removal as fallback
            for f in dir_path.rglob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                except OSError:
                    pass
            try:
                dir_path.rmdir()
            except OSError:
                pass

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        method = inputs.get("method", "auto")
        if method == "rembg":
            return 120.0
        elif method == "chromakey":
            return 30.0
        return 60.0  # auto
