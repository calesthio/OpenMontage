"""Sentence Timeline — unified per-sentence timeline for P4 rendering.

Combines, for each sentence:

  * sentence_id, original_text, normalized_text
  * audio_asset_id, audio_path, audio duration
  * start_ms / end_ms / duration_ms (from audio alignment)
  * image_asset_id, image_path (from image generation engine)
  * status and QC results

This is the single source P4 consumes to show one unique image per sentence
for exactly the duration of its audio.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SentenceTimelineEntry:
    """One sentence's place in the final timeline."""

    sentence_id: str
    original_text: str
    normalized_text: str
    audio_asset_id: str
    audio_path: str
    start_ms: int
    end_ms: int
    duration_ms: int
    alignment_confidence: float
    image_asset_id: str | None = None
    image_path: str | None = None
    image_qc_passed: bool = False
    audio_qc_passed: bool = False
    status: str = "planned"  # planned | audio_ready | image_ready | ready | blocked | failed
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SentenceTimeline:
    """Complete timeline for one project."""

    project_id: str
    version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_duration_ms: int = 0
    total_sentences: int = 0
    entries: list[SentenceTimelineEntry] = field(default_factory=list)
    ready_count: int = 0
    blocked_count: int = 0

    @property
    def by_id(self) -> dict[str, SentenceTimelineEntry]:
        return {e.sentence_id: e for e in self.entries}

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "version": self.version,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms,
            "total_sentences": self.total_sentences,
            "ready_count": self.ready_count,
            "blocked_count": self.blocked_count,
            "entries": [e.to_dict() for e in self.entries],
        }

    def ready_for_p4(self) -> bool:
        """True if every sentence has audio QC-passed (ready to merge images in P4)."""
        return (
            self.total_sentences > 0
            and all(e.audio_qc_passed for e in self.entries)
            and self.blocked_count == 0
        )


class SentenceTimelineBuilder:
    """Build a SentenceTimeline from audio alignment + image engine output."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.timeline: SentenceTimeline | None = None

    def build(
        self,
        *,
        audio_timings: list[dict[str, Any]],
        image_plans: list[dict[str, Any]],
        audio_qc: dict[str, bool] | None = None,
        image_qc: dict[str, bool] | None = None,
    ) -> SentenceTimeline:
        """Merge audio timings with image plans into a timeline.

        *audio_timings* — list of SentenceTiming dicts (order = playback order)
        *image_plans* — list of SentenceImagePlan dicts keyed by sentence_id
        *audio_qc* — sentence_id -> bool (audio QC passed)
        *image_qc* — sentence_id -> bool (image QC passed)
        """
        audio_qc = audio_qc or {}
        image_qc = image_qc or {}
        image_by_id = {p.get("sentence_id"): p for p in image_plans}

        entries: list[SentenceTimelineEntry] = []
        total_duration_ms = 0
        ready = blocked = 0

        for at in audio_timings:
            sid = at["sentence_id"]
            ip = image_by_id.get(sid, {})
            total_duration_ms = max(total_duration_ms, int(at.get("end_ms", 0)))

            audio_ok = bool(audio_qc.get(sid, False))
            image_ok = bool(image_qc.get(sid, False))

            if audio_ok and image_ok:
                status = "ready"
                ready += 1
            elif not audio_ok and not image_ok:
                status = "blocked"
                blocked += 1
            else:
                status = "partial"

            entries.append(SentenceTimelineEntry(
                sentence_id=sid,
                original_text=at.get("original_text", ""),
                normalized_text=at.get("normalized_text", ""),
                audio_asset_id=at.get("audio_asset_id", ""),
                audio_path=at.get("audio_path", ""),
                start_ms=int(at.get("start_ms", 0)),
                end_ms=int(at.get("end_ms", 0)),
                duration_ms=int(at.get("duration_ms", 0)),
                alignment_confidence=float(at.get("alignment_confidence", 0.0)),
                image_asset_id=ip.get("asset_id"),
                image_path=ip.get("output_path"),
                image_qc_passed=image_ok,
                audio_qc_passed=audio_ok,
                status=status,
            ))

        self.timeline = SentenceTimeline(
            project_id=self.project_id,
            total_duration_ms=total_duration_ms,
            total_sentences=len(entries),
            entries=entries,
            ready_count=ready,
            blocked_count=blocked,
        )
        return self.timeline

    def save(self, path: str | Path) -> None:
        if self.timeline is None:
            raise RuntimeError("build() must be called before save()")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(self.timeline.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self, path: str | Path) -> SentenceTimeline:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = [SentenceTimelineEntry(**e) for e in data.get("entries", [])]
        self.timeline = SentenceTimeline(
            project_id=data.get("project_id", self.project_id),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
            total_duration_ms=data.get("total_duration_ms", 0),
            total_sentences=data.get("total_sentences", 0),
            entries=entries,
            ready_count=data.get("ready_count", 0),
            blocked_count=data.get("blocked_count", 0),
        )
        return self.timeline
