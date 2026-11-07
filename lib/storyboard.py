"""Storyboard / scene manifest — V8 §3.5, §8.7, §8.8, §8.9.

Each scene gets:
- claim_ids: links to the claim ledger (§8.8)
- visual_class: one of REAL_ARCHIVE, DATA_VISUALIZATION,
  SCIENTIFIC_DIAGRAM, SCIENTIFIC_RECONSTRUCTION, HYPOTHETICAL_RECONSTRUCTION,
  ARTISTIC_METAPHOR (§8.9)
- visual_role: scale_establishing | evidence | explanation | transition | ...
- motion: {type, amplitude, depth_map_required} (§3.5)
- music_cue: music state for this scene (§3.7)
- start_frame / end_frame: derived from audio master sample rate (§3.4)

This is a logical zone of responsibility, not a separate microservice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# V8 §8.9: six visual classes — replaces the binary archival vs ai_generated split.
VISUAL_CLASSES = frozenset({
    "REAL_ARCHIVE",
    "DATA_VISUALIZATION",
    "SCIENTIFIC_DIAGRAM",
    "SCIENTIFIC_RECONSTRUCTION",
    "HYPOTHETICAL_RECONSTRUCTION",
    "ARTISTIC_METAPHOR",
})

# V8 §3.5: motion types.
MOTION_TYPES = frozenset({
    "static_intentional",
    "optical_push_pull",
    "lateral_drift",
    "depth_parallax",
    "reveal_mask",
    "diagram_animation",
    "real_footage_stabilization",
    "no_motion",
})


@dataclass
class MotionPlan:
    """Planned camera/motion treatment for one scene."""

    type: str  # one of MOTION_TYPES
    amplitude: str = "low"  # low | medium | high
    depth_map_required: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SceneManifest:
    """One scene's manifest entry — the contract between storyboard and edit."""

    scene_id: str
    narration_segment: str | None = None
    start_frame: int = 0
    end_frame: int = 0
    claim_ids: list[str] = field(default_factory=list)
    visual_role: str = "establish_context"
    visual_class: str = "SCIENTIFIC_DIAGRAM"
    asset_ids: list[str] = field(default_factory=list)
    motion: MotionPlan | None = None
    transition_in: str = "cut"
    transition_out: str = "cut"
    music_cue: str | None = None
    disclosure_required: bool = False
    qc_profile: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["motion"] = self.motion.to_dict() if self.motion else None
        return d

    def validate(self) -> list[str]:
        """Return list of validation problems (empty = OK)."""
        problems: list[str] = []
        if self.visual_class not in VISUAL_CLASSES:
            problems.append(
                f"{self.scene_id}: invalid visual_class {self.visual_class!r}; "
                f"valid: {sorted(VISUAL_CLASSES)}"
            )
        if self.motion and self.motion.type not in MOTION_TYPES:
            problems.append(
                f"{self.scene_id}: invalid motion type {self.motion.type!r}; "
                f"valid: {sorted(MOTION_TYPES)}"
            )
        if self.end_frame <= self.start_frame and self.start_frame != 0:
            problems.append(
                f"{self.scene_id}: end_frame {self.end_frame} <= start_frame {self.start_frame}"
            )
        return problems


@dataclass
class StoryboardManifest:
    """Complete storyboard for one episode — ordered scene manifests."""

    version: str = "1.0"
    episode_id: str = ""
    fps_num: int = 30
    fps_den: int = 1
    audio_sample_rate: int = 48000
    timeline_source: str = ""
    scenes: list[SceneManifest] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "episode_id": self.episode_id,
            "fps": {"num": self.fps_num, "den": self.fps_den},
            "audio_sample_rate": self.audio_sample_rate,
            "timeline_source": self.timeline_source,
            "scenes": [s.to_dict() for s in self.scenes],
            "created_at": self.created_at,
        }

    def validate(self) -> list[str]:
        problems: list[str] = []
        seen_ids: set[str] = set()
        for s in self.scenes:
            problems.extend(s.validate())
            if s.scene_id in seen_ids:
                problems.append(f"duplicate scene_id: {s.scene_id}")
            seen_ids.add(s.scene_id)
        # Frames must be contiguous and non-overlapping.
        sorted_scenes = sorted(self.scenes, key=lambda s: s.start_frame)
        prev_end = 0
        for s in sorted_scenes:
            if s.start_frame < prev_end:
                problems.append(
                    f"{s.scene_id}: overlaps previous scene ending at {prev_end}"
                )
            prev_end = max(prev_end, s.end_frame)
        return problems


def frames_from_seconds(
    seconds: float, *, fps_num: int = 30, fps_den: int = 1
) -> int:
    """Convert seconds to frame index using rational timebase.

    No per-frame independent rounding — applies consistent rational PTS.
    """
    return int(round(seconds * fps_num / fps_den))


def seconds_from_frames(
    frames: int, *, fps_num: int = 30, fps_den: int = 1
) -> float:
    """Convert frame index to seconds using rational timebase."""
    return frames * fps_den / fps_num

