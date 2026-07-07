"""Scene detection tool wrapping PySceneDetect.

Detects scene boundaries and shot changes in video. Falls back to
FFmpeg-based detection if PySceneDetect is not installed.
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
    ToolStatus,
    ToolTier,
)


class SceneDetect(BaseTool):
    name = "scene_detect"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "FFmpeg is required. For better detection install PySceneDetect:\n"
        "pip install scenedetect[opencv]"
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "detect_scenes",
        "detect_content_changes",
        "detect_threshold",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "method": {
                "type": "string",
                "enum": ["content", "threshold", "adaptive"],
                "default": "content",
            },
            "threshold": {
                "type": "number",
                "description": "Detection threshold (method-dependent)",
            },
            "min_scene_length_seconds": {
                "type": "number",
                "minimum": 0.1,
                "default": 1.0,
            },
            "output_path": {"type": "string", "description": "Path for scene list JSON"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=100)
    idempotency_key_fields = ["input_path", "method", "threshold"]
    side_effects = ["writes scene list JSON to output_path"]
    user_visible_verification = [
        "Spot-check detected scene boundaries against the video",
    ]

    def _has_pyscenedetect(self) -> bool:
        try:
            import scenedetect  # noqa: F401
            return True
        except ImportError:
            return False

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        start = time.time()

        if self._has_pyscenedetect():
            scenes = self._detect_pyscenedetect(inputs)
        else:
            scenes = self._detect_ffmpeg(inputs)

        elapsed = time.time() - start

        # Write scene list
        output_path = Path(
            inputs.get("output_path", str(input_path.with_suffix(".scenes.json")))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"scenes": scenes}, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "scene_count": len(scenes),
                "scenes": scenes,
                "method": "pyscenedetect" if self._has_pyscenedetect() else "ffmpeg",
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _detect_pyscenedetect(self, inputs: dict[str, Any]) -> list[dict]:
        """Use PySceneDetect for scene detection."""
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector, ThresholdDetector, AdaptiveDetector

        input_path = str(inputs["input_path"])
        method = inputs.get("method", "content")
        threshold = inputs.get("threshold")
        min_scene_len = inputs.get("min_scene_length_seconds", 1.0)

        video = open_video(input_path)
        scene_manager = SceneManager()

        if method == "content":
            detector = ContentDetector(
                threshold=threshold or 27.0,
                min_scene_len=int(min_scene_len * video.frame_rate),
            )
        elif method == "threshold":
            detector = ThresholdDetector(
                threshold=threshold or 12.0,
                min_scene_len=int(min_scene_len * video.frame_rate),
            )
        elif method == "adaptive":
            detector = AdaptiveDetector(
                adaptive_threshold=threshold or 3.0,
                min_scene_len=int(min_scene_len * video.frame_rate),
            )
        else:
            detector = ContentDetector()

        scene_manager.add_detector(detector)
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        scenes = []
        for i, (scene_start, scene_end) in enumerate(scene_list):
            scenes.append({
                "index": i,
                "start_seconds": round(scene_start.get_seconds(), 3),
                "end_seconds": round(scene_end.get_seconds(), 3),
                "duration_seconds": round(
                    scene_end.get_seconds() - scene_start.get_seconds(), 3
                ),
            })

        return scenes

    @staticmethod
    def _escape_lavfi_movie_path(path: str) -> str:
        """Escape a path for FFmpeg lavfi movie=... without allowing filter injection."""
        normalized = path.replace("\\", "/")
        if "'" in normalized:
            raise ValueError("FFmpeg lavfi movie paths containing single quotes are unsupported")
        escaped = []
        for char in normalized:
            if char in "\\:,[];":
                escaped.append("\\" + char)
            else:
                escaped.append(char)
        return "".join(escaped)

    def _detect_ffmpeg(self, inputs: dict[str, Any]) -> list[dict]:
        """Fallback: use FFmpeg scene change filter."""
        input_path = str(inputs["input_path"])
        threshold = inputs.get("threshold", 0.3)
        min_scene_len = inputs.get("min_scene_length_seconds", 1.0)
        escaped_input = self._escape_lavfi_movie_path(input_path)

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "frame=pts_time",
            "-of", "json",
            "-f", "lavfi",
            f"movie='{escaped_input}',select='gt(scene,{threshold})'",
        ]

        try:
            result = self.run_command(cmd, timeout=120)
            data = json.loads(result.stdout)
        except Exception:
            # If ffprobe lavfi approach fails, try a simpler method
            return self._detect_ffmpeg_simple(input_path, threshold, min_scene_len)

        change_points = [0.0]
        for frame in data.get("frames", []):
            ts = float(frame.get("pts_time", 0))
            if ts - change_points[-1] >= min_scene_len:
                change_points.append(ts)

        # Get total duration
        dur_cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json", input_path,
        ]
        dur_result = self.run_command(dur_cmd)
        total_dur = float(json.loads(dur_result.stdout)["format"]["duration"])
        change_points.append(total_dur)

        scenes = []
        for i in range(len(change_points) - 1):
            start = change_points[i]
            end = change_points[i + 1]
            scenes.append({
                "index": i,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "duration_seconds": round(end - start, 3),
            })

        return scenes

    def _detect_ffmpeg_simple(
        self, input_path: str, threshold: float, min_scene_len: float
    ) -> list[dict]:
        """Simplest fallback: split into uniform segments."""
        dur_cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json", input_path,
        ]
        dur_result = self.run_command(dur_cmd)
        total_dur = float(json.loads(dur_result.stdout)["format"]["duration"])

        # Use select filter to find scene changes via stdout
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ]
        try:
            result = self.run_command(cmd, timeout=120)
            output = result.stderr
        except Exception:
            output = ""

        import re
        change_points = [0.0]
        for match in re.finditer(r"pts_time:(\d+\.?\d*)", output):
            ts = float(match.group(1))
            if ts - change_points[-1] >= min_scene_len:
                change_points.append(ts)
        change_points.append(total_dur)

        scenes = []
        for i in range(len(change_points) - 1):
            start = change_points[i]
            end = change_points[i + 1]
            scenes.append({
                "index": i,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "duration_seconds": round(end - start, 3),
            })

        return scenes
