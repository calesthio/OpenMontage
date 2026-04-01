"""Analyze audio energy profile to find optimal playback offset.

Uses ffmpeg's ebur128 loudness meter to measure momentary loudness
at 100ms intervals, then identifies where the music "gets interesting"
(crosses a configurable energy threshold). Returns a recommended offset
in seconds plus the full energy profile.

Key use cases:
  - Skip quiet intros in ambient/cinematic music tracks
  - Find the peak energy section for a 30-second video from a 3-minute track
  - Determine if music needs looping (total duration vs video duration)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class AudioEnergy(BaseTool):
    name = "audio_energy"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "ffmpeg"
    stability = ToolStability.PRODUCTION
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
        "find_music_offset",
        "energy_profile",
        "best_window",
        "loop_recommendation",
    ]
    best_for = [
        "finding where ambient music gets interesting (skip quiet intros)",
        "choosing the best offset for a music track in a video",
        "determining if a music track needs looping for a longer video",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to audio file (mp3, wav, ogg, etc.)",
            },
            "video_duration_seconds": {
                "type": "number",
                "description": "Duration of the video this music will accompany. "
                "Used to recommend looping and find the best offset window.",
            },
            "energy_threshold_lufs": {
                "type": "number",
                "description": "Momentary loudness threshold in LUFS to consider "
                "music 'active' (default: -40). Higher = stricter. "
                "Typical: -50 for very quiet, -30 for energetic.",
                "default": -40,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=0, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["input_path"]
    side_effects = []

    def get_status(self) -> ToolStatus:
        if shutil.which("ffmpeg"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"File not found: {input_path}")

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return ToolResult(success=False, error="ffmpeg not found on PATH")

        threshold_lufs = inputs.get("energy_threshold_lufs", -40)
        video_duration = inputs.get("video_duration_seconds")

        start = time.time()

        # ------------------------------------------------------------------
        # Step 1: Get audio duration
        # ------------------------------------------------------------------
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return ToolResult(success=False, error="ffprobe not found on PATH")

        try:
            probe_result = subprocess.run(
                [
                    ffprobe, "-v", "quiet", "-print_format", "json",
                    "-show_format", str(input_path),
                ],
                capture_output=True, text=True, timeout=10,
            )
            probe_data = json.loads(probe_result.stdout)
            audio_duration = float(probe_data["format"]["duration"])
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to probe duration: {e}")

        # ------------------------------------------------------------------
        # Step 2: Run ebur128 loudness analysis
        # ------------------------------------------------------------------
        # ebur128 outputs momentary loudness (M:) every 100ms — very precise.
        try:
            result = subprocess.run(
                [
                    ffmpeg, "-i", str(input_path),
                    "-af", "ebur128",
                    "-f", "null", "-",
                ],
                capture_output=True, text=True, timeout=120,
            )
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="ebur128 analysis timed out (120s)")

        # ------------------------------------------------------------------
        # Step 3: Parse momentary loudness (M:) values
        # ------------------------------------------------------------------
        # Pattern: t: 0.0999773  TARGET:-23 LUFS    M:-120.7 S:-120.7 ...
        pattern = re.compile(r"t:\s*([\d.]+)\s+.*?M:\s*(-?[\d.]+)")
        raw_points: list[tuple[float, float]] = []

        for line in stderr.split("\n"):
            match = pattern.search(line)
            if match:
                t = float(match.group(1))
                m_lufs = float(match.group(2))
                raw_points.append((t, m_lufs))

        if not raw_points:
            return ToolResult(
                success=False,
                error="Failed to parse ebur128 output — no loudness data found",
            )

        # ------------------------------------------------------------------
        # Step 4: Downsample to 1-second intervals (average per second)
        # ------------------------------------------------------------------
        max_sec = int(raw_points[-1][0]) + 1
        energy_profile: list[dict[str, Any]] = []

        for sec in range(max_sec):
            # Collect all 100ms points within this second
            points_in_sec = [
                m for t, m in raw_points
                if sec <= t < sec + 1 and m > -120  # -120 = silence marker
            ]

            if points_in_sec:
                avg_lufs = sum(points_in_sec) / len(points_in_sec)
            else:
                avg_lufs = -120.0

            energy_profile.append({
                "time_seconds": sec,
                "loudness_lufs": round(avg_lufs, 1),
                "active": avg_lufs > threshold_lufs,
            })

        # ------------------------------------------------------------------
        # Step 5: Find key moments
        # ------------------------------------------------------------------
        # First active second (music becomes meaningful)
        first_active_sec = 0.0
        for seg in energy_profile:
            if seg["active"]:
                first_active_sec = float(seg["time_seconds"])
                break

        # Peak loudness second
        active_segments = [s for s in energy_profile if s["loudness_lufs"] > -120]
        if active_segments:
            peak_seg = max(active_segments, key=lambda s: s["loudness_lufs"])
            peak_sec = float(peak_seg["time_seconds"])
            peak_lufs = peak_seg["loudness_lufs"]
        else:
            peak_sec = 0.0
            peak_lufs = -120.0

        # ------------------------------------------------------------------
        # Step 6: Find best window for video duration
        # ------------------------------------------------------------------
        recommended_offset = first_active_sec
        offset_reason = (
            f"First active music at {first_active_sec}s "
            f"(threshold: {threshold_lufs} LUFS)"
        )

        if video_duration and video_duration < audio_duration:
            window_size = int(video_duration)
            loudness_values = [
                s["loudness_lufs"] if s["loudness_lufs"] > -120 else -60
                for s in energy_profile
            ]

            if len(loudness_values) >= window_size:
                best_avg = -999.0
                best_start = 0

                for i in range(len(loudness_values) - window_size + 1):
                    window = loudness_values[i : i + window_size]
                    avg = sum(window) / len(window)
                    if avg > best_avg:
                        best_avg = avg
                        best_start = i

                recommended_offset = float(best_start)
                offset_reason = (
                    f"Best {window_size}s window starts at {best_start}s "
                    f"(avg loudness: {round(best_avg, 1)} LUFS)"
                )

        # ------------------------------------------------------------------
        # Step 7: Loop recommendation
        # ------------------------------------------------------------------
        needs_loop = False
        loop_info = None
        if video_duration:
            available_from_offset = audio_duration - recommended_offset
            if available_from_offset < video_duration:
                needs_loop = True
                loop_info = {
                    "music_available_from_offset": round(available_from_offset, 1),
                    "video_duration": round(video_duration, 1),
                    "shortfall_seconds": round(
                        video_duration - available_from_offset, 1
                    ),
                    "recommendation": (
                        f"Music from offset {recommended_offset}s provides only "
                        f"{round(available_from_offset, 1)}s but video is "
                        f"{round(video_duration, 1)}s. Set loop=true and "
                        f"offsetSeconds={recommended_offset} in audio config."
                    ),
                }

        # ------------------------------------------------------------------
        # Result
        # ------------------------------------------------------------------
        result_data = {
            "file": str(input_path),
            "audio_duration_seconds": round(audio_duration, 1),
            "analysis": {
                "threshold_lufs": threshold_lufs,
                "total_seconds": len(energy_profile),
                "active_seconds": sum(1 for s in energy_profile if s["active"]),
                "quiet_intro_seconds": first_active_sec,
                "peak_loudness_at_seconds": peak_sec,
                "peak_loudness_lufs": peak_lufs,
            },
            "recommended_offset_seconds": recommended_offset,
            "offset_reason": offset_reason,
            "needs_loop": needs_loop,
            "loop_info": loop_info,
            "energy_profile": energy_profile,
        }

        return ToolResult(
            success=True,
            data=result_data,
            duration_seconds=round(time.time() - start, 2),
        )
