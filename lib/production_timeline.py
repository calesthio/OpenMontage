"""Production Timeline — unified P4 timeline + validation.

Merges P3 sentence timings (audio) with P4 edit decisions (images + motion)
into a single render-ready timeline, then validates:

  * every sentence_id present exactly once
  * unique image + audio per sentence (ONE SENTENCE = ONE IMAGE = ONE AUDIO)
  * chronological, gap-free, non-overlapping
  * explicit pause elements between sentences (not accidental gaps)
  * total duration matches audio + video

Produces a ProductionTimeline that the RenderEngine consumes.  Zero-cost:
pure validation; no generation, no credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TimelinePause:
    """Explicit pause between two sentences (a timeline element, not a gap)."""

    pause_id: str
    from_sentence_id: str
    to_sentence_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    reason: str = "inter_sentence_pause"


@dataclass
class TimelineEntry:
    """One timeline entry (scene + its explicit trailing pause, if any)."""

    sentence_id: str
    scene_id: str
    image_asset_id: str
    image_path: str
    audio_asset_id: str
    audio_path: str
    start_ms: int
    end_ms: int
    duration_ms: int
    motion_type: str
    camera_parameters: dict[str, Any]
    transition: str
    transition_duration: float
    visual_effects: list[str]
    narrative_role: str
    hero_moment: bool
    # Stickman rig fields (optional, additive)
    rig_pose_id: str | None = None
    rig_expression_id: str | None = None
    rig_view: str | None = None
    prop_ids: list[str] = field(default_factory=list)
    signature_detail_present: bool = True
    motivated_hold: bool = False
    rig_overlay_path: str | None = None
    pause_after: TimelinePause | None = None
    status: str = "planned"  # planned | validated | rendered | failed


@dataclass
class ProductionTimeline:
    """Complete validated timeline for P4 rendering."""

    version: str = "1.0"
    project_id: str = ""
    run_id: str = ""
    created_at: str = ""
    total_duration_ms: int = 0
    total_sentences: int = 0
    total_pause_ms: int = 0
    entries: list[TimelineEntry] = field(default_factory=list)
    pauses: list[TimelinePause] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | validated | blocked | failed

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0 and self.status == "validated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms,
            "total_sentences": self.total_sentences,
            "total_pause_ms": self.total_pause_ms,
            "entries": [e.to_dict() if hasattr(e, "to_dict") else asdict(e)
                        for e in self.entries],
            "pauses": [asdict(p) for p in self.pauses],
            "issues": self.issues,
            "status": self.status,
            "is_valid": self.is_valid,
        }


class ProductionTimelineBuilder:
    """Build and validate the unified production timeline."""

    def __init__(
        self,
        *,
        default_pause_ms: int = 300,
        max_gap_tolerance_ms: int = 10,
    ) -> None:
        self.default_pause_ms = default_pause_ms
        self.max_gap_tolerance_ms = max_gap_tolerance_ms

    def build(
        self,
        *,
        project_id: str,
        run_id: str,
        edit_decisions: list[dict[str, Any]],
        audio_timings: list[dict[str, Any]] | None = None,
    ) -> ProductionTimeline:
        """Build timeline from edit decisions + optional audio timings.

        Args:
            edit_decisions: list of EditDecision dicts (P4).
            audio_timings: optional list of alignment dicts with
                sentence_id, start_ms, end_ms (P3).  If omitted, uses the
                edit decision's own start/end.
        """
        audio_by_id = {}
        if audio_timings:
            for t in audio_timings:
                audio_by_id[t["sentence_id"]] = t

        entries: list[TimelineEntry] = []
        pauses: list[TimelinePause] = []
        issues: list[str] = []
        total_duration_ms = 0
        total_pause_ms = 0
        seen_sentence: set[str] = set()
        seen_image: set[str] = set()
        seen_audio: set[str] = set()

        prev_end_ms = 0
        for i, ed in enumerate(edit_decisions):
            sid = ed.get("sentence_id", ed.get("scene_id", f"s{i:03d}"))
            start_ms = int(ed.get("start_ms", 0))
            end_ms = int(ed.get("end_ms", start_ms + ed.get("duration_ms", 0)))
            dur_ms = int(end_ms - start_ms)
            total_duration_ms = max(total_duration_ms, end_ms)

            # Uniqueness checks.
            if sid in seen_sentence:
                issues.append(f"duplicate sentence_id: {sid}")
            seen_sentence.add(sid)
            iid = ed.get("image_asset_id", "")
            if iid:
                if iid in seen_image:
                    issues.append(f"duplicate image_asset_id: {iid}")
                seen_image.add(iid)
            aid = ed.get("audio_asset_id", "")
            if aid:
                if aid in seen_audio:
                    issues.append(f"duplicate audio_asset_id: {aid}")
                seen_audio.add(aid)

            # Chronology / gap / overlap vs previous.
            if i > 0:
                gap = start_ms - prev_end_ms
                if gap < -self.max_gap_tolerance_ms:
                    issues.append(
                        f"overlap: {sid} starts {start_ms}ms before previous "
                        f"ends {prev_end_ms}ms"
                    )
                elif gap > self.max_gap_tolerance_ms:
                    # Explicit pause element.
                    pauses.append(
                        TimelinePause(
                            pause_id=f"{project_id}-pause-{i:03d}",
                            from_sentence_id=edit_decisions[i-1].get(
                                "sentence_id", edit_decisions[i-1].get("scene_id","")
                            ),
                            to_sentence_id=sid,
                            start_ms=prev_end_ms,
                            end_ms=start_ms,
                            duration_ms=gap,
                            reason="inter_sentence_pause",
                        )
                    )
                    total_pause_ms += gap

            # Audio timing override (P3 alignment is authoritative).
            if sid in audio_by_id:
                at = audio_by_id[sid]
                start_ms = int(at.get("start_ms", start_ms))
                end_ms = int(at.get("end_ms", end_ms))
                dur_ms = int(end_ms - start_ms)

            entry = TimelineEntry(
                sentence_id=sid,
                scene_id=ed.get("scene_id", sid),
                image_asset_id=iid,
                image_path=ed.get("image_path", ""),
                audio_asset_id=aid,
                audio_path=ed.get("audio_path", ""),
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=dur_ms,
                motion_type=ed.get("motion_type", "static"),
                camera_parameters=ed.get("camera_parameters", {}),
                transition=ed.get("transition", "cut"),
                transition_duration=float(ed.get("transition_duration", 0.5)),
                visual_effects=list(ed.get("visual_effects", [])),
                narrative_role=ed.get("narrative_role", "establish_context"),
                hero_moment=bool(ed.get("hero_moment", False)),
                rig_pose_id=ed.get("rig_pose_id"),
                rig_expression_id=ed.get("rig_expression_id"),
                rig_view=ed.get("rig_view"),
                prop_ids=list(ed.get("prop_ids", []) or []),
                signature_detail_present=bool(ed.get("signature_detail_present", True)),
                motivated_hold=bool(ed.get("motivated_hold", False)),
                rig_overlay_path=ed.get("rig_overlay_path"),
                status="planned",
            )
            entries.append(entry)
            prev_end_ms = end_ms

        status = "validated" if not issues else "blocked"

        return ProductionTimeline(
            project_id=project_id,
            run_id=run_id,
            created_at=self._now(),
            total_duration_ms=total_duration_ms,
            total_sentences=len(entries),
            total_pause_ms=total_pause_ms,
            entries=entries,
            pauses=pauses,
            issues=issues,
            status=status,
        )

    def validate_gaps_overlaps(self, timeline: ProductionTimeline) -> dict[str, Any]:
        """Re-validate an already-built timeline (idempotent check)."""
        problems: list[str] = []
        prev_end = 0
        for i, e in enumerate(timeline.entries):
            if i > 0 and e.start_ms < prev_end - self.max_gap_tolerance_ms:
                problems.append(
                    f"overlap at {e.sentence_id}: starts {e.start_ms}ms "
                    f"before previous ends {prev_end}ms"
                )
            prev_end = e.end_ms
        # duration consistency.
        computed = max((e.end_ms for e in timeline.entries), default=0)
        if computed != timeline.total_duration_ms:
            problems.append(
                f"duration mismatch: timeline says "
                f"{timeline.total_duration_ms}ms, entries end at {computed}ms"
            )
        return {
            "ok": len(problems) == 0,
            "problems": problems,
            "total_duration_ms": timeline.total_duration_ms,
            "total_sentences": timeline.total_sentences,
            "total_pause_ms": timeline.total_pause_ms,
        }

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


# Give TimelineEntry a to_dict for clean serialization.
def _timeline_entry_to_dict(self: TimelineEntry) -> dict[str, Any]:
    d = asdict(self)
    if self.pause_after is not None:
        d["pause_after"] = asdict(self.pause_after)
    return d


TimelineEntry.to_dict = _timeline_entry_to_dict
