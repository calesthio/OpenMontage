"""Video stitch tool wrapping FFmpeg.

Multi-clip assembly with validation, transitions, and spatial layouts.
Supports sequential concatenation (TikTok-style stitch), crossfade/fade
transitions, and spatial compositions (side-by-side, vertical stack,
picture-in-picture) for duet-style content.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

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


class VideoStitch(BaseTool):
    name = "video_stitch"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html\n"
        "Windows: winget install FFmpeg\n"
        "macOS: brew install ffmpeg\n"
        "Linux: sudo apt install ffmpeg"
    )
    agent_skills = ["ffmpeg", "video-toolkit"]

    capabilities = [
        "validate_clips",
        "stitch",
        "crossfade",
        "fade_through_black",
        "preview_stitch",
        "spatial_side_by_side",
        "spatial_vertical_stack",
        "spatial_picture_in_picture",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["validate", "stitch", "preview_stitch", "spatial"],
            },
            "clips": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of input video file paths",
            },
            "output_path": {"type": "string"},
            "transition": {
                "type": "string",
                "enum": ["cut", "crossfade", "fade"],
                "default": "cut",
                "description": "Transition type: cut (default), crossfade, or fade (fade-through-black)",
            },
            "transition_duration": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 5.0,
                "default": 0.5,
                "description": "Transition duration in seconds",
            },
            "auto_normalize": {
                "type": "boolean",
                "default": False,
                "description": "Re-encode clips to a common format before concat if they differ",
            },
            "target_resolution": {
                "type": "string",
                "description": "Target resolution for normalization (e.g. '1920x1080')",
            },
            "target_fps": {
                "type": "integer",
                "description": "Target FPS for normalization",
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 23},
            "preset": {"type": "string", "default": "medium"},
            "profile": {
                "type": "string",
                "description": "Media profile name from media_profiles.py",
            },
            "layout": {
                "type": "string",
                "enum": ["side_by_side", "vertical_stack", "picture_in_picture"],
                "description": "Spatial layout for the spatial operation",
            },
            "pip_position": {
                "type": "string",
                "enum": ["top_left", "top_right", "bottom_left", "bottom_right"],
                "default": "bottom_right",
                "description": "Position of the PiP overlay",
            },
            "pip_scale": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 0.5,
                "default": 0.3,
                "description": "Scale of PiP overlay relative to base video",
            },
            "pip_margin": {
                "type": "integer",
                "default": 10,
                "description": "Margin in pixels for PiP overlay from edges",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, return what would be done without executing",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=5000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["Conversion failed"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "clips", "transition", "layout"]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = [
        "Play the stitched output and verify clip ordering, transitions, and A/V sync",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]
        start = time.time()

        if inputs.get("dry_run"):
            return ToolResult(
                success=True,
                data=self.dry_run(inputs),
            )

        try:
            if operation == "validate":
                result = self._validate(inputs)
            elif operation == "stitch":
                result = self._stitch(inputs)
            elif operation == "preview_stitch":
                result = self._preview_stitch(inputs)
            elif operation == "spatial":
                result = self._spatial(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Preflight check: validate clips and report what would happen."""
        clips = inputs.get("clips", [])
        operation = inputs.get("operation", "stitch")
        info = {
            "tool": self.name,
            "operation": operation,
            "clip_count": len(clips),
            "transition": inputs.get("transition", "cut"),
            "auto_normalize": inputs.get("auto_normalize", False),
            "estimated_cost_usd": self.estimate_cost(inputs),
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }
        if clips:
            probe_results = []
            for clip in clips:
                if Path(clip).exists():
                    probe = self._probe_clip(clip)
                    if probe:
                        probe_results.append(probe)
            info["clip_info"] = probe_results
        return info

    # ------------------------------------------------------------------
    # Audio-stream detection and silent-audio helpers
    # ------------------------------------------------------------------

    def _clip_has_audio(self, clip_path: str) -> bool:
        """Return True if *clip_path* contains at least one audio stream."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "json",
            str(clip_path),
        ]
        try:
            proc = self.run_command(cmd)
            data = json.loads(proc.stdout)
            return len(data.get("streams", [])) > 0
        except Exception:
            return False

    def _ensure_audio_for_clips(
        self,
        clips: list[str],
        temp_dir: Path,
        temp_files: list[Path],
    ) -> list[str]:
        """Return a list of clip paths where every clip is guaranteed to have
        an audio stream.  Clips that already contain audio are returned as-is.
        For clips without audio, a silent stereo AAC track is muxed in and the
        path to the new file is returned instead.  All generated temp files are
        appended to *temp_files* so the caller can clean them up.
        """
        result: list[str] = []
        for i, clip in enumerate(clips):
            if self._clip_has_audio(clip):
                result.append(clip)
            else:
                augmented = temp_dir / f"audio_aug_{i:04d}.mp4"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(clip),
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    str(augmented),
                ]
                self.run_command(cmd)
                temp_files.append(augmented)
                result.append(str(augmented))
        return result

    # ------------------------------------------------------------------
    # Probe helper
    # ------------------------------------------------------------------

    def _probe_clip(self, clip_path: str) -> Optional[dict[str, Any]]:
        """Probe a single clip with ffprobe and return metadata dict."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(clip_path),
        ]
        try:
            proc = self.run_command(cmd)
            data = json.loads(proc.stdout)
        except Exception:
            return None

        info: dict[str, Any] = {"path": str(clip_path)}

        # Extract video stream info
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["video_codec"] = stream.get("codec_name")
                info["pixel_format"] = stream.get("pix_fmt")
                # Parse fps from r_frame_rate (e.g. "30/1")
                rfr = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = rfr.split("/")
                    info["fps"] = round(int(num) / int(den), 2)
                except (ValueError, ZeroDivisionError):
                    info["fps"] = None
                break

        # Extract audio stream info
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                info["audio_codec"] = stream.get("codec_name")
                info["sample_rate"] = stream.get("sample_rate")
                info["audio_channels"] = stream.get("channels")
                break

        # Duration from format
        fmt = data.get("format", {})
        try:
            info["duration"] = float(fmt.get("duration", 0))
        except (TypeError, ValueError):
            info["duration"] = 0.0
        try:
            info["file_size_bytes"] = int(fmt.get("size", 0))
        except (TypeError, ValueError):
            info["file_size_bytes"] = 0

        return info

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    def _validate(self, inputs: dict[str, Any]) -> ToolResult:
        """Check clip compatibility: resolution, fps, codec, audio format.

        Returns a detailed report of mismatches.
        """
        clips = inputs.get("clips", [])
        if not clips:
            return ToolResult(success=False, error="No clips provided")

        # Probe all clips
        probes: list[dict[str, Any]] = []
        missing: list[str] = []
        probe_errors: list[str] = []

        for clip in clips:
            if not Path(clip).exists():
                missing.append(clip)
                continue
            info = self._probe_clip(clip)
            if info is None:
                probe_errors.append(clip)
            else:
                probes.append(info)

        if missing:
            return ToolResult(
                success=False,
                error=f"Clips not found: {', '.join(missing)}",
            )
        if probe_errors:
            return ToolResult(
                success=False,
                error=f"Failed to probe clips: {', '.join(probe_errors)}",
            )

        # Compare properties across clips
        mismatches: list[dict[str, Any]] = []
        reference = probes[0]
        check_fields = [
            ("width", "resolution width"),
            ("height", "resolution height"),
            ("fps", "frame rate"),
            ("video_codec", "video codec"),
            ("pixel_format", "pixel format"),
            ("audio_codec", "audio codec"),
            ("sample_rate", "audio sample rate"),
            ("audio_channels", "audio channels"),
        ]

        for i, probe in enumerate(probes[1:], start=1):
            clip_mismatches: list[str] = []
            for field_key, label in check_fields:
                ref_val = reference.get(field_key)
                cur_val = probe.get(field_key)
                if ref_val is not None and cur_val is not None and ref_val != cur_val:
                    clip_mismatches.append(
                        f"{label}: clip[0]={ref_val} vs clip[{i}]={cur_val}"
                    )
            if clip_mismatches:
                mismatches.append({
                    "clip_index": i,
                    "clip_path": probe["path"],
                    "differences": clip_mismatches,
                })

        compatible = len(mismatches) == 0
        total_duration = sum(p.get("duration", 0) for p in probes)

        return ToolResult(
            success=True,
            data={
                "operation": "validate",
                "clip_count": len(clips),
                "compatible": compatible,
                "total_duration": round(total_duration, 2),
                "reference_clip": {
                    "path": reference["path"],
                    "resolution": f"{reference.get('width')}x{reference.get('height')}",
                    "fps": reference.get("fps"),
                    "video_codec": reference.get("video_codec"),
                    "audio_codec": reference.get("audio_codec"),
                },
                "mismatches": mismatches,
                "clips": probes,
            },
        )

    # ------------------------------------------------------------------
    # Normalization helper
    # ------------------------------------------------------------------

    def _resolve_normalization_target(
        self, inputs: dict[str, Any], probes: list[dict[str, Any]]
    ) -> tuple[int, int, int, str, str]:
        """Determine the target resolution, fps, and codecs for normalization.

        Returns (width, height, fps, video_codec, audio_codec).
        """
        # If a media profile is specified, use it
        profile_name = inputs.get("profile")
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                profile = get_profile(profile_name)
                return (profile.width, profile.height, profile.fps, profile.codec, profile.audio_codec)
            except (ImportError, ValueError):
                pass

        # Explicit target overrides
        target_w, target_h = None, None
        if inputs.get("target_resolution"):
            parts = inputs["target_resolution"].split("x")
            if len(parts) == 2:
                target_w, target_h = int(parts[0]), int(parts[1])

        target_fps = inputs.get("target_fps")

        # Fall back to first clip as reference
        ref = probes[0] if probes else {}
        width = target_w or ref.get("width", 1920)
        height = target_h or ref.get("height", 1080)
        fps = target_fps or ref.get("fps", 30)
        video_codec = inputs.get("codec", "libx264")
        audio_codec = "aac"

        return (width, height, int(fps), video_codec, audio_codec)

    def _normalize_clip(
        self,
        clip_path: str,
        output_path: Path,
        width: int,
        height: int,
        fps: int,
        video_codec: str,
        audio_codec: str,
        crf: int,
        preset: str,
    ) -> None:
        """Re-encode a clip to the target format."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(fps),
            "-c:v", video_codec, "-crf", str(crf), "-preset", preset,
            "-c:a", audio_codec, "-ar", "44100", "-ac", "2",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        self.run_command(cmd)

    def _needs_normalization(self, probes: list[dict[str, Any]]) -> bool:
        """Check whether clips need normalization to be concat-compatible."""
        if len(probes) < 2:
            return False
        ref = probes[0]
        for probe in probes[1:]:
            for key in ("width", "height", "fps", "video_codec", "audio_codec", "sample_rate"):
                if ref.get(key) != probe.get(key) and ref.get(key) is not None:
                    return True
        return False

    # ------------------------------------------------------------------
    # stitch
    # ------------------------------------------------------------------

    def _stitch(self, inputs: dict[str, Any]) -> ToolResult:
        """Concatenate clips sequentially with FFmpeg concat demuxer.

        Supports transitions: cut (default), crossfade, fade-through-black.
        """
        clips = inputs.get("clips", [])
        if not clips:
            return ToolResult(success=False, error="No clips provided")
        if len(clips) < 2:
            return ToolResult(success=False, error="At least 2 clips required for stitch")

        output_path = Path(inputs.get("output_path", "stitched_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        transition = inputs.get("transition", "cut")
        transition_dur = inputs.get("transition_duration", 0.5)
        auto_normalize = inputs.get("auto_normalize", False)
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)
        preset = inputs.get("preset", "medium")

        # Verify all clips exist
        for clip in clips:
            if not Path(clip).exists():
                return ToolResult(success=False, error=f"Clip not found: {clip}")

        # Probe clips for compatibility check
        probes: list[dict[str, Any]] = []
        for clip in clips:
            info = self._probe_clip(clip)
            if info is None:
                return ToolResult(success=False, error=f"Failed to probe clip: {clip}")
            probes.append(info)

        needs_norm = self._needs_normalization(probes)

        # If clips are incompatible and auto_normalize is off, fail with advice
        if needs_norm and not auto_normalize and transition == "cut":
            return ToolResult(
                success=False,
                error=(
                    "Clips have mismatched properties (resolution/fps/codec). "
                    "Set auto_normalize=true to re-encode to a common format, "
                    "or use a transition type other than 'cut'."
                ),
            )

        temp_dir = output_path.parent / ".stitch_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_files: list[Path] = []

        try:
            # Normalize clips if needed
            working_clips: list[str] = []
            if needs_norm or auto_normalize or transition != "cut":
                width, height, fps, vid_codec, aud_codec = self._resolve_normalization_target(inputs, probes)
                for i, clip in enumerate(clips):
                    norm_path = temp_dir / f"norm_{i:04d}.mp4"
                    self._normalize_clip(clip, norm_path, width, height, fps, vid_codec, aud_codec, crf, preset)
                    working_clips.append(str(norm_path))
                    temp_files.append(norm_path)
            else:
                working_clips = list(clips)

            # For crossfade/fade transitions, ensure every clip has an audio
            # stream so that the acrossfade filter does not fail.  Image-derived
            # video clips typically lack audio; we add a silent track for those.
            if transition in ("crossfade", "fade"):
                working_clips = self._ensure_audio_for_clips(
                    working_clips, temp_dir, temp_files,
                )

            if transition == "cut":
                result_data = self._stitch_cut(working_clips, output_path, temp_dir, temp_files)
            elif transition == "crossfade":
                result_data = self._stitch_crossfade(working_clips, output_path, transition_dur, probes)
            elif transition == "fade":
                result_data = self._stitch_fade_through_black(working_clips, output_path, transition_dur, probes)
            else:
                return ToolResult(success=False, error=f"Unknown transition type: {transition}")

            # Get output file info
            file_size = output_path.stat().st_size if output_path.exists() else 0
            out_probe = self._probe_clip(str(output_path))
            out_duration = out_probe.get("duration", 0) if out_probe else 0

            return ToolResult(
                success=True,
                data={
                    "operation": "stitch",
                    "clip_count": len(clips),
                    "transition": transition,
                    "transition_duration": transition_dur if transition != "cut" else 0,
                    "auto_normalized": needs_norm or auto_normalize,
                    "output": str(output_path),
                    "duration": round(out_duration, 2),
                    "file_size_bytes": file_size,
                    **result_data,
                },
                artifacts=[str(output_path)],
            )
        finally:
            self._cleanup_temp(temp_dir, temp_files)

    def _stitch_cut(
        self,
        clips: list[str],
        output_path: Path,
        temp_dir: Path,
        temp_files: list[Path],
    ) -> dict[str, Any]:
        """Simple concat via FFmpeg concat demuxer (no transition)."""
        concat_list = temp_dir / "concat_list.txt"
        temp_files.append(concat_list)
        with open(concat_list, "w", encoding="utf-8") as f:
            for clip in clips:
                safe_path = str(Path(clip).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_path),
        ]
        self.run_command(cmd)
        return {"method": "concat_demuxer"}

    def _stitch_crossfade(
        self,
        clips: list[str],
        output_path: Path,
        duration: float,
        probes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Crossfade between adjacent clips using xfade filter."""
        if len(clips) == 2:
            # Simple two-clip crossfade
            cmd = [
                "ffmpeg", "-y",
                "-i", clips[0],
                "-i", clips[1],
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={duration}:offset={self._get_xfade_offset(probes, 0, duration)}[v];"
                f"[0:a][1:a]acrossfade=d={duration}[a]",
                "-map", "[v]", "-map", "[a]",
                str(output_path),
            ]
            self.run_command(cmd)
        else:
            # Chain crossfades for N clips
            self._chain_xfade(clips, output_path, duration, probes, transition="fade")
        return {"method": "xfade_crossfade"}

    def _stitch_fade_through_black(
        self,
        clips: list[str],
        output_path: Path,
        duration: float,
        probes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Fade-through-black between adjacent clips using xfade fadeblack."""
        if len(clips) == 2:
            cmd = [
                "ffmpeg", "-y",
                "-i", clips[0],
                "-i", clips[1],
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fadeblack:duration={duration}:offset={self._get_xfade_offset(probes, 0, duration)}[v];"
                f"[0:a][1:a]acrossfade=d={duration}[a]",
                "-map", "[v]", "-map", "[a]",
                str(output_path),
            ]
            self.run_command(cmd)
        else:
            self._chain_xfade(clips, output_path, duration, probes, transition="fadeblack")
        return {"method": "xfade_fadeblack"}

    def _get_xfade_offset(
        self, probes: list[dict[str, Any]], clip_index: int, duration: float
    ) -> float:
        """Calculate xfade offset for a given clip pair.

        The offset is the timestamp in the output where the transition starts,
        which equals the duration of the first clip minus the transition duration.
        """
        clip_dur = probes[clip_index].get("duration", 0) if clip_index < len(probes) else 0
        offset = max(0, clip_dur - duration)
        return round(offset, 3)

    def _chain_xfade(
        self,
        clips: list[str],
        output_path: Path,
        duration: float,
        probes: list[dict[str, Any]],
        transition: str,
    ) -> None:
        """Chain xfade filters for N > 2 clips.

        Builds a complex filtergraph that progressively applies xfade
        between each adjacent pair of clips.
        """
        n = len(clips)
        input_args: list[str] = []
        for clip in clips:
            input_args.extend(["-i", clip])

        # Calculate cumulative offsets
        # Each xfade offset = cumulative duration of all previous segments
        # minus cumulative transition overlaps minus current transition duration
        video_filters: list[str] = []
        audio_filters: list[str] = []
        cumulative_offset = 0.0

        for i in range(n - 1):
            clip_dur = probes[i].get("duration", 0) if i < len(probes) else 0
            offset = round(cumulative_offset + clip_dur - duration, 3)
            offset = max(0, offset)

            if i == 0:
                v_in1 = "[0:v]"
                a_in1 = "[0:a]"
            else:
                v_in1 = f"[vfade{i-1}]"
                a_in1 = f"[afade{i-1}]"

            v_in2 = f"[{i+1}:v]"
            a_in2 = f"[{i+1}:a]"

            if i < n - 2:
                v_out = f"[vfade{i}]"
                a_out = f"[afade{i}]"
            else:
                v_out = "[vout]"
                a_out = "[aout]"

            video_filters.append(
                f"{v_in1}{v_in2}xfade=transition={transition}:duration={duration}:offset={offset}{v_out}"
            )
            audio_filters.append(
                f"{a_in1}{a_in2}acrossfade=d={duration}{a_out}"
            )

            # Cumulative offset advances by clip duration minus overlap
            cumulative_offset = offset

        filter_complex = ";".join(video_filters + audio_filters)

        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        cmd.append(str(output_path))
        self.run_command(cmd)

    # ------------------------------------------------------------------
    # preview_stitch
    # ------------------------------------------------------------------

    def _preview_stitch(self, inputs: dict[str, Any]) -> ToolResult:
        """Generate a low-resolution preview of the stitched result."""
        clips = inputs.get("clips", [])
        if not clips:
            return ToolResult(success=False, error="No clips provided")
        if len(clips) < 2:
            return ToolResult(success=False, error="At least 2 clips required for preview")

        output_path = Path(inputs.get("output_path", "stitch_preview.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Verify all clips exist
        for clip in clips:
            if not Path(clip).exists():
                return ToolResult(success=False, error=f"Clip not found: {clip}")

        # Build preview by normalizing to low-res and stitching
        preview_inputs = dict(inputs)
        preview_inputs["auto_normalize"] = True
        preview_inputs["target_resolution"] = "640x360"
        preview_inputs["target_fps"] = 24
        preview_inputs["crf"] = 30
        preview_inputs["preset"] = "ultrafast"
        preview_inputs["output_path"] = str(output_path)

        # Delegate to _stitch with preview settings
        result = self._stitch(preview_inputs)

        if result.success:
            result.data["operation"] = "preview_stitch"
            result.data["preview"] = True
            result.data["preview_resolution"] = "640x360"

        return result

    # ------------------------------------------------------------------
    # spatial
    # ------------------------------------------------------------------

    def _spatial(self, inputs: dict[str, Any]) -> ToolResult:
        """Side-by-side, vertical stack, or picture-in-picture layouts.

        Designed for TikTok Stitch/Duet style compositions (D3.5.8).
        """
        clips = inputs.get("clips", [])
        if not clips or len(clips) < 2:
            return ToolResult(
                success=False,
                error="At least 2 clips required for spatial layout",
            )

        layout = inputs.get("layout")
        if not layout:
            return ToolResult(success=False, error="layout is required for spatial operation")

        output_path = Path(inputs.get("output_path", "spatial_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)

        # Verify all clips exist
        for clip in clips:
            if not Path(clip).exists():
                return ToolResult(success=False, error=f"Clip not found: {clip}")

        temp_dir = output_path.parent / ".spatial_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_files: list[Path] = []

        try:
            # side_by_side and vertical_stack use amix which requires audio
            # on both inputs.  Ensure silent tracks for audio-less clips.
            working_clips = list(clips)
            if layout in ("side_by_side", "vertical_stack"):
                working_clips = self._ensure_audio_for_clips(
                    working_clips, temp_dir, temp_files,
                )

            if layout == "side_by_side":
                self._spatial_side_by_side(working_clips, output_path, codec, crf)
            elif layout == "vertical_stack":
                self._spatial_vertical_stack(working_clips, output_path, codec, crf)
            elif layout == "picture_in_picture":
                self._spatial_pip(working_clips, output_path, inputs, codec, crf)
            else:
                return ToolResult(success=False, error=f"Unknown layout: {layout}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        finally:
            self._cleanup_temp(temp_dir, temp_files)

        file_size = output_path.stat().st_size if output_path.exists() else 0
        out_probe = self._probe_clip(str(output_path))
        out_duration = out_probe.get("duration", 0) if out_probe else 0

        return ToolResult(
            success=True,
            data={
                "operation": "spatial",
                "layout": layout,
                "clip_count": len(clips),
                "output": str(output_path),
                "duration": round(out_duration, 2),
                "file_size_bytes": file_size,
            },
            artifacts=[str(output_path)],
        )

    def _spatial_side_by_side(
        self, clips: list[str], output_path: Path, codec: str, crf: int
    ) -> None:
        """Place clips side by side (horizontal split).

        Both clips are scaled to the same height and placed left-right.
        Uses the first two clips; additional clips are ignored.
        """
        input_args = ["-i", clips[0], "-i", clips[1]]
        filter_complex = (
            "[0:v]scale=-2:480[left];"
            "[1:v]scale=-2:480[right];"
            "[left][right]hstack=inputs=2[v];"
            "[0:a][1:a]amix=inputs=2:duration=shortest[a]"
        )
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ])
        self.run_command(cmd)

    def _spatial_vertical_stack(
        self, clips: list[str], output_path: Path, codec: str, crf: int
    ) -> None:
        """Place clips in a vertical stack (top-bottom).

        Both clips are scaled to the same width and stacked vertically.
        Ideal for portrait/mobile viewing.
        """
        input_args = ["-i", clips[0], "-i", clips[1]]
        filter_complex = (
            "[0:v]scale=540:-2[top];"
            "[1:v]scale=540:-2[bottom];"
            "[top][bottom]vstack=inputs=2[v];"
            "[0:a][1:a]amix=inputs=2:duration=shortest[a]"
        )
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ])
        self.run_command(cmd)

    def _spatial_pip(
        self,
        clips: list[str],
        output_path: Path,
        inputs: dict[str, Any],
        codec: str,
        crf: int,
    ) -> None:
        """Picture-in-picture: overlay second clip on first.

        clips[0] is the base (full-screen), clips[1] is the PiP overlay.
        """
        pip_position = inputs.get("pip_position", "bottom_right")
        pip_scale = inputs.get("pip_scale", 0.3)
        pip_margin = inputs.get("pip_margin", 10)

        # Build position expression based on corner
        position_map = {
            "top_left": f"{pip_margin}:{pip_margin}",
            "top_right": f"main_w-overlay_w-{pip_margin}:{pip_margin}",
            "bottom_left": f"{pip_margin}:main_h-overlay_h-{pip_margin}",
            "bottom_right": f"main_w-overlay_w-{pip_margin}:main_h-overlay_h-{pip_margin}",
        }
        position = position_map.get(pip_position, position_map["bottom_right"])

        input_args = ["-i", clips[0], "-i", clips[1]]
        filter_complex = (
            f"[1:v]scale=iw*{pip_scale}:ih*{pip_scale}[pip];"
            f"[0:v][pip]overlay={position}:shortest=1[v]"
        )
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ])
        self.run_command(cmd)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_temp(temp_dir: Path, temp_files: list[Path]) -> None:
        """Remove temporary files and directory."""
        for f in temp_files:
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except OSError:
                pass
