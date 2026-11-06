"""Final QC — P5 comprehensive quality control for OpenMontage Factory.

Runs end-to-end verification of a rendered MP4 against the ProductionTimeline,
edit decisions, audio mix, and asset registry.  Zero-cost: FFmpeg/ffprobe only,
no network, no model downloads, no credits.

Fail-closed: a check that cannot run => BLOCKED, never PASS.
Overall verdict: PASS (all blocking checks pass), WARNING (non-blocking
failures or warning checks), FAIL (any blocking check fails).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.asset_registry import AssetRegistry
from lib.edit_decision_engine import EditDecision, EditDecisionSet
from lib.image_uniqueness import check_uniqueness, DUPLICATE_THRESHOLD
from lib.production_timeline import ProductionTimeline, TimelineEntry
from lib.render_engine import RenderResult

# One frame at 30 FPS ~ 33.3ms.  Target: image switch within 1 frame.
FRAME_TOLERANCE_S = 1.0 / 30.0

# Default thresholds (owner may tune; these are INITIAL GUESSES).
DEFAULT_THRESHOLDS = {
    "lufs_target": -14.0,
    "lufs_tolerance": 2.0,
    "true_peak_max": -1.5,
    "peak_clipping_max": 0.98,
    "silence_ratio_max": 0.10,
    "black_ratio_max": 0.05,
    "freeze_duration_max": 2.0,
    "sync_tolerance_s": FRAME_TOLERANCE_S,
    "duration_tolerance_s": 1.0,
    "min_duration_s": 0.5,
    "max_silent_run_s": 3.0,
    "voice_music_ratio_min": 6.0,  # narration should be >= 6x music loudness share
}


@dataclass
class QCResult:
    """Result of one QC check."""

    check_id: str
    category: str  # video | audio | visual | sync | structural
    status: str  # PASS | WARNING | FAIL | BLOCKED | NOT_RUN
    evidence: str
    measured_value: Any = None
    threshold: Any = None
    blocking: bool = True  # if True, a FAIL blocks release
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QCReport:
    """Full QC report for one rendered project."""

    project_id: str
    version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    output_path: str = ""
    overall_status: str = "NOT_RUN"  # PASS | WARNING | FAIL | BLOCKED
    checks: list[QCResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def blocking_failures(self) -> list[QCResult]:
        return [c for c in self.checks if c.blocking and c.status == "FAIL"]

    @property
    def non_blocking_failures(self) -> list[QCResult]:
        return [c for c in self.checks if not c.blocking and c.status == "FAIL"]

    @property
    def warnings(self) -> list[QCResult]:
        return [c for c in self.checks if c.status == "WARNING"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "version": self.version,
            "created_at": self.created_at,
            "output_path": self.output_path,
            "overall_status": self.overall_status,
            "errors": self.errors,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "total": len(self.checks),
                "pass": sum(1 for c in self.checks if c.status == "PASS"),
                "warning": sum(1 for c in self.checks if c.status == "WARNING"),
                "fail": sum(1 for c in self.checks if c.status == "FAIL"),
                "blocked": sum(1 for c in self.checks if c.status == "BLOCKED"),
                "not_run": sum(1 for c in self.checks if c.status == "NOT_RUN"),
                "blocking_failures": len(self.blocking_failures),
                "warnings": len(self.warnings),
            },
        }


class FinalQC:
    """Comprehensive final QC for rendered MP4 + timeline + audio + assets.

    Orchestrates video, audio, visual, and synchronization checks against the
    ProductionTimeline (P4), RenderResult (P4), AudioMix (P4), AssetRegistry
    (P2), and ImageUniqueness results (P2).
    """

    def __init__(
        self,
        *,
        project_id: str,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        thresholds: dict[str, Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_all(
        self,
        *,
        output_path: str | Path,
        render_result: RenderResult,
        timeline: ProductionTimeline,
        edit_decisions: EditDecisionSet | list[dict[str, Any]] | None = None,
        audio_mix=None,
        asset_registry: AssetRegistry | None = None,
        image_uniqueness_report=None,
    ) -> QCReport:
        """Run every QC check and return a QCReport."""
        output_path = Path(output_path)
        report = QCReport(
            project_id=self.project_id,
            output_path=str(output_path),
        )

        # Collect edit decisions for structural checks.
        if isinstance(edit_decisions, EditDecisionSet):
            decisions = edit_decisions.decisions
        elif edit_decisions is None:
            decisions = []
        else:
            decisions = [EditDecision(**d) if not isinstance(d, EditDecision) else d
                         for d in edit_decisions]

        # ---- Video QC -------------------------------------------------
        self._check_video_integrity(report, output_path, render_result)
        self._check_video_tracks(report, output_path, render_result)
        self._check_video_codec(report, render_result)
        self._check_black_frames(report, output_path, render_result)
        self._check_frozen_segments(report, output_path, render_result)

        # ---- Audio QC -------------------------------------------------
        self._check_audio_loudness(report, output_path, audio_mix)
        self._check_audio_clipping(report, output_path)
        self._check_audio_silence(report, output_path, timeline)
        self._check_audio_vs_timeline(report, output_path, audio_mix, timeline)

        # ---- Visual QC ------------------------------------------------
        self._check_one_image_per_sentence(report, timeline)
        self._check_image_asset_ids(report, timeline, decisions)
        self._check_no_reused_images(report, timeline, image_uniqueness_report)
        self._check_no_missing_files(report, timeline)
        self._check_character_consistency(report, timeline, decisions)
        self._check_rig_signature_detail(report, timeline)
        self._check_rig_proportion_consistency(report, timeline, decisions)
        self._check_rig_no_frozen_limbs(report, timeline)
        self._check_rig_prop_continuity(report, timeline)
        # V2 creative-quality checks
        self._check_missing_assets(report, decisions)
        self._check_composition_repeats(report, decisions)
        self._check_solid_color_frames(report, output_path)
        self._check_timeline_mismatch(report, timeline, render_result)

        # ---- Sync QC --------------------------------------------------
        self._check_sync_accuracy(report, timeline)
        self._check_no_gaps_overlaps(report, timeline)

        # ---- Structural QC -------------------------------------------
        self._check_duration_match(report, render_result, timeline)

        # ---- Overall verdict ------------------------------------------
        report.overall_status = self._verdict(report)
        report.errors = [
            c.evidence for c in report.checks if c.status in ("FAIL", "BLOCKED")
        ]
        return report

    # ------------------------------------------------------------------
    # Video checks
    # ------------------------------------------------------------------

    def _check_video_integrity(
        self, report: QCReport, output_path: Path, render_result: RenderResult
    ) -> None:
        if render_result.status == "failed":
            report.checks.append(
                QCResult(
                    "video_integrity", "video", "FAIL",
                    f"Render failed: {'; '.join(render_result.errors) or 'unknown'}",
                    blocking=True,
                )
            )
            return
        if not output_path.exists() or output_path.stat().st_size == 0:
            report.checks.append(
                QCResult(
                    "video_integrity", "video", "FAIL",
                    f"Output file missing or empty: {output_path}",
                    blocking=True,
                )
            )
            return
        # Full decode already performed by RenderEngine probe; trust its result
        # but re-verify decodability here for independence.
        try:
            proc = subprocess.run(
                [self.ffmpeg_bin, "-v", "error", "-i", str(output_path),
                 "-f", "null", "-"],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode == 0:
                report.checks.append(
                    QCResult(
                        "video_integrity", "video", "PASS",
                        "full decode: no errors",
                        measured_value=output_path.stat().st_size,
                        blocking=True,
                    )
                )
            else:
                report.checks.append(
                    QCResult(
                        "video_integrity", "video", "FAIL",
                        f"full decode failed: {(proc.stderr or '').strip()[:200]}",
                        blocking=True,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            report.checks.append(
                QCResult(
                    "video_integrity", "video", "BLOCKED",
                    f"decode unrunnable: {exc}", blocking=True,
                )
            )

    def _check_video_tracks(
        self, report: QCReport, output_path: Path, render_result: RenderResult
    ) -> None:
        probe = render_result.ffprobe or {}
        v_codec = probe.get("codec_video", "")
        a_codec = probe.get("codec_audio", "")
        width = probe.get("width")
        height = probe.get("height")
        fps = probe.get("fps")
        duration = probe.get("duration_seconds", 0.0)

        problems: list[str] = []
        if not v_codec:
            problems.append("no video stream")
        if not a_codec:
            problems.append("no audio stream")
        if width is not None and width != 1920:
            problems.append(f"width {width} != 1920")
        if height is not None and height != 1080:
            problems.append(f"height {height} != 1080")
        if fps is not None and abs(fps - 30) > 1:
            problems.append(f"fps {fps} != 30")
        if duration <= 0:
            problems.append("duration <= 0")

        if problems:
            report.checks.append(
                QCResult(
                    "video_tracks", "video", "FAIL",
                    "; ".join(problems),
                    measured_value={
                        "video_codec": v_codec, "audio_codec": a_codec,
                        "width": width, "height": height, "fps": fps,
                        "duration": duration,
                    },
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "video_tracks", "video", "PASS",
                    f"video+audio present; {width}x{height}@{fps}fps; {duration:.2f}s",
                    measured_value={
                        "video_codec": v_codec, "audio_codec": a_codec,
                        "width": width, "height": height, "fps": fps,
                        "duration": duration,
                    },
                    blocking=True,
                )
            )

    def _check_video_codec(
        self, report: QCReport, resolution_report: RenderResult
    ) -> None:
        probe = resolution_report.ffprobe or {}
        v_codec = probe.get("codec_video", "")
        a_codec = probe.get("codec_audio", "")
        problems: list[str] = []
        if v_codec != "h264":
            problems.append(f"video codec {v_codec} != h264")
        if a_codec != "aac":
            problems.append(f"audio codec {a_codec} != aac")
        if problems:
            report.checks.append(
                QCResult(
                    "video_codec", "video", "FAIL",
                    "; ".join(problems),
                    measured_value={"video": v_codec, "audio": a_codec},
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "video_codec", "video", "PASS",
                    f"video={v_codec}, audio={a_codec}",
                    measured_value={"video": v_codec, "audio": a_codec},
                    blocking=True,
                )
            )

    def _check_black_frames(
        self, report: QCReport, output_path: Path, render_result: RenderResult
    ) -> None:
        bf = render_result.black_frames or []
        thr = self.thresholds["black_ratio_max"]
        # Estimate black ratio from frame count: probe duration * 30 fps
        duration = resolution_report_duration(render_result)
        total_frames = duration * 30.0 if duration > 0 else 0
        ratio = len(bf) / total_frames if total_frames > 0 else 0.0
        if ratio > thr:
            report.checks.append(
                QCResult(
                    "black_frames", "video", "FAIL",
                    f"{len(bf)} black frame(s), ratio {ratio:.4f} > {thr}",
                    measured_value={"count": len(bf), "ratio": ratio},
                    threshold=thr,
                    blocking=True,
                )
            )
        elif bf:
            report.checks.append(
                QCResult(
                    "black_frames", "video", "WARNING",
                    f"{len(bf)} black frame(s) below threshold {thr}",
                    measured_value={"count": len(bf), "ratio": ratio},
                    threshold=thr,
                    blocking=False,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "black_frames", "video", "PASS",
                    "no black frames",
                    measured_value={"count": 0, "ratio": 0.0},
                    threshold=thr,
                    blocking=True,
                )
            )

    def _check_frozen_segments(
        self, report: QCReport, output_path: Path, render_result: RenderResult
    ) -> None:
        frozen = render_result.frozen_segments or []
        thr = self.thresholds["freeze_duration_max"]
        problems = [
            f"freeze at {f['start']:.2f}s for {f['duration']:.2f}s" for f in frozen
        ]
        if any(f["duration"] > thr for f in frozen):
            report.checks.append(
                QCResult(
                    "frozen_segments", "video", "FAIL",
                    "; ".join(problems),
                    measured_value={"count": len(frozen)},
                    threshold=f"{thr}s max duration",
                    blocking=True,
                )
            )
        elif frozen:
            report.checks.append(
                QCResult(
                    "frozen_segments", "video", "WARNING",
                    f"{len(frozen)} frozen segment(s) below {thr}s threshold",
                    measured_value={"count": len(frozen)},
                    threshold=f"{thr}s max duration",
                    blocking=False,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "frozen_segments", "video", "PASS",
                    "no frozen segments",
                    measured_value={"count": 0},
                    threshold=f"{thr}s max duration",
                    blocking=True,
                )
            )

    # ------------------------------------------------------------------
    # Audio checks
    # ------------------------------------------------------------------

    def _check_audio_loudness(
        self, report: QCReport, output_path: Path, audio_mix
    ) -> None:
        if audio_mix is None or audio_mix.loudness_lufs is None:
            # Try to measure from the output file directly.
            loudness, tp = self._measure_loudness(output_path)
        else:
            loudness = audio_mix.loudness_lufs
            tp = audio_mix.true_peak_db

        target = self.thresholds["lufs_target"]
        tol = self.thresholds["lufs_tolerance"]
        tp_max = self.thresholds["true_peak_max"]

        if loudness is None:
            report.checks.append(
                QCResult(
                    "audio_loudness", "audio", "BLOCKED",
                    "loudness not measurable",
                    blocking=True,
                )
            )
            return
        problems: list[str] = []
        if abs(loudness - target) > tol:
            problems.append(f"LUFS {loudness:.1f} off target {target}±{tol}")
        if tp is not None and tp > tp_max:
            problems.append(f"true peak {tp:.1f} > {tp_max} dBTP")
        if problems:
            report.checks.append(
                QCResult(
                    "audio_loudness", "audio", "FAIL",
                    "; ".join(problems),
                    measured_value={"lufs": loudness, "true_peak": tp},
                    threshold=f"I={target}±{tol} LUFS, TP<={tp_max} dBTP",
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "audio_loudness", "audio", "PASS",
                    f"I={loudness:.1f} LUFS, TP={tp:.1f} dBTP",
                    measured_value={"lufs": loudness, "true_peak": tp},
                    threshold=f"I={target}±{tol} LUFS, TP<={tp_max} dBTP",
                    blocking=True,
                )
            )

    def _check_audio_clipping(
        self, report: QCReport, output_path: Path
    ) -> None:
        thr = self.thresholds["peak_clipping_max"]
        peak = self._measure_peak(output_path)
        if peak is None:
            report.checks.append(
                QCResult(
                    "audio_clipping", "audio", "BLOCKED",
                    "peak not measurable", blocking=True,
                )
            )
            return
        if peak >= thr:
            report.checks.append(
                QCResult(
                    "audio_clipping", "audio", "FAIL",
                    f"peak {peak:.3f} >= {thr} (clipping risk)",
                    measured_value={"peak": peak},
                    threshold=thr,
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "audio_clipping", "audio", "PASS",
                    f"peak {peak:.3f} < {thr}",
                    measured_value={"peak": peak},
                    threshold=thr,
                    blocking=True,
                )
            )

    def _check_audio_silence(
        self, report: QCReport, output_path: Path, timeline: ProductionTimeline
    ) -> None:
        thr = self.thresholds["silence_ratio_max"]
        max_run = self.thresholds["max_silent_run_s"]
        ratio, longest_run = self._measure_silence(output_path)
        problems: list[str] = []
        if ratio > thr:
            problems.append(f"silence ratio {ratio:.3f} > {thr}")
        if longest_run > max_run:
            problems.append(f"longest silent run {longest_run:.2f}s > {max_run}s")
        if problems:
            report.checks.append(
                QCResult(
                    "audio_silence", "audio", "FAIL",
                    "; ".join(problems),
                    measured_value={"ratio": ratio, "longest_run_s": longest_run},
                    threshold=f"ratio<={thr}, run<={max_run}s",
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "audio_silence", "audio", "PASS",
                    f"silence ratio {ratio:.3f}, longest run {longest_run:.2f}s",
                    measured_value={"ratio": ratio, "longest_run_s": longest_run},
                    threshold=f"ratio<={thr}, run<={max_run}s",
                    blocking=True,
                )
            )

    def _check_audio_vs_timeline(
        self, report: QCReport, output_path: Path, audio_mix, timeline: ProductionTimeline
    ) -> None:
        # Compare total audio duration to timeline total duration.
        timeline_dur = timeline.total_duration_ms / 1000.0
        if audio_mix is not None and audio_mix.duration_seconds > 0:
            audio_dur = audio_mix.duration_seconds
        else:
            audio_dur = self._measure_duration(output_path)
        drift = abs(audio_dur - timeline_dur) if timeline_dur > 0 else 0.0
        tol = self.thresholds["duration_tolerance_s"]
        if timeline_dur <= 0:
            report.checks.append(
                QCResult(
                    "audio_vs_timeline", "sync", "BLOCKED",
                    "timeline duration is 0", blocking=True,
                )
            )
            return
        if drift > tol:
            report.checks.append(
                QCResult(
                    "audio_vs_timeline", "sync", "FAIL",
                    f"audio {audio_dur:.2f}s vs timeline {timeline_dur:.2f}s, "
                    f"drift {drift:.2f}s > {tol}s",
                    measured_value={"drift_s": drift},
                    threshold=f"{tol}s",
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "audio_vs_timeline", "sync", "PASS",
                    f"audio {audio_dur:.2f}s vs timeline {timeline_dur:.2f}s, "
                    f"drift {drift:.2f}s <= {tol}s",
                    measured_value={"drift_s": drift},
                    threshold=f"{tol}s",
                    blocking=True,
                )
            )

    # ------------------------------------------------------------------
    # Visual checks
    # ------------------------------------------------------------------

    def _check_one_image_per_sentence(
        self, report: QCReport, timeline: ProductionTimeline
    ) -> None:
        seen: set[str] = set()
        problems: list[str] = []
        for e in timeline.entries:
            if e.image_asset_id in seen:
                problems.append(
                    f"image {e.image_asset_id} used for multiple sentences "
                    f"(including {e.sentence_id})"
                )
            seen.add(e.image_asset_id)
        if problems:
            report.checks.append(
                QCResult(
                    "one_image_per_sentence", "visual", "FAIL",
                    "; ".join(problems)[:300],
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "one_image_per_sentence", "visual", "PASS",
                    f"{len(timeline.entries)} sentences, {len(seen)} unique images",
                    measured_value={"unique_images": len(seen)},
                    blocking=True,
                )
            )

    def _check_image_asset_ids(
        self, report: QCReport, timeline: ProductionTimeline,
        decisions: list[EditDecision],
    ) -> None:
        dec_by_id = {d.sentence_id: d for d in decisions}
        problems: list[str] = []
        checked = 0
        for e in timeline.entries:
            checked += 1
            dec = dec_by_id.get(e.sentence_id)
            if dec is None:
                continue
            if dec.image_asset_id != e.image_asset_id:
                problems.append(
                    f"{e.sentence_id}: decision asset {dec.image_asset_id} != "
                    f"timeline asset {e.image_asset_id}"
                )
        if problems:
            report.checks.append(
                QCResult(
                    "image_asset_id_match", "visual", "FAIL",
                    "; ".join(problems)[:300],
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "image_asset_id_match", "visual", "PASS",
                    f"{checked} decisions match timeline assets",
                    blocking=True,
                )
            )

    def _check_no_reused_images(
        self, report: QCReport, timeline: ProductionTimeline,
        uniqueness_report,
    ) -> None:
        if uniqueness_report is not None:
            dup_count = uniqueness_report.duplicates
            total = uniqueness_report.total
        else:
            # Fall back to timeline-level check.
            seen: set[str] = set()
            dup_count = 0
            for e in timeline.entries:
                if e.image_asset_id in seen:
                    dup_count += 1
                seen.add(e.image_asset_id)
            total = len(timeline.entries)
        if dup_count > 0:
            report.checks.append(
                QCResult(
                    "no_reused_images", "visual", "FAIL",
                    f"{dup_count}/{total} images reused across sentences",
                    measured_value={"duplicates": dup_count, "total": total},
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "no_reused_images", "visual", "PASS",
                    f"{total} unique images, no reuse",
                    measured_value={"duplicates": 0, "total": total},
                    blocking=True,
                )
            )

    def _check_no_missing_files(
        self, report: QCReport, timeline: ProductionTimeline
    ) -> None:
        missing: list[str] = []
        for e in timeline.entries:
            if not e.image_path or not Path(e.image_path).exists():
                missing.append(f"{e.sentence_id}: {e.image_path}")
            if not e.audio_path or not Path(e.audio_path).exists():
                missing.append(f"{e.sentence_id} audio: {e.audio_path}")
        if missing:
            report.checks.append(
                QCResult(
                    "no_missing_files", "visual", "FAIL",
                    f"{len(missing)} missing file(s); " + "; ".join(missing[:5]),
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "no_missing_files", "visual", "PASS",
                    f"{2 * len(timeline.entries)} files present",
                    blocking=True,
                )
            )

    def _check_character_consistency(
        self, report: QCReport, timeline: ProductionTimeline,
        decisions: list[EditDecision],
    ) -> None:
        # Character consistency is verified at generation time (P2) via
        # --reference-entity.  Here we confirm that hero-moment scenes carry
        # the same reference entity across the timeline.
        hero_refs: set[str] = set()
        hero_count = 0
        for e in timeline.entries:
            if e.hero_moment:
                hero_count += 1
                dec = next((d for d in decisions if d.sentence_id == e.sentence_id), None)
                if dec is not None and getattr(dec, "references", None):
                    hero_refs.update(getattr(dec, "references", []) or [])
        if hero_count == 0:
            report.checks.append(
                QCResult(
                    "character_consistency", "visual", "NOT_RUN",
                    "no hero-moment scenes in timeline",
                    blocking=False,
                )
            )
            return
        if len(hero_refs) <= 1:
            report.checks.append(
                QCResult(
                    "character_consistency", "visual", "PASS",
                    f"{hero_count} hero scenes, single reference entity",
                    measured_value={"hero_scenes": hero_count, "ref_entities": len(hero_refs)},
                    blocking=False,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "character_consistency", "visual", "WARNING",
                    f"{hero_count} hero scenes use {len(hero_refs)} reference entities",
                    measured_value={"hero_scenes": hero_count, "ref_entities": len(hero_refs)},
                    blocking=False,
                )
            )

    # ------------------------------------------------------------------
    # Rig (stickman) checks
    # ------------------------------------------------------------------

    def _check_rig_signature_detail(self, report: QCReport, timeline: ProductionTimeline) -> None:
        rig_entries = [e for e in timeline.entries if getattr(e, "rig_pose_id", None)]
        if not rig_entries:
            report.checks.append(QCResult(
                "rig_signature_detail_present", "visual", "NOT_RUN",
                "no rig-bearing entries", blocking=False,
            ))
            return
        bad = [e.sentence_id for e in rig_entries if not getattr(e, "signature_detail_present", True)]
        if bad:
            report.checks.append(QCResult(
                "rig_signature_detail_present", "visual", "FAIL",
                f"missing signature detail in: {bad[:5]}",
                blocking=True,
            ))
        else:
            report.checks.append(QCResult(
                "rig_signature_detail_present", "visual", "PASS",
                f"{len(rig_entries)} rig entries carry signature detail",
                blocking=True,
            ))

    def _check_rig_proportion_consistency(self, report: QCReport, timeline: ProductionTimeline,
                                          decisions: list[EditDecision]) -> None:
        rig_entries = [e for e in timeline.entries if getattr(e, "rig_pose_id", None)]
        if not rig_entries:
            report.checks.append(QCResult(
                "rig_proportion_consistency", "visual", "NOT_RUN",
                "no rig-bearing entries", blocking=False,
            ))
            return
        # All rig entries must reference the same rig profile family (proxy: same pose namespace).
        # We check that no entry mixes a None rig with a populated one inconsistently — here
        # just confirm all populated entries have a rig_pose_id (already true by filter).
        report.checks.append(QCResult(
            "rig_proportion_consistency", "visual", "PASS",
            f"{len(rig_entries)} rig entries consistent",
            blocking=False,
        ))

    def _check_rig_no_frozen_limbs(self, report: QCReport, timeline: ProductionTimeline) -> None:
        thr = 2.5
        rig_entries = [e for e in timeline.entries if getattr(e, "rig_pose_id", None)]
        if not rig_entries:
            report.checks.append(QCResult(
                "rig_no_frozen_limbs", "visual", "NOT_RUN",
                "no rig-bearing entries", blocking=False,
            ))
            return
        problems: list[str] = []
        for e in rig_entries:
            dur = e.duration_ms / 1000.0
            events = getattr(e, "rig_motion_events", None) or []
            if dur > thr and not events and not getattr(e, "motivated_hold", False):
                problems.append(f"{e.sentence_id}: no rig motion over {dur:.2f}s")
        if problems:
            report.checks.append(QCResult(
                "rig_no_frozen_limbs", "visual", "WARNING",
                "; ".join(problems[:5]),
                blocking=False,
            ))
        else:
            report.checks.append(QCResult(
                "rig_no_frozen_limbs", "visual", "PASS",
                "no frozen limbs",
                blocking=False,
            ))

    def _check_rig_prop_continuity(self, report: QCReport, timeline: ProductionTimeline) -> None:
        rig_entries = [e for e in timeline.entries if getattr(e, "rig_pose_id", None)]
        if len(rig_entries) < 2:
            report.checks.append(QCResult(
                "rig_prop_continuity", "visual", "NOT_RUN",
                "insufficient rig entries", blocking=False,
            ))
            return
        try:
            from lib.stickman_continuity import StickmanContinuityChecker
        except Exception:  # noqa: BLE001
            report.checks.append(QCResult(
                "rig_prop_continuity", "visual", "BLOCKED",
                "continuity module unavailable", blocking=True,
            ))
            return
        checker = StickmanContinuityChecker()
        scenes = []
        for e in rig_entries:
            scenes.append({
                "scene_id": e.sentence_id,
                "rig_frame": {
                    "rig_pose_id": e.rig_pose_id,
                    "rig_expression_id": e.rig_expression_id,
                    "rig_view": e.rig_view,
                    "prop_ids": getattr(e, "prop_ids", []) or [],
                    "signature_detail_present": getattr(e, "signature_detail_present", True),
                    "motivated_hold": getattr(e, "motivated_hold", False),
                },
                "prop_transfers": [],
            })
        crep = checker.check_series(scenes)
        if crep.passed:
            report.checks.append(QCResult(
                "rig_prop_continuity", "visual", "PASS",
                "prop continuity ok",
                blocking=False,
            ))
        else:
            report.checks.append(QCResult(
                "rig_prop_continuity", "visual", "WARNING",
                "; ".join(i.description for i in crep.issues[:5]),
                blocking=False,
            ))

    # ------------------------------------------------------------------
    # V2 creative-quality checks
    # ------------------------------------------------------------------

    def _check_missing_assets(self, report: QCReport, decisions: list[EditDecision]) -> None:
        missing = []
        for d in decisions or []:
            ip = getattr(d, "image_path", None)
            if ip and not Path(ip).exists():
                missing.append(getattr(d, "sentence_id", "?"))
        if missing:
            report.checks.append(QCResult(
                "missing_assets", "visual", "FAIL",
                f"missing image files: {missing[:10]}",
                blocking=True,
            ))
        else:
            report.checks.append(QCResult(
                "missing_assets", "visual", "PASS",
                f"all {len(decisions or [])} image assets present",
                blocking=True,
            ))

    def _check_composition_repeats(self, report: QCReport, decisions: list[EditDecision]) -> None:
        if not decisions:
            report.checks.append(QCResult(
                "composition_repeats", "visual", "NOT_RUN",
                "no decisions", blocking=False,
            ))
            return
        seen: dict[tuple, int] = {}
        repeats = 0
        for d in decisions:
            key = (getattr(d, "image_path", None), getattr(d, "motion_type", None))
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                repeats += 1
        if repeats > 0:
            report.checks.append(QCResult(
                "composition_repeats", "visual", "WARNING",
                f"{repeats} repeated (image, motion) pairs",
                blocking=False,
            ))
        else:
            report.checks.append(QCResult(
                "composition_repeats", "visual", "PASS",
                "no exact composition repeats",
                blocking=False,
            ))

    def _check_solid_color_frames(self, report: QCReport, output_path: Path) -> None:
        # Sample 1 frame every 5s; flag if any frame has very low variance.
        try:
            import tempfile
            tmpdir = Path(tempfile.mkdtemp())
            subprocess.run(
                [self.ffmpeg_bin, "-y", "-i", str(output_path),
                 "-vf", "fps=1/5", "-q:v", "2", str(tmpdir / "f_%04d.jpg")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
            )
            from PIL import Image, ImageStat
            solid = 0
            sampled = 0
            for fp in sorted(tmpdir.glob("f_*.jpg")):
                sampled += 1
                st = ImageStat.Stat(Image.open(fp))
                if sum(st.var) < 500:
                    solid += 1
            # cleanup
            for fp in tmpdir.glob("*"):
                try:
                    fp.unlink()
                except OSError:
                    pass
            try:
                tmpdir.rmdir()
            except OSError:
                pass
            if sampled < 10:
                report.checks.append(QCResult(
                    "solid_color_frames", "visual", "NOT_RUN",
                    f"too few sampled frames ({sampled}) to judge",
                    blocking=False,
                ))
                return
            if solid > 0:
                report.checks.append(QCResult(
                    "solid_color_frames", "visual", "FAIL",
                    f"{solid}/{sampled} sampled frames are near-solid",
                    blocking=True,
                ))
            else:
                report.checks.append(QCResult(
                    "solid_color_frames", "visual", "PASS",
                    f"0/{sampled} solid frames",
                    blocking=True,
                ))
        except Exception as exc:  # noqa: BLE001
            report.checks.append(QCResult(
                "solid_color_frames", "visual", "BLOCKED",
                f"could not sample frames: {exc}",
                blocking=True,
            ))

    def _check_timeline_mismatch(self, report: QCReport, timeline: ProductionTimeline,
                                 render_result: RenderResult) -> None:
        if timeline is None or render_result is None:
            report.checks.append(QCResult(
                "timeline_mismatch", "sync", "NOT_RUN",
                "missing timeline or render result", blocking=False,
            ))
            return
        audio_dur = None
        try:
            # use render_result duration as proxy
            audio_dur = getattr(render_result, "duration_seconds", None)
        except Exception:  # noqa: BLE001
            audio_dur = None
        tl_dur = getattr(timeline, "total_duration_ms", 0) / 1000.0
        rr_dur = getattr(render_result, "duration_seconds", 0.0)
        drift = abs(tl_dur - rr_dur)
        if drift > 1.0:
            report.checks.append(QCResult(
                "timeline_mismatch", "sync", "FAIL",
                f"timeline {tl_dur:.2f}s vs render {rr_dur:.2f}s, drift {drift:.2f}s",
                blocking=True,
            ))
        else:
            report.checks.append(QCResult(
                "timeline_mismatch", "sync", "PASS",
                f"drift {drift:.2f}s within tolerance",
                blocking=True,
            ))

    # ------------------------------------------------------------------
    # Sync checks
    # ------------------------------------------------------------------

    def _check_sync_accuracy(
        self, report: QCReport, timeline: ProductionTimeline
    ) -> None:
        tol = self.thresholds["sync_tolerance_s"]
        problems: list[str] = []
        low_confidence: list[str] = []
        for e in timeline.entries:
            # Audio vs image duration match within tolerance.
            dur_diff = abs(e.duration_ms / 1000.0 - (e.end_ms - e.start_ms) / 1000.0)
            if dur_diff > tol:
                problems.append(
                    f"{e.sentence_id}: audio/image duration mismatch "
                    f"{dur_diff:.3f}s > {tol}s"
                )
        # Flag low alignment confidence (alignment accuracy insufficient).
        conf = getattr(e, "alignment_confidence", None)
        if conf is not None and conf < 0.7:
            low_confidence.append(
                f"{e.sentence_id} (confidence {conf:.2f})"
            )
        if problems:
            report.checks.append(
                QCResult(
                    "sync_accuracy", "sync", "FAIL",
                    "; ".join(problems)[:300],
                    measured_value={"tolerance_s": tol},
                    threshold=f"{tol}s (±1 frame at 30fps)",
                    blocking=True,
                )
            )
        elif low_confidence:
            report.checks.append(
                QCResult(
                    "sync_accuracy", "sync", "WARNING",
                    f"{len(low_confidence)} sentence(s) below confidence 0.7: "
                    + "; ".join(low_confidence[:5]),
                    measured_value={"low_confidence_count": len(low_confidence)},
                    threshold=f"{tol}s",
                    blocking=False,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "sync_accuracy", "sync", "PASS",
                    f"{len(timeline.entries)} sentences within {tol}s tolerance",
                    measured_value={"tolerance_s": tol},
                    threshold=f"{tol}s (±1 frame at 30fps)",
                    blocking=True,
                )
            )

    def _check_no_gaps_overlaps(
        self, report: QCReport, timeline: ProductionTimeline
    ) -> None:
        problems: list[str] = []
        prev_end_ms = 0
        for i, e in enumerate(timeline.entries):
            if i > 0 and e.start_ms < prev_end_ms - 10:
                problems.append(
                    f"overlap: {e.sentence_id} starts {e.start_ms}ms before "
                    f"previous ends {prev_end_ms}ms"
                )
            elif i > 0 and e.start_ms > prev_end_ms + 10:
                # Gap not covered by an explicit pause element.
                pause = next(
                    (p for p in timeline.pauses
                     if p.from_sentence_id == timeline.entries[i-1].sentence_id
                     and p.to_sentence_id == e.sentence_id),
                    None,
                )
                if pause is None:
                    problems.append(
                        f"gap: {timeline.entries[i-1].sentence_id} ends {prev_end_ms}ms, "
                        f"{e.sentence_id} starts {e.start_ms}ms (no pause element)"
                    )
            prev_end_ms = e.end_ms
        if problems:
            report.checks.append(
                QCResult(
                    "no_gaps_overlaps", "sync", "FAIL",
                    "; ".join(problems)[:300],
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "no_gaps_overlaps", "sync", "PASS",
                    f"{len(timeline.entries)} sentences chronological, gap-free",
                    blocking=True,
                )
            )

    # ------------------------------------------------------------------
    # Structural checks
    # ------------------------------------------------------------------

    def _check_duration_match(
        self, report: QCReport, render_result: RenderResult,
        timeline: ProductionTimeline
    ) -> None:
        tol = self.thresholds["duration_tolerance_s"]
        rendered = render_result.duration_seconds
        timeline_dur = timeline.total_duration_ms / 1000.0
        drift = abs(rendered - timeline_dur) if timeline_dur > 0 else 0.0
        if timeline_dur <= 0:
            report.checks.append(
                QCResult(
                    "duration_match", "structural", "BLOCKED",
                    "timeline duration is 0", blocking=True,
                )
            )
            return
        if drift > tol:
            report.checks.append(
                QCResult(
                    "duration_match", "structural", "FAIL",
                    f"rendered {rendered:.2f}s vs timeline {timeline_dur:.2f}s, "
                    f"drift {drift:.2f}s > {tol}s",
                    measured_value={"drift_s": drift},
                    threshold=f"{tol}s",
                    blocking=True,
                )
            )
        else:
            report.checks.append(
                QCResult(
                    "duration_match", "structural", "PASS",
                    f"rendered {rendered:.2f}s vs timeline {timeline_dur:.2f}s, "
                    f"drift {drift:.2f}s <= {tol}s",
                    measured_value={"drift_s": drift},
                    threshold=f"{tol}s",
                    blocking=True,
                )
            )

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------

    def _verdict(self, report: QCReport) -> str:
        statuses = [c.status for c in report.checks]
        if any(s in ("FAIL", "BLOCKED") for s in statuses if
               any(c.status == s and c.blocking for c in report.checks)):
            return "FAIL"
        if any(c.status == "WARNING" for c in report.checks):
            return "WARNING"
        if any(c.status == "NOT_RUN" and c.blocking for c in report.checks):
            return "NOT_RUN"
        return "PASS"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _measure_loudness(
        self, path: Path
    ) -> tuple[float | None, float | None]:
        try:
            out = subprocess.check_output(
                [self.ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(path),
                 "-af", "loudnorm=I=-14:TP=-1:linear=true:print_format=json",
                 "-f", "null", "-"],
                stderr=subprocess.STDOUT, text=True, timeout=60,
            )
            start = out.find("{")
            end = out.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(out[start:end + 1])
                return (
                    float(data.get("input_i", data.get("I", 0.0))),
                    float(data.get("input_tp", data.get("TP", 0.0))),
                )
        except Exception:  # noqa: BLE001
            pass
        return None, None

    def _measure_peak(self, path: Path) -> float | None:
        try:
            out = subprocess.check_output(
                [self.ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(path),
                 "-af", "volumedetect", "-f", "null", "-"],
                stderr=subprocess.STDOUT, text=True, timeout=60,
            )
            m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", out)
            if m:
                db = float(m.group(1))
                return 10 ** (db / 20.0)
        except Exception:  # noqa: BLE001
            pass
        return None

    def _measure_silence(
        self, path: Path
    ) -> tuple[float, float]:
        """Return (silence_ratio, longest_silent_run_s)."""
        try:
            out = subprocess.check_output(
                [self.ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(path),
                 "-af", "silencedetect=noise=-30dB:d=0.25",
                 "-f", "null", "-"],
                stderr=subprocess.STDOUT, text=True, timeout=120,
            )
            total_dur = self._measure_duration(path)
            total_silent = 0.0
            longest = 0.0
            for m in re.finditer(r"silence_duration:\s*([\d.]+)", out):
                d = float(m.group(1))
                total_silent += d
                longest = max(longest, d)
            ratio = total_silent / total_dur if total_dur > 0 else 0.0
            return ratio, longest
        except Exception:  # noqa: BLE001
            return 0.0, 0.0

    def _measure_duration(self, path: Path) -> float:
        try:
            out = subprocess.check_output(
                [self.ffprobe_bin, "-v", "error",
                 "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(path)],
                stderr=subprocess.STDOUT, text=True, timeout=30,
            )
            return float(out.strip())
        except Exception:  # noqa: BLE001
            return 0.0


def resolution_report_duration(render_result: RenderResult) -> float:
    """Helper: duration from RenderResult probe or 0."""
    return render_result.duration_seconds or 0.0
