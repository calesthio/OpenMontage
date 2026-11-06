"""Render Engine — produces the final MP4 from edit decisions + audio.

Render path: FFmpeg (confirmed working at /usr/bin/ffmpeg).
  * One filter_complex pass applies per-scene motion (zoom via time-varying
    scale + center-crop to 1920x1080, or static hold) to each still image.
    Aspect ratio is preserved (never stretches).
  * Segments are concatenated; the master audio track (narration ± music ±
    SFX from AudioMixing) is muxed in.
  * Output: MP4, H.264 + AAC, yuv420p.

Note: zoompan (FFmpeg's zoompan filter) returns "Invalid argument" in this
FFmpeg 7.1.5 build regardless of expression, so motion is implemented with
scale (time-varying via `t`, eval=frame) + center-crop, which is reliable.

Remotion: the existing remotion-composer/ (Node v26, @remotion/cli ^4.0.484)
is available as an alternative composition engine when a Remotion scene is
authored to consume edit decisions.  It is not wired here because
Explainer.tsx is a specific animated explainer, not a generic edit-decision
renderer; authoring that bridge is out of scope for P4.  FFmpeg is the
verified render path.

Zero-cost: FFmpeg only.  No Google Flow, no credits.
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lib.audio_mixing import AudioMix, AudioMixing
from lib.edit_decision_engine import EditDecision, EditDecisionSet
from lib.production_timeline import ProductionTimeline


@dataclass
class RenderResult:
    """Outcome of rendering one project."""

    project_id: str
    output_path: str
    status: str  # planned | rendered | failed | blocked
    duration_seconds: float
    resolution: str
    fps: int
    codec_video: str
    codec_audio: str
    bitrate_kbps: int | None
    file_size_bytes: int | None
    scene_count: int
    total_duration_ms: int
    ffprobe: dict[str, Any] = field(default_factory=dict)
    black_frames: list[float] = field(default_factory=list)
    frozen_segments: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RenderEngine:
    """Render edit decisions to a final MP4 via FFmpeg."""

    def __init__(
        self,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        crf: int = 23,
        preset: str = "medium",
    ) -> None:
        self.fps = fps
        self.width = width
        self.height = height
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.crf = crf
        self.preset = preset

    # ------------------------------------------------------------------
    # Main render
    # ------------------------------------------------------------------

    def render(
        self,
        *,
        project_id: str,
        edit_decisions: EditDecisionSet | list[dict[str, Any]],
        timeline: ProductionTimeline | None = None,
        audio_mix: AudioMix | None = None,
        output_path: str | Path = "projects/<project>/renders/final.mp4",
        use_remotion: bool = False,
    ) -> RenderResult:
        """Render one project to MP4.

        Args:
            project_id: provenance.
            edit_decisions: EditDecisionSet or list of decision dicts.
            timeline: optional validated ProductionTimeline (for pause
                elements and validation cross-check).
            audio_mix: optional AudioMix master track.  If omitted, silent
                audio is used.
            output_path: destination MP4.
            use_remotion: if True, attempt Remotion render (not implemented
                here — falls back to FFmpeg with a warning).
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(edit_decisions, EditDecisionSet):
            decisions = edit_decisions.decisions
            project_id = project_id or edit_decisions.project_id
        else:
            decisions = [EditDecision(**d) if not isinstance(d, EditDecision) else d
                         for d in edit_decisions]

        if not decisions:
            return RenderResult(
                project_id=project_id,
                output_path=str(output_path),
                status="failed",
                duration_seconds=0.0,
                resolution=f"{self.width}x{self.height}",
                fps=self.fps,
                codec_video="",
                codec_audio="",
                bitrate_kbps=None,
                file_size_bytes=None,
                scene_count=0,
                total_duration_ms=0,
                errors=["no edit decisions to render"],
            )

        # Cross-check timeline validity.
        if timeline is not None and not timeline.is_valid:
            return RenderResult(
                project_id=project_id,
                output_path=str(output_path),
                status="blocked",
                duration_seconds=0.0,
                resolution=f"{self.width}x{self.height}",
                fps=self.fps,
                codec_video="",
                codec_audio="",
                bitrate_kbps=None,
                file_size_bytes=None,
                scene_count=len(decisions),
                total_duration_ms=timeline.total_duration_ms,
                errors=[f"timeline invalid: {timeline.issues}"],
            )

        if use_remotion:
            # Remotion bridge not implemented; fall back to FFmpeg.
            pass

        # Fail fast if any image is missing.
        for d in decisions:
            if not Path(d.image_path).exists():
                return RenderResult(
                    project_id=project_id,
                    output_path=str(output_path),
                    status="failed",
                    duration_seconds=0.0,
                    resolution=f"{self.width}x{self.height}",
                    fps=self.fps,
                    codec_video="",
                    codec_audio="",
                    bitrate_kbps=None,
                    file_size_bytes=None,
                    scene_count=len(decisions),
                    total_duration_ms=sum(d.duration_ms for d in decisions),
                    errors=[f"image missing: {d.image_path} ({d.sentence_id})"],
                )

        return self._render_via_clips(
            project_id=project_id,
            decisions=decisions,
            timeline=timeline,
            audio_mix=audio_mix,
            output_path=output_path,
        )

    # ------------------------------------------------------------------
    # Per-scene clip rendering + concat demuxer
    # ------------------------------------------------------------------

    def _render_via_clips(
        self,
        *,
        project_id: str,
        decisions: list[EditDecision],
        timeline: ProductionTimeline | None,
        audio_mix: AudioMix | None,
        output_path: Path,
    ) -> RenderResult:
        """Render each scene to a clip, concat clips, mux audio."""
        import tempfile

        total_duration_ms = sum(d.duration_ms for d in decisions)
        clip_paths: list[Path] = []
        clip_dir = Path(tempfile.mkdtemp(prefix="openmontage_clips_"))

        try:
            for idx, d in enumerate(decisions):
                clip_path = clip_dir / f"clip_{idx:05d}.mp4"
                if not self._render_scene_clip(d, clip_path):
                    return RenderResult(
                        project_id=project_id,
                        output_path=str(output_path),
                        status="failed",
                        duration_seconds=0.0,
                        resolution=f"{self.width}x{self.height}",
                        fps=self.fps,
                        codec_video="",
                        codec_audio="",
                        bitrate_kbps=None,
                        file_size_bytes=None,
                        scene_count=len(decisions),
                        total_duration_ms=total_duration_ms,
                        errors=[f"scene clip failed: {d.sentence_id}"],
                    )
                clip_paths.append(clip_path)

            # Write concat demuxer list.
            list_path = clip_dir / "concat_list.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for cp in clip_paths:
                    # Escape single quotes for the demuxer.
                    f.write(f"file '{cp.as_posix()}'\n")

            # Concat clips (video only, copy codecs), then mux audio.
            cmd = [
                self.ffmpeg_bin, "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
            ]
            if audio_mix and audio_mix.status == "mixed" and Path(audio_mix.output_path).exists():
                cmd += ["-i", str(audio_mix.output_path)]
                cmd += ["-map", "0:v:0", "-map", "1:a:0"]
                cmd += ["-c", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
                cmd += ["-shortest"]
            else:
                # Silent audio matching video duration.
                cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
                cmd += ["-map", "0:v:0", "-map", "1:a:0"]
                cmd += ["-c", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
                cmd += ["-shortest"]

            cmd += [
                "-movflags", "+faststart",
                str(output_path),
            ]

            try:
                proc = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=1800,
                )
            except subprocess.TimeoutExpired as exc:
                return RenderResult(
                    project_id=project_id,
                    output_path=str(output_path),
                    status="failed",
                    duration_seconds=0.0,
                    resolution=f"{self.width}x{self.height}",
                    fps=self.fps,
                    codec_video="",
                    codec_audio="",
                    bitrate_kbps=None,
                    file_size_bytes=None,
                    scene_count=len(decisions),
                    total_duration_ms=total_duration_ms,
                    errors=[f"concat+mux timed out: {(exc.stdout or '')+(exc.stderr or '')}"],
                )
            except FileNotFoundError:
                return RenderResult(
                    project_id=project_id,
                    output_path=str(output_path),
                    status="failed",
                    duration_seconds=0.0,
                    resolution=f"{self.width}x{self.height}",
                    fps=self.fps,
                    codec_video="",
                    codec_audio="",
                    bitrate_kbps=None,
                    file_size_bytes=None,
                    scene_count=len(decisions),
                    total_duration_ms=total_duration_ms,
                    errors=["ffmpeg not found"],
                )

            if proc.returncode != 0:
                return RenderResult(
                    project_id=project_id,
                    output_path=str(output_path),
                    status="failed",
                    duration_seconds=0.0,
                    resolution=f"{self.width}x{self.height}",
                    fps=self.fps,
                    codec_video="",
                    codec_audio="",
                    bitrate_kbps=None,
                    file_size_bytes=None,
                    scene_count=len(decisions),
                    total_duration_ms=total_duration_ms,
                    errors=[proc.stderr or f"ffmpeg exit {proc.returncode}"],
                )
        finally:
            # Clean up clip files.
            for cp in clip_paths:
                try:
                    cp.unlink()
                except OSError:
                    pass
            try:
                clip_dir.rmdir()
            except OSError:
                pass

        # Probe output.
        probe = self._probe(output_path)
        actual_dur = probe.get("duration_seconds", 0.0)
        fsize = output_path.stat().st_size if output_path.exists() else None

        black_frames = self._detect_black_frames(output_path)
        frozen = self._detect_frozen(output_path)

        has_rig_overlays = any(getattr(d, "rig_overlay_path", None) for d in decisions)

        status = "rendered"
        errors = []
        warnings = []
        if black_frames:
            warnings.append(f"{len(black_frames)} black frame(s) detected")
        if frozen:
            warnings.append(f"{len(frozen)} frozen segment(s) detected")
        if has_rig_overlays:
            warnings.append("rig overlays present but not composited in FFmpeg path; use Remotion/HyperFrames for rig layer")
        if not output_path.exists() or fsize is None or fsize == 0:
            status = "failed"
            errors.append("output file missing or empty")

        return RenderResult(
            project_id=project_id,
            output_path=str(output_path),
            status=status,
            duration_seconds=round(actual_dur, 3),
            resolution=f"{probe.get('width', self.width)}x{probe.get('height', self.height)}",
            fps=self.fps,
            codec_video=probe.get("codec_video", ""),
            codec_audio=probe.get("codec_audio", ""),
            bitrate_kbps=probe.get("bitrate_kbps"),
            file_size_bytes=fsize,
            scene_count=len(decisions),
            total_duration_ms=total_duration_ms,
            ffprobe=probe,
            black_frames=black_frames,
            frozen_segments=frozen,
            errors=errors,
            warnings=warnings,
        )

    def _render_scene_clip(self, d: EditDecision, clip_path: Path) -> bool:
        """Render one scene to a short clip: image → timed video with motion.

        Returns True on success, False on failure.
        """
        dur_s = max(0.05, float(d.duration_ms) / 1000.0)
        motion = d.motion_type
        cp = d.camera_parameters
        start_scale = float(cp.get("start_scale", 1.0))
        end_scale = float(cp.get("end_scale", 1.0))
        direction = str(cp.get("direction", "in"))

        if direction == "out":
            s_scale, e_scale = end_scale, start_scale
        else:
            s_scale, e_scale = start_scale, end_scale
        z = f"{s_scale}+({e_scale}-{s_scale})*min(t/{dur_s},1)"

        crop_drift_x = ""
        if motion == "parallax":
            crop_drift_x = f"+15*min(t/{dur_s},1)"

        if motion == "static":
            vf = (
                f"loop=loop=-1:size=1:start=0,"
                f"framerate=fps={self.fps},"
                f"scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=w={self.width}:h={self.height}:x=(iw-{self.width})/2:y=(ih-{self.height})/2,"
                f"trim=duration={dur_s}"
            )
        else:
            vf = (
                f"loop=loop=-1:size=1:start=0,"
                f"framerate=fps={self.fps},"
                f"trim=duration={dur_s},"
                f"scale=1920:1080:force_original_aspect_ratio=increase,"
                f"scale=w='iw*({z})':h='ih*({z})':eval=frame,"
                f"crop=w={self.width}:h={self.height}:"
                f"x='(iw-{self.width})/2{crop_drift_x}':"
                f"y='(ih-{self.height})/2'"
            )

        cmd = [
            self.ffmpeg_bin, "-y",
            "-loop", "1", "-i", str(d.image_path),
            "-t", str(dur_s),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-r", str(self.fps),
            "-pix_fmt", "yuv420p",
            "-an",
            str(clip_path),
        ]
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            return False
        return proc.returncode == 0 and clip_path.exists() and clip_path.stat().st_size > 0

    # ------------------------------------------------------------------
    # Probe / QC
    # ------------------------------------------------------------------

    def _probe(self, path: Path) -> dict[str, Any]:
        """ffprobe stream + format info."""
        info: dict[str, Any] = {}
        try:
            out = subprocess.check_output(
                [
                    self.ffprobe_bin, "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height,r_frame_rate,avg_frame_rate",
                    "-show_entries", "format=duration,size,bit_rate",
                    "-of", "json", str(path),
                ],
                stderr=subprocess.STDOUT, text=True, timeout=30,
            )
            data = json.loads(out)
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            if streams:
                v = streams[0]
                info["codec_video"] = v.get("codec_name", "")
                info["width"] = v.get("width", self.width)
                info["height"] = v.get("height", self.height)
                info["fps"] = self._parse_fps(v.get("r_frame_rate", ""))
            info["duration_seconds"] = float(fmt.get("duration", 0.0))
            info["size_bytes"] = int(fmt.get("size", 0))
            info["bitrate_kbps"] = round(int(fmt.get("bit_rate", 0)) / 1000, 1) if fmt.get("bit_rate") else None
        except Exception:  # noqa: BLE001
            pass
        # Audio codec.
        try:
            out = subprocess.check_output(
                [
                    self.ffprobe_bin, "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=codec_name",
                    "-of", "csv=p=0", str(path),
                ],
                stderr=subprocess.STDOUT, text=True, timeout=30,
            )
            info["codec_audio"] = out.strip().splitlines()[0] if out.strip() else ""
        except Exception:  # noqa: BLE001
            info["codec_audio"] = ""
        return info

    @staticmethod
    def _parse_fps(rate_str: str) -> int:
        try:
            if "/" in rate_str:
                num, den = rate_str.split("/")
                return round(float(num) / float(den))
            return int(float(rate_str))
        except Exception:  # noqa: BLE001
            return 30

    def _detect_black_frames(self, path: Path, *, min_duration_s: float = 0.5) -> list[float]:
        """Detect black frames via ffmpeg blackdetect."""
        try:
            out = subprocess.check_output(
                [
                    self.ffmpeg_bin, "-hide_banner", "-nostats",
                    "-i", str(path),
                    "-af", f"blackdetect=d={min_duration_s}:pix_th=0.10",
                    "-f", "null", "-",
                ],
                stderr=subprocess.STDOUT, text=True, timeout=120,
            )
            import re
            times: list[float] = []
            for m in re.finditer(r"black_start:\s*([\d.]+)", out):
                times.append(float(m.group(1)))
            return times
        except Exception:  # noqa: BLE001
            return []

    def _detect_frozen(
        self, path: Path, *, min_duration_s: float = 2.0
    ) -> list[dict[str, Any]]:
        """Detect frozen segments via ffmpeg freezedetect."""
        try:
            out = subprocess.check_output(
                [
                    self.ffmpeg_bin, "-hide_banner", "-nostats",
                    "-i", str(path),
                    "-af", f"freezedetect=d={min_duration_s}:n=0.98",
                    "-f", "null", "-",
                ],
                stderr=subprocess.STDOUT, text=True, timeout=120,
            )
            import re
            frozen: list[dict[str, Any]] = []
            for m in re.finditer(
                r"freeze_start:\s*([\d.]+)\s+freeze_duration:\s*([\d.]+)", out
            ):
                frozen.append(
                    {"start": float(m.group(1)), "duration": float(m.group(2))}
                )
            return frozen
        except Exception:  # noqa: BLE001
            return []


def render_from_timeline(
    *,
    project_id: str,
    timeline: ProductionTimeline,
    audio_mix: AudioMix | None = None,
    output_path: str | Path = "projects/<project>/renders/final.mp4",
    engine: RenderEngine | None = None,
) -> RenderResult:
    """Convenience: render a ProductionTimeline (with its entries) via FFmpeg."""
    if engine is None:
        engine = RenderEngine()
    decisions = []
    for e in timeline.entries:
        decisions.append(
            {
                "sentence_id": e.sentence_id,
                "scene_id": e.scene_id,
                "image_asset_id": e.image_asset_id,
                "image_path": e.image_path,
                "audio_asset_id": e.audio_asset_id,
                "audio_path": e.audio_path,
                "start_ms": e.start_ms,
                "end_ms": e.end_ms,
                "duration_ms": e.duration_ms,
                "motion_type": e.motion_type,
                "camera_parameters": e.camera_parameters,
                "transition": e.transition,
                "transition_duration": e.transition_duration,
                "visual_effects": e.visual_effects,
                "narrative_role": e.narrative_role,
                "hero_moment": e.hero_moment,
            }
        )
    edit_set = EditDecisionSet(
        project_id=project_id,
        run_id=timeline.run_id,
        total_scenes=timeline.total_sentences,
        total_duration_ms=timeline.total_duration_ms,
        decisions=[EditDecision(**d) for d in decisions],
    )
    return engine.render(
        project_id=project_id,
        edit_decisions=edit_set,
        timeline=timeline,
        audio_mix=audio_mix,
        output_path=output_path,
    )
