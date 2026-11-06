"""Render Integration — connects a Production Manifest to the existing
OpenMontage render pipeline (video_compose.py / FFmpeg / Remotion).

Validates the manifest before render:
  - scene sequence is chronological and gap-free
  - total duration matches timeline + audio
  - all validated assets exist on disk
  - format compatibility with target media profile
  - audio sync is consistent
  - transitions are well-formed

Then produces an edit_decisions artifact and, optionally, a short test
render using local stub images (no real render of a full release).

Zero-cost: validation only; the optional test render uses locally-generated
placeholder images, never Google Flow.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lib.production_manifest import ProductionManifest


@dataclass
class RenderCheck:
    """One pre-render validation check result."""

    name: str
    passed: bool
    detail: str
    severity: str  # "low" | "medium" | "high"
    blocking: bool = False


@dataclass
class RenderReadinessReport:
    """Aggregate pre-render readiness assessment."""

    manifest_id: str
    project: str
    total_scenes: int
    validated_assets: int
    missing_assets: int
    total_duration_seconds: float
    audio_duration_seconds: float
    checks: list[RenderCheck] = field(default_factory=list)
    all_passed: bool = False
    blocking_count: int = 0

    @property
    def ready_for_render(self) -> bool:
        return self.all_passed and self.blocking_count == 0


@dataclass
class RenderIntegrationOutput:
    """Result of integrating a manifest with the render pipeline."""

    version: str = "1.0"
    run_id: str = ""
    project: str = ""
    status: str = "not_ready"  # not_ready | ready | rendered | failed
    readiness: RenderReadinessReport | None = None
    edit_decisions: dict[str, Any] | None = None
    test_render_path: str | None = None
    test_render_duration_seconds: float | None = None
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class RenderIntegration:
    """Validate and connect a Production Manifest to rendering."""

    def __init__(
        self,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ) -> None:
        self.fps = fps
        self.width = width
        self.height = height
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_manifest(
        self,
        manifest: ProductionManifest,
        *,
        require_all_assets: bool = True,
        require_audio_sync: bool = True,
    ) -> RenderReadinessReport:
        """Run all pre-render validation checks on a manifest.

        Returns a RenderReadinessReport.  The manifest is not modified.
        """
        checks: list[RenderCheck] = []
        blocking = 0

        scenes = manifest.scenes
        total_scenes = len(scenes)

        # 1. Manifest integrity
        integrity_ok = manifest.verify_integrity()
        checks.append(
            RenderCheck(
                name="manifest_integrity",
                passed=integrity_ok,
                detail=(
                    "Integrity hash verified"
                    if integrity_ok
                    else "Integrity hash mismatch — manifest may be truncated or tampered"
                ),
                severity="high",
                blocking=not integrity_ok,
            )
        )
        if not integrity_ok:
            blocking += 1

        # 2. Schema validity
        try:
            manifest.validate_schema()
            schema_ok = True
            schema_detail = "Manifest conforms to production_manifest schema"
        except Exception as exc:
            schema_ok = False
            schema_detail = f"Schema validation failed: {exc}"
        checks.append(
            RenderCheck(
                name="manifest_schema",
                passed=schema_ok,
                detail=schema_detail,
                severity="high",
                blocking=not schema_ok,
            )
        )
        if not schema_ok:
            blocking += 1

        # 3. Scene sequence chronological + gap-free
        sorted_scenes = sorted(scenes, key=lambda s: s.timeline_position)
        seq_ok = True
        seq_detail = "Scenes are chronological and contiguous"
        prev_end = 0.0
        for i, s in enumerate(sorted_scenes):
            if s.timeline_position < prev_end - 0.01:
                seq_ok = False
                seq_detail = (
                    f"Scene {s.scene_id} starts ({s.timeline_position:.2f}s) "
                    f"before previous ends ({prev_end:.2f}s) — overlap"
                )
                break
            gap = s.timeline_position - prev_end
            if gap > 0.5 and i > 0:
                seq_ok = False
                seq_detail = (
                    f"Gap of {gap:.2f}s before scene {s.scene_id} "
                    f"(previous ends {prev_end:.2f}s)"
                )
                break
            prev_end = s.timeline_position + s.duration_seconds
        checks.append(
            RenderCheck(
                name="scene_sequence",
                passed=seq_ok,
                detail=seq_detail,
                severity="medium",
                blocking=not seq_ok,
            )
        )
        if not seq_ok:
            blocking += 1

        # 4. All validated assets exist on disk
        validated_assets = 0
        missing_assets = 0
        asset_detail_parts: list[str] = []
        for s in scenes:
            if s.file_status == "validated" and s.file_path:
                p = Path(s.file_path)
                if p.exists():
                    validated_assets += 1
                else:
                    missing_assets += 1
                    asset_detail_parts.append(f"{s.scene_id}: {s.file_path} not on disk")
            elif s.file_status in ("missing", "corrupted", "duplicate"):
                missing_assets += 1
                asset_detail_parts.append(f"{s.scene_id}: status={s.file_status}")
        asset_ok = missing_assets == 0 or not require_all_assets
        asset_detail = (
            f"{validated_assets}/{total_scenes} assets validated on disk"
            + (f"; {len(asset_detail_parts)} missing: " + "; ".join(asset_detail_parts[:5])
               if asset_detail_parts else "")
        )
        checks.append(
            RenderCheck(
                name="assets_present",
                passed=asset_ok,
                detail=asset_detail,
                severity="high",
                blocking=(not asset_ok) and require_all_assets,
            )
        )
        if not asset_ok and require_all_assets:
            blocking += 1

        # 5. Format compatibility
        fmt_ok = True
        fmt_detail = "All asset resolutions compatible with target profile"
        expected = f"{self.width}x{self.height}"
        for s in scenes:
            if s.file_resolution and s.file_resolution != expected:
                # Not blocking — render can letterbox/pillarbox. Just note it.
                fmt_detail += f"; {s.scene_id} is {s.file_resolution} (will letterbox/pillarbox)"
        checks.append(
            RenderCheck(
                name="format_compatibility",
                passed=fmt_ok,
                detail=fmt_detail,
                severity="low",
                blocking=False,
            )
        )

        # 6. Audio sync consistency
        audio_dur = 0.0
        audio_ok = True
        audio_detail = "No audio sync data"
        if manifest.audio_sync is not None:
            audio_dur = manifest.audio_sync.total_duration_seconds
            segs = manifest.audio_sync.segments
            issues = [seg for seg in segs if seg.issue != "ok"]
            audio_ok = len(issues) == 0
            audio_detail = (
                f"Audio {audio_dur:.2f}s; {len(issues)} segment(s) with duration issues"
                if issues
                else f"Audio {audio_dur:.2f}s synced to {len(segs)} scene(s)"
            )
            if require_audio_sync and not audio_ok:
                blocking += 1
        checks.append(
            RenderCheck(
                name="audio_sync",
                passed=audio_ok or not require_audio_sync,
                detail=audio_detail,
                severity="medium",
                blocking=(not audio_ok) and require_audio_sync,
            )
        )

        # 7. Duration match: timeline vs audio
        timeline_dur = (
            manifest.timeline.total_duration_seconds if manifest.timeline else 0.0
        )
        dur_match = abs(timeline_dur - audio_dur) <= 1.0 if audio_dur > 0 else True
        dur_detail = (
            f"Timeline {timeline_dur:.2f}s vs audio {audio_dur:.2f}s — "
            f"{'match' if dur_match else 'mismatch'}"
        )
        checks.append(
            RenderCheck(
                name="duration_match",
                passed=dur_match,
                detail=dur_detail,
                severity="medium",
                blocking=not dur_match,
            )
        )
        if not dur_match:
            blocking += 1

        # 8. Transitions well-formed
        trans_ok = True
        trans_detail = "All transitions well-formed"
        for s in scenes:
            if s.transition not in ("cut", "dissolve", "fade", "wipe"):
                trans_ok = False
                trans_detail = f"Scene {s.scene_id} has unknown transition {s.transition!r}"
                break
        checks.append(
            RenderCheck(
                name="transitions",
                passed=trans_ok,
                detail=trans_detail,
                severity="low",
                blocking=not trans_ok,
            )
        )

        all_passed = all(c.passed for c in checks)

        return RenderReadinessReport(
            manifest_id=manifest.manifest_id,
            project=manifest.project,
            total_scenes=total_scenes,
            validated_assets=validated_assets,
            missing_assets=missing_assets,
            total_duration_seconds=timeline_dur,
            audio_duration_seconds=audio_dur,
            checks=checks,
            all_passed=all_passed,
            blocking_count=blocking,
        )

    # ------------------------------------------------------------------
    # Edit decisions generation
    # ------------------------------------------------------------------

    def build_edit_decisions(
        self,
        manifest: ProductionManifest,
        *,
        audio_path: str | None = None,
        subtitle_path: str | None = None,
    ) -> dict[str, Any]:
        """Convert a validated manifest into an edit_decisions artifact.

        Produces cuts with source paths, in/out seconds, transitions, and
        overlays suitable for video_compose.py operation='render'.
        """
        sorted_scenes = sorted(manifest.scenes, key=lambda s: s.timeline_position)
        cuts: list[dict[str, Any]] = []
        overlays: list[dict[str, Any]] = []

        for i, s in enumerate(sorted_scenes):
            source = s.file_path or ""
            in_s = s.timeline_position
            out_s = in_s + s.duration_seconds

            # Determine transform/animation from camera_move params.
            transform: dict[str, Any] = {"scale": 1.0, "position": "center"}
            animation = None
            if s.pan_zoom_params:
                pz = s.pan_zoom_params
                animation = f"{pz.direction}_{pz.easing}"
                transform = {
                    "scale": pz.start_scale,
                    "position": "center",
                    "animation": animation,
                }

            cut = {
                "id": s.scene_id,
                "source": source,
                "in_seconds": round(in_s, 3),
                "out_seconds": round(out_s, 3),
                "speed": 1.0,
                "layer": "primary",
                "transform": transform,
                "transition_in": s.transition if i == 0 else "cut",
                "transition_out": s.transition,
                "transition_duration": s.transition_duration,
                "reason": s.narrative_role,
            }
            cuts.append(cut)

            # Caption space overlay (reserved region marker for editor).
            if s.caption_space and s.caption_space.reserved:
                cs = s.caption_space
                overlays.append(
                    {
                        "asset_id": f"{s.scene_id}-caption-space",
                        "start_seconds": round(in_s, 3),
                        "end_seconds": round(out_s, 3),
                        "position": {
                            "x": cs.x,
                            "y": cs.y,
                            "width": cs.width,
                            "height": cs.height,
                        },
                        "animation": "static",
                        "opacity": 0.0,  # invisible marker; editor fills content
                    }
                )

        total_dur = max(
            (s.timeline_position + s.duration_seconds for s in sorted_scenes),
            default=0.0,
        )

        edit_decisions: dict[str, Any] = {
            "version": "1.0",
            "cuts": cuts,
            "overlays": overlays,
            "render_runtime": "ffmpeg",
            "renderer_family": "documentary-montage",
            "composition_mode": "templated",
            "audio": {
                "narration": {
                    "segments": [
                        {
                            "asset_id": seg.scene_id,
                            "start_seconds": seg.start_seconds,
                            "end_seconds": seg.end_seconds,
                        }
                        for seg in (manifest.audio_sync.segments if manifest.audio_sync else [])
                    ]
                }
            } if audio_path else None,
            "subtitles": {
                "enabled": subtitle_path is not None,
                "source": subtitle_path or "",
                "style": "sentence",
            },
            "metadata": {
                "project": manifest.project,
                "run_id": manifest.run_id,
                "manifest_id": manifest.manifest_id,
                "total_duration_seconds": round(total_dur, 3),
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "compose_target": {
                    "width": self.width,
                    "height": self.height,
                    "fit": "pad",
                },
            },
        }
        if audio_path:
            edit_decisions["audio"]["music"] = {
                "asset_id": "",
                "volume": 0.15,
                "fade_in_seconds": 2.0,
                "fade_out_seconds": 2.0,
                "ducking": {"enabled": True, "threshold_db": -20, "reduction_db": -12},
            }

        return edit_decisions

    # ------------------------------------------------------------------
    # Test render (stub images only)
    # ------------------------------------------------------------------

    def create_test_render(
        self,
        manifest: ProductionManifest,
        *,
        output_path: str | Path,
        stub_width: int = 1920,
        stub_height: int = 1080,
        stub_color: str = "0x2a4a6a",
        stub_text: str | None = None,
    ) -> dict[str, Any]:
        """Create a short test render using locally-generated stub images.

        Generates one placeholder image per scene (solid color + optional
        text) via FFmpeg, assembles them per the manifest timeline, and
        muxes silent audio.  Never touches Google Flow.

        Returns a dict with output path, duration, and per-scene info.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sorted_scenes = sorted(manifest.scenes, key=lambda s: s.timeline_position)
        if not sorted_scenes:
            return {
                "status": "no_scenes",
                "output": str(output_path),
                "error": "No scenes in manifest to render",
            }

        # Generate stub images
        stub_dir = output_path.parent / ".stubs"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub_paths: list[tuple[float, float, str]] = []  # (in, out, path)

        for i, s in enumerate(sorted_scenes):
            stub = stub_dir / f"stub_{i:03d}.png"
            text = stub_text or f"Scene {i+1}: {s.scene_id}"
            try:
                subprocess.run(
                    [
                        self.ffmpeg_bin, "-y",
                        "-f", "lavfi",
                        "-i", f"color=c={stub_color}:s={stub_width}x{stub_height}:d={s.duration_seconds}",
                        "-vf",
                        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                        f"text='{text}':fontcolor=white:fontsize=40:"
                        f"x=(w-text_w)/2:y=(h-text_h)/2",
                        "-frames:v", "1",
                        str(stub),
                    ],
                    check=True,
                    capture_output=True,
                )
            except Exception:
                # FFmpeg may not have drawtext font; create a plain color frame.
                subprocess.run(
                    [
                        self.ffmpeg_bin, "-y",
                        "-f", "lavfi",
                        "-i", f"color=c={stub_color}:s={stub_width}x{stub_height}:d={s.duration_seconds}",
                        "-frames:v", "1",
                        str(stub),
                    ],
                    check=True,
                    capture_output=True,
                )
            stub_paths.append((s.timeline_position, s.timeline_position + s.duration_seconds, str(stub)))

        # Build concat list with per-segment durations.
        concat_list = stub_dir / "concat_list.txt"
        with open(concat_list, "w") as f:
            for in_s, out_s, path in stub_paths:
                dur = out_s - in_s
                safe = str(Path(path).resolve()).replace("\\", "/")
                f.write(f"file '{safe}'\n")
                f.write(f"duration {dur:.3f}\n")

        # Silent audio track matching total duration.
        total_dur = max((out_s for _, out_s, _ in stub_paths), default=0.0)
        silent_audio = stub_dir / "silent.aac"
        subprocess.run(
            [
                self.ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", str(total_dur),
                "-c:a", "aac",
                str(silent_audio),
            ],
            check=True,
            capture_output=True,
        )

        # Render: concat stubs + silent audio.
        try:
            subprocess.run(
                [
                    self.ffmpeg_bin, "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_list),
                    "-i", str(silent_audio),
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-pix_fmt", "yuv420p",
                    "-r", str(self.fps),
                    "-shortest",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            return {
                "status": "render_failed",
                "output": str(output_path),
                "error": exc.stderr.decode() if exc.stderr else str(exc),
            }

        # Measure actual output duration.
        actual_dur = self._probe_duration(output_path)

        return {
            "status": "rendered",
            "output": str(output_path),
            "duration_seconds": round(actual_dur, 3),
            "scene_count": len(sorted_scenes),
            "stub_count": len(stub_paths),
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}",
        }

    @staticmethod
    def _probe_duration(path: Path) -> float:
        """Probe media duration in seconds via ffprobe."""
        try:
            out = subprocess.check_output(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    str(path),
                ],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return float(out.strip())
        except Exception:
            return 0.0
