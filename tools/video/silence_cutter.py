"""Silence cutter tool for automatic jump cuts.

Detects silent segments in talking-head footage and removes them,
creating tight jump cuts. Uses FFmpeg's silencedetect filter — no
external dependencies beyond FFmpeg.

Modes:
  - remove: Cut out silent segments entirely (jump cut)
  - speed_up: Speed up silent segments instead of cutting (less jarring)
  - mark: Don't cut — just output silence timestamps for manual review
"""

from __future__ import annotations

import json
import re
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


class SilenceCutter(BaseTool):
    name = "silence_cutter"
    version = "0.1.1"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg"]

    capabilities = [
        "silence_detection",
        "jump_cut",
        "silence_removal",
        "silence_speedup",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["remove", "speed_up", "mark"],
                "default": "remove",
                "description": "remove=jump cut, speed_up=fast-forward silence, mark=detect only",
            },
            "silence_threshold_db": {
                "type": "number",
                "default": -35,
                "description": "Audio level below this (in dB) is considered silence. Lower = more sensitive.",
            },
            "min_silence_duration": {
                "type": "number",
                "default": 0.5,
                "minimum": 0.1,
                "description": "Minimum silence duration in seconds to trigger a cut",
            },
            "padding_seconds": {
                "type": "number",
                "default": 0.08,
                "minimum": 0.0,
                "description": "Seconds of silence to keep on each side of speech (prevents clipped words)",
            },
            "silence_speed_factor": {
                "type": "number",
                "default": 6.0,
                "minimum": 1.5,
                "maximum": 100.0,
                "description": "Speed multiplier for silent segments (only used in speed_up mode)",
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 18},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=4000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["FFmpeg error"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = [
        "input_path", "mode", "silence_threshold_db", "min_silence_duration",
        "padding_seconds", "silence_speed_factor", "codec", "crf",
    ]
    side_effects = ["writes cut video to output_path"]
    user_visible_verification = [
        "Watch output for unnaturally clipped words at cut points",
        "Compare duration: output should be noticeably shorter than input",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        mode = inputs.get("mode", "remove")
        start = time.time()

        # Step 1: Detect silence segments
        threshold_db = inputs.get("silence_threshold_db", -35)
        min_dur = inputs.get("min_silence_duration", 0.5)
        padding = inputs.get("padding_seconds", 0.08)

        silences = self._detect_silence(input_path, threshold_db, min_dur)

        if not silences:
            elapsed = time.time() - start
            return ToolResult(
                success=True,
                data={
                    "message": "No silence detected — video unchanged",
                    "silence_segments": 0,
                    "input": str(input_path),
                    "output": str(input_path),
                },
                artifacts=[str(input_path)],
                duration_seconds=round(elapsed, 2),
            )

        # Get total duration
        total_duration = self._get_duration(input_path)

        # Step 2: Compute speech segments (inverse of silence)
        speech_segments = self._compute_speech_segments(
            silences, total_duration, padding
        )

        # Step 3: Handle based on mode
        if mode == "mark":
            elapsed = time.time() - start
            output_json = Path(
                inputs.get("output_path", str(input_path.with_suffix(".silence.json")))
            )
            result_data = {
                "silences": silences,
                "speech_segments": speech_segments,
                "total_duration": total_duration,
                "silence_duration": sum(s["duration"] for s in silences),
                "speech_duration": sum(s["end"] - s["start"] for s in speech_segments),
            }
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
            return ToolResult(
                success=True,
                data={
                    "mode": "mark",
                    "silence_segments": len(silences),
                    "speech_segments": len(speech_segments),
                    "silence_duration_seconds": round(result_data["silence_duration"], 2),
                    "speech_duration_seconds": round(result_data["speech_duration"], 2),
                    "output": str(output_json),
                },
                artifacts=[str(output_json)],
                duration_seconds=round(elapsed, 2),
            )

        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_cut")))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 18)

        if mode == "speed_up":
            speed_factor = inputs.get("silence_speed_factor", 6.0)
            result = self._render_speed_up(
                input_path, output_path, silences, speech_segments,
                total_duration, speed_factor, codec, crf,
            )
        else:
            result = self._render_jump_cut(
                input_path, output_path, speech_segments, codec, crf,
            )

        if not result.success:
            return result

        elapsed = time.time() - start

        silence_dur = sum(s["duration"] for s in silences)
        speech_dur = sum(s["end"] - s["start"] for s in speech_segments)

        return ToolResult(
            success=True,
            data={
                "mode": mode,
                "input": str(input_path),
                "output": str(output_path),
                "input_duration": round(total_duration, 2),
                "output_duration": round(speech_dur, 2) if mode == "remove" else None,
                "silence_removed_seconds": round(silence_dur, 2),
                "silence_segments": len(silences),
                "speech_segments": len(speech_segments),
                "time_saved_percent": round(silence_dur / total_duration * 100, 1) if total_duration > 0 else 0,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _detect_silence(
        self, input_path: Path, threshold_db: float, min_duration: float
    ) -> list[dict]:
        """Detect silent segments using FFmpeg silencedetect filter."""
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
            "-f", "null", "-",
        ]

        try:
            result = self.run_command(cmd, timeout=300)
            output = result.stderr
        except Exception as e:
            # FFmpeg writes to stderr even on success for filters
            output = str(e)

        # Parse silencedetect output
        # Format: [silencedetect @ ...] silence_start: 1.234
        #         [silencedetect @ ...] silence_end: 2.567 | silence_duration: 1.333
        starts = re.findall(r"silence_start:\s*([\d.]+)", output)
        ends = re.findall(r"silence_end:\s*([\d.]+)", output)
        durations = re.findall(r"silence_duration:\s*([\d.]+)", output)

        silences = []
        for i in range(min(len(starts), len(ends))):
            silences.append({
                "start": float(starts[i]),
                "end": float(ends[i]),
                "duration": float(durations[i]) if i < len(durations) else float(ends[i]) - float(starts[i]),
            })

        return silences

    def _get_duration(self, input_path: Path) -> float:
        """Get video duration via ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json", str(input_path),
        ]
        try:
            result = self.run_command(cmd)
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return 0.0

    def _compute_speech_segments(
        self, silences: list[dict], total_duration: float, padding: float
    ) -> list[dict]:
        """Compute speech segments as the inverse of silence segments, with padding."""
        segments = []
        cursor = 0.0

        for silence in silences:
            speech_end = silence["start"] + padding
            if speech_end > cursor:
                segments.append({"start": cursor, "end": min(speech_end, total_duration)})
            cursor = max(cursor, silence["end"] - padding)

        # Final segment after last silence
        if cursor < total_duration:
            segments.append({"start": cursor, "end": total_duration})

        # Merge very short gaps (segments < 0.05s apart)
        merged = []
        for seg in segments:
            if seg["end"] - seg["start"] < 0.01:
                continue  # Skip tiny segments
            if merged and seg["start"] - merged[-1]["end"] < 0.05:
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)

        return merged

    def _render_jump_cut(
        self,
        input_path: Path, output_path: Path,
        speech_segments: list[dict],
        codec: str, crf: int,
    ) -> ToolResult:
        """Remove silence by concatenating speech segments."""
        if not speech_segments:
            return ToolResult(success=False, error="No speech segments found")

        temp_dir = output_path.parent / ".silence_cut_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Cut each speech segment
            seg_files = []
            for i, seg in enumerate(speech_segments):
                seg_path = temp_dir / f"seg_{i:04d}.mp4"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-ss", f"{seg['start']:.3f}",
                    "-to", f"{seg['end']:.3f}",
                    "-c:v", codec, "-crf", str(crf), "-preset", "fast",
                    "-c:a", "aac", "-b:a", "192k",
                    # Force keyframe at start for clean cuts
                    "-force_key_frames", f"{seg['start']:.3f}",
                    str(seg_path),
                ]
                self.run_command(cmd, timeout=120)
                if seg_path.exists() and seg_path.stat().st_size > 0:
                    seg_files.append(seg_path)

            if not seg_files:
                return ToolResult(success=False, error="No segments were successfully cut")

            # Concat all segments
            list_path = temp_dir / "concat_list.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for sf in seg_files:
                    safe_path = str(sf.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(output_path),
            ]
            self.run_command(cmd, timeout=120)

            return ToolResult(success=True)
        except Exception as e:
            return ToolResult(success=False, error=f"Jump cut render failed: {e}")
        finally:
            # Clean up temp files
            for f in temp_dir.glob("*"):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    def _render_speed_up(
        self,
        input_path: Path, output_path: Path,
        silences: list[dict], speech_segments: list[dict],
        total_duration: float,
        speed_factor: float,
        codec: str, crf: int,
    ) -> ToolResult:
        """Speed up silent segments instead of removing them.

        This is less jarring than jump cuts — the viewer sees a brief
        fast-forward during pauses.
        """
        temp_dir = output_path.parent / ".silence_speed_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Build a timeline of segments: speech at 1x, silence at Nx
            all_segments = []

            cursor = 0.0
            for seg in speech_segments:
                if seg["start"] > cursor:
                    all_segments.append({
                        "start": cursor, "end": seg["start"], "speed": speed_factor
                    })
                all_segments.append({**seg, "speed": 1.0})
                cursor = seg["end"]
            if cursor < total_duration:
                all_segments.append({
                    "start": cursor, "end": total_duration, "speed": speed_factor
                })

            # Process each segment
            seg_files = []
            for i, seg in enumerate(all_segments):
                seg_path = temp_dir / f"seg_{i:04d}.mp4"
                duration = seg["end"] - seg["start"]
                if duration < 0.05:
                    continue

                if seg["speed"] == 1.0:
                    # Normal speed
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(input_path),
                        "-ss", f"{seg['start']:.3f}",
                        "-to", f"{seg['end']:.3f}",
                        "-c:v", codec, "-crf", str(crf), "-preset", "fast",
                        "-c:a", "aac", "-b:a", "192k",
                        str(seg_path),
                    ]
                else:
                    # Speed up
                    pts = 1.0 / seg["speed"]
                    atempo_chain = self._build_atempo_chain(seg["speed"])
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(input_path),
                        "-filter:v", (
                            f"trim=start={seg['start']:.6f}:end={seg['end']:.6f},"
                            f"setpts={pts:.8f}*(PTS-STARTPTS)"
                        ),
                        "-filter:a", (
                            f"atrim=start={seg['start']:.6f}:end={seg['end']:.6f},"
                            f"asetpts=PTS-STARTPTS,{atempo_chain}"
                        ),
                        "-c:v", codec, "-crf", str(crf), "-preset", "fast",
                        "-c:a", "aac", "-b:a", "192k",
                        str(seg_path),
                    ]

                self.run_command(cmd, timeout=120)
                if seg_path.exists() and seg_path.stat().st_size > 0:
                    seg_files.append(seg_path)

            if not seg_files:
                return ToolResult(success=False, error="No segments rendered")

            # Concat
            list_path = temp_dir / "concat_list.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for sf in seg_files:
                    safe_path = str(sf.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(output_path),
            ]
            self.run_command(cmd, timeout=120)

            return ToolResult(success=True)
        except Exception as e:
            return ToolResult(success=False, error=f"Speed-up render failed: {e}")
        finally:
            for f in temp_dir.glob("*"):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    @staticmethod
    def _build_atempo_chain(factor: float) -> str:
        """Build atempo filter chain. atempo accepts [0.5, 100.0]."""
        filters = []
        remaining = factor
        while remaining > 100.0:
            filters.append("atempo=100.0")
            remaining /= 100.0
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 45.0
