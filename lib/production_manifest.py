"""Production Manifest — unified interchange format between preproduction,
asset generation, audio sync, motion, and render stages.

The manifest is versioned and integrity-hashed so every downstream stage can
detect tampering or truncation.  All fields are JSON-serializable; no binary
data is embedded — only hashes, paths, and references.

Zero-cost: no generation, no credits, no network.  Pure data structures plus
validation helpers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CameraMoveParams:
    """Parameters for pan/zoom/parallax motion on a still image."""

    start_scale: float = 1.0
    end_scale: float = 1.12
    easing: str = "easeinout"
    direction: str = "in"  # "in" or "out"
    pan_x: float = 0.0
    pan_y: float = 0.0


@dataclass
class CaptionSpace:
    """Reserved on-screen space for editor-added captions/subtitles."""

    reserved: bool = True
    x: float = 0.0
    y: float = 0.66  # bottom third by default
    width: float = 1.0
    height: float = 0.30


@dataclass
class ManifestScene:
    """One scene entry in the production manifest."""

    scene_id: str
    asset_id: str
    script_section_id: str
    prompt: str
    expected_format: str
    duration_seconds: float
    timeline_position: float
    camera_move: str
    transition: str
    file_status: str  # "missing" | "stub" | "validated" | "corrupted" | "duplicate"
    qc_result: str  # "pass" | "fail" | "pending" | "human_review"
    negative_prompt: str = ""
    references: list[str] = field(default_factory=list)
    pan_zoom_params: CameraMoveParams | None = None
    parallax_layers: int = 1
    transition_duration: float = 0.5
    caption_space: CaptionSpace | None = None
    file_path: str | None = None
    file_sha256: str | None = None
    file_resolution: str | None = None
    qc_notes: str = ""
    character_id: str | None = None
    hero_moment: bool = False
    narrative_role: str = "establish_context"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.pan_zoom_params is not None:
            d["pan_zoom_params"] = asdict(self.pan_zoom_params)
        if self.caption_space is not None:
            d["caption_space"] = asdict(self.caption_space)
        return d


@dataclass
class AudioSegment:
    """One narrated audio segment synchronized to a scene."""

    segment_id: str
    scene_id: str
    text: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    word_timestamps: list[dict[str, Any]] = field(default_factory=list)
    issue: str = "ok"  # "ok" | "too_long" | "too_short"
    issue_threshold_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioSync:
    """Narration-to-scene synchronization block."""

    narration_manifest_id: str
    total_duration_seconds: float
    segments: list[AudioSegment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Timeline:
    """Render timeline specification."""

    total_duration_seconds: float
    fps: int
    resolution: str
    aspect_ratio: str = "16:9"
    cuts_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionManifest:
    """Complete production manifest for one project run."""

    version: str = "1.0"
    manifest_id: str = ""
    run_id: str = ""
    created_at: str = ""
    project: str = ""
    media_profile: str = "youtube_landscape"
    target_duration_seconds: float = 0.0
    scenes: list[ManifestScene] = field(default_factory=list)
    audio_sync: AudioSync | None = None
    timeline: Timeline | None = None
    status: str = "draft"  # draft | validated | ready_for_render | rendering | completed | failed
    missing_assets: list[str] = field(default_factory=list)
    integrity_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialization / integrity
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dict (includes integrity hash)."""
        return {
            "version": self.version,
            "manifest_id": self.manifest_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "project": self.project,
            "media_profile": self.media_profile,
            "target_duration_seconds": self.target_duration_seconds,
            "scenes": [s.to_dict() for s in self.scenes],
            "audio_sync": self.audio_sync.to_dict() if self.audio_sync else None,
            "timeline": self.timeline.to_dict() if self.timeline else None,
            "status": self.status,
            "missing_assets": list(self.missing_assets),
            "integrity_hash": self.integrity_hash,
            "metadata": dict(self.metadata),
        }

    def compute_integrity_hash(self) -> str:
        """Compute SHA-256 over the canonical (sorted-key) JSON serialization.

        The hash excludes the integrity_hash field itself so it can be
        recomputed after the field is populated.
        """
        data = self.to_dict()
        data.pop("integrity_hash", None)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def seal(self) -> None:
        """Compute and store the integrity hash."""
        self.integrity_hash = self.compute_integrity_hash()

    def verify_integrity(self) -> bool:
        """Return True iff the stored integrity hash matches recomputation."""
        if not self.integrity_hash:
            return False
        return self.integrity_hash == self.compute_integrity_hash()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_schema(self) -> None:
        """Validate the manifest against its JSON schema."""
        validate_artifact("production_manifest", self.to_dict())

    # ------------------------------------------------------------------
    # Scene helpers
    # ------------------------------------------------------------------

    def scene_by_id(self, scene_id: str) -> ManifestScene | None:
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        return None

    def add_or_replace_scene(self, scene: ManifestScene) -> None:
        """Insert or replace a scene by scene_id."""
        for i, existing in enumerate(self.scenes):
            if existing.scene_id == scene.scene_id:
                self.scenes[i] = scene
                return
        self.scenes.append(scene)

    def remove_scene(self, scene_id: str) -> bool:
        for i, existing in enumerate(self.scenes):
            if existing.scene_id == scene_id:
                self.scenes.pop(i)
                return True
        return False

    def missing_scene_ids(self) -> list[str]:
        """Return scene_ids whose file_status is missing/corrupted/duplicate."""
        return [
            s.scene_id
            for s in self.scenes
            if s.file_status in ("missing", "corrupted", "duplicate")
        ]

    def recompute_timeline(self) -> None:
        """Rebuild the timeline from scene positions and durations."""
        if not self.scenes:
            self.timeline = Timeline(
                total_duration_seconds=0.0,
                fps=30,
                resolution="1920x1080",
            )
            return
        sorted_scenes = sorted(self.scenes, key=lambda s: s.timeline_position)
        end_times = [
            s.timeline_position + s.duration_seconds for s in sorted_scenes
        ]
        total = max(end_times) if end_times else 0.0
        self.timeline = Timeline(
            total_duration_seconds=round(total, 3),
            fps=30,
            resolution="1920x1080",
            aspect_ratio="16:9",
            cuts_count=len(sorted_scenes),
        )
        self.missing_assets = self.missing_scene_ids()


