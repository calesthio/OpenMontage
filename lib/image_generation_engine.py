"""Image Generation Engine — full-image pipeline for OpenMontage Factory.

Architecture (no module is duplicated; existing modules are reused):

  * Orchestrator          — this class; coordinates the pipeline
  * Provider Adapter      — lib.gflow_provider.GflowProvider (gflow-cli)
  * Prompt Generation     — lib.prompt_engineer.PromptEngineer (reused)
  * Character Reference   — lib.character_consistency_manager (reused)
  * Visual Direction      — lib.visual_director.VisualDirector (reused)
  * Batch Scheduler       — lib.batch_scheduler.BatchScheduler
  * Image QC              — lib.quality_control.QualityControl + lib.image_uniqueness
  * Asset Registry        — lib.asset_registry.AssetRegistry
  * Recovery Manager      — lib.recovery_manager.RecoveryManager
  * Sentence input        — lib.sentence_segmenter.SentenceSegmenter (reused)

Rule enforced: ONE SENTENCE = ONE UNIQUE PROMPT = ONE UNIQUE IMAGE.
One image is never used for two sentences.

Default mode is dry-run / mock: no gflow call, no credit spend, no real
generation.  Execution of credit-bearing work requires explicit owner
approval and passes through the zero-cost gate in GflowWrapper.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.asset_registry import AssetRegistry, AssetRecord
from lib.batch_scheduler import BatchPrompt, BatchScheduler
from lib.character_consistency_manager import (
    CharacterConsistencyManager,
)
from lib.gflow_provider import GflowProvider, ProviderImageRequest
from lib.gflow_wrapper import GflowWrapper, ZeroCostViolation
from lib.image_uniqueness import (
    DUPLICATE_THRESHOLD,
    build_revision_prompt,
    check_uniqueness,
    compute_ahash,
)
from lib.prompt_engineer import PromptEngineer, ScenePromptPacket
from lib.quality_control import QualityControl
from lib.recovery_manager import RecoveryManager
from lib.sentence_segmenter import Sentence, SentenceSegmenter
from lib.visual_director import VisualDirector

DEFAULT_MODEL = "nano2"
DEFAULT_ASPECT = "16:9"
DEFAULT_VISUAL_STYLE = (
    "bold ink illustration, crisp black outlines, flat expressive colour fills, "
    "scientific-documentary composition, expressive lighting"
)


@dataclass
class SentenceImagePlan:
    """Plan for turning one sentence into one image."""

    sentence_id: str
    sentence_text: str
    prompt_id: str
    asset_id: str
    job_id: str | None = None
    prompt: str = ""
    negative_prompt: str = ""
    output_path: str = ""
    model: str = DEFAULT_MODEL
    aspect_ratio: str = DEFAULT_ASPECT
    reference_entity: str | None = None
    generation_params: dict = field(default_factory=dict)
    state: str = "planned"  # planned | ready_for_approval | generated | qc_passed | qc_failed | duplicate | failed | blocked
    qc_result: dict | None = None
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class GenerationPlan:
    """Full plan for all sentences of one project."""

    project_id: str
    version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sentences: list[SentenceImagePlan] = field(default_factory=list)
    character_id: str | None = None
    total: int = 0

    @property
    def by_id(self) -> dict[str, SentenceImagePlan]:
        return {p.sentence_id: p for p in self.sentences}


@dataclass
class GenerationResult:
    """Outcome of running (or dry-running) the engine."""

    project_id: str
    total_sentences: int
    planned: int
    ready_for_approval: int
    generated: int
    qc_passed: int
    qc_failed: int
    failed: int
    duplicates: int
    blocked: int
    plans: list[SentenceImagePlan] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "total_sentences": self.total_sentences,
            "planned": self.planned,
            "ready_for_approval": self.ready_for_approval,
            "generated": self.generated,
            "qc_passed": self.qc_passed,
            "qc_failed": self.qc_failed,
            "failed": self.failed,
            "duplicates": self.duplicates,
            "blocked": self.blocked,
            "errors": self.errors,
        }


class ImageGenerationEngine:
    """Orchestrate sentence -> prompt -> job -> image -> QC -> asset."""

    def __init__(
        self,
        project_id: str,
        *,
        base_dir: str | Path = "projects",
        visual_style: str = DEFAULT_VISUAL_STYLE,
        mock: bool = True,
        max_attempts: int = 3,
        uniqueness_threshold: int = DUPLICATE_THRESHOLD,
    ) -> None:
        self.project_id = project_id
        self.mock = mock
        self.max_attempts = max_attempts
        self.uniqueness_threshold = uniqueness_threshold

        self.registry = AssetRegistry(project_id, base_dir=base_dir)
        self.recovery = RecoveryManager(self.registry)
        self.scheduler = BatchScheduler()
        self.provider = GflowProvider()
        self.wrapper: GflowWrapper = self.provider.wrapper
        self.quality_control = QualityControl()
        self.prompt_engineer = PromptEngineer(visual_style=visual_style)
        self.visual_director = VisualDirector(visual_style=visual_style)
        self.character_manager = CharacterConsistencyManager()
        self.segmenter = SentenceSegmenter()

        self.plan: GenerationPlan | None = None
        self._generated_image_paths: list[str] = []  # for uniqueness across run

    # ------------------------------------------------------------------
    # Character setup
    # ------------------------------------------------------------------

    def register_hero_character(
        self,
        *,
        character_id: str,
        display_name: str,
        role: str,
        body_type: str,
        distinguishing_features: list[str],
        clothing_notes: str,
        color_palette: list[str] | None = None,
        reference_image_path: str | None = None,
    ) -> None:
        """Register the main hero character once for the whole project.

        The character is referenced (via --reference-entity) only in scenes
        that require them — never placed in every image.
        """
        self.character_manager.register_character(
            character_id=character_id,
            display_name=display_name,
            role=role,
            body_type=body_type,
            distinguishing_features=list(distinguishing_features),
            clothing_notes=clothing_notes,
            color_palette=list(color_palette or []),
        )
        if reference_image_path:
            self.character_manager.add_reference(
                reference_id=f"{character_id}-ref-1",
                character_id=character_id,
                reference_type="image",
                source_path=reference_image_path,
                description="Approved master reference for the hero character",
                captured_features=list(distinguishing_features),
            )
        # Remember as the project's hero so scene plans can opt in.
        self._hero_character_id = character_id

    # ------------------------------------------------------------------
    # Pipeline: build plan (zero-cost; stops at READY_FOR_APPROVAL)
    # ------------------------------------------------------------------

    def build_plan(
        self,
        *,
        sentences: list[Sentence],
        scene_plans: list[dict[str, Any]],
        visual_directives: dict[str, dict[str, Any]] | None = None,
        character_map: dict[str, str] | None = None,
        reference_entity: str | None = None,
        output_root: str | Path = "projects",
    ) -> GenerationPlan:
        """Build the complete generation plan for *sentences*.

        For each sentence:
          1. build a visual prompt (PromptEngineer, with story + neighbour context)
          2. register an asset (AssetRegistry, one image per sentence)
          3. create a Flow Job held at READY_FOR_APPROVAL (GflowProvider)

        No credits are spent.  Real generation waits for owner approval.
        """
        visual_directives = visual_directives or {}
        character_map = character_map or {}

        # Build scene lookup by sentence_id (scene_plans carry scene_id).
        scene_by_sentence: dict[str, dict[str, Any]] = {}
        for sp in scene_plans:
            sid = sp.get("sentence_id") or sp.get("scene_id", "")
            scene_by_sentence[sid] = sp

        all_descriptions = {
            sp.get("sentence_id") or sp.get("scene_id", f"s{i}"): sp.get(
                "visual_idea", ""
            )
            for i, sp in enumerate(scene_plans)
        }
        all_compositions = {
            sp.get("sentence_id") or sp.get("scene_id", f"s{i}"): sp.get(
                "composition", ""
            )
            for i, sp in enumerate(scene_plans)
        }

        plans: list[SentenceImagePlan] = []
        root = Path(output_root) / self.project_id
        assets_dir = root / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        prompt_packets_by_scene: dict[str, dict[str, Any]] = {}

        for sentence in sentences:
            sid = sentence.sentence_id
            scene = scene_by_sentence.get(sid, {})
            visual_idea = scene.get("visual_idea", sentence.text)

            # --- Prompt generation (PromptEngineer) ----------------------
            char_id = character_map.get(sid)
            anat = (
                self.character_manager.characters.get(char_id).__dict__
                if char_id and char_id in self.character_manager.characters
                else {}
            )
            refs: list[str] = []
            if char_id and char_id in self.character_manager.references:
                refs = [
                    r.source_path or r.reference_id
                    for r in self.character_manager.references[char_id]
                ]

            packet = self.prompt_engineer.build_packet(
                scene_id=sid,
                scene_plan=scene,
                visual_directive=visual_directives.get(sid, {}),
                character_anatomy=anat,
                references=refs,
                generation_params={
                    "model": DEFAULT_MODEL,
                    "count": 1,
                    "aspect_ratio": DEFAULT_ASPECT,
                },
            )
            prompt_packets_by_scene[sid] = asdict(packet)

            # Use the single hero reference entity for scenes that need the character.
            ref_entity = None
            if char_id == getattr(self, "_hero_character_id", None) and reference_entity:
                ref_entity = reference_entity

            output_path = str(assets_dir / f"{sid}.png")
            prompt_id = f"{self.project_id}-PRT-{sid}"
            asset_id = f"{self.project_id}-AST-{sid}"

            plan = SentenceImagePlan(
                sentence_id=sid,
                sentence_text=sentence.text,
                prompt_id=prompt_id,
                asset_id=asset_id,
                prompt=packet.main_prompt,
                negative_prompt=packet.negative_prompt,
                output_path=output_path,
                model=DEFAULT_MODEL,
                aspect_ratio=DEFAULT_ASPECT,
                reference_entity=ref_entity,
                generation_params=dict(packet.generation_params),
                state="planned",
            )
            plans.append(plan)

            # --- Register asset (one image per sentence) -----------------
            self.registry.register_asset(
                sentence_id=sid,
                prompt_id=prompt_id,
                source_prompt=packet.main_prompt,
                model=DEFAULT_MODEL,
                aspect_ratio=DEFAULT_ASPECT,
                references=[ref_entity] if ref_entity else [],
                generation_params=dict(packet.generation_params),
                job_id=None,
                file_path=output_path,
                status="planned",
            )

            # --- Plan flow job (READY_FOR_APPROVAL; no spend) -------------
            req = ProviderImageRequest(
                sentence_id=sid,
                project_id=self.project_id,
                prompt=packet.main_prompt,
                prompt_id=prompt_id,
                asset_id=asset_id,
                output_path=output_path,
                aspect_ratio=DEFAULT_ASPECT,
                model=DEFAULT_MODEL,
                reference_entity=ref_entity,
                generation_params=dict(packet.generation_params),
            )
            prov_result = self.provider.plan_image(req=req)
            plan.job_id = prov_result.job_id
            plan.state = prov_result.state  # READY_FOR_APPROVAL

        self.plan = GenerationPlan(
            project_id=self.project_id,
            sentences=plans,
            character_id=getattr(self, "_hero_character_id", None),
            total=len(plans),
        )

        # Visual direction variety report (reused, informational).
        vd_report = self.visual_director.direct(
            scenes=[sp for sp in scene_plans],
            characters=list(character_map.values()),
        )
        self._visual_direction_report = self.visual_director.to_dict(vd_report)

        return self.plan

    def load_plan(self) -> GenerationPlan | None:
        """Reconstruct a GenerationPlan from the registry (for restart/resume).

        Reads existing AssetRecord entries and rebuilds SentenceImagePlan
        objects so a new engine instance can resume without recreating
        Flow Jobs.
        """
        if not self.registry._assets:
            return None
        plans: list[SentenceImagePlan] = []
        for rec in self.registry.list_assets():
            plans.append(
                SentenceImagePlan(
                    sentence_id=rec.sentence_id,
                    sentence_text=rec.source_prompt,
                    prompt_id=rec.prompt_id,
                    asset_id=rec.asset_id,
                    job_id=rec.job_id,
                    prompt=rec.source_prompt,
                    negative_prompt="",
                    output_path=rec.file_path,
                    model=rec.model,
                    aspect_ratio=rec.aspect_ratio,
                    reference_entity=(
                        rec.references[0] if rec.references else None
                    ),
                    generation_params=dict(rec.generation_params or {}),
                    state=rec.status,
                    qc_result=rec.qc_result,
                    error=(
                        rec.generation_params.get("last_error")
                        if rec.generation_params
                        else None
                    ),
                )
            )
        self.plan = GenerationPlan(
            project_id=self.project_id,
            sentences=plans,
            character_id=getattr(self, "_hero_character_id", None),
            total=len(plans),
        )
        return self.plan

    # ------------------------------------------------------------------
    # Execution (credit-bearing; only APPROVED jobs; mock by default)
    # ------------------------------------------------------------------

    def execute_approved(
        self,
        *,
        user_approved: bool = False,
        cost_usd: float | None = None,
    ) -> GenerationResult:
        """Execute all READY_FOR_APPROVAL / APPROVED jobs.

        In mock mode (default) no gflow call is made; placeholder results are
        recorded so QC and the asset registry can be exercised end-to-end
        without spending credits.

        In real mode each job must be APPROVED by the owner first and pass
        the zero-cost gate before gflow-cli is invoked.
        """
        if self.plan is None:
            raise RuntimeError("build_plan must be called before execute_approved")

        result = GenerationResult(
            project_id=self.project_id,
            total_sentences=len(self.plan.sentences),
            planned=0,
            ready_for_approval=0,
            generated=0,
            qc_passed=0,
            qc_failed=0,
            failed=0,
            duplicates=0,
            blocked=0,
        )

        for plan in self.plan.sentences:
            result.planned += 1
            if plan.state in ("READY_FOR_APPROVAL", "APPROVED"):
                result.ready_for_approval += 1

            if self.mock:
                # --- Mock generation (zero-cost, no gflow) ----------------
                plan.attempts += 1
                self._mock_generate(plan)
                result.generated += 1
            else:
                # --- Real execution (requires APPROVED + zero-cost gate) ---
                if plan.state != "APPROVED":
                    plan.state = "blocked"
                    plan.error = "not APPROVED — owner gate"
                    result.blocked += 1
                    result.errors.append(f"{plan.sentence_id}: {plan.error}")
                    continue
                try:
                    prov = self.provider.execute_image(
                        job_id=plan.job_id,
                        user_approved=True,
                        cost_usd=cost_usd,
                    )
                    if prov.state in ("COMPLETED",) and prov.gflow_result:
                        plan.state = "generated"
                        plan.attempts += 1
                        self.registry.record_generation(
                            sentence_id=plan.sentence_id,
                            file_path=plan.output_path,
                            gflow_result=prov.gflow_result.to_dict(),
                        )
                        result.generated += 1
                    else:
                        plan.state = "failed"
                        plan.error = prov.error or "generation failed"
                        self.registry.record_failure(
                            sentence_id=plan.sentence_id, error=plan.error
                        )
                        result.failed += 1
                        result.errors.append(f"{plan.sentence_id}: {plan.error}")
                except ZeroCostViolation as exc:
                    plan.state = "blocked"
                    plan.error = str(exc)
                    result.blocked += 1
                    result.errors.append(f"{plan.sentence_id}: {plan.error}")

        # --- QC pass over everything generated -----------------------------
        self._run_qc(result)

        # --- Uniqueness / duplicate detection ------------------------------
        self._check_duplicates(result)

        return result

    # ------------------------------------------------------------------
    # Resume / recovery
    # ------------------------------------------------------------------

    def resume(self) -> dict[str, list[str]]:
        """Return sentences to process after a restart (skip completed)."""
        if self.plan is None:
            raise RuntimeError("build_plan must be called before resume")
        all_ids = [p.sentence_id for p in self.plan.sentences]
        return self.recovery.sentences_to_process(all_ids)

    def snapshot_recovery(self) -> None:
        self.recovery.save(self.recovery.snapshot())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mock_generate(self, plan: SentenceImagePlan) -> None:
        """Simulate a successful generation without calling gflow.

        Writes a small, sentence-specific PNG so file-existence / sha256 /
        QC checks can run.  Clearly marked as mock content.  Images vary by
        sentence so aHash uniqueness is meaningful.
        """
        from PIL import Image, ImageDraw

        p = Path(plan.output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Deterministic, structurally varied pattern per sentence.
        seed = sum(ord(c) for c in plan.sentence_text) % 256
        img = Image.new("RGB", (1920, 1080), color=(seed, 128, 200 - seed))
        draw = ImageDraw.Draw(img)
        # Outer frame
        draw.rectangle(
            [0, 0, 1919, 1079],
            outline=((seed * 3) % 256, (seed * 5) % 256, (seed * 7) % 256),
            width=10,
        )
        # Content: variable number of shapes at seed-dependent positions.
        n_boxes = 2 + (seed % 6)
        for i in range(n_boxes):
            x0 = (seed * 17 + i * 313) % 1500
            y0 = (seed * 23 + i * 211) % 700
            x1 = min(x0 + 150 + (seed % 200), 1850)
            y1 = min(y0 + 150 + (seed % 200), 1000)
            shape = i % 3
            if shape == 0:
                draw.rectangle(
                    [x0, y0, x1, y1],
                    outline=((seed + 40 * i) % 256, (seed + 80 * i) % 256,
                             (seed + 120 * i) % 256),
                    width=5,
                )
            elif shape == 1:
                draw.ellipse(
                    [x0, y0, x1, y1],
                    outline=((seed + 60 * i) % 256, (seed + 100 * i) % 256,
                             (seed + 140 * i) % 256),
                    width=5,
                )
            else:
                draw.line(
                    [x0, y0, x1, y1],
                    fill=((seed + 80 * i) % 256, (seed + 120 * i) % 256,
                          (seed + 160 * i) % 256),
                    width=6,
                )
        img.save(p)
        plan.state = "generated"
        plan.attempts += 1
        self.registry.record_generation(
            sentence_id=plan.sentence_id,
            file_path=plan.output_path,
            gflow_result={
                "media_id": f"mock-{plan.sentence_id}",
                "output_path": plan.output_path,
                "width": 1920,
                "height": 1080,
                "sha256": self._sha256_file(p),
                "bytes": p.stat().st_size,
                "mock": True,
            },
        )
        self._generated_image_paths.append(plan.output_path)

    def _run_qc(self, result: GenerationResult) -> None:
        """Run Quality Control + image-uniqueness over generated assets."""
        script_excerpts = {p.sentence_id: p.sentence_text for p in self.plan.sentences}
        character_map: dict[str, str] = {}
        for p in self.plan.sentences:
            if p.reference_entity:
                character_map[p.sentence_id] = getattr(
                    self, "_hero_character_id", ""
                )

        all_descriptions = {
            p.sentence_id: p.sentence_text for p in self.plan.sentences
        }
        all_compositions = {
            p.sentence_id: p.generation_params.get(
                "composition_description", ""
            )
            for p in self.plan.sentences
        }

        prompt_packets = {
            p.sentence_id: {
                "main_prompt": p.prompt,
                "negative_prompt": p.negative_prompt,
                "image_format": "1920x1080, ink illustration",
                "aspect_ratio": p.aspect_ratio,
                "generation_params": p.generation_params,
            }
            for p in self.plan.sentences
        }

        char_anatomy_by_id: dict[str, dict[str, Any]] = {}
        hero_id = getattr(self, "_hero_character_id", None)
        if hero_id and hero_id in self.character_manager.characters:
            char_anatomy_by_id[hero_id] = (
                self.character_manager.characters[hero_id].__dict__
            )

        qc_report = self.quality_control.check_batch(
            scenes=[
                {
                    "scene_id": p.sentence_id,
                    "visual_idea": p.sentence_text,
                    "composition": p.generation_params.get(
                        "composition_description", ""
                    ),
                    "aspect_ratio": p.aspect_ratio,
                }
                for p in self.plan.sentences
            ],
            script_excerpts=script_excerpts,
            character_map=character_map,
            character_anatomy_by_id=char_anatomy_by_id,
            prompt_packets_by_scene=prompt_packets,
        )

        # Image QC: file exists, 16:9, resolution, decodeable.
        for p in self.plan.sentences:
            qc = self._image_qc(p)
            # Merge structural QC + image QC.
            structural = qc_report.reports.get(p.sentence_id)
            merged_passed = qc["passed"] and (structural.passed if structural else True)
            merged_score = round((qc["score"] + (structural.overall_score if structural else 1.0)) / 2, 2)
            merged_blocking = list(qc["blocking"]) + (structural.blocking_issues if structural else [])

            p.qc_result = {
                "sentence_id": p.sentence_id,
                "passed": merged_passed,
                "score": merged_score,
                "blocking_issues": merged_blocking,
                "image_checks": qc,
            }
            self.registry.record_qc(
                sentence_id=p.sentence_id,
                qc_result=p.qc_result,
            )

            if merged_passed:
                p.state = "qc_passed"
                result.qc_passed += 1
            else:
                p.state = "qc_failed"
                result.qc_failed += 1
                result.errors.append(f"{p.sentence_id}: QC failed — {merged_blocking}")

    def _image_qc(self, plan: SentenceImagePlan) -> dict[str, Any]:
        """Per-image checks: file exists, decodable, 16:9, resolution."""
        blocking: list[str] = []
        score = 1.0
        checks: dict[str, Any] = {}

        checks["file_exists"] = False
        if not plan.output_path or not Path(plan.output_path).exists():
            blocking.append(f"image file missing: {plan.output_path}")
            score = 0.0
        else:
            checks["file_exists"] = True
            try:
                from PIL import Image

                with Image.open(plan.output_path) as img:
                    w, h = img.size
                    checks["width"] = w
                    checks["height"] = h
                    checks["decodable"] = True
                    # 16:9 check (allow small rounding)
                    ratio = w / h if h else 0
                    checks["aspect_16_9"] = abs(ratio - 16 / 9) < 0.02
                    checks["resolution_ok"] = w >= 1280 and h >= 720
                    if not checks["aspect_16_9"]:
                        blocking.append(f"aspect ratio {ratio:.3f} is not 16:9")
                        score -= 0.4
                    if not checks["resolution_ok"]:
                        blocking.append(f"resolution {w}x{h} below 720p")
                        score -= 0.3
            except Exception as exc:  # noqa: BLE001
                checks["decodable"] = False
                blocking.append(f"image not decodable: {exc}")
                score = 0.0

        checks["prompt_non_empty"] = bool(plan.prompt.strip())
        if not checks["prompt_non_empty"]:
            blocking.append("empty prompt")
            score -= 0.2

        return {"passed": len(blocking) == 0, "score": round(max(0.0, score), 2),
                "blocking": blocking, "checks": checks}

    def _check_duplicates(self, result: GenerationResult) -> None:
        """Perform aHash near-duplicate detection over generated images."""
        paths = [p.output_path for p in self.plan.sentences if p.output_path and Path(p.output_path).exists()]
        if not paths:
            return
        report = check_uniqueness(paths, threshold=self.uniqueness_threshold)
        for dup_group in report.duplicate_groups:
            # Mark all but the first as duplicates (candidate for re-roll).
            for dup_path in dup_group[1:]:
                for p in self.plan.sentences:
                    if p.output_path == dup_path:
                        p.state = "duplicate"
                        p.qc_result = p.qc_result or {}
                        p.qc_result["duplicate_of"] = dup_group[0]
                        p.qc_result["blocking_issues"] = list(
                            p.qc_result.get("blocking_issues", [])
                        ) + [f"near-duplicate of {dup_group[0]}"]
                        result.duplicates += 1
                        result.errors.append(f"{p.sentence_id}: near-duplicate image")
                        break

    @staticmethod
    def _sha256_file(path: Path) -> str | None:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def integrity_report(self) -> dict[str, Any]:
        return self.registry.integrity_check()

    def to_dict(self) -> dict[str, Any]:
        if self.plan is None:
            return {"project_id": self.project_id, "plan": None}
        return {
            "project_id": self.project_id,
            "total": self.plan.total,
            "character_id": self.plan.character_id,
            "sentences": [asdict(p) for p in self.plan.sentences],
            "registry": self.registry.integrity_check(),
        }
