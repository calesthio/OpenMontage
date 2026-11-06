"""Audio Sync — binds preproduction scenes to narrated audio segments.

Reads a narration manifest (produced by the TTS stage) and aligns each scene
to the audio segment that covers its script section.  Computes approximate
timestamps, flags segments whose duration is too long or too short for the
planned scene length, and supports manual timestamp correction.

Zero-cost: reads existing audio manifest JSON only.  Never modifies the
original audio files or the narration manifest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from lib.production_manifest import AudioSegment, AudioSync, ProductionManifest, Timeline


@dataclass
class SyncIssue:
    """A detected audio/scene synchronization problem."""

    segment_id: str
    scene_id: str
    issue_type: str  # "too_long" | "too_short" | "gap" | "overlap" | "missing_audio"
    description: str
    severity: str  # "low" | "medium" | "high"
    suggested_fix: str | None = None


@dataclass
class SyncReport:
    """Result of synchronizing scenes to audio."""

    narration_manifest_id: str
    total_audio_seconds: float
    total_scenes_seconds: float
    segments: list[AudioSegment] = field(default_factory=list)
    issues: list[SyncIssue] = field(default_factory=list)
    all_synced: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class AudioSyncEngine:
    """Synchronize production manifest scenes to narration audio segments."""

    # Thresholds (seconds) for flagging duration mismatches.
    TOO_LONG_THRESHOLD = 1.5   # scene exceeds audio by >1.5s
    TOO_SHORT_THRESHOLD = 1.0  # scene is shorter than audio by >1.0s
    GAP_THRESHOLD = 0.5        # gap between segments >0.5s

    def __init__(
        self,
        too_long_threshold: float = TOO_LONG_THRESHOLD,
        too_short_threshold: float = TOO_SHORT_THRESHOLD,
        gap_threshold: float = GAP_THRESHOLD,
    ) -> None:
        self.too_long_threshold = too_long_threshold
        self.too_short_threshold = too_short_threshold
        self.gap_threshold = gap_threshold

    def sync(
        self,
        manifest: ProductionManifest,
        narration_manifest: dict[str, Any],
        scene_script_map: dict[str, str],
    ) -> SyncReport:
        """Bind each scene to its audio segment and compute timestamps.

        Args:
            manifest: ProductionManifest (mutated in place with audio_sync).
            narration_manifest: Parsed narration_manifest artifact dict.
            scene_script_map: scene_id -> script_section_id mapping.

        Returns:
            SyncReport with per-segment results and detected issues.
        """
        segments_raw = narration_manifest.get("segments", [])
        total_audio = float(narration_manifest.get("total_duration_seconds", 0.0))

        # Index audio segments by script_section for fast lookup.
        by_section: dict[str, dict[str, Any]] = {}
        for seg in segments_raw:
            section = seg.get("script_section", "")
            by_section[section] = seg

        sync_segments: list[AudioSegment] = []
        issues: list[SyncIssue] = []

        # Build sorted scene list by timeline position.
        sorted_scenes = sorted(manifest.scenes, key=lambda s: s.timeline_position)

        prev_end = 0.0
        for scene in sorted_scenes:
            sid = scene.scene_id
            section_id = scene_script_map.get(sid, "")
            audio_seg = by_section.get(section_id)

            if audio_seg is None:
                # No audio for this scene — flag as missing audio.
                issues.append(
                    SyncIssue(
                        segment_id=f"{sid}-audio",
                        scene_id=sid,
                        issue_type="missing_audio",
                        description=(
                            f"No narration segment for script section {section_id!r}; "
                            f"scene {sid} has no audio binding."
                        ),
                        severity="high",
                        suggested_fix=(
                            "Synthesize narration for this script section or "
                            "adjust scene_script_map to point to an existing section."
                        ),
                    )
                )
                # Create a placeholder segment with zero duration.
                seg = AudioSegment(
                    segment_id=f"{sid}-seg",
                    scene_id=sid,
                    text="",
                    start_seconds=scene.timeline_position,
                    end_seconds=scene.timeline_position + scene.duration_seconds,
                    duration_seconds=scene.duration_seconds,
                    issue="missing_audio",
                    issue_threshold_seconds=0.0,
                )
                sync_segments.append(seg)
                prev_end = seg.end_seconds
                continue

            # Bind scene to this audio segment.
            start = float(audio_seg.get("start_seconds", scene.timeline_position))
            end = float(audio_seg.get("end_seconds", start + scene.duration_seconds))
            dur = float(audio_seg.get("duration_seconds", end - start))
            text = str(audio_seg.get("text", ""))

            # Detect duration mismatch between scene plan and audio.
            scene_dur = float(scene.duration_seconds)
            issue = "ok"
            if dur > scene_dur + self.too_long_threshold:
                issue = "too_long"
                issues.append(
                    SyncIssue(
                        segment_id=audio_seg.get("segment_id", f"{sid}-seg"),
                        scene_id=sid,
                        issue_type="too_long",
                        description=(
                            f"Audio ({dur:.2f}s) exceeds planned scene "
                            f"duration ({scene_dur:.2f}s) by "
                            f"{dur - scene_dur:.2f}s."
                        ),
                        severity="medium",
                        suggested_fix=(
                            "Extend scene duration or trim narration; "
                            "review with human editor."
                        ),
                    )
                )
            elif scene_dur > dur + self.too_short_threshold:
                issue = "too_short"
                issues.append(
                    SyncIssue(
                        segment_id=audio_seg.get("segment_id", f"{sid}-seg"),
                        scene_id=sid,
                        issue_type="too_short",
                        description=(
                            f"Planned scene ({scene_dur:.2f}s) exceeds audio "
                            f"({dur:.2f}s) by {scene_dur - dur:.2f}s."
                        ),
                        severity="medium",
                        suggested_fix=(
                            "Shorten scene duration or extend narration; "
                            "review with human editor."
                        ),
                    )
                )

            # Detect gap between this segment and the previous one.
            if start > prev_end + self.gap_threshold:
                issues.append(
                    SyncIssue(
                        segment_id=audio_seg.get("segment_id", f"{sid}-seg"),
                        scene_id=sid,
                        issue_type="gap",
                        description=(
                            f"Gap of {start - prev_end:.2f}s between previous "
                            f"segment end ({prev_end:.2f}s) and this segment "
                            f"start ({start:.2f}s)."
                        ),
                        severity="low",
                        suggested_fix=(
                            "Add filler scene or extend previous segment to "
                            "close the gap."
                        ),
                    )
                )

            word_ts = audio_seg.get("word_timestamps", [])
            if isinstance(word_ts, list):
                word_ts = [
                    {
                        "word": w.get("word", ""),
                        "start_seconds": float(w.get("start_seconds", 0.0)),
                        "end_seconds": float(w.get("end_seconds", 0.0)),
                    }
                    for w in word_ts
                ]

            seg = AudioSegment(
                segment_id=str(audio_seg.get("segment_id", f"{sid}-seg")),
                scene_id=sid,
                text=text,
                start_seconds=start,
                end_seconds=end,
                duration_seconds=dur,
                word_timestamps=word_ts,
                issue=issue,
                issue_threshold_seconds=max(
                    self.too_long_threshold, self.too_short_threshold
                ),
                metadata={
                    "source_script_section": section_id,
                    "planned_scene_duration": scene_dur,
                },
            )
            sync_segments.append(seg)
            prev_end = end

        # Detect trailing gap after last segment.
        if sync_segments and prev_end < total_audio - self.gap_threshold:
            issues.append(
                SyncIssue(
                    segment_id="trailing",
                    scene_id=sorted_scenes[-1].scene_id if sorted_scenes else "",
                    issue_type="gap",
                    description=(
                        f"Trailing gap of {total_audio - prev_end:.2f}s after "
                        f"last segment end ({prev_end:.2f}s) vs audio total "
                        f"({total_audio:.2f}s)."
                    ),
                    severity="low",
                )
            )

        total_scenes = sum(s.duration_seconds for s in manifest.scenes)
        all_synced = len(issues) == 0

        sync = AudioSync(
            narration_manifest_id=str(narration_manifest.get("run_id", "")),
            total_duration_seconds=total_audio,
            segments=sync_segments,
        )

        # Update manifest in place.
        manifest.audio_sync = sync
        manifest.timeline = Timeline(
            total_duration_seconds=max(total_audio, total_scenes),
            fps=manifest.timeline.fps if manifest.timeline else 30,
            resolution=manifest.timeline.resolution if manifest.timeline else "1920x1080",
            aspect_ratio=manifest.timeline.aspect_ratio if manifest.timeline else "16:9",
            cuts_count=len(manifest.scenes),
            metadata=dict(manifest.timeline.metadata) if manifest.timeline else {},
        )
        manifest.seal()

        return SyncReport(
            narration_manifest_id=sync.narration_manifest_id,
            total_audio_seconds=total_audio,
            total_scenes_seconds=total_scenes,
            segments=sync_segments,
            issues=issues,
            all_synced=all_synced,
        )

    # ------------------------------------------------------------------
    # Manual correction
    # ------------------------------------------------------------------

    def adjust_segment(
        self,
        manifest: ProductionManifest,
        segment_id: str,
        *,
        start_seconds: float | None = None,
        end_seconds: float | None = None,
        scene_id: str | None = None,
    ) -> AudioSegment:
        """Manually correct a segment's timestamps.

        Does not modify the original narration manifest — only the manifest's
        audio_sync copy.  Re-seals the manifest after change.
        """
        sync = manifest.audio_sync
        if sync is None:
            raise ValueError("Manifest has no audio_sync; run sync() first.")

        target: AudioSegment | None = None
        for seg in sync.segments:
            if seg.segment_id == segment_id:
                target = seg
                break
        if target is None:
            raise KeyError(f"Segment {segment_id} not found in audio_sync.")

        if start_seconds is not None:
            target.start_seconds = float(start_seconds)
        if end_seconds is not None:
            target.end_seconds = float(end_seconds)
        target.duration_seconds = target.end_seconds - target.start_seconds
        if scene_id is not None:
            target.scene_id = scene_id

        # Re-flag duration issue against planned scene duration.
        scene = manifest.scene_by_id(target.scene_id)
        planned_dur = scene.duration_seconds if scene else target.duration_seconds
        if target.duration_seconds > planned_dur + self.too_long_threshold:
            target.issue = "too_long"
        elif planned_dur > target.duration_seconds + self.too_short_threshold:
            target.issue = "too_short"
        else:
            target.issue = "ok"

        manifest.seal()
        return target

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self, sync_report: SyncReport) -> dict[str, Any]:
        """Produce a plain dict report for logging/display."""
        return {
            "narration_manifest_id": sync_report.narration_manifest_id,
            "total_audio_seconds": round(sync_report.total_audio_seconds, 3),
            "total_scenes_seconds": round(sync_report.total_scenes_seconds, 3),
            "all_synced": sync_report.all_synced,
            "segment_count": len(sync_report.segments),
            "issue_count": len(sync_report.issues),
            "issues": [
                {
                    "segment_id": i.segment_id,
                    "scene_id": i.scene_id,
                    "issue_type": i.issue_type,
                    "description": i.description,
                    "severity": i.severity,
                    "suggested_fix": i.suggested_fix,
                }
                for i in sync_report.issues
            ],
            "segments": [s.to_dict() for s in sync_report.segments],
        }