# ---------------------------------------------------------------------------
# Factory: build a manifest from preproduction outputs
# ---------------------------------------------------------------------------


def build_manifest_from_preproduction(
    *,
    run_id: str,
    project: str,
    media_profile: str = "youtube_landscape",
    scene_plans: list[dict[str, Any]],
    prompt_packets: list[dict[str, Any]],
    quality_reports: dict[str, dict[str, Any]],
    visual_directives: dict[str, dict[str, Any]] | None = None,
    references_by_scene: dict[str, list[str]] | None = None,
    target_duration_seconds: float | None = None,
) -> ProductionManifest:
    """Construct a :class:`ProductionManifest` from preproduction outputs.

    Every scene starts with file_status="missing" (no media has been
    generated yet) and inherits its QC pass/fail from the quality report.
    """
    visual_directives = visual_directives or {}
    references_by_scene = references_by_scene or {}
    packets_by_id = {p.get("scene_id", ""): p for p in prompt_packets}
    qc_by_id = {q.get("scene_id", ""): q for q in quality_reports.values()}

    scenes: list[ManifestScene] = []
    for sp in scene_plans:
        sid = sp.get("scene_id", "unknown")
        packet = packets_by_id.get(sid, {})
        qc = qc_by_id.get(sid, {})
        directive = visual_directives.get(sid, {})

        pan_zoom = None
        pz = directive.get("pan_zoom_params") if directive else None
        if pz:
            pan_zoom = CameraMoveParams(
                start_scale=pz.get("start_scale", 1.0),
                end_scale=pz.get("end_scale", 1.12),
                easing=pz.get("easing", "easeinout"),
                direction=pz.get("direction", "in"),
                pan_x=pz.get("pan_x", 0.0),
                pan_y=pz.get("pan_y", 0.0),
            )

        caption_space = None
        cs = directive.get("caption_space") if directive else None
        if cs:
            caption_space = CaptionSpace(
                reserved=cs.get("reserved", True),
                x=cs.get("x", 0.0),
                y=cs.get("y", 0.66),
                width=cs.get("width", 1.0),
                height=cs.get("height", 0.30),
            )

        scenes.append(
            ManifestScene(
                scene_id=sid,
                asset_id=f"{run_id}-asset-{sid}",
                script_section_id=sp.get("script_section_id", ""),
                prompt=packet.get("main_prompt", ""),
                negative_prompt=packet.get("negative_prompt", ""),
                references=references_by_scene.get(sid, []),
                expected_format=packet.get("image_format", "1920x1080, ink illustration"),
                duration_seconds=sp.get("duration_seconds", 5.0),
                timeline_position=sp.get("timeline_position", 0.0),
                camera_move=directive.get("shot_size", "medium") if directive else "medium",
                transition=sp.get("transition_to_next", "cut"),
                transition_duration=sp.get("transition_duration", 0.5),
                file_status="missing",
                qc_result=qc.get("passed", False) and "pass" or "fail",
                qc_notes=(
                    qc.get("blocking_issues", [""])[0]
                    if qc.get("blocking_issues")
                    else ""
                ),
                pan_zoom_params=pan_zoom,
                parallax_layers=directive.get("parallax_layers", 1) if directive else 1,
                caption_space=caption_space,
                character_id=sp.get("character_id"),
                hero_moment=sp.get("hero_moment", False),
                narrative_role=sp.get("narrative_role", "establish_context"),
                metadata={"shot_purpose": sp.get("shot_purpose", "")},
            )
        )

    manifest = ProductionManifest(
        run_id=run_id,
        project=project,
        media_profile=media_profile,
        target_duration_seconds=target_duration_seconds or 0.0,
        scenes=scenes,
        status="draft",
    )
    manifest.recompute_timeline()
    manifest.seal()
    return manifest


