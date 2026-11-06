"""Quality Control — pre-flight checks before a scene is queued for Flow.

Every check is structural and local.  No claim of scientific authority is
made: scientific claims are flagged for human review, not certified.

All checks are zero-cost: no model calls, no generation, no credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QCResult:
    """Result of one quality criterion."""

    criterion: str
    passed: bool
    score: float  # 0.0 - 1.0
    detail: str
    requires_human_review: bool = False


@dataclass
class SceneQCReport:
    """QC report for one scene."""

    scene_id: str
    passed: bool
    overall_score: float  # 0.0 - 1.0
    results: list[QCResult] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


@dataclass
class QCBatchReport:
    """QC report for a whole batch of scenes."""

    version: str = "1.0"
    total_scenes: int = 0
    passed_scenes: int = 0
    failed_scenes: int = 0
    reports: dict[str, SceneQCReport] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QualityControl:
    """Run quality checks on scenes and prompt packets."""

    def __init__(self) -> None:
        # No external state; all criteria are pure functions of inputs.
        pass

    # -- Individual criteria ------------------------------------------------

    def check_script_alignment(
        self, scene_description: str, script_excerpt: str
    ) -> QCResult:
        """Does the scene serve the script section it is bound to?"""
        if not script_excerpt or not scene_description:
            return QCResult(
                "script_alignment", False, 0.0,
                "Missing scene description or script excerpt",
                requires_human_review=True,
            )
        # Structural overlap: share at least one meaningful content word.
        script_words = set(
            w.lower() for w in script_excerpt.split() if len(w) > 4
        )
        scene_words = set(
            w.lower() for w in scene_description.split() if len(w) > 4
        )
        if not script_words:
            return QCResult(
                "script_alignment", False, 0.0,
                "Script excerpt has no content words",
                requires_human_review=True,
            )
        overlap = len(script_words & scene_words) / len(script_words)
        passed = overlap >= 0.25
        return QCResult(
            "script_alignment", passed, round(overlap, 2),
            f"{overlap:.0%} of script content words reflected in scene",
        )

    def check_scientific_accuracy(
        self, scene_description: str, scientific_claims: list[dict[str, Any]]
    ) -> QCResult:
        """Flag whether visual illustration matches stated claims.

        Does NOT certify truth — only notes whether the scene description
        references the claim domain and whether human review is needed.
        """
        if not scientific_claims:
            return QCResult(
                "scientific_accuracy", True, 1.0,
                "No scientific claims to verify",
            )
        claim_text = " ".join(c.get("text", "") for c in scientific_claims).lower()
        scene_words = set(w.lower() for w in scene_description.split() if len(w) > 4)
        claim_words = set(w.lower() for w in claim_text.split() if len(w) > 4)
        if not claim_words:
            return QCResult(
                "scientific_accuracy", True, 1.0,
                "Claims have no content words to cross-check",
            )
        overlap = len(claim_words & scene_words) / len(claim_words)
        # Always require human review for scientific accuracy — we never
        # certify correctness.
        return QCResult(
            "scientific_accuracy", True, round(overlap, 2),
            f"{overlap:.0%} of claim keywords appear in scene description; "
            "human review required for factual correctness",
            requires_human_review=True,
        )

    def check_character_reference(
        self,
        character_id: str | None,
        scene_description: str,
        character_anatomy: dict[str, Any] | None,
        consistency_issues: list[dict[str, Any]] | None,
    ) -> QCResult:
        """Does the scene depiction match the registered character design?"""
        if not character_id or not character_anatomy:
            return QCResult(
                "character_reference", True, 1.0,
                "No character in scene — check not applicable",
            )
        issues = consistency_issues or []
        high_issues = [i for i in issues if i.get("severity") == "high"]
        if high_issues:
            return QCResult(
                "character_reference", False, 0.0,
                f"{len(high_issues)} high-severity character inconsistency(ies)",
            )
        medium_issues = [i for i in issues if i.get("severity") == "medium"]
        if medium_issues:
            return QCResult(
                "character_reference", True, 0.5,
                f"{len(medium_issues)} medium-severity inconsistency(ies)",
            )
        return QCResult(
            "character_reference", True, 1.0,
            "Character depiction consistent with design",
        )

    def check_duplicate_frames(
        self, scene_id: str, all_scene_descriptions: dict[str, str]
    ) -> QCResult:
        """Is this scene visually duplicate of another?"""
        own_desc = all_scene_descriptions.get(scene_id, "").strip().lower()
        if not own_desc:
            return QCResult("duplicate_frames", False, 0.0, "No description to compare")
        for other_id, other_desc in all_scene_descriptions.items():
            if other_id == scene_id:
                continue
            other = other_desc.strip().lower()
            if not other:
                continue
            # Simple Jaccard on words
            own_words = set(own_desc.split())
            other_words = set(other.split())
            if not own_words or not other_words:
                continue
            jaccard = len(own_words & other_words) / len(own_words | other_words)
            if jaccard > 0.85:
                return QCResult(
                    "duplicate_frames", False, 0.0,
                    f"Near-duplicate of scene {other_id} (Jaccard {jaccard:.2f})",
                )
        return QCResult("duplicate_frames", True, 1.0, "No near-duplicate detected")

    def check_anatomy_errors(
        self,
        character_anatomy: dict[str, Any] | None,
        scene_description: str,
        consistency_issues: list[dict[str, Any]] | None,
    ) -> QCResult:
        """Check for anatomy errors (wrong limb count, missing features)."""
        if not character_anatomy:
            return QCResult("anatomy_errors", True, 1.0, "No character — not applicable")
        issues = consistency_issues or []
        anatomy_issues = [
            i for i in issues
            if i.get("issue_type") in ("wrong_limb_count", "missing_limb")
        ]
        if anatomy_issues:
            return QCResult(
                "anatomy_errors", False, 0.0,
                f"{len(anatomy_issues)} anatomy error(s) detected",
            )
        return QCResult("anatomy_errors", True, 1.0, "No anatomy errors detected")

    def check_prompt_contradictions(
        self,
        main_prompt: str,
        negative_prompt: str,
    ) -> QCResult:
        """Do main and negative prompts contradict each other?"""
        if not main_prompt or not negative_prompt:
            return QCResult(
                "prompt_contradictions", False, 0.0,
                "Missing prompt text",
            )
        # Stop words that are common foundation terms appearing on both sides.
        stop = {
            "no", "not", "without", "the", "and", "a", "an", "of", "in", "on",
            "at", "to", "for", "text", "caption", "watermark", "logo",
            "repetition", "template", "illustration", "composition", "lighting",
        }
        main_words = set(main_prompt.lower().split())
        neg_words = set(negative_prompt.lower().split())
        # Direct contradictions: a word appearing as both positive and negative,
        # excluding foundation stop-words.
        main_content = main_words - stop
        neg_content = neg_words - stop
        overlap = main_content & neg_content
        if overlap:
            return QCResult(
                "prompt_contradictions", False, 0.3,
                f"Contradictory terms in main vs negative: {sorted(overlap)[:5]}",
            )
        return QCResult(
            "prompt_contradictions", True, 1.0,
            "No prompt contradictions detected",
        )

    def check_composition_variety(
        self,
        scene_id: str,
        all_compositions: dict[str, str],
    ) -> QCResult:
        """Is this scene's composition distinct enough from neighbours?"""
        own = all_compositions.get(scene_id, "").lower()
        if not own:
            return QCResult("composition_variety", True, 1.0, "No composition to compare")
        own_words = set(own.split())
        similarities = []
        for other_id, other in all_compositions.items():
            if other_id == scene_id:
                continue
            other_words = set(other.split())
            if not other_words:
                continue
            jaccard = len(own_words & other_words) / len(own_words | other_words)
            similarities.append((other_id, jaccard))
        if similarities:
            max_sim = max(s for _, s in similarities)
            if max_sim > 0.8:
                most_similar = max(similarities, key=lambda x: x[1])[0]
                return QCResult(
                    "composition_variety", False, 0.4,
                    f"Composition too similar to {most_similar} (Jaccard {max_sim:.2f})",
                )
        return QCResult("composition_variety", True, 1.0, "Composition is varied")

    def check_no_text_in_image(
        self, main_prompt: str, negative_prompt: str
    ) -> QCResult:
        """Is there any instruction to put text inside the image?

        Only flags POSITIVE instructions to add text.  Prohibitions
        ("no text", "without caption") are expected and correct.
        """
        # Positive instructions to ADD text to the image.
        positive_markers = (
            "add text", "write text", "include text", "with text",
            "text overlay", "caption:", "write caption", "display text",
            "show text", "insert text", "place text", "put text",
        )
        main_lower = main_prompt.lower()
        found_in_main = [m for m in positive_markers if m in main_lower]
        # Negative prompt SHOULD prohibit text
        neg_lower = negative_prompt.lower()
        has_text_prohibition = any(
            m in neg_lower for m in ("text", "caption", "watermark", "logo")
        )
        if found_in_main:
            return QCResult(
                "no_text_in_image", False, 0.0,
                f"Positive text instruction found in main prompt: {found_in_main}",
            )
        if not has_text_prohibition:
            return QCResult(
                "no_text_in_image", True, 0.7,
                "No explicit text prohibition in negative prompt (recommended)",
            )
        return QCResult(
            "no_text_in_image", True, 1.0,
            "No text in main prompt; text prohibited in negative prompt",
        )

    def check_technical_suitability(
        self,
        image_format: str,
        aspect_ratio: str,
        generation_params: dict[str, Any] | None,
    ) -> QCResult:
        """Is the prompt technically suitable for the target model?"""
        issues = []
        if image_format not in ("1920x1080, ink illustration",):
            issues.append(f"Unusual format: {image_format}")
        valid_ratios = {"16:9", "9:16", "1:1", "4:3", "3:2"}
        if aspect_ratio not in valid_ratios:
            issues.append(f"Unusual aspect ratio: {aspect_ratio}")
        if generation_params:
            # No model-specific params should request generation spend.
            if any(k in generation_params for k in ("budget_usd", "credits", "paid")):
                issues.append("Generation params reference credits/budget — not allowed")
        if issues:
            return QCResult(
                "technical_suitability", False, 0.5,
                "; ".join(issues),
            )
        return QCResult(
            "technical_suitability", True, 1.0,
            "Technically suitable for Flow",
        )

    # -- Batch --------------------------------------------------------------

    def check_scene(
        self,
        *,
        scene_id: str,
        scene_plan: dict[str, Any],
        script_excerpt: str,
        scientific_claims: list[dict[str, Any]] | None = None,
        character_id: str | None = None,
        character_anatomy: dict[str, Any] | None = None,
        consistency_issues: list[dict[str, Any]] | None = None,
        all_scene_descriptions: dict[str, str] | None,
        all_compositions: dict[str, str] | None,
        prompt_packet: dict[str, Any] | None = None,
    ) -> SceneQCReport:
        """Run every applicable criterion on one scene."""
        results: list[QCResult] = []
        blocking: list[str] = []

        scientific_claims = scientific_claims or []
        all_scene_descriptions = all_scene_descriptions or {}
        all_compositions = all_compositions or {}
        prompt_packet = prompt_packet or {}

        # 1. Script alignment
        r = self.check_script_alignment(
            scene_plan.get("visual_idea", ""), script_excerpt
        )
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 2. Scientific accuracy
        r = self.check_scientific_accuracy(
            scene_plan.get("visual_idea", ""), scientific_claims
        )
        results.append(r)

        # 3. Character reference
        r = self.check_character_reference(
            character_id,
            scene_plan.get("visual_idea", ""),
            character_anatomy,
            consistency_issues,
        )
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 4. Duplicate frames
        r = self.check_duplicate_frames(scene_id, all_scene_descriptions)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 5. Anatomy errors
        r = self.check_anatomy_errors(
            character_anatomy, scene_plan.get("visual_idea", ""), consistency_issues
        )
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 6. Prompt contradictions
        if prompt_packet:
            r = self.check_prompt_contradictions(
                prompt_packet.get("main_prompt", ""),
                prompt_packet.get("negative_prompt", ""),
            )
            results.append(r)
            if not r.passed:
                blocking.append(r.detail)

            # 7. Composition variety
            r = self.check_composition_variety(
                scene_id, all_compositions
            )
            results.append(r)
            if not r.passed:
                blocking.append(r.detail)

            # 8. No text in image
            r = self.check_no_text_in_image(
                prompt_packet.get("main_prompt", ""),
                prompt_packet.get("negative_prompt", ""),
            )
            results.append(r)
            if not r.passed:
                blocking.append(r.detail)

            # 9. Technical suitability
            r = self.check_technical_suitability(
                prompt_packet.get("image_format", ""),
                prompt_packet.get("aspect_ratio", ""),
                prompt_packet.get("generation_params", {}),
            )
            results.append(r)
            if not r.passed:
                blocking.append(r.detail)

        overall = sum(r.score for r in results) / len(results) if results else 0.0
        passed = len(blocking) == 0

        return SceneQCReport(
            scene_id=scene_id,
            passed=passed,
            overall_score=round(overall, 2),
            results=results,
            blocking_issues=blocking,
        )

    def check_batch(
        self,
        scenes: list[dict[str, Any]],
        script_excerpts: dict[str, str],
        scientific_claims_by_scene: dict[str, list[dict[str, Any]]] | None = None,
        character_map: dict[str, str] | None = None,
        character_anatomy_by_id: dict[str, dict[str, Any]] | None = None,
        consistency_issues_by_scene: dict[str, list[dict[str, Any]]] | None = None,
        prompt_packets_by_scene: dict[str, dict[str, Any]] | None = None,
    ) -> QCBatchReport:
        """Run QC on every scene in the batch."""
        scientific_claims_by_scene = scientific_claims_by_scene or {}
        character_map = character_map or {}
        character_anatomy_by_id = character_anatomy_by_id or {}
        consistency_issues_by_scene = consistency_issues_by_scene or {}
        prompt_packets_by_scene = prompt_packets_by_scene or {}

        all_descriptions = {
            s.get("scene_id", f"scene-{i}"): s.get("visual_idea", "")
            for i, s in enumerate(scenes)
        }
        all_compositions = {
            s.get("scene_id", f"scene-{i}"): s.get("composition", "")
            for i, s in enumerate(scenes)
        }

        reports: dict[str, SceneQCReport] = {}
        passed = 0
        failed = 0

        for scene in scenes:
            sid = scene.get("scene_id", "unknown")
            char_id = character_map.get(sid)
            anat = character_anatomy_by_id.get(char_id, {}) if char_id else {}
            report = self.check_scene(
                scene_id=sid,
                scene_plan=scene,
                script_excerpt=script_excerpts.get(sid, ""),
                scientific_claims=scientific_claims_by_scene.get(sid, []),
                character_id=char_id,
                character_anatomy=anat,
                consistency_issues=consistency_issues_by_scene.get(sid, []),
                all_scene_descriptions=all_descriptions,
                all_compositions=all_compositions,
                prompt_packet=prompt_packets_by_scene.get(sid, {}),
            )
            reports[sid] = report
            if report.passed:
                passed += 1
            else:
                failed += 1

        total = len(scenes)
        return QCBatchReport(
            total_scenes=total,
            passed_scenes=passed,
            failed_scenes=failed,
            reports=reports,
            summary={
                "pass_rate": round(passed / total, 2) if total else 0.0,
                "average_score": round(
                    sum(r.overall_score for r in reports.values()) / total, 2
                ) if total else 0.0,
            },
        )

    def to_dict(self, report: QCBatchReport) -> dict[str, Any]:
        return {
            "version": report.version,
            "total_scenes": report.total_scenes,
            "passed_scenes": report.passed_scenes,
            "failed_scenes": report.failed_scenes,
            "reports": {
                sid: {
                    "scene_id": r.scene_id,
                    "passed": r.passed,
                    "overall_score": r.overall_score,
                    "results": [asdict(x) for x in r.results],
                    "blocking_issues": r.blocking_issues,
                }
                for sid, r in report.reports.items()
            },
            "summary": report.summary,
        }
