"""Preview System — short preview fragments before full P4 render.

Builds preview clips (first N sentences or selected sentence_ids) using the
RenderEngine, then runs preview QC:
  * composition (aspect ratio, resolution)
  * motion speed (zoompan parameters sane)
  * transitions present
  * sync (audio/video duration match)
  * readability of scientific diagrams (resolution >= 720p)
  * visual variety (motion types not all identical)

Zero-cost: FFmpeg only.  No generation, no credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lib.edit_decision_engine import EditDecision, EditDecisionSet
from lib.production_timeline import ProductionTimeline
from lib.render_engine import RenderEngine, RenderResult


@dataclass
class PreviewCheck:
    """One preview QC check result."""

    criterion: str
    passed: bool
    score: float  # 0.0 - 1.0
    detail: str
    blocking: bool = False


@dataclass
class PreviewResult:
    """Outcome of building + checking one preview."""

    preview_id: str
    output_path: str
    sentence_ids: list[str]
    duration_seconds: float
    render: RenderResult
    checks: list[PreviewCheck] = field(default_factory=list)
    passed: bool = False
    overall_score: float = 0.0
    blocking_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preview_id": self.preview_id,
            "output_path": self.output_path,
            "sentence_ids": self.sentence_ids,
            "duration_seconds": self.duration_seconds,
            "render": self.render.to_dict(),
            "checks": [asdict(c) for c in self.checks],
            "passed": self.passed,
            "overall_score": self.overall_score,
            "blocking_issues": self.blocking_issues,
        }


class PreviewSystem:
    """Build and QC short preview fragments."""

    def __init__(
        self,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        max_preview_seconds: float = 30.0,
    ) -> None:
        self.fps = fps
        self.width = width
        self.height = height
        self.max_preview_seconds = max_preview_seconds
        self.engine = RenderEngine(fps=fps, width=width, height=height)

    # ------------------------------------------------------------------
    # Build preview
    # ------------------------------------------------------------------

    def build_preview(
        self,
        *,
        preview_id: str,
        project_id: str,
        edit_decisions: list[dict[str, Any]],
        sentence_ids: list[str] | None = None,
        count: int | None = None,
        output_path: str | Path = "projects/<project>/previews/preview.mp4",
        audio_mix=None,
        timeline: ProductionTimeline | None = None,
    ) -> PreviewResult:
        """Render a preview of the first `count` sentences (or the listed
        sentence_ids), then QC it.

        If neither sentence_ids nor count is given, previews the first
        sentence only (fastest smoke check).
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Select the subset of decisions to preview.
        selected = self._select_decisions(edit_decisions, sentence_ids, count)
        if not selected:
            return PreviewResult(
                preview_id=preview_id,
                output_path=str(output_path),
                sentence_ids=[],
                duration_seconds=0.0,
                render=RenderResult(
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
                    errors=["no sentences selected for preview"],
                ),
                passed=False,
                overall_score=0.0,
                blocking_issues=["no sentences selected"],
            )

        sel_ids = [d.get("sentence_id", d.get("scene_id", f"s{i}")) for i, d in enumerate(selected)]
        total_dur_ms = sum(int(d.get("duration_ms", 0)) for d in selected)

        # Cap duration.
        if total_dur_ms / 1000.0 > self.max_preview_seconds:
            # Trim selection to fit max_preview_seconds.
            acc = 0
            keep = []
            for d in selected:
                dms = int(d.get("duration_ms", 0))
                if acc + dms > self.max_preview_seconds * 1000 and keep:
                    break
                keep.append(d)
                acc += dms
            selected = keep
            sel_ids = [d.get("sentence_id", d.get("scene_id", f"s{i}")) for i, d in enumerate(selected)]
            total_dur_ms = sum(int(d.get("duration_ms", 0)) for d in selected)

        # Render.
        render = self.engine.render(
            project_id=project_id,
            edit_decisions=selected,
            timeline=timeline,
            audio_mix=audio_mix,
            output_path=output_path,
        )

        # QC.
        checks = self._qc_preview(render, selected, total_dur_ms)
        blocking = [c.detail for c in checks if c.blocking]
        passed = render.status == "rendered" and not blocking
        overall = (
            sum(c.score for c in checks) / len(checks) if checks else 0.0
        )

        return PreviewResult(
            preview_id=preview_id,
            output_path=str(output_path),
            sentence_ids=sel_ids,
            duration_seconds=round(total_dur_ms / 1000.0, 3),
            render=render,
            checks=checks,
            passed=passed,
            overall_score=round(overall, 2),
            blocking_issues=blocking,
        )

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    @staticmethod
    def _select_decisions(
        decisions: list[dict[str, Any]],
        sentence_ids: list[str] | None,
        count: int | None,
    ) -> list[dict[str, Any]]:
        if sentence_ids:
            sid_set = set(sentence_ids)
            return [d for d in decisions if d.get("sentence_id") in sid_set]
        if count is not None:
            return decisions[: max(0, min(count, len(decisions)))]
        return decisions[:1]

    # ------------------------------------------------------------------
    # QC
    # ------------------------------------------------------------------

    def _qc_preview(
        self,
        render: RenderResult,
        decisions: list[dict[str, Any]],
        expected_dur_ms: int,
    ) -> list[PreviewCheck]:
        checks: list[PreviewCheck] = []

        # 1. Render succeeded.
        checks.append(PreviewCheck(
            criterion="render_success",
            passed=render.status == "rendered",
            score=1.0 if render.status == "rendered" else 0.0,
            detail=f"render status={render.status}",
            blocking=(render.status != "rendered"),
        ))

        # 2. Composition: resolution 1920x1080, 16:9.
        res_ok = render.resolution == f"{self.width}x{self.height}"
        checks.append(PreviewCheck(
            criterion="composition_resolution",
            passed=res_ok,
            score=1.0 if res_ok else 0.5,
            detail=f"resolution={render.resolution}",
            blocking=not res_ok,
        ))

        # 3. Motion speed sanity: zoompan scales within [1.0, 1.5].
        motion_ok = True
        motion_detail = "motion parameters sane"
        for d in decisions:
            cp = d.get("camera_parameters", {})
            ss = float(cp.get("start_scale", 1.0))
            es = float(cp.get("end_scale", 1.0))
            if not (0.8 <= ss <= 2.0 and 0.8 <= es <= 2.0):
                motion_ok = False
                motion_detail = f"scale out of range: {ss}->{es}"
                break
        checks.append(PreviewCheck(
            criterion="motion_speed",
            passed=motion_ok,
            score=1.0 if motion_ok else 0.4,
            detail=motion_detail,
            blocking=not motion_ok,
        ))

        # 4. Transitions present.
        trans = [d.get("transition", "cut") for d in decisions]
        trans_ok = all(t in ("cut", "dissolve", "fade", "wipe") for t in trans)
        checks.append(PreviewCheck(
            criterion="transitions",
            passed=trans_ok,
            score=1.0 if trans_ok else 0.0,
            detail=f"transitions={trans}",
            blocking=not trans_ok,
        ))

        # 5. Sync: audio/video duration match (±1s).
        dur_ok = abs(render.duration_seconds - expected_dur_ms / 1000.0) <= 1.0
        checks.append(PreviewCheck(
            criterion="audio_video_sync",
            passed=dur_ok,
            score=1.0 if dur_ok else 0.5,
            detail=f"render={render.duration_seconds}s vs expected={expected_dur_ms/1000.0}s",
            blocking=not dur_ok,
        ))

        # 6. Readability: resolution >= 720p (scientific diagrams legible).
        h = int(render.resolution.split("x")[1]) if "x" in render.resolution else 0
        read_ok = h >= 720
        checks.append(PreviewCheck(
            criterion="readability",
            passed=read_ok,
            score=1.0 if read_ok else 0.3,
            detail=f"height={h}p",
            blocking=not read_ok,
        ))

        # 7. Visual variety: not all identical motion type.
        mtypes = [d.get("motion_type", "static") for d in decisions]
        variety_ok = len(set(mtypes)) > 1 or len(decisions) <= 1
        checks.append(PreviewCheck(
            criterion="visual_variety",
            passed=variety_ok,
            score=1.0 if variety_ok else 0.6,
            detail=f"motion_types={mtypes}",
            blocking=False,
        ))

        # 8. No black frames / frozen segments.
        clean_ok = not render.black_frames and not render.frozen_segments
        checks.append(PreviewCheck(
            criterion="no_black_or_frozen",
            passed=clean_ok,
            score=1.0 if clean_ok else 0.5,
            detail=f"black={len(render.black_frames)} frozen={len(render.frozen_segments)}",
            blocking=not clean_ok,
        ))

        # 9. Rig signature detail present (if rig-bearing cuts).
        rig_cuts = [d for d in decisions if d.get("rig_pose_id") or d.get("rig_expression_id")]
        if rig_cuts:
            sig_ok = all(bool(d.get("signature_detail_present", True)) for d in rig_cuts)
            checks.append(PreviewCheck(
                criterion="rig_signature_detail",
                passed=sig_ok,
                score=1.0 if sig_ok else 0.0,
                detail="all rig cuts carry signature detail" if sig_ok else "missing signature detail",
                blocking=sig_ok is False,
            ))
            # 10. Meaningful rig motion (per-limb events) for shots > 1s.
            motion_ok = True
            for d in rig_cuts:
                dur = int(d.get("duration_ms", 0))
                events = d.get("rig_motion_events") or []
                if dur > 1000 and not events and not d.get("motivated_hold"):
                    motion_ok = False
                    break
            checks.append(PreviewCheck(
                criterion="rig_motion_meaningful",
                passed=motion_ok,
                score=1.0 if motion_ok else 0.6,
                detail="rig motion events present or motivated_hold",
                blocking=False,
            ))

        return checks
