"""Frame sampler tool wrapping FFmpeg.

Extracts representative frames from video for AI analysis, thumbnails,
or quality inspection. Supports interval-based, count-based, and
timestamp-based extraction strategies.
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
    ToolResult,
    ToolStability,
    ToolTier,
)


class FrameSampler(BaseTool):
    name = "frame_sampler"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html"
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "extract_frames_interval",
        "extract_frames_count",
        "extract_frames_timestamps",
        "extract_frames_scene_guided",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path", "strategy"],
        "properties": {
            "input_path": {"type": "string"},
            "strategy": {
                "type": "string",
                "enum": ["interval", "count", "timestamps", "scene_guided"],
            },
            "interval_seconds": {
                "type": "number",
                "minimum": 0.1,
                "description": "Seconds between frames (for interval strategy)",
            },
            "count": {
                "type": "integer",
                "minimum": 1,
                "description": "Total frames to extract (for count strategy)",
            },
            "timestamps": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Specific timestamps in seconds (for timestamps strategy)",
            },
            "scene_boundaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_seconds": {"type": "number"},
                        "end_seconds": {"type": "number"},
                    },
                },
                "description": "Scene boundary list (for scene_guided strategy)",
            },
            "max_frames": {
                "type": "integer",
                "minimum": 1,
                "default": 20,
                "description": "Max frames to extract (for scene_guided strategy)",
            },
            "output_dir": {"type": "string"},
            "format": {"type": "string", "enum": ["png", "jpg"], "default": "jpg"},
            "quality": {"type": "integer", "minimum": 1, "maximum": 31, "default": 2},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["input_path", "strategy", "interval_seconds", "count"]
    side_effects = ["writes frame images to output_dir"]
    user_visible_verification = ["Inspect extracted frames for representative coverage"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        strategy = inputs["strategy"]
        fmt = inputs.get("format", "jpg")
        quality = inputs.get("quality", 2)
        output_dir = Path(inputs.get("output_dir", input_path.parent / "frames"))
        output_dir.mkdir(parents=True, exist_ok=True)

        start = time.time()

        try:
            if strategy == "interval":
                frames = self._extract_interval(input_path, output_dir, fmt, quality, inputs)
            elif strategy == "count":
                frames = self._extract_count(input_path, output_dir, fmt, quality, inputs)
            elif strategy == "timestamps":
                frames = self._extract_timestamps(input_path, output_dir, fmt, quality, inputs)
            elif strategy == "scene_guided":
                frames = self._extract_scene_guided(input_path, output_dir, fmt, quality, inputs)
            else:
                return ToolResult(success=False, error=f"Unknown strategy: {strategy}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "strategy": strategy,
                "frame_count": len(frames),
                "frames": frames,
                "output_dir": str(output_dir),
            },
            artifacts=[str(output_dir)],
            duration_seconds=round(elapsed, 2),
        )

    def _extract_interval(
        self,
        input_path: Path,
        output_dir: Path,
        fmt: str,
        quality: int,
        inputs: dict,
    ) -> list[dict]:
        interval = inputs.get("interval_seconds", 5.0)
        output_pattern = str(output_dir / f"frame_%04d.{fmt}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps=1/{interval}",
        ]
        if fmt == "jpg":
            cmd.extend(["-qscale:v", str(quality)])
        cmd.append(output_pattern)

        self.run_command(cmd)

        return self._collect_frames(output_dir, fmt, interval)

    def _extract_count(
        self,
        input_path: Path,
        output_dir: Path,
        fmt: str,
        quality: int,
        inputs: dict,
    ) -> list[dict]:
        count = inputs.get("count", 10)
        duration = self._get_duration(input_path)
        if duration <= 0:
            return []

        interval = duration / count
        output_pattern = str(output_dir / f"frame_%04d.{fmt}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps=1/{interval}",
            "-frames:v", str(count),
        ]
        if fmt == "jpg":
            cmd.extend(["-qscale:v", str(quality)])
        cmd.append(output_pattern)

        self.run_command(cmd)

        return self._collect_frames(output_dir, fmt, interval)

    def _extract_timestamps(
        self,
        input_path: Path,
        output_dir: Path,
        fmt: str,
        quality: int,
        inputs: dict,
    ) -> list[dict]:
        timestamps = inputs.get("timestamps", [])
        frames = []

        for i, ts in enumerate(timestamps):
            output_file = output_dir / f"frame_{i:04d}.{fmt}"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", str(input_path),
                "-frames:v", "1",
            ]
            if fmt == "jpg":
                cmd.extend(["-qscale:v", str(quality)])
            cmd.append(str(output_file))

            self.run_command(cmd)

            if output_file.exists():
                frames.append({
                    "path": str(output_file),
                    "timestamp_seconds": ts,
                    "index": i,
                })

        return frames

    def _extract_scene_guided(
        self,
        input_path: Path,
        output_dir: Path,
        fmt: str,
        quality: int,
        inputs: dict,
    ) -> list[dict]:
        """Extract keyframes guided by scene boundaries.

        Extracts the first frame of each scene plus a midpoint frame for scenes
        longer than 3 seconds. This captures all visual transitions with a
        bounded, predictable number of frames — much better than uniform FPS.
        """
        scene_boundaries = inputs.get("scene_boundaries", [])
        max_frames = inputs.get("max_frames", 20)

        if not scene_boundaries:
            # No scene data — fall back to count-based
            return self._extract_count(input_path, output_dir, fmt, quality, {
                "count": min(max_frames, 15),
            })

        # Compute timestamps: first frame + midpoint for long scenes
        timestamps = []
        for scene in scene_boundaries:
            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", 0)
            duration = end - start

            # First frame of scene (offset slightly to avoid black frames)
            timestamps.append(start + 0.1)

            # Midpoint for scenes > 3 seconds
            if duration > 3.0:
                timestamps.append(start + duration / 2)

        # Deduplicate, sort, limit
        timestamps = sorted(set(round(t, 3) for t in timestamps))
        if len(timestamps) > max_frames:
            step = len(timestamps) / max_frames
            timestamps = [timestamps[int(i * step)] for i in range(max_frames)]

        # Extract via timestamps strategy
        return self._extract_timestamps(
            input_path, output_dir, fmt, quality, {"timestamps": timestamps}
        )

    def _get_duration(self, input_path: Path) -> float:
        """Get video duration in seconds via ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            str(input_path),
        ]
        result = self.run_command(cmd)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))

    def _collect_frames(
        self, output_dir: Path, fmt: str, interval: float
    ) -> list[dict]:
        """Collect extracted frame files and build metadata."""
        frames = []
        pattern = f"frame_*.{fmt}"
        for i, path in enumerate(sorted(output_dir.glob(pattern))):
            frames.append({
                "path": str(path),
                "timestamp_seconds": round(i * interval, 3),
                "index": i,
            })
        return frames
