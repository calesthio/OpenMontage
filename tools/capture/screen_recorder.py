"""FFmpeg-based screen recorder.

Cross-platform screen capture using FFmpeg's native capture devices.
Records screen + optional audio to MP4. Designed as the "quick start"
option — no install beyond FFmpeg, works everywhere, CLI-driven.

Platform capture devices:
  Windows: gdigrab (screen) + dshow (audio)
  macOS:   avfoundation (screen + audio)
  Linux:   x11grab (screen) + pulse (audio)
"""

from __future__ import annotations

import os
import platform
import subprocess
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
    ToolTier,
)


def _detect_audio_device_windows() -> str | None:
    """Find a working audio input device on Windows via dshow."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, timeout=10,
        )
        # dshow lists devices in stderr
        output = result.stderr
        lines = output.splitlines()
        for i, line in enumerate(lines):
            if "audio" in line.lower() and "DirectShow audio" in line:
                # Next line(s) contain actual device names
                for j in range(i + 1, min(i + 10, len(lines))):
                    if '"' in lines[j] and "Alternative name" not in lines[j]:
                        name = lines[j].split('"')[1]
                        return name
    except Exception:
        pass
    return None


def _detect_audio_device_mac() -> str | None:
    """Find the default audio input index on macOS via avfoundation."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stderr
        in_audio = False
        for line in output.splitlines():
            if "AVFoundation audio devices" in line:
                in_audio = True
                continue
            if in_audio and "[" in line and "]" in line:
                # Return first audio device index
                idx = line.split("[")[1].split("]")[0].strip()
                if idx.isdigit():
                    return idx
    except Exception:
        pass
    return None


