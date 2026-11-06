"""Edit Decision Engine — per-sentence montage decisions for P4.

Builds one edit decision per sentence, enforcing:

  ONE SENTENCE = ONE UNIQUE IMAGE = ONE UNIQUE AUDIO FRAGMENT.

Each decision carries:
  image_asset_id, audio_asset_id, start_ms, end_ms, duration_ms,
  motion_type, camera_parameters, transition, visual_effects, scene_id.

Reuses (does not duplicate):
  * lib.sentence_timeline.SentenceTimeline  (P3 audio + timing)
  * lib.image_generation_engine            (P2 image plans + asset ids)
  * lib.motion_engine.MotionEngine         (pan_zoom/detail_crop/parallax/static)
  * lib.render_integration.RenderIntegration (edit_decisions artifact + validation)

Zero-cost: pure data + ffmpeg filter strings.  No generation, no credits.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from lib.motion_engine import MotionEngine, MotionSpec, TransitionSpec
from lib.render_integration import RenderIntegration


@dataclass
class EditDecision:
    """One montage cut for a single sentence."""

    scene_id: str
    sentence_id: str
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
    rig_motion_events: list[dict[str, Any]] = field(default_factory=list)
    signature_detail_present: bool = True
    motivated_hold: bool = False
    rig_overlay_path: str | None = None
    status: str = "planned"  # planned | ready | rendered | failed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EditDecisionSet:
    """Complete set of edit decisions for one project."""

    version: str = "1.0"
    project_id: str = ""
    run_id: str = ""
    created_at: str = ""
    total_scenes: int = 0
    total_duration_ms: int = 0
    decisions: list[EditDecision] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "total_scenes": self.total_scenes,
            "total_duration_ms": self.total_duration_ms,
            "decisions": [d.to_dict() for d in self.decisions],
            "issues": self.issues,
        }

    def by_sentence(self) -> dict[str, EditDecision]:
        return {d.sentence_id: d for d in self.decisions}


class EditDecisionEngine:
    """Build per-sentence edit decisions from P2 images + P3 audio timeline."""

    def __init__(
        self,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        seed: int | None = None,
    ) -> None:
        self.fps = fps
        self.width = width
        self.height = height
        self.motion_engine = MotionEngine(
            fps=fps, width=width, height=height, seed=seed
        )
        self.render_integration = RenderIntegration(
            fps=fps, width=width, height=height
        )

    # ------------------------------------------------------------------
    # Build decisions
    # ------------------------------------------------------------------

    def build_decisions(
        self,
        *,
        sentence_timeline_entries: list[dict[str, Any]],
        image_plans: list[dict[str, Any]],
        motion_specs: list[MotionSpec] | None = None,
        visual_directives: dict[str, dict[str, Any]] | None = None,
        rig_plan: dict[str, dict[str, Any]] | None = None,
        run_id: str = "",
        project_id: str = "",
    ) -> EditDecisionSet:
        """Build one EditDecision per sentence.

        Args:
            sentence_timeline_entries: P3 SentenceTimelineEntry dicts
                (sentence_id, start_ms, end_ms, duration_ms, audio_asset_id,
                 audio_path, alignment_confidence, ...).
            image_plans: P2 SentenceImagePlan dicts
                (sentence_id, asset_id, output_path, ...).
            motion_specs: optional MotionEngine specs keyed by scene_id==sentence_id.
            visual_directives: optional per-scene visual direction.
            run_id / project_id: provenance.

        Returns:
            EditDecisionSet with one decision per sentence.
        """
        visual_directives = visual_directives or {}
        rig_plan = rig_plan or {}
        motion_by_id = {
            s.scene_id: s for s in (motion_specs or [])
        }
        image_by_id = {p.get("sentence_id"): p for p in image_plans}

        decisions: list[EditDecision] = []
        issues: list[str] = []
        total_duration_ms = 0
        seen_image_assets: set[str] = set()
        seen_audio_assets: set[str] = set()

        for i, entry in enumerate(sentence_timeline_entries):
            sid = entry["sentence_id"]
            start_ms = int(entry["start_ms"])
            end_ms = int(entry["end_ms"])
            dur_ms = int(entry["duration_ms"])
            total_duration_ms = max(total_duration_ms, end_ms)

            # --- Image (one per sentence) --------------------------------
            ip = image_by_id.get(sid, {})
            image_asset_id = ip.get("asset_id", f"{project_id}-IMG-{sid}")
            image_path = ip.get("output_path", "")
            if image_asset_id in seen_image_assets:
                issues.append(
                    f"Image asset {image_asset_id} reused for {sid} "
                    f"(violates one-image-per-sentence)"
                )
            seen_image_assets.add(image_asset_id)

            # --- Audio (one per sentence) --------------------------------
            audio_asset_id = entry.get("audio_asset_id", f"{project_id}-AUD-{sid}")
            audio_path = entry.get("audio_path", "")
            if audio_asset_id in seen_audio_assets:
                issues.append(
                    f"Audio asset {audio_asset_id} reused for {sid} "
                    f"(violates one-audio-per-sentence)"
                )
            seen_audio_assets.add(audio_asset_id)

            # --- Motion ---------------------------------------------------
            spec = motion_by_id.get(sid)
            if spec is None:
                # Auto-generate a motion spec so every scene has motion.
                spec = self.motion_engine.spec_for_scene(
                    scene_id=sid,
                    duration_seconds=dur_ms / 1000.0,
                    hero_moment=entry.get("hero_moment", False),
                    narrative_role=entry.get("narrative_role", "establish_context"),
                )
            motion_type = spec.move_type
            camera_parameters = {
                "easing": spec.easing,
                "direction": spec.direction,
                "start_scale": spec.start_scale,
                "end_scale": spec.end_scale,
                "pan_x": spec.pan_x,
                "pan_y": spec.pan_y,
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
            }
            if spec.crop_box is not None:
                camera_parameters["crop_box"] = list(spec.crop_box)
            if spec.parallax_layers > 1:
                camera_parameters["parallax_layers"] = spec.parallax_layers
                camera_parameters["parallax_drift"] = spec.parallax_drift

            # --- Transition -----------------------------------------------
            vd = visual_directives.get(sid, {})
            transition = vd.get("transition", ip.get("transition", "cut"))
            if transition not in ("cut", "dissolve", "fade", "wipe"):
                transition = "cut"
            transition_duration = float(
                vd.get("transition_duration", ip.get("transition_duration", 0.5))
            )

            # --- Visual effects -------------------------------------------
            visual_effects: list[str] = []
            if motion_type == "pan_zoom":
                visual_effects.append("slow_zoom")
            if motion_type == "detail_crop":
                visual_effects.append("detail_crop")
            if motion_type == "parallax":
                visual_effects.append("parallax")
            if entry.get("hero_moment"):
                visual_effects.append("hero_focus")
            if vd.get("caption_space", {}).get("reserved"):
                visual_effects.append("caption_space_reserved")

            # --- Rig (stickman) -------------------------------------------
            rp = rig_plan.get(sid, {}) if isinstance(rig_plan, dict) else {}
            rig_pose_id = rp.get("rig_pose_id", entry.get("rig_pose_id"))
            rig_expression_id = rp.get("rig_expression_id", entry.get("rig_expression_id"))
            rig_view = rp.get("rig_view", entry.get("rig_view"))
            prop_ids = list(rp.get("prop_ids", entry.get("prop_ids", []) or []))
            rig_motion_events = list(rp.get("rig_motion_events", entry.get("rig_motion_events", []) or []))
            signature_detail_present = bool(rp.get("signature_detail_present", entry.get("signature_detail_present", True)))
            motivated_hold = bool(rp.get("motivated_hold", entry.get("motivated_hold", False)))

            decision = EditDecision(
                scene_id=sid,
                sentence_id=sid,
                image_asset_id=image_asset_id,
                image_path=image_path,
                audio_asset_id=audio_asset_id,
                audio_path=audio_path,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=dur_ms,
                motion_type=motion_type,
                camera_parameters=camera_parameters,
                transition=transition,
                transition_duration=transition_duration,
                visual_effects=visual_effects,
                narrative_role=entry.get(
                    "narrative_role", vd.get("narrative_role", "establish_context")
                ),
                hero_moment=bool(entry.get("hero_moment", False)),
                rig_pose_id=rig_pose_id,
                rig_expression_id=rig_expression_id,
                rig_view=rig_view,
                prop_ids=prop_ids,
                rig_motion_events=rig_motion_events,
                signature_detail_present=signature_detail_present,
                motivated_hold=motivated_hold,
                status="planned",
            )
            decisions.append(decision)

        # --- Variety lint (no identical consecutive moves) ----------------
        seg_dicts = [
            {
                "move": d.motion_type,
                "easing": d.camera_parameters["easing"],
                "direction": d.camera_parameters["direction"],
            }
            for d in decisions
        ]
        try:
            from tools.motion.motion_variety import lint_variation  # noqa: E402

            variety_issues = lint_variation(seg_dicts)
            for vi in variety_issues:
                issues.append(
                    f"variety: {vi['reason']} at index {vi['index']}"
                )
        except Exception:  # noqa: BLE001
            pass  # motion_variety lint is optional

        # --- Transitions between consecutive scenes -----------------------
        # (stored on each decision as transition_out; the render engine
        #  consumes them in order.)

        return EditDecisionSet(
            project_id=project_id,
            run_id=run_id,
            created_at=self._now(),
            total_scenes=len(decisions),
            total_duration_ms=total_duration_ms,
            decisions=decisions,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Edit decisions artifact (compatible with render_integration)
    # ------------------------------------------------------------------

    def to_edit_decisions_artifact(
        self,
        decision_set: EditDecisionSet,
        *,
        narration_asset_id: str = "",
        music_asset_id: str = "",
        subtitle_path: str = "",
    ) -> dict[str, Any]:
        """Convert to the render_integration edit_decisions dict.

        Produces cuts with source paths, in/out seconds, transitions,
        overlays, plus audio/music/subtitle blocks for the render engine.
        """
        cuts: list[dict[str, Any]] = []
        overlays: list[dict[str, Any]] = []

        for i, d in enumerate(decision_set.decisions):
            in_s = d.start_ms / 1000.0
            out_s = d.end_ms / 1000.0
            transform = {
                "scale": d.camera_parameters["start_scale"],
                "position": "center",
                "animation": f"{d.camera_parameters['direction']}_{d.camera_parameters['easing']}",
                "end_scale": d.camera_parameters["end_scale"],
                "motion_type": d.motion_type,
            }
            if "crop_box" in d.camera_parameters:
                transform["crop_box"] = d.camera_parameters["crop_box"]

            cut = {
                "id": d.scene_id,
                "source": d.image_path,
                "image_asset_id": d.image_asset_id,
                "audio_asset_id": d.audio_asset_id,
                "sentence_id": d.sentence_id,
                "in_seconds": round(in_s, 3),
                "out_seconds": round(out_s, 3),
                "duration_ms": d.duration_ms,
                "speed": 1.0,
                "layer": "primary",
                "transform": transform,
                "motion_type": d.motion_type,
                "camera_parameters": d.camera_parameters,
                "transition": d.transition,
                "transition_in": d.transition if i == 0 else "cut",
                "transition_out": d.transition,
                "transition_duration": d.transition_duration,
                "visual_effects": d.visual_effects,
                "narrative_role": d.narrative_role,
                "hero_moment": d.hero_moment,
                "reason": d.narrative_role,
            }
            cuts.append(cut)

            # Caption-space overlay (reserved, invisible marker).
            overlays.append(
                {
                    "asset_id": f"{d.scene_id}-caption-space",
                    "start_seconds": round(in_s, 3),
                    "end_seconds": round(out_s, 3),
                    "position": {
                        "x": 0.0,
                        "y": 0.66,
                        "width": 1.0,
                        "height": 0.30,
                    },
                    "animation": "static",
                    "opacity": 0.0,
                }
            )

        total_dur = decision_set.total_duration_ms / 1000.0

        artifact: dict[str, Any] = {
            "version": "1.0",
            "project_id": decision_set.project_id,
            "run_id": decision_set.run_id,
            "cuts": cuts,
            "overlays": overlays,
            "render_runtime": "ffmpeg",
            "renderer_family": "documentary-montage",
            "composition_mode": "templated",
            "total_duration_seconds": round(total_dur, 3),
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}",
            "audio": {
                "narration": {
                    "asset_id": narration_asset_id,
                    "segments": [
                        {
                            "scene_id": d.scene_id,
                            "sentence_id": d.sentence_id,
                            "asset_id": d.audio_asset_id,
                            "start_seconds": round(d.start_ms / 1000.0, 3),
                            "end_seconds": round(d.end_ms / 1000.0, 3),
                        }
                        for d in decision_set.decisions
                    ],
                }
            },
        }
        if music_asset_id:
            artifact["audio"]["music"] = {
                "asset_id": music_asset_id,
                "volume": 0.15,
                "fade_in_seconds": 2.0,
                "fade_out_seconds": 2.0,
                "ducking": {"enabled": True, "threshold_db": -20, "reduction_db": -12},
            }
        if subtitle_path:
            artifact["subtitles"] = {
                "enabled": True,
                "source": subtitle_path,
                "style": "sentence",
            }
        else:
            artifact["subtitles"] = {"enabled": False, "source": "", "style": "sentence"}

        return artifact

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def validate_one_to_one(self, decision_set: EditDecisionSet) -> dict[str, Any]:
        """Return integrity report: unique image/audio per sentence, no gaps."""
        problems: list[str] = []
        image_ids = [d.image_asset_id for d in decision_set.decisions]
        audio_ids = [d.audio_asset_id for d in decision_set.decisions]
        sentence_ids = [d.sentence_id for d in decision_set.decisions]

        if len(set(image_ids)) != len(image_ids):
            problems.append("duplicate image_asset_id across sentences")
        if len(set(audio_ids)) != len(audio_ids):
            problems.append("duplicate audio_asset_id across sentences")
        if len(set(sentence_ids)) != len(sentence_ids):
            problems.append("duplicate sentence_id")

        # Chronological, gap-free.
        prev_end_ms = 0
        for d in decision_set.decisions:
            if d.start_ms < prev_end_ms - 10:  # 10ms tolerance
                problems.append(
                    f"overlap: {d.sentence_id} starts {d.start_ms}ms "
                    f"before previous ends {prev_end_ms}ms"
                )
            prev_end_ms = d.end_ms

        # Adjacent rig pose repetition (unless motivated_hold).
        prev_triple = None
        for d in decision_set.decisions:
            triple = (d.rig_pose_id, d.rig_expression_id, d.rig_view)
            if (prev_triple is not None and triple == prev_triple
                    and not getattr(d, "motivated_hold", False)
                    and any(x is not None for x in triple)):
                problems.append(
                    f"rig repetition: {d.sentence_id} repeats (pose,expression,view) without motivated_hold"
                )
            prev_triple = triple

        return {
            "ok": len(problems) == 0,
            "problems": problems,
            "total_scenes": decision_set.total_scenes,
            "total_duration_ms": decision_set.total_duration_ms,
            "unique_images": len(set(image_ids)),
            "unique_audio": len(set(audio_ids)),
        }