def load_manifest(path: str | Path) -> ProductionManifest:
    """Load a manifest from disk and verify its integrity hash."""
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    # Rebuild typed objects from the raw dict
    scenes = [ManifestScene(**{**s, "pan_zoom_params": CameraMoveParams(**s["pan_zoom_params"]) if s.get("pan_zoom_params") else None, "caption_space": CaptionSpace(**s["caption_space"]) if s.get("caption_space") else None}) for s in data.get("scenes", [])]

    audio_sync = None
    if data.get("audio_sync"):
        as_data = data["audio_sync"]
        segments = [AudioSegment(**seg) for seg in as_data.get("segments", [])]
        audio_sync = AudioSync(
            narration_manifest_id=as_data.get("narration_manifest_id", ""),
            total_duration_seconds=as_data.get("total_duration_seconds", 0.0),
            segments=segments,
        )

    timeline = None
    if data.get("timeline"):
        timeline = Timeline(**data["timeline"])

    manifest = ProductionManifest(
        version=data.get("version", "1.0"),
        manifest_id=data.get("manifest_id", ""),
        run_id=data.get("run_id", ""),
        created_at=data.get("created_at", ""),
        project=data.get("project", ""),
        media_profile=data.get("media_profile", "youtube_landscape"),
        target_duration_seconds=data.get("target_duration_seconds", 0.0),
        scenes=scenes,
        audio_sync=audio_sync,
        timeline=timeline,
        status=data.get("status", "draft"),
        missing_assets=data.get("missing_assets", []),
        integrity_hash=data.get("integrity_hash"),
        metadata=data.get("metadata", {}),
    )

    # Verify integrity (hash was computed over the data without the hash field)
    stored_hash = manifest.integrity_hash
    if stored_hash:
        manifest.integrity_hash = None
        recomputed = manifest.compute_integrity_hash()
        manifest.integrity_hash = stored_hash
        if recomputed != stored_hash:
            raise ValueError(
                f"Manifest integrity check failed: stored {stored_hash}, "
                f"recomputed {recomputed}"
            )

    return manifest


def save_manifest(manifest: ProductionManifest, path: str | Path) -> None:
    """Save a manifest to disk, sealing its integrity hash first."""
    manifest.seal()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)