class ScreenRecorder(BaseTool):
    name = "screen_recorder"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "screen_capture"
    provider = "ffmpeg"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["binary:ffmpeg"]
    install_instructions = (
        "Install ffmpeg:\n"
        "  Windows: winget install ffmpeg\n"
        "  macOS: brew install ffmpeg\n"
        "  Linux: sudo apt install ffmpeg"
    )

    capabilities = [
        "record_screen",
        "record_screen_with_audio",
        "record_region",
    ]

    best_for = [
        "Quick screen recording without additional software",
        "Automated screen capture for demo pipelines",
        "Recording specific screen regions for tutorials",
    ]

    not_good_for = [
        "Webcam overlay (PiP) — use Cap for that",
        "Cursor highlight effects — use Cap for that",
        "Interactive recording with pause/resume UI",
    ]

    input_schema = {
        "type": "object",
        "required": ["output_path"],
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Path for the output MP4 file",
            },
            "duration_seconds": {
                "type": "integer",
                "default": 60,
                "description": "Recording duration in seconds (default: 60, max: 600)",
            },
            "fps": {
                "type": "integer",
                "default": 30,
                "description": "Frames per second (15, 24, 30, or 60)",
            },
            "capture_audio": {
                "type": "boolean",
                "default": True,
                "description": "Whether to capture system/microphone audio",
            },
            "region": {
                "type": "object",
                "description": "Optional screen region to capture (full screen if omitted)",
                "properties": {
                    "x": {"type": "integer", "description": "Left offset in pixels"},
                    "y": {"type": "integer", "description": "Top offset in pixels"},
                    "width": {"type": "integer", "description": "Width in pixels"},
                    "height": {"type": "integer", "description": "Height in pixels"},
                },
            },
            "screen_index": {
                "type": "integer",
                "default": 0,
                "description": "Monitor index for multi-monitor setups (0 = primary)",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "duration_seconds": {"type": "number"},
            "resolution": {"type": "string"},
            "has_audio": {"type": "boolean"},
            "file_size_mb": {"type": "number"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=500, network_required=False,
    )

    side_effects = ["creates_file"]
    fallback_tools = ["cap_recorder"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        output_path = Path(inputs["output_path"])
        duration = min(inputs.get("duration_seconds", 60), 600)
        fps = inputs.get("fps", 30)
        capture_audio = inputs.get("capture_audio", True)
        region = inputs.get("region")
        screen_index = inputs.get("screen_index", 0)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        sys_platform = platform.system()
        cmd = self._build_command(
            sys_platform, str(output_path), duration, fps,
            capture_audio, region, screen_index,
        )

        if cmd is None:
            return ToolResult(
                success=False,
                error=f"Screen recording not supported on {sys_platform}. "
                      f"Supported: Windows, macOS, Linux.",
            )

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=duration + 30,  # grace period
            )
            elapsed = time.time() - start_time

            if not output_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Recording failed — no output file. FFmpeg stderr: {proc.stderr[-500:]}",
                )

            file_size_mb = output_path.stat().st_size / (1024 * 1024)

            # Probe the output to get actual resolution
            resolution = self._probe_resolution(str(output_path))

            return ToolResult(
                success=True,
                data={
                    "output_path": str(output_path),
                    "duration_seconds": round(elapsed, 1),
                    "resolution": resolution,
                    "has_audio": capture_audio,
                    "file_size_mb": round(file_size_mb, 1),
                    "platform": sys_platform,
                    "capture_method": "ffmpeg",
                },
                artifacts=[str(output_path)],
                duration_seconds=elapsed,
            )

        except subprocess.TimeoutExpired:
            # Recording completed by timeout — this is expected behavior
            if output_path.exists():
                file_size_mb = output_path.stat().st_size / (1024 * 1024)
                return ToolResult(
                    success=True,
                    data={
                        "output_path": str(output_path),
                        "duration_seconds": duration,
                        "has_audio": capture_audio,
                        "file_size_mb": round(file_size_mb, 1),
                        "platform": sys_platform,
                        "capture_method": "ffmpeg",
                    },
                    artifacts=[str(output_path)],
                    duration_seconds=duration,
                )
            return ToolResult(success=False, error="Recording timed out with no output")

        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _build_command(
        self,
        sys_platform: str,
        output_path: str,
        duration: int,
        fps: int,
        capture_audio: bool,
        region: dict | None,
        screen_index: int,
    ) -> list[str] | None:
        """Build platform-specific FFmpeg capture command."""

        if sys_platform == "Windows":
            return self._build_windows_cmd(
                output_path, duration, fps, capture_audio, region,
            )
        elif sys_platform == "Darwin":
            return self._build_mac_cmd(
                output_path, duration, fps, capture_audio, region, screen_index,
            )
        elif sys_platform == "Linux":
            return self._build_linux_cmd(
                output_path, duration, fps, capture_audio, region,
            )
        return None

    def _build_windows_cmd(
        self, output_path: str, duration: int, fps: int,
        capture_audio: bool, region: dict | None,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y"]

        # Video input: gdigrab
        cmd += ["-f", "gdigrab"]
        cmd += ["-framerate", str(fps)]
        cmd += ["-t", str(duration)]

        if region:
            cmd += ["-offset_x", str(region.get("x", 0))]
            cmd += ["-offset_y", str(region.get("y", 0))]
            cmd += ["-video_size", f"{region['width']}x{region['height']}"]

        cmd += ["-i", "desktop"]

        # Audio input: dshow
        if capture_audio:
            audio_device = _detect_audio_device_windows()
            if audio_device:
                cmd += ["-f", "dshow", "-i", f"audio={audio_device}"]

        # Output encoding
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
        if capture_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-pix_fmt", "yuv420p"]
        cmd += [output_path]

        return cmd

    def _build_mac_cmd(
        self, output_path: str, duration: int, fps: int,
        capture_audio: bool, region: dict | None, screen_index: int,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y"]

        # avfoundation: "screen_index:audio_index" or "screen_index:none"
        audio_idx = "none"
        if capture_audio:
            detected = _detect_audio_device_mac()
            if detected:
                audio_idx = detected

        cmd += ["-f", "avfoundation"]
        cmd += ["-framerate", str(fps)]
        cmd += ["-t", str(duration)]

        if region:
            # avfoundation doesn't support region directly — we crop in post
            cmd += ["-i", f"{screen_index}:{audio_idx}"]
            cmd += ["-vf", f"crop={region['width']}:{region['height']}:{region.get('x', 0)}:{region.get('y', 0)}"]
        else:
            cmd += ["-i", f"{screen_index}:{audio_idx}"]

        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
        if capture_audio and audio_idx != "none":
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-pix_fmt", "yuv420p"]
        cmd += [output_path]

        return cmd

    def _build_linux_cmd(
        self, output_path: str, duration: int, fps: int,
        capture_audio: bool, region: dict | None,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y"]

        # x11grab
        display = os.environ.get("DISPLAY", ":0.0")
        cmd += ["-f", "x11grab"]
        cmd += ["-framerate", str(fps)]
        cmd += ["-t", str(duration)]

        if region:
            cmd += ["-video_size", f"{region['width']}x{region['height']}"]
            cmd += ["-i", f"{display}+{region.get('x', 0)},{region.get('y', 0)}"]
        else:
            # Full screen — need to detect resolution
            cmd += ["-i", display]

        if capture_audio:
            cmd += ["-f", "pulse", "-i", "default"]

        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
        if capture_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-pix_fmt", "yuv420p"]
        cmd += [output_path]

        return cmd

    def _probe_resolution(self, path: str) -> str:
        """Get video resolution via ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0",
                    path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            parts = result.stdout.strip().split(",")
            if len(parts) == 2:
                return f"{parts[0]}x{parts[1]}"
        except Exception:
            pass
        return "unknown"
