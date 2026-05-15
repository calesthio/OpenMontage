"""Segment-level TTS audition lab.

This tool sits before final narration generation. It creates controlled
voiceover samples for high-risk script segments, records the parameters used,
and writes a selection file that later asset generation can reuse.
"""

from __future__ import annotations

import json
import os
import re
import time
from html import escape
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class TTSSegmentLab(BaseTool):
    name = "tts_segment_lab"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts_audition"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = []
    install_instructions = "Requires at least one available TTS provider through tts_selector for generate mode."
    fallback_tools = ["tts_selector"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "tts_audition_batch",
        "script_section_extraction",
        "provider_comparison",
        "tts_candidate_audio_analysis",
        "voice_variant_selection",
    ]
    supports = {
        "dry_run": True,
        "audio_analysis": True,
        "provider_comparison": True,
        "selection_manifest": True,
        "timestamps_when_provider_supports_them": True,
        "optional_transcription_check": True,
    }
    best_for = [
        "auditioning generated narration before final asset generation",
        "generated explainers, product demos, and animated UI walkthroughs",
        "comparing TTS providers and voices for sensitive script lines",
        "recording chosen voiceover variants for production reuse",
    ]
    not_good_for = [
        "objective speech-quality benchmarking",
        "large-scale MOS listening studies",
        "source-footage voice, human-recorded narration, or already-approved voice tracks",
        "music-led or SFX-led videos where TTS does not carry the story",
        "subtitle generation after narration is locked",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["dry_run", "generate", "analyze", "annotate", "apply_review", "select"],
                "default": "dry_run",
            },
            "manifest_path": {"type": "string"},
            "manifest": {"type": "object"},
            "results_path": {"type": "string"},
            "analysis_options": {"type": "object"},
            "annotations": {"type": ["object", "array"]},
            "annotations_path": {"type": "string"},
            "selections": {"type": "object"},
            "segment_actions": {"type": "object"},
            "generate": {"type": "boolean"},
            "output_path": {"type": "string"},
            "output_dir": {"type": "string"},
        },
        "anyOf": [{"required": ["manifest_path"]}, {"required": ["manifest"]}, {"required": ["results_path"]}],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "status": {"type": "string"},
            "output_dir": {"type": "string"},
            "results_path": {"type": "string"},
            "review_path": {"type": "string"},
            "compare_path": {"type": "string"},
            "audio_profile_path": {"type": "string"},
            "analysis_path": {"type": "string"},
            "review_notes_path": {"type": "string"},
            "selection_path": {"type": "string"},
            "review_complete": {"type": "boolean"},
            "next_operation": {"type": "string"},
            "loaded_env_files": {"type": "array", "items": {"type": "string"}},
            "segments": {"type": "array"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True)
    idempotency_key_fields = [
        "operation",
        "manifest_path",
        "manifest",
        "results_path",
        "analysis_options",
        "annotations",
        "annotations_path",
        "selections",
        "segment_actions",
        "generate",
        "output_dir",
    ]
    side_effects = [
        "writes TTS audition audio samples",
        "writes per-variant provider metadata",
        "writes results.json, review.md, and compare.html",
        "writes audio_profile.json and analysis.md in analyze mode",
        "writes review_notes.json and review_annotated.md in annotate mode",
        "writes a follow-up audition round in apply_review mode",
        "writes selection.json in select mode",
        "calls configured TTS providers in generate mode",
    ]
    user_visible_verification = [
        "Listen to generated samples in compare.html or review.md",
        "Confirm selection.json points to the chosen narration variants",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        manifest = self._load_manifest(inputs)
        total = 0.0
        try:
            from tools.audio.tts_selector import TTSSelector

            selector = TTSSelector()
            for segment in self._segments_with_text(manifest):
                for variant in segment.get("variants", []):
                    selector_inputs = self._selector_inputs(manifest, segment, variant, output_path=Path("estimate.mp3"))
                    total += selector.estimate_cost(selector_inputs)
        except Exception:
            total = sum(
                len((variant.get("text") or segment.get("text") or "")) * 0.00002
                for segment in manifest.get("segments", [])
                for variant in segment.get("variants", [])
            )
        return round(total, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs.get("operation", "dry_run")
        start = time.time()
        try:
            if operation == "select":
                result = self._select(inputs)
            elif operation == "apply_review":
                result = self._apply_review(inputs)
            elif operation == "annotate":
                result = self._annotate(inputs)
            elif operation == "analyze":
                result = self._analyze(inputs)
            elif operation in {"dry_run", "generate"}:
                result = self._run(inputs, generate=operation == "generate")
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS Segment Lab failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs) if operation == "generate" else 0.0
        return result

    def _run(self, inputs: dict[str, Any], *, generate: bool) -> ToolResult:
        manifest = self._load_manifest(inputs)
        output_dir = self._output_dir(manifest)
        output_dir.mkdir(parents=True, exist_ok=True)
        loaded_env_files = self._load_project_env_files(
            self._env_search_roots(inputs, manifest=manifest, output_dir=output_dir)
        )

        selector = None
        if generate:
            from tools.audio.tts_selector import TTSSelector

            selector = TTSSelector()

        results: dict[str, Any] = {
            "version": self.version,
            "tool": self.name,
            "operation": "generate" if generate else "dry_run",
            "status": "completed",
            "project": manifest.get("project"),
            "run_id": manifest.get("run_id") or self._timestamp_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(output_dir),
            "script_path": manifest.get("script_path") or manifest.get("script"),
            "review_language": manifest.get("review_language", "auto"),
            "segments": [],
        }
        if loaded_env_files:
            results["loaded_env_files"] = loaded_env_files
        artifacts: list[str] = []

        for segment in self._segments_with_text(manifest):
            segment_result = {
                "id": segment["id"],
                "section_id": segment.get("section_id"),
                "label": segment.get("label", segment["id"]),
                "text": segment["text"],
                "variants": [],
            }
            for timing_key in ("start_seconds", "end_seconds", "expected_duration_seconds"):
                if segment.get(timing_key) is not None:
                    segment_result[timing_key] = segment[timing_key]
            segment_result["variants"].extend(self._reference_variants(segment))
            for variant in segment.get("variants", []):
                variant_id = self._slug(variant["id"])
                stem = f"{self._slug(segment['id'])}__{variant_id}"
                output_path = output_dir / f"{stem}.mp3"
                metadata_path = output_dir / f"{stem}_metadata.json"
                selector_inputs = self._selector_inputs(manifest, segment, variant, output_path=output_path)
                variant_result: dict[str, Any] = {
                    "id": variant_id,
                    "note": variant.get("note", ""),
                    "preferred_provider": selector_inputs.get("preferred_provider", "auto"),
                    "text": selector_inputs["text"],
                    "audio": str(output_path),
                    "metadata": str(metadata_path),
                    "params": self._visible_params(selector_inputs),
                }

                if not generate:
                    variant_result["planned"] = True
                else:
                    assert selector is not None
                    provider_result = selector.execute(selector_inputs)
                    metadata_payload = {
                        "selector_inputs": self._metadata_safe_inputs(selector_inputs),
                        "success": provider_result.success,
                        "data": provider_result.data,
                        "artifacts": provider_result.artifacts,
                        "error": provider_result.error,
                    }
                    self._write_json(metadata_path, metadata_payload)
                    artifacts.append(str(metadata_path))
                    if provider_result.success:
                        data = provider_result.data
                        variant_result.update(
                            {
                                "success": True,
                                "selected_provider": data.get("selected_provider") or data.get("provider"),
                                "selected_tool": data.get("selected_tool"),
                                "duration_seconds": data.get("audio_duration_seconds"),
                                "provider_metadata_path": data.get("metadata_path"),
                                "provider_artifacts": provider_result.artifacts,
                            }
                        )
                        if output_path.exists():
                            artifacts.append(str(output_path))
                    else:
                        variant_result["success"] = False
                        variant_result["error"] = provider_result.error
                        results["status"] = "completed-with-errors"

                segment_result["variants"].append(variant_result)
            results["segments"].append(segment_result)

        results_path = output_dir / "results.json"
        review_path = output_dir / "review.md"
        compare_path = output_dir / "compare.html"
        self._write_json(results_path, results)
        review_path.write_text(self._review_markdown(results), encoding="utf-8")
        compare_path.write_text(self._comparison_html(results, compare_path), encoding="utf-8")
        artifacts.extend([str(results_path), str(review_path), str(compare_path)])

        return ToolResult(
            success=results["status"] != "completed-with-errors",
            data={
                "operation": results["operation"],
                "status": results["status"],
                "output_dir": str(output_dir),
                "results_path": str(results_path),
                "review_path": str(review_path),
                "compare_path": str(compare_path),
                "loaded_env_files": loaded_env_files,
                "segments": results["segments"],
            },
            artifacts=artifacts,
            error=None if results["status"] == "completed" else "One or more variants failed.",
        )

    def _analyze(self, inputs: dict[str, Any]) -> ToolResult:
        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        options = self._analysis_options(inputs.get("analysis_options", {}))
        profile = {
            "version": self.version,
            "tool": self.name,
            "operation": "analyze",
            "status": "completed",
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "analysis_options": options,
            "segments": [],
            "review_queue": [],
        }

        for segment in results.get("segments", []):
            segment_profile = {
                "id": segment["id"],
                "section_id": segment.get("section_id"),
                "label": segment.get("label"),
                "text": segment.get("text", ""),
                "variants": [],
            }
            for variant in segment.get("variants", []):
                variant_profile = self._analyze_variant(segment, variant, options)
                segment_profile["variants"].append(variant_profile)
                if variant_profile.get("suggested_review"):
                    profile["review_queue"].append(
                        {
                            "segment_id": segment.get("id"),
                            "section_id": segment.get("section_id"),
                            "variant_id": variant.get("id"),
                            "reasons": [item["message"] for item in variant_profile.get("findings", [])],
                        }
                    )
            profile["segments"].append(segment_profile)

        profile["summary"] = self._analysis_summary(profile)
        output_path = Path(inputs.get("output_path") or results_path.with_name("audio_profile.json"))
        analysis_path = output_path.with_name("analysis.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, profile)
        analysis_path.write_text(self._analysis_markdown(profile), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "analyze",
                "status": "completed",
                "audio_profile_path": str(output_path),
                "analysis_path": str(analysis_path),
                "summary": profile["summary"],
                "review_queue": profile["review_queue"],
            },
            artifacts=[str(output_path), str(analysis_path)],
        )

    def _annotate(self, inputs: dict[str, Any]) -> ToolResult:
        review_payload = self._review_payload(inputs)
        annotations = review_payload.get("annotations")
        selections = review_payload.get("selections")
        segment_actions = review_payload.get("segment_actions")
        if not annotations and not segment_actions:
            return ToolResult(success=False, error="annotate operation requires non-empty annotations/segment_actions or annotations_path")

        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        annotated_results = deepcopy(results)
        by_segment = self._segment_lookup(annotated_results)
        applied_annotations = []

        if annotations:
            for item in self._normalize_annotations(annotations):
                segment_key = item["segment_key"]
                variant_id = item["variant_id"]
                segment = by_segment.get(segment_key)
                if not segment:
                    return ToolResult(success=False, error=f"Unknown annotation segment/section key: {segment_key}")
                variant = next((entry for entry in segment.get("variants", []) if entry.get("id") == variant_id), None)
                if not variant:
                    return ToolResult(success=False, error=f"Unknown variant {variant_id!r} for segment {segment_key!r}")

                annotation = self._clean_annotation(item)
                variant["review"] = annotation
                applied_annotations.append(
                    {
                        "segment_id": segment["id"],
                        "section_id": segment.get("section_id"),
                        "label": segment.get("label"),
                        "variant_id": variant["id"],
                        **annotation,
                    }
                )

        applied_segment_actions = []
        for segment_key, action in self._normalize_segment_actions(segment_actions).items():
            segment = by_segment.get(segment_key)
            if not segment:
                return ToolResult(success=False, error=f"Unknown segment action key: {segment_key}")
            clean_action = self._clean_segment_action(action)
            segment["review_action"] = clean_action
            applied_segment_actions.append(
                {
                    "segment_id": segment["id"],
                    "section_id": segment.get("section_id"),
                    "label": segment.get("label"),
                    **clean_action,
                }
            )

        summary = self._review_summary(annotated_results)
        action_items = self._action_items(applied_annotations, applied_segment_actions)
        completion = self._review_completion(annotated_results, selections or {}, action_items)
        review_notes = {
            "version": self.version,
            "tool": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "summary": summary,
            "completion": completion,
            "action_items": action_items,
            "segment_actions": applied_segment_actions,
            "annotations": applied_annotations,
        }

        output_path = Path(inputs.get("output_path") or results_path.with_name("review_notes.json"))
        review_path = output_path.with_name("review_annotated.md")
        annotated_results_path = output_path.with_name("results_annotated.json")
        compare_path = output_path.with_name("compare_annotated.html")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, review_notes)
        self._write_json(annotated_results_path, annotated_results)
        review_path.write_text(self._review_markdown(annotated_results), encoding="utf-8")
        compare_path.write_text(self._comparison_html(annotated_results, compare_path), encoding="utf-8")

        selection_path = None
        selection_payload = None
        if selections:
            annotated_results["selections"] = selections
        if segment_actions:
            annotated_results["segment_actions"] = segment_actions
        if selections or segment_actions:
            self._write_json(annotated_results_path, annotated_results)
            compare_path.write_text(self._comparison_html(annotated_results, compare_path), encoding="utf-8")
        if selections and completion["review_complete"]:
            selection_path = output_path.with_name("selection.json")
            selection_payload = self._build_selection_payload(results, results_path, selections)
            self._write_json(selection_path, selection_payload)

        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "status": "completed",
                "results_path": str(annotated_results_path),
                "review_path": str(review_path),
                "compare_path": str(compare_path),
                "review_notes_path": str(output_path),
                "selection_path": str(selection_path) if selection_path else None,
                "summary": summary,
                "review_complete": completion["review_complete"],
                "next_operation": completion["next_operation"],
                "missing_selection_segments": completion["missing_selection_segments"],
                "pending_review_segments": completion["pending_review_segments"],
                "selection_deferred_reason": completion["selection_deferred_reason"],
                "action_item_count": len(action_items),
                "action_items": action_items,
                "segment_actions": applied_segment_actions,
                "selection_count": len(selection_payload["selections"]) if selection_payload else 0,
                "annotations": applied_annotations,
            },
            artifacts=[
                str(path)
                for path in [output_path, annotated_results_path, review_path, compare_path, selection_path]
                if path
            ],
        )

    def _apply_review(self, inputs: dict[str, Any]) -> ToolResult:
        review_payload = self._review_payload(inputs)
        annotations = review_payload.get("annotations")
        selections = review_payload.get("selections") or {}
        segment_actions = review_payload.get("segment_actions") or {}
        if not annotations and not segment_actions:
            return ToolResult(success=False, error="apply_review operation requires annotations/segment_actions or annotations_path")

        results_path = self._results_path(inputs)
        source_results = json.loads(results_path.read_text(encoding="utf-8"))
        source_segments = self._segment_lookup(source_results)
        output_dir = Path(
            inputs.get("output_dir")
            or results_path.with_name(f"{source_results.get('run_id') or 'tts-review'}-review-round")
        ).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        loaded_env_files = self._load_project_env_files(
            self._env_search_roots(inputs, results_path=results_path, output_dir=output_dir)
        )

        submission_path = output_dir / "review_submission.json"
        self._write_json(submission_path, review_payload)

        generate_audio = bool(inputs.get("generate", True))
        selector = None
        if generate_audio:
            from tools.audio.tts_selector import TTSSelector

            selector = TTSSelector()

        round_results: dict[str, Any] = {
            "version": self.version,
            "tool": self.name,
            "operation": "apply_review",
            "status": "completed",
            "project": source_results.get("project"),
            "run_id": inputs.get("run_id") or f"{source_results.get('run_id') or 'tts-review'}-review-round",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(output_dir),
            "script_path": source_results.get("script_path"),
            "review_language": source_results.get("review_language", "auto"),
            "source_results": str(results_path),
            "review_submission": str(submission_path),
            "selections": {},
            "segments": [],
        }
        if loaded_env_files:
            round_results["loaded_env_files"] = loaded_env_files
        artifacts: list[str] = [str(submission_path)]
        regenerated: list[dict[str, Any]] = []
        approved: list[dict[str, Any]] = []

        normalized_annotations = self._normalize_annotations(annotations) if annotations else []
        annotation_by_segment = {item["segment_key"]: item for item in normalized_annotations}
        segment_action_map = self._normalize_segment_actions(segment_actions)

        for source_segment in source_results.get("segments", []):
            segment_id = str(source_segment.get("id") or "")
            section_id = str(source_segment.get("section_id") or "")
            annotation = annotation_by_segment.get(segment_id) or annotation_by_segment.get(section_id)
            segment_action = segment_action_map.get(segment_id) or segment_action_map.get(section_id)
            selected_variant_id = selections.get(segment_id) or selections.get(section_id)

            round_segment = {
                "id": segment_id,
                "section_id": source_segment.get("section_id"),
                "label": source_segment.get("label", segment_id),
                "text": source_segment.get("text", ""),
                "variants": [],
            }
            for timing_key in ("start_seconds", "end_seconds", "expected_duration_seconds"):
                if source_segment.get(timing_key) is not None:
                    round_segment[timing_key] = source_segment[timing_key]

            if segment_action:
                action = self._clean_segment_action(segment_action)
                variant_result, generated_artifacts = self._review_regenerate_variant(
                    source_results,
                    source_segment,
                    None,
                    action,
                    output_dir,
                    selector,
                    generate=generate_audio,
                    suffix="new",
                )
                round_segment["variants"].append(variant_result)
                round_results["selections"][segment_id] = variant_result["id"]
                regenerated.append(
                    {
                        "segment_id": segment_id,
                        "section_id": source_segment.get("section_id"),
                        "variant_id": variant_result["id"],
                        "source_variant_id": None,
                        "notes": action["notes"],
                        "adjustment": variant_result.get("note", ""),
                    }
                )
                artifacts.extend(generated_artifacts)
                if variant_result.get("success") is False:
                    round_results["status"] = "completed-with-errors"
            elif annotation and selected_variant_id:
                source_variant = self._find_segment_variant(source_segments, segment_id, selected_variant_id)
                clean_annotation = self._clean_annotation(annotation)
                notes = clean_annotation.get("notes") or clean_annotation.get("fix_target") or ""
                if clean_annotation["decision"] in {"REGENERATE", "NEEDS_REVIEW"} or notes:
                    variant_result, generated_artifacts = self._review_regenerate_variant(
                        source_results,
                        source_segment,
                        source_variant,
                        clean_annotation,
                        output_dir,
                        selector,
                        generate=generate_audio,
                        suffix="adjusted",
                    )
                    round_segment["variants"].append(variant_result)
                    round_results["selections"][segment_id] = variant_result["id"]
                    regenerated.append(
                        {
                            "segment_id": segment_id,
                            "section_id": source_segment.get("section_id"),
                            "variant_id": variant_result["id"],
                            "source_variant_id": source_variant.get("id"),
                            "notes": notes,
                            "adjustment": variant_result.get("note", ""),
                        }
                    )
                    artifacts.extend(generated_artifacts)
                    if variant_result.get("success") is False:
                        round_results["status"] = "completed-with-errors"
                else:
                    kept_variant = deepcopy(source_variant)
                    kept_variant["note"] = self._append_note(
                        kept_variant.get("note", ""),
                        "上一轮已通过，保留为当前选择。",
                    )
                    kept_variant["review_source"] = {"decision": "APPROVED", "round": "previous"}
                    round_segment["variants"].append(kept_variant)
                    round_results["selections"][segment_id] = kept_variant["id"]
                    approved.append(
                        {
                            "segment_id": segment_id,
                            "section_id": source_segment.get("section_id"),
                            "variant_id": kept_variant["id"],
                        }
                    )
            else:
                round_segment["variants"].extend(deepcopy(source_segment.get("variants", [])))
                if selected_variant_id:
                    round_results["selections"][segment_id] = str(selected_variant_id)

            round_results["segments"].append(round_segment)

        results_out = output_dir / "results.json"
        review_out = output_dir / "review.md"
        compare_out = output_dir / "compare.html"
        summary_out = output_dir / "review_round_summary.json"
        round_summary = {
            "version": self.version,
            "tool": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "review_submission": str(submission_path),
            "approved": approved,
            "regenerated": regenerated,
            "selection_count": len(round_results["selections"]),
            "review_complete": False,
            "next_operation": "annotate",
            "loaded_env_files": loaded_env_files,
        }
        self._write_json(results_out, round_results)
        self._write_json(summary_out, round_summary)
        review_out.write_text(self._review_markdown(round_results), encoding="utf-8")
        compare_out.write_text(self._comparison_html(round_results, compare_out), encoding="utf-8")
        artifacts.extend([str(results_out), str(review_out), str(compare_out), str(summary_out)])

        return ToolResult(
            success=round_results["status"] != "completed-with-errors",
            data={
                "operation": "apply_review",
                "status": round_results["status"],
                "output_dir": str(output_dir),
                "results_path": str(results_out),
                "review_path": str(review_out),
                "compare_path": str(compare_out),
                "review_submission_path": str(submission_path),
                "summary_path": str(summary_out),
                "approved_count": len(approved),
                "regenerated_count": len(regenerated),
                "selection_count": len(round_results["selections"]),
                "review_complete": False,
                "next_operation": "annotate",
                "loaded_env_files": loaded_env_files,
                "regenerated": regenerated,
            },
            artifacts=artifacts,
            error=None if round_results["status"] == "completed" else "One or more review-round variants failed.",
        )

    def _select(self, inputs: dict[str, Any]) -> ToolResult:
        selections = inputs.get("selections")
        if not isinstance(selections, dict) or not selections:
            return ToolResult(success=False, error="select operation requires non-empty selections mapping")

        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        selection = self._build_selection_payload(results, results_path, selections)
        output_path = Path(inputs.get("output_path") or results_path.with_name("selection.json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, selection)

        return ToolResult(
            success=True,
            data={
                "operation": "select",
                "status": "completed",
                "selection_path": str(output_path),
                "selection_count": len(selection["selections"]),
                "selections": selection["selections"],
            },
            artifacts=[str(output_path)],
        )

    def _build_selection_payload(self, results: dict[str, Any], results_path: Path, selections: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(selections, dict) or not selections:
            raise ValueError("selections must be a non-empty mapping")
        by_segment = self._segment_lookup(results)
        selected_items = []
        for segment_key, variant_id in selections.items():
            segment = by_segment.get(str(segment_key))
            if not segment:
                raise ValueError(f"Unknown segment/section selection key: {segment_key}")
            variant = next((item for item in segment.get("variants", []) if item.get("id") == str(variant_id)), None)
            if not variant:
                raise ValueError(f"Unknown variant {variant_id!r} for segment {segment_key!r}")
            selected_items.append(
                {
                    "segment_id": segment["id"],
                    "section_id": segment.get("section_id"),
                    "label": segment.get("label"),
                    "variant_id": variant["id"],
                    "text": variant.get("text") or segment.get("text"),
                    "audio": variant.get("audio"),
                    "metadata": variant.get("metadata"),
                    "provider_metadata_path": variant.get("provider_metadata_path"),
                    "selected_provider": variant.get("selected_provider") or variant.get("preferred_provider"),
                    "selected_tool": variant.get("selected_tool"),
                    "duration_seconds": variant.get("duration_seconds"),
                    "params": variant.get("params", {}),
                    "note": variant.get("note", ""),
                }
            )

        return {
            "version": self.version,
            "tool": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "selections": selected_items,
        }

    @classmethod
    def _review_completion(
        cls,
        results: dict[str, Any],
        selections: dict[str, Any],
        action_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        selected_segment_ids: set[str] = set()
        by_segment = cls._segment_lookup(results)
        for segment_key, variant_id in (selections or {}).items():
            segment = by_segment.get(str(segment_key))
            if not segment:
                continue
            if any(str(variant.get("id")) == str(variant_id) for variant in segment.get("variants", [])):
                selected_segment_ids.add(str(segment.get("id")))

        missing_selection_segments = [
            str(segment.get("id"))
            for segment in results.get("segments", [])
            if str(segment.get("id")) not in selected_segment_ids
        ]
        pending_review_segments = sorted(
            {
                str(item.get("segment_id"))
                for item in action_items
                if item.get("segment_id")
            }
        )
        review_complete = not missing_selection_segments and not pending_review_segments
        if review_complete:
            next_operation = "complete"
            selection_deferred_reason = ""
        elif pending_review_segments:
            next_operation = "apply_review"
            selection_deferred_reason = "pending_review_actions"
        else:
            next_operation = "annotate"
            selection_deferred_reason = "missing_segment_selections"
        return {
            "review_complete": review_complete,
            "next_operation": next_operation,
            "missing_selection_segments": missing_selection_segments,
            "pending_review_segments": pending_review_segments,
            "selection_deferred_reason": selection_deferred_reason,
        }

    @classmethod
    def _env_search_roots(
        cls,
        inputs: dict[str, Any],
        *,
        manifest: dict[str, Any] | None = None,
        results_path: Path | None = None,
        output_dir: Path | None = None,
    ) -> list[Path]:
        roots: list[Path] = [Path.cwd()]
        if inputs.get("manifest_path"):
            roots.append(Path(inputs["manifest_path"]).expanduser())
        if manifest:
            for key in ("script_path", "script", "output_dir"):
                if manifest.get(key):
                    roots.append(Path(str(manifest[key])).expanduser())
        if results_path:
            roots.append(results_path)
            try:
                source_results = json.loads(results_path.read_text(encoding="utf-8"))
                if source_results.get("script_path"):
                    roots.append(Path(str(source_results["script_path"])).expanduser())
                if source_results.get("output_dir"):
                    roots.append(Path(str(source_results["output_dir"])).expanduser())
            except Exception:
                pass
        if output_dir:
            roots.append(output_dir)
        return roots

    @classmethod
    def _load_project_env_files(cls, roots: list[Path]) -> list[str]:
        loaded: list[str] = []
        seen: set[Path] = set()
        for raw_root in roots:
            try:
                root = raw_root.expanduser().resolve()
            except Exception:
                continue
            if root.is_file():
                root = root.parent
            for parent in (root, *root.parents):
                env_path = parent / ".env"
                if env_path in seen:
                    pass
                elif env_path.exists() and env_path.is_file():
                    cls._load_env_file(env_path)
                    loaded.append(str(env_path))
                    seen.add(env_path)
                if parent == Path.home() or parent.parent == parent:
                    break
        return loaded

    @staticmethod
    def _load_env_file(env_path: Path) -> None:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            if key in os.environ:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value

    @staticmethod
    def _review_payload(inputs: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if inputs.get("annotations_path"):
            payload.update(json.loads(Path(inputs["annotations_path"]).expanduser().read_text(encoding="utf-8")))
        for key in ("annotations", "selections", "segment_actions"):
            if inputs.get(key) is not None:
                payload[key] = inputs[key]
        return payload

    @staticmethod
    def _segment_lookup(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
        by_segment: dict[str, dict[str, Any]] = {}
        for segment in results.get("segments", []):
            by_segment[segment["id"]] = segment
            if segment.get("section_id"):
                by_segment[segment["section_id"]] = segment
        return by_segment

    @staticmethod
    def _find_segment_variant(
        by_segment: dict[str, dict[str, Any]],
        segment_key: str,
        variant_id: str,
    ) -> dict[str, Any]:
        segment = by_segment.get(str(segment_key))
        if not segment:
            raise ValueError(f"Unknown segment/section key: {segment_key}")
        variant = next((item for item in segment.get("variants", []) if item.get("id") == str(variant_id)), None)
        if not variant:
            raise ValueError(f"Unknown variant {variant_id!r} for segment {segment_key!r}")
        return variant

    def _review_regenerate_variant(
        self,
        source_results: dict[str, Any],
        source_segment: dict[str, Any],
        source_variant: dict[str, Any] | None,
        review: dict[str, Any],
        output_dir: Path,
        selector: Any,
        *,
        generate: bool,
        suffix: str,
    ) -> tuple[dict[str, Any], list[str]]:
        notes = review.get("notes") or review.get("fix_target") or ""
        base_variant = source_variant or self._first_generated_variant(source_segment)
        source_id = str(base_variant.get("id") or "auto")
        variant_id = self._unique_variant_id(source_segment, self._slug(f"{source_id}-review-{suffix}"))
        stem = f"{self._slug(source_segment.get('id', 'segment'))}__{variant_id}"
        output_path = output_dir / f"{stem}.mp3"
        metadata_path = output_dir / f"{stem}_metadata.json"
        selector_inputs = self._selector_inputs_from_result_variant(source_segment, base_variant, output_path=output_path)
        selector_inputs = self._apply_review_adjustments(selector_inputs, notes, source_results, base_variant)
        variant_result: dict[str, Any] = {
            "id": variant_id,
            "source_type": "review_adjustment" if source_variant else "review_regeneration",
            "source_variant_id": source_variant.get("id") if source_variant else None,
            "note": self._adjustment_note(notes, selector_inputs, base_variant, suffix=suffix),
            "preferred_provider": selector_inputs.get("preferred_provider", "auto"),
            "text": selector_inputs["text"],
            "audio": str(output_path),
            "metadata": str(metadata_path),
            "params": self._visible_params(selector_inputs),
            "review_instruction": {
                "decision": review.get("decision", "REGENERATE"),
                "notes": notes,
                "fix_target": review.get("fix_target") or notes,
            },
        }
        artifacts: list[str] = []
        if not generate:
            variant_result["planned"] = True
            return variant_result, artifacts

        provider_result = selector.execute(selector_inputs)
        metadata_payload = {
            "selector_inputs": self._metadata_safe_inputs(selector_inputs),
            "success": provider_result.success,
            "data": provider_result.data,
            "artifacts": provider_result.artifacts,
            "error": provider_result.error,
        }
        self._write_json(metadata_path, metadata_payload)
        artifacts.append(str(metadata_path))
        if provider_result.success:
            data = provider_result.data
            variant_result.update(
                {
                    "success": True,
                    "selected_provider": data.get("selected_provider") or data.get("provider"),
                    "selected_tool": data.get("selected_tool"),
                    "duration_seconds": data.get("audio_duration_seconds"),
                    "provider_metadata_path": data.get("metadata_path"),
                    "provider_artifacts": provider_result.artifacts,
                }
            )
            if output_path.exists():
                artifacts.append(str(output_path))
        else:
            variant_result["success"] = False
            variant_result["error"] = provider_result.error
        return variant_result, artifacts

    @staticmethod
    def _first_generated_variant(segment: dict[str, Any]) -> dict[str, Any]:
        for variant in segment.get("variants", []):
            if variant.get("source_type") != "reference":
                return variant
        if segment.get("variants"):
            return segment["variants"][0]
        raise ValueError(f"Segment {segment.get('id')} has no source variants to regenerate from")

    def _selector_inputs_from_result_variant(
        self,
        segment: dict[str, Any],
        variant: dict[str, Any],
        *,
        output_path: Path,
    ) -> dict[str, Any]:
        inputs = deepcopy(variant.get("params") or {})
        inputs["text"] = variant.get("text") or segment.get("text", "")
        inputs["operation"] = "generate"
        inputs["output_path"] = str(output_path)
        if "preferred_provider" not in inputs:
            inputs["preferred_provider"] = variant.get("selected_provider") or variant.get("preferred_provider") or "auto"
        return inputs

    def _apply_review_adjustments(
        self,
        inputs: dict[str, Any],
        notes: str,
        source_results: dict[str, Any],
        source_variant: dict[str, Any],
    ) -> dict[str, Any]:
        adjusted = deepcopy(inputs)
        normalized = notes.lower()
        mentions_speed = "语速" in notes or "速度" in notes or "speed" in normalized or "rate" in normalized
        if mentions_speed and ("快" in notes or "faster" in normalized):
            adjusted["speech_rate"] = min(int(adjusted.get("speech_rate", 0) or 0) + (1 if "稍微" in notes else 2), 100)
        if mentions_speed and ("慢" in notes or "slower" in normalized):
            adjusted["speech_rate"] = max(int(adjusted.get("speech_rate", 0) or 0) - (1 if "稍微" in notes else 2), -50)
        if any(token in notes for token in ("换一个声音", "换个声音", "换音色", "换一个音色")) or "different voice" in normalized:
            alternate_voice = self._alternate_voice_id(source_results, source_variant)
            if alternate_voice:
                adjusted["voice_id"] = alternate_voice
            else:
                adjusted.pop("voice_id", None)
                adjusted["preferred_provider"] = "auto"
        if notes:
            context_texts = list(adjusted.get("context_texts") or [])
            context_texts.append(f"上一轮试听反馈：{notes}。请按反馈微调，但保持原脚本含义不变。")
            adjusted["context_texts"] = context_texts
        return adjusted

    @staticmethod
    def _alternate_voice_id(source_results: dict[str, Any], source_variant: dict[str, Any]) -> str | None:
        current = (source_variant.get("params") or {}).get("voice_id")
        seen: list[str] = []
        for segment in source_results.get("segments", []):
            for variant in segment.get("variants", []):
                voice_id = (variant.get("params") or {}).get("voice_id")
                if voice_id and voice_id not in seen:
                    seen.append(voice_id)
        for voice_id in seen:
            if voice_id != current:
                return voice_id
        return None

    @staticmethod
    def _unique_variant_id(segment: dict[str, Any], candidate: str) -> str:
        existing = {str(variant.get("id")) for variant in segment.get("variants", [])}
        if candidate not in existing:
            return candidate
        index = 2
        while f"{candidate}-{index}" in existing:
            index += 1
        return f"{candidate}-{index}"

    @staticmethod
    def _adjustment_note(notes: str, selector_inputs: dict[str, Any], source_variant: dict[str, Any], *, suffix: str) -> str:
        prefix = "已按上一轮建议重新生成" if suffix == "adjusted" else "已按上一轮反馈生成新候选"
        details = []
        source_rate = (source_variant.get("params") or {}).get("speech_rate")
        target_rate = selector_inputs.get("speech_rate")
        if source_rate != target_rate and target_rate is not None:
            details.append(f"speech_rate {source_rate} -> {target_rate}")
        source_voice = (source_variant.get("params") or {}).get("voice_id")
        target_voice = selector_inputs.get("voice_id")
        if source_voice != target_voice and target_voice:
            details.append(f"voice {source_voice} -> {target_voice}")
        detail_text = f"（{'; '.join(details)}）" if details else ""
        return f"{prefix}{detail_text}：{notes}".rstrip("：")

    @staticmethod
    def _append_note(existing: str, addition: str) -> str:
        existing = str(existing or "").strip()
        return f"{existing} {addition}".strip() if existing else addition

    @staticmethod
    def _normalize_annotations(raw_annotations: Any) -> list[dict[str, Any]]:
        if isinstance(raw_annotations, list):
            items = raw_annotations
        elif isinstance(raw_annotations, dict):
            items = []
            for segment_key, segment_annotations in raw_annotations.items():
                if isinstance(segment_annotations, list):
                    for annotation in segment_annotations:
                        if isinstance(annotation, dict):
                            item = deepcopy(annotation)
                            item.setdefault("segment_key", segment_key)
                            items.append(item)
                elif isinstance(segment_annotations, dict):
                    if "variant_id" in segment_annotations:
                        item = deepcopy(segment_annotations)
                        item.setdefault("segment_key", segment_key)
                        items.append(item)
                    else:
                        for variant_id, annotation in segment_annotations.items():
                            item = deepcopy(annotation) if isinstance(annotation, dict) else {"decision": annotation}
                            item.setdefault("segment_key", segment_key)
                            item.setdefault("variant_id", variant_id)
                            items.append(item)
                else:
                    raise ValueError(f"Annotation for {segment_key!r} must be an object or list")
        else:
            raise ValueError("annotations must be an object or list")

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("each annotation must be an object")
            segment_key = item.get("segment_key") or item.get("segment_id") or item.get("section_id")
            variant_id = item.get("variant_id") or item.get("variant")
            if not segment_key or not variant_id:
                raise ValueError("each annotation needs segment_key/segment_id/section_id and variant_id")
            normalized.append({**item, "segment_key": str(segment_key), "variant_id": str(variant_id)})
        return normalized

    @staticmethod
    def _clean_annotation(item: dict[str, Any]) -> dict[str, Any]:
        allowed = {"APPROVED", "NEEDS_REVIEW", "REGENERATE", "REJECTED", "KEEP_REFERENCE"}
        decision = str(item.get("decision", "NEEDS_REVIEW")).strip().upper().replace("-", "_")
        if decision not in allowed:
            raise ValueError(f"Unknown annotation decision {decision!r}; expected one of {sorted(allowed)}")
        requires_user_review = item.get("requires_user_review")
        if requires_user_review is None:
            requires_user_review = decision == "NEEDS_REVIEW"
        return {
            "decision": decision,
            "requires_user_review": bool(requires_user_review),
            "issue_category": item.get("issue_category") or "",
            "fix_target": item.get("fix_target") or "",
            "notes": item.get("notes") or item.get("note") or "",
            "user_decision": item.get("user_decision") or "",
        }

    @staticmethod
    def _normalize_segment_actions(raw_actions: Any) -> dict[str, dict[str, Any]]:
        if not raw_actions:
            return {}
        if not isinstance(raw_actions, dict):
            raise ValueError("segment_actions must be an object")
        normalized = {}
        for segment_key, action in raw_actions.items():
            if isinstance(action, dict):
                normalized[str(segment_key)] = action
            else:
                normalized[str(segment_key)] = {"decision": action}
        return normalized

    @staticmethod
    def _clean_segment_action(item: dict[str, Any]) -> dict[str, Any]:
        allowed = {"REGENERATE", "NEEDS_REVIEW"}
        decision = str(item.get("decision", "REGENERATE")).strip().upper().replace("-", "_")
        if decision not in allowed:
            raise ValueError(f"Unknown segment action decision {decision!r}; expected one of {sorted(allowed)}")
        notes = item.get("notes") or item.get("note") or item.get("fix_target") or ""
        return {
            "decision": decision,
            "requires_user_review": bool(item.get("requires_user_review", True)),
            "issue_category": item.get("issue_category") or "voice_review",
            "fix_target": item.get("fix_target") or notes,
            "notes": notes,
            "user_decision": item.get("user_decision") or "",
        }

    @staticmethod
    def _review_summary(results: dict[str, Any]) -> dict[str, Any]:
        decisions = {
            "APPROVED": 0,
            "NEEDS_REVIEW": 0,
            "REGENERATE": 0,
            "REJECTED": 0,
            "KEEP_REFERENCE": 0,
            "UNREVIEWED": 0,
        }
        review_queue = []
        total_variants = 0
        for segment in results.get("segments", []):
            for variant in segment.get("variants", []):
                total_variants += 1
                review = variant.get("review") or {}
                decision = review.get("decision") or "UNREVIEWED"
                decisions[decision] = decisions.get(decision, 0) + 1
                if review.get("requires_user_review") or decision in {"NEEDS_REVIEW", "REGENERATE"}:
                    review_queue.append(
                        {
                            "segment_id": segment.get("id"),
                            "section_id": segment.get("section_id"),
                            "variant_id": variant.get("id"),
                            "decision": decision,
                            "notes": review.get("notes", ""),
                        }
                    )
        return {
            "segments": len(results.get("segments", [])),
            "variants": total_variants,
            "decisions": decisions,
            "review_queue": review_queue,
        }

    @staticmethod
    def _comparison_review_state(results: dict[str, Any], summary: dict[str, Any], copy: dict[str, str]) -> dict[str, Any]:
        segment_count = len(results.get("segments", []))
        selections = results.get("selections") if isinstance(results.get("selections"), dict) else {}
        selected_count = len(selections)
        segment_actions = results.get("segment_actions") if isinstance(results.get("segment_actions"), dict) else {}
        segment_action_count = len(segment_actions)
        segment_action_count += sum(1 for segment in results.get("segments", []) if segment.get("review_action"))
        decisions = summary.get("decisions", {})
        reviewed_count = sum(
            int(decisions.get(key, 0) or 0)
            for key in ("APPROVED", "NEEDS_REVIEW", "REGENERATE", "REJECTED", "KEEP_REFERENCE")
        )
        action_count = len(summary.get("review_queue", [])) + segment_action_count
        has_review_round_candidates = any(
            variant.get("source_type") in {"review_adjustment", "review_regeneration"}
            for segment in results.get("segments", [])
            for variant in segment.get("variants", [])
        )
        if action_count:
            state = copy["review_state_needs_changes"]
        elif reviewed_count and int(decisions.get("APPROVED", 0) or 0) + int(decisions.get("KEEP_REFERENCE", 0) or 0) == summary.get("variants", 0):
            state = copy["review_state_approved"]
        elif has_review_round_candidates or results.get("operation") == "apply_review":
            state = copy["review_state_recheck"]
        elif selected_count:
            state = copy["review_state_selected"]
        else:
            state = copy["review_state_unreviewed"]
        return {
            "selected_count": selected_count,
            "segment_count": segment_count,
            "state": state,
        }

    @staticmethod
    def _action_items(
        annotations: list[dict[str, Any]],
        segment_actions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        items = []
        for annotation in annotations:
            decision = annotation.get("decision")
            if decision not in {"NEEDS_REVIEW", "REGENERATE"} and not annotation.get("requires_user_review"):
                continue
            items.append(
                {
                    "segment_id": annotation.get("segment_id"),
                    "section_id": annotation.get("section_id"),
                    "variant_id": annotation.get("variant_id"),
                    "decision": decision,
                    "issue_category": annotation.get("issue_category", ""),
                    "notes": annotation.get("notes", ""),
                    "fix_target": annotation.get("fix_target", ""),
                }
            )
        for action in segment_actions or []:
            items.append(
                {
                    "segment_id": action.get("segment_id"),
                    "section_id": action.get("section_id"),
                    "variant_id": None,
                    "decision": action.get("decision"),
                    "issue_category": action.get("issue_category", ""),
                    "notes": action.get("notes", ""),
                    "fix_target": action.get("fix_target", ""),
                }
            )
        return items

    @staticmethod
    def _analysis_options(raw_options: Any) -> dict[str, Any]:
        options = raw_options if isinstance(raw_options, dict) else {}
        return {
            "duration_tolerance_ratio": float(options.get("duration_tolerance_ratio", 0.35)),
            "energy_threshold_lufs": float(options.get("energy_threshold_lufs", -45)),
            "long_quiet_run_seconds": int(options.get("long_quiet_run_seconds", 2)),
            "quiet_intro_seconds": float(options.get("quiet_intro_seconds", 1.0)),
            "include_transcript": bool(options.get("include_transcript", False)),
            "transcriber_model_size": options.get("transcriber_model_size", "base"),
            "language": options.get("language"),
        }

    def _analyze_variant(self, segment: dict[str, Any], variant: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        audio_path = Path(variant.get("audio", "")).expanduser() if variant.get("audio") else None
        findings: list[dict[str, str]] = []
        profile: dict[str, Any] = {
            "id": variant.get("id"),
            "source_type": variant.get("source_type", "generated"),
            "selected_provider": variant.get("selected_provider") or variant.get("preferred_provider"),
            "audio": str(audio_path) if audio_path else None,
            "text": variant.get("text") or segment.get("text", ""),
            "findings": findings,
            "suggested_review": False,
        }

        if variant.get("success") is False:
            findings.append({"severity": "error", "kind": "generation_failed", "message": variant.get("error", "Generation failed.")})
        if not audio_path or not audio_path.exists():
            findings.append({"severity": "error", "kind": "audio_missing", "message": "Audio file is missing; cannot analyze this candidate."})
            profile["suggested_review"] = True
            return profile

        probe = self._run_audio_probe(audio_path)
        profile["probe"] = probe
        duration = probe.get("duration_seconds") or variant.get("duration_seconds")
        expected_duration = self._expected_duration_seconds(segment, variant)
        profile["duration_check"] = self._duration_check(duration, expected_duration, options)
        if profile["duration_check"].get("outside_tolerance"):
            findings.append(
                {
                    "severity": "warning",
                    "kind": "duration_outlier",
                    "message": profile["duration_check"]["message"],
                }
            )

        energy = self._run_audio_energy(audio_path, options)
        profile["energy"] = energy
        for issue in self._energy_findings(energy, options):
            findings.append(issue)

        timing_hints = self._extract_variant_timing_hints(variant)
        profile["timing_hints"] = timing_hints

        if options.get("include_transcript"):
            transcript = self._run_transcriber(audio_path, options)
            profile["transcript"] = transcript
            for issue in self._transcript_findings(profile["text"], transcript):
                findings.append(issue)
        else:
            profile["transcript"] = {"status": "skipped", "reason": "Set analysis_options.include_transcript=true to run ASR checks."}

        profile["suggested_review"] = any(item.get("severity") in {"error", "warning"} for item in findings)
        return profile

    def _run_audio_probe(self, audio_path: Path) -> dict[str, Any]:
        try:
            from tools.analysis.audio_probe import AudioProbe

            result = AudioProbe().execute({"input_path": str(audio_path)})
            if result.success:
                return {"status": "ok", **(result.data or {})}
            return {"status": "failed", "error": result.error}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def _run_audio_energy(self, audio_path: Path, options: dict[str, Any]) -> dict[str, Any]:
        try:
            from tools.analysis.audio_energy import AudioEnergy

            result = AudioEnergy().execute(
                {
                    "input_path": str(audio_path),
                    "energy_threshold_lufs": options["energy_threshold_lufs"],
                }
            )
            if result.success:
                return {"status": "ok", **(result.data or {})}
            return {"status": "failed", "error": result.error}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def _run_transcriber(self, audio_path: Path, options: dict[str, Any]) -> dict[str, Any]:
        try:
            from tools.analysis.transcriber import Transcriber

            result = Transcriber().execute(
                {
                    "input_path": str(audio_path),
                    "model_size": options["transcriber_model_size"],
                    "language": options.get("language"),
                    "diarize": False,
                    "output_dir": str(audio_path.parent),
                }
            )
            if result.success:
                data = result.data or {}
                return {
                    "status": "ok",
                    "language": data.get("language"),
                    "segments": data.get("segments", []),
                    "word_timestamps_count": len(data.get("word_timestamps", [])),
                    "text": " ".join(item.get("text", "") for item in data.get("segments", [])).strip(),
                }
            return {"status": "failed", "error": result.error}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    @classmethod
    def _expected_duration_seconds(cls, segment: dict[str, Any], variant: dict[str, Any]) -> float:
        explicit = (
            variant.get("expected_duration_seconds")
            or segment.get("expected_duration_seconds")
            or (
                float(segment["end_seconds"]) - float(segment["start_seconds"])
                if segment.get("start_seconds") is not None and segment.get("end_seconds") is not None
                else None
            )
        )
        if explicit:
            return round(float(explicit), 2)
        return cls._estimate_speech_duration(variant.get("text") or segment.get("text", ""))

    @staticmethod
    def _estimate_speech_duration(text: str) -> float:
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_words = len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", text))
        punctuation_pauses = len(re.findall(r"[，。！？,.!?;；:：]", text)) * 0.18
        duration = (cjk_chars / 4.6) + (latin_words / 2.7) + punctuation_pauses
        return round(max(duration, 0.8), 2)

    @staticmethod
    def _duration_check(duration: Any, expected_duration: float, options: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(duration, (int, float)) or duration <= 0:
            return {
                "status": "unknown",
                "expected_duration_seconds": expected_duration,
                "message": "Audio duration is unavailable.",
            }
        tolerance = float(options["duration_tolerance_ratio"])
        ratio = abs(float(duration) - expected_duration) / max(expected_duration, 0.1)
        outside = ratio > tolerance
        return {
            "status": "outside_tolerance" if outside else "ok",
            "duration_seconds": round(float(duration), 2),
            "expected_duration_seconds": expected_duration,
            "difference_ratio": round(ratio, 3),
            "outside_tolerance": outside,
            "message": (
                f"Duration {round(float(duration), 2)}s differs from estimated {expected_duration}s by {round(ratio * 100)}%."
                if outside
                else "Duration is within the heuristic tolerance."
            ),
        }

    @staticmethod
    def _energy_findings(energy: dict[str, Any], options: dict[str, Any]) -> list[dict[str, str]]:
        if energy.get("status") != "ok":
            return [{"severity": "info", "kind": "energy_unavailable", "message": energy.get("error", "Energy analysis unavailable.")}]
        analysis = energy.get("analysis", {})
        profile = energy.get("energy_profile", [])
        findings = []
        quiet_intro = float(analysis.get("quiet_intro_seconds", 0) or 0)
        if quiet_intro > float(options["quiet_intro_seconds"]):
            findings.append(
                {
                    "severity": "warning",
                    "kind": "quiet_intro",
                    "message": f"Detected {quiet_intro}s before the first active speech/music energy point.",
                }
            )
        longest_quiet_run = TTSSegmentLab._longest_inactive_run(profile)
        if longest_quiet_run >= int(options["long_quiet_run_seconds"]):
            findings.append(
                {
                    "severity": "warning",
                    "kind": "long_low_energy_run",
                    "message": f"Detected a low-energy run of about {longest_quiet_run}s; review for awkward pause or dropped delivery.",
                }
            )
        return findings

    @staticmethod
    def _longest_inactive_run(energy_profile: list[dict[str, Any]]) -> int:
        longest = 0
        current = 0
        for point in energy_profile:
            if point.get("active"):
                current = 0
            else:
                current += 1
                longest = max(longest, current)
        return longest

    def _extract_variant_timing_hints(self, variant: dict[str, Any]) -> dict[str, Any]:
        payloads = []
        for key in ("provider_metadata_path", "metadata"):
            if variant.get(key):
                path = Path(variant[key]).expanduser()
                if path.exists():
                    try:
                        payloads.append(json.loads(path.read_text(encoding="utf-8")))
                    except Exception:
                        pass
        found = []
        for payload in payloads:
            found.extend(self._find_timing_like_values(payload))
        return {
            "status": "found" if found else "not_found",
            "source_count": len(payloads),
            "hint_count": len(found),
            "hints": found[:5],
        }

    def _find_timing_like_values(self, payload: Any, path: str = "$") -> list[dict[str, Any]]:
        found = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                next_path = f"{path}.{key}"
                key_lower = str(key).lower()
                if any(token in key_lower for token in ("timestamp", "timestamps", "word", "words", "phoneme", "alignment")):
                    if isinstance(value, (list, dict)):
                        found.append({"path": next_path, "type": type(value).__name__})
                found.extend(self._find_timing_like_values(value, next_path))
        elif isinstance(payload, list):
            for index, item in enumerate(payload[:20]):
                found.extend(self._find_timing_like_values(item, f"{path}[{index}]"))
        return found

    @staticmethod
    def _transcript_findings(expected_text: str, transcript: dict[str, Any]) -> list[dict[str, str]]:
        if transcript.get("status") != "ok":
            return [{"severity": "info", "kind": "transcript_unavailable", "message": transcript.get("error", "Transcript check unavailable.")}]
        expected_norm = TTSSegmentLab._normalize_text_for_compare(expected_text)
        actual_norm = TTSSegmentLab._normalize_text_for_compare(transcript.get("text", ""))
        if not actual_norm:
            return [{"severity": "warning", "kind": "empty_transcript", "message": "ASR returned no transcript text."}]
        if expected_norm and expected_norm not in actual_norm and actual_norm not in expected_norm:
            return [{"severity": "warning", "kind": "transcript_mismatch", "message": "ASR transcript differs from the expected script; review for misread or pronunciation issue."}]
        return []

    @staticmethod
    def _normalize_text_for_compare(text: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"[^\w\u3400-\u9fff]+", "", text.lower()))

    @staticmethod
    def _analysis_summary(profile: dict[str, Any]) -> dict[str, Any]:
        variants = 0
        findings = 0
        warnings = 0
        errors = 0
        for segment in profile.get("segments", []):
            for variant in segment.get("variants", []):
                variants += 1
                for item in variant.get("findings", []):
                    findings += 1
                    warnings += 1 if item.get("severity") == "warning" else 0
                    errors += 1 if item.get("severity") == "error" else 0
        return {
            "segments": len(profile.get("segments", [])),
            "variants": variants,
            "findings": findings,
            "warnings": warnings,
            "errors": errors,
            "review_queue_count": len(profile.get("review_queue", [])),
        }

    @staticmethod
    def _analysis_markdown(profile: dict[str, Any]) -> str:
        summary = profile.get("summary", {})
        lines = [
            f"# TTS Segment Lab Analysis: {profile.get('run_id', '')}",
            "",
            f"- Project: `{profile.get('project', '')}`",
            f"- Created: `{profile.get('created_at', '')}`",
            f"- Source results: `{profile.get('source_results', '')}`",
            "",
            "## Summary",
            "",
            f"- Segments: `{summary.get('segments', 0)}`",
            f"- Variants: `{summary.get('variants', 0)}`",
            f"- Findings: `{summary.get('findings', 0)}` (`{summary.get('warnings', 0)}` warnings, `{summary.get('errors', 0)}` errors)",
            f"- Suggested human review: `{summary.get('review_queue_count', 0)}`",
            "",
            "These checks are heuristics. Use them to prioritize listening; do not treat them as final creative approval.",
            "",
        ]
        if profile.get("review_queue"):
            lines.extend(["## Suggested Review Queue", ""])
            for item in profile["review_queue"]:
                reason = "; ".join(item.get("reasons", []))
                lines.append(f"- `{item['segment_id']}` / `{item['variant_id']}`: {reason}")
            lines.append("")
        for segment in profile.get("segments", []):
            lines.extend([f"## {segment.get('label') or segment['id']}", "", f"- Text: {segment.get('text', '')}", ""])
            lines.extend(["| Variant | Duration Check | Energy | Timing Hints | Findings |", "|---|---|---|---|---|"])
            for variant in segment.get("variants", []):
                duration = variant.get("duration_check", {})
                energy = variant.get("energy", {})
                timing = variant.get("timing_hints", {})
                findings = "<br>".join(item.get("message", "") for item in variant.get("findings", [])) or "-"
                lines.append(
                    f"| `{variant.get('id')}` | {duration.get('status', '-')} | "
                    f"{energy.get('status', '-')} | {timing.get('status', '-')} ({timing.get('hint_count', 0)}) | {findings} |"
                )
            lines.append("")
        return "\n".join(lines)

    def _load_manifest(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("manifest") is not None:
            manifest = deepcopy(inputs["manifest"])
        elif inputs.get("manifest_path"):
            manifest = json.loads(Path(inputs["manifest_path"]).read_text(encoding="utf-8"))
        else:
            raise ValueError("manifest or manifest_path is required")
        if "output_dir" not in manifest:
            raise ValueError("manifest.output_dir is required")
        if not manifest.get("segments"):
            raise ValueError("manifest.segments must contain at least one segment")
        return manifest

    def _output_dir(self, manifest: dict[str, Any]) -> Path:
        return Path(manifest["output_dir"]).expanduser().resolve()

    def _results_path(self, inputs: dict[str, Any]) -> Path:
        if inputs.get("results_path"):
            return Path(inputs["results_path"]).expanduser().resolve()
        manifest = self._load_manifest(inputs)
        return self._output_dir(manifest) / "results.json"

    def _segments_with_text(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        script_sections = self._load_script_sections(manifest)
        segments = []
        for raw_segment in manifest.get("segments", []):
            segment = deepcopy(raw_segment)
            section_id = segment.get("section_id") or segment.get("script_section_id")
            if not segment.get("text") and section_id:
                if section_id not in script_sections:
                    raise ValueError(f"Script section not found: {section_id}")
                segment["text"] = script_sections[section_id]
            if not segment.get("text"):
                raise ValueError(f"Segment {segment.get('id', '<unknown>')} needs text or section_id")
            if "id" not in segment:
                segment["id"] = section_id or self._slug(segment["text"][:32])
            segment["section_id"] = section_id
            if not segment.get("variants"):
                if not segment.get("reference") and not segment.get("references"):
                    raise ValueError(f"Segment {segment['id']} must contain variants or references")
            segments.append(segment)
        return segments

    def _load_script_sections(self, manifest: dict[str, Any]) -> dict[str, str]:
        script_path = manifest.get("script_path") or manifest.get("script")
        if not script_path:
            return {}
        payload = json.loads(Path(script_path).expanduser().read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            section_list = (
                payload.get("sections")
                or payload.get("script")
                or payload.get("scenes")
                or payload.get("segments")
                or []
            )
        elif isinstance(payload, list):
            section_list = payload
        else:
            section_list = []
        sections: dict[str, str] = {}
        for item in section_list:
            if not isinstance(item, dict):
                continue
            section_id = item.get("id") or item.get("section_id") or item.get("scene_id")
            text = item.get("text") or item.get("narration") or item.get("voiceover")
            if section_id and text:
                sections[str(section_id)] = str(text)
        return sections

    def _selector_inputs(
        self,
        manifest: dict[str, Any],
        segment: dict[str, Any],
        variant: dict[str, Any],
        *,
        output_path: Path,
    ) -> dict[str, Any]:
        defaults = deepcopy(manifest.get("defaults", {}))
        provider_options = deepcopy(variant.get("provider_options", {}))
        overrides = deepcopy(variant.get("overrides", {}))
        inputs: dict[str, Any] = {}
        inputs.update(defaults)
        inputs.update(provider_options)
        inputs.update(overrides)
        inputs["text"] = variant.get("text") or segment["text"]
        if "provider" in variant:
            inputs["preferred_provider"] = variant["provider"]
        inputs.setdefault("preferred_provider", manifest.get("preferred_provider", "auto"))
        inputs.setdefault("operation", "generate")
        inputs["output_path"] = str(output_path)
        return inputs

    def _reference_variants(self, segment: dict[str, Any]) -> list[dict[str, Any]]:
        raw_references = []
        if segment.get("reference"):
            raw_references.append(segment["reference"])
        raw_references.extend(segment.get("references", []))

        references = []
        for index, reference in enumerate(raw_references, start=1):
            if not isinstance(reference, dict):
                raise ValueError(f"Reference for segment {segment['id']} must be an object")
            audio = reference.get("audio") or reference.get("path")
            if not audio:
                raise ValueError(f"Reference for segment {segment['id']} needs audio or path")
            ref_id = self._slug(reference.get("id") or ("reference-current" if index == 1 else f"reference-{index}"))
            references.append(
                {
                    "id": ref_id,
                    "source_type": "reference",
                    "success": True,
                    "note": reference.get("note", "Existing approved audio used as comparison baseline."),
                    "preferred_provider": reference.get("provider", "reference"),
                    "selected_provider": reference.get("provider", "reference"),
                    "selected_tool": "reference_audio",
                    "text": reference.get("text") or segment["text"],
                    "audio": str(Path(audio).expanduser().resolve()),
                    "metadata": str(Path(reference["metadata"]).expanduser().resolve()) if reference.get("metadata") else None,
                    "duration_seconds": reference.get("duration_seconds"),
                    "params": {
                        "source": reference.get("source", "existing_audio"),
                        "provider": reference.get("provider", "reference"),
                    },
                }
            )
        return references

    @staticmethod
    def _visible_params(inputs: dict[str, Any]) -> dict[str, Any]:
        hidden = {"text", "output_path", "operation"}
        return {key: value for key, value in inputs.items() if key not in hidden and value is not None}

    @staticmethod
    def _metadata_safe_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in inputs.items() if "key" not in key.lower() and "token" not in key.lower()}

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip()).strip("-")
        return slug or "sample"

    @staticmethod
    def _timestamp_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @classmethod
    def _review_markdown(cls, results: dict[str, Any]) -> str:
        summary = cls._review_summary(results)
        lines = [
            f"# TTS Segment Lab Review: {results.get('run_id', '')}",
            "",
            f"- Project: `{results.get('project', '')}`",
            f"- Created: `{results.get('created_at', '')}`",
            f"- Status: `{results.get('status', '')}`",
            "",
            "## Summary",
            "",
            f"- Segments: `{summary['segments']}`",
            f"- Variants: `{summary['variants']}`",
            "- Decisions: "
            + ", ".join(f"`{key}` {value}" for key, value in summary["decisions"].items() if value),
            "",
        ]
        if summary["review_queue"]:
            lines.extend(["## Needs Human Review", ""])
            for item in summary["review_queue"]:
                note = f" {item.get('notes', '')}" if item.get("notes") else ""
                lines.append(
                    f"- `{item['segment_id']}` / `{item['variant_id']}`: `{item['decision']}`{note}"
                )
            lines.append("")
        for segment in results.get("segments", []):
            lines.extend(
                [
                    f"## {segment.get('label') or segment['id']}",
                    "",
                    f"- Segment id: `{segment['id']}`",
                    f"- Section id: `{segment.get('section_id') or ''}`",
                    f"- Text: {segment.get('text', '')}",
                    "",
                    "| Variant | Provider | Duration | Audio | Decision | Review Notes | Note | Key Params |",
                    "|---|---|---:|---|---|---|---|---|",
                ]
            )
            for variant in segment.get("variants", []):
                duration = variant.get("duration_seconds")
                duration_text = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "-"
                audio = variant.get("audio")
                audio_link = f"[mp3]({audio})" if audio else "-"
                provider = variant.get("selected_provider") or variant.get("preferred_provider") or "auto"
                params = variant.get("params", {})
                key_params = ", ".join(
                    f"{key}={params.get(key)}"
                    for key in (
                        "preferred_provider",
                        "voice_id",
                        "voice",
                        "model",
                        "model_id",
                        "speech_rate",
                        "speaking_rate",
                        "speed",
                        "emotion",
                        "emotion_scale",
                        "post_process_pitch",
                        "pitch",
                        "style",
                        "source",
                        "provider",
                    )
                    if params.get(key) is not None
                )
                if variant.get("success") is False:
                    key_params = f"ERROR: {variant.get('error', '')}"
                review = variant.get("review") or {}
                decision = review.get("decision", "UNREVIEWED")
                review_notes = review.get("notes", "")
                lines.append(
                    f"| `{variant['id']}` | `{provider}` | {duration_text} | {audio_link} | "
                    f"`{decision}` | {review_notes} | {variant.get('note', '')} | {key_params} |"
                )
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def _comparison_html(cls, results: dict[str, Any], html_path: Path) -> str:
        language = cls._review_language(results)
        copy = cls._ui_copy(language)
        title = f"{copy['title']}: {results.get('run_id', '')}".strip()
        summary = cls._review_summary(results)
        review_state = cls._comparison_review_state(results, summary, copy)

        css = """
:root {
  color-scheme: dark;
  --bg: #0c111d;
  --panel: rgba(255,255,255,.06);
  --panel-strong: rgba(255,255,255,.1);
  --border: rgba(149,172,214,.24);
  --text: #eef4ff;
  --muted: #aebbd0;
  --accent: #68d8ff;
  --ok: #4ade80;
  --warn: #facc15;
  --bad: #fb7185;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 20% 0%, rgba(104,216,255,.16), transparent 32rem),
    linear-gradient(135deg, #0a0f1d 0%, var(--bg) 54%, #101524 100%);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", sans-serif;
  line-height: 1.5;
}
main { max-width: 1120px; margin: 0 auto; padding: 36px 28px 64px; }
header { margin-bottom: 26px; }
h1 { margin: 0 0 10px; font-size: 30px; letter-spacing: 0; }
p { color: var(--muted); }
.summary { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.review-toolbar {
  align-items: start;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.045);
  border-radius: 12px;
  display: grid;
  gap: 14px;
  grid-template-columns: minmax(0, 1fr) auto;
  margin-top: 18px;
  padding: 14px;
}
.review-copy {
  display: grid;
  gap: 10px;
}
.review-action {
  align-items: flex-end;
  display: flex;
  justify-content: flex-end;
}
.review-copy .hint,
.save-status {
  background: rgba(8,14,27,.38);
  border: 1px solid rgba(149,172,214,.14);
  border-radius: 10px;
  color: var(--muted);
  font-size: 13px;
  padding: 9px 11px;
}
.review-copy .hint {
  border-color: rgba(98,216,255,.22);
}
.pill {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 999px;
  padding: 6px 12px;
  color: #dbe7fb;
  font-size: 13px;
}
button.pill {
  cursor: pointer;
  font: inherit;
}
.primary-action {
  background: linear-gradient(135deg, rgba(98,216,255,.95), rgba(74,222,128,.74));
  border-color: rgba(98,216,255,.9);
  box-shadow: 0 12px 32px rgba(98,216,255,.2);
  color: #06111f;
  font-weight: 700;
  min-height: 40px;
  padding: 9px 16px;
}
.floating-actions {
  bottom: 22px;
  position: fixed;
  right: 22px;
  z-index: 45;
}
.floating-actions .pill {
  backdrop-filter: blur(12px);
  box-shadow: 0 14px 34px rgba(0,0,0,.26);
}
.segment {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 14px;
  padding: 22px;
  margin: 22px 0;
  box-shadow: 0 18px 48px rgba(0,0,0,.22);
}
.segment h2 { margin: 0 0 12px; font-size: 22px; letter-spacing: 0; }
.text {
  color: #dbe7fb;
  background: rgba(0,0,0,.2);
  border: 1px solid rgba(255,255,255,.06);
  border-radius: 10px;
  padding: 14px 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 14px;
  margin-top: 16px;
}
.card {
  border: 1px solid rgba(149,172,214,.22);
  background: rgba(8,14,27,.74);
  border-radius: 12px;
  padding: 14px;
}
.card h3 { margin: 0 0 6px; font-size: 16px; letter-spacing: 0; }
.meta { color: #94a7c4; font-size: 13px; margin-bottom: 10px; }
.note { min-height: 1.5em; color: var(--muted); font-size: 13px; }
audio { width: 100%; margin: 8px 0; }
.choose-row,
.decision-row,
.regenerate-all {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.choose-pill,
.decision-pill,
.regenerate-pill {
  align-items: center;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.22);
  border-radius: 999px;
  color: #dbe8fb;
  cursor: pointer;
  display: grid;
  gap: 8px;
  grid-template-columns: 18px 1fr;
  min-height: 38px;
  padding: 8px 12px;
  text-align: left;
}
.choose-pill input,
.decision-pill input,
.regenerate-pill input {
  accent-color: var(--accent);
  margin: 0;
  place-self: center;
}
.choose-pill span,
.decision-pill span,
.regenerate-pill span {
  min-width: 0;
  white-space: nowrap;
}
.choose-pill:has(input:checked),
.decision-pill:has(input:checked),
.regenerate-pill:has(input:checked) {
  background: rgba(98,216,255,.16);
  border-color: rgba(98,216,255,.68);
  color: var(--text);
}
.decision-row {
  grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));
}
.review-note {
  background: rgba(0,0,0,.24);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: var(--text);
  font: inherit;
  margin-top: 10px;
  line-height: 1.45;
  min-height: 96px;
  padding: 10px 12px;
  resize: vertical;
  width: 100%;
}
.review-note.is-hidden { display: none; }
.regenerate-all {
  border: 1px dashed rgba(149,172,214,.3);
  border-radius: 12px;
  padding: 12px;
}
.regenerate-all textarea {
  background: rgba(0,0,0,.24);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: var(--text);
  display: none;
  font: inherit;
  min-height: 74px;
  padding: 8px 10px;
  resize: vertical;
  width: 100%;
}
.regenerate-all.is-active textarea { display: block; }
.regenerate-all.is-missing-note {
  border-color: rgba(251,113,133,.72);
}
.segment.is-missing-selection {
  border-color: rgba(251,113,133,.7);
  box-shadow: 0 0 0 1px rgba(251,113,133,.28), 0 18px 48px rgba(0,0,0,.22);
}
.badge { border: 1px solid var(--border); border-radius: 999px; padding: 3px 8px; }
.approved { color: var(--ok); border-color: rgba(74,222,128,.42); }
.needs, .regenerate { color: var(--warn); border-color: rgba(250,204,21,.45); }
.rejected { color: var(--bad); border-color: rgba(251,113,133,.45); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.missing {
  border: 1px dashed rgba(149,172,214,.28);
  color: #94a7c4;
  border-radius: 9px;
  padding: 10px 12px;
  font-size: 14px;
}
.export-panel {
  border: 1px solid rgba(98,216,255,.24);
  background: rgba(8,14,27,.9);
  border-radius: 12px;
  display: none;
  margin-top: 18px;
  padding: 14px;
}
.export-panel.is-visible { display: block; }
.export-panel textarea {
  background: rgba(0,0,0,.32);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: var(--text);
  font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  min-height: 180px;
  padding: 10px;
  width: 100%;
}
.toast {
  background: rgba(8,14,27,.96);
  border: 1px solid rgba(98,216,255,.35);
  border-radius: 12px;
  box-shadow: 0 18px 42px rgba(0,0,0,.36);
  color: var(--text);
  display: grid;
  gap: 4px;
  left: 50%;
  max-width: min(520px, calc(100vw - 32px));
  opacity: 0;
  padding: 14px 16px;
  pointer-events: none;
  position: fixed;
  top: 18px;
  transform: translate(-50%, -12px);
  transition: opacity .18s ease, transform .18s ease;
  z-index: 60;
}
.toast.is-visible {
  opacity: 1;
  transform: translate(-50%, 0);
}
@media (max-width: 720px) {
  main { padding: 28px 16px 46px; }
  h1 { font-size: 25px; }
  .review-toolbar { align-items: stretch; grid-template-columns: 1fr; }
  .review-action { justify-content: start; }
  .floating-actions { bottom: 14px; right: 14px; }
}
""".strip()

        lines = [
            "<!doctype html>",
            f"<html lang=\"{escape(language)}\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"<title>{escape(title)}</title>",
            f"<style>{css}</style>",
            "</head>",
            "<body>",
            "<main>",
            "<header>",
            f"<h1>{escape(title)}</h1>",
            f"<p>{escape(copy['description'])}</p>",
            "<div class=\"summary\">",
            f"<span class=\"pill\">{escape(copy['project'])}: {escape(str(results.get('project') or '-'))}</span>",
            f"<span class=\"pill\">{escape(copy['segments'])}: {summary['segments']}</span>",
            f"<span class=\"pill\">{escape(copy['variants'])}: {summary['variants']}</span>",
            f"<span class=\"pill\">{escape(copy['selected'])}: {review_state['selected_count']}/{review_state['segment_count']}</span>",
            f"<span class=\"pill\">{escape(copy['review_status'])}: {escape(str(review_state['state']))}</span>",
            "</div>",
            "<div class=\"review-toolbar\">",
            "<div class=\"review-copy\">",
            f"<span class=\"save-status\" data-save-status data-submitted-text=\"{escape(copy['submitted_hint'], quote=True)}\">{escape(copy['save_hint'])}</span>",
            f"<span class=\"hint\">{escape(copy['submit_hint'])}</span>",
            "</div>",
            "<div class=\"review-action\">",
            (
                f"<button type=\"button\" class=\"pill primary-action\" data-save-review "
                f"data-submitted-label=\"{escape(copy['submitted_button'], quote=True)}\" "
                f"data-run-id=\"{escape(str(results.get('run_id') or 'tts-segment-review'), quote=True)}\">"
                f"{escape(copy['save_review'])}</button>"
            ),
            "</div>",
            "</div>",
            "<section class=\"export-panel\" data-export-panel>",
            f"<h2>{escape(copy['export_title'])}</h2>",
            f"<p>{escape(copy['export_body'])}</p>",
            "<textarea data-export-json readonly></textarea>",
            "</section>",
            "<div class=\"floating-actions\">",
            f"<button type=\"button\" class=\"pill\" data-scroll-top>{escape(copy['back_to_top'])}</button>",
            "</div>",
            "</header>",
        ]

        selections = results.get("selections") if isinstance(results.get("selections"), dict) else {}
        segment_actions = results.get("segment_actions") if isinstance(results.get("segment_actions"), dict) else {}
        for segment in results.get("segments", []):
            segment_id = str(segment.get("id") or "")
            segment_action = segment.get("review_action") or segment_actions.get(segment.get("id")) or segment_actions.get(segment.get("section_id")) or {}
            segment_for_html = deepcopy(segment)
            segment_for_html["_selected_variant_id"] = (
                selections.get(segment.get("id"))
                or selections.get(segment.get("section_id"))
                or ""
            )
            lines.extend(
                [
                    f"<section class=\"segment\" data-segment-card data-segment-id=\"{escape(segment_id, quote=True)}\">",
                    f"<h2>{escape(str(segment.get('label') or segment.get('id') or ''))}</h2>",
                    f"<div class=\"text\">{escape(str(segment.get('text') or ''))}</div>",
                    "<div class=\"grid\">",
                ]
            )
            for variant in segment.get("variants", []):
                lines.append(cls._comparison_card_html(segment_for_html, variant, html_path, copy))
            segment_action_notes = segment_action.get("notes") or segment_action.get("fix_target") or ""
            segment_action_active = bool(segment_action)
            lines.extend(
                [
                    "</div>",
                    f"<div class=\"regenerate-all{' is-active' if segment_action_active else ''}\" data-regenerate-all>",
                    (
                        f"<label class=\"regenerate-pill\"><input type=\"radio\" "
                        f"name=\"selection-{escape(segment_id, quote=True)}\" data-regenerate-all-field "
                        f"value=\"__regenerate__\"{' checked' if segment_action_active else ''}>"
                        f"<span>{escape(copy['regenerate_all'])}</span></label>"
                    ),
                    (
                        f"<textarea data-segment-action-notes placeholder=\"{escape(copy['regenerate_all_placeholder'], quote=True)}\">"
                        f"{escape(segment_action_notes)}</textarea>"
                    ),
                    "</div>",
                    "</section>",
                ]
            )

        lines.extend([cls._comparison_script(copy), "</main>", "</body>", "</html>"])
        return "\n".join(lines) + "\n"

    @classmethod
    def _comparison_card_html(cls, segment: dict[str, Any], variant: dict[str, Any], html_path: Path, copy: dict[str, str]) -> str:
        segment_id = str(segment.get("id") or "")
        variant_id = str(variant.get("id") or "variant")
        provider = variant.get("selected_provider") or variant.get("preferred_provider") or "auto"
        params = variant.get("params", {})
        voice = (
            params.get("voice_id")
            or params.get("voice")
            or params.get("model")
            or params.get("model_id")
            or params.get("source")
            or provider
        )
        duration = variant.get("duration_seconds")
        duration_text = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "-"
        audio = variant.get("audio")
        audio_src = cls._html_audio_src(audio, html_path) if audio else ""
        note = variant.get("note") or ""
        review_notes = (variant.get("review") or {}).get("notes", "")
        audio_is_current = bool(audio and Path(audio).expanduser().exists()) and not variant.get("planned")
        selected = str(segment.get("_selected_variant_id") or "") == variant_id

        lines = [
            (
                f"<article class=\"card\" data-variant-card data-segment-id=\"{escape(segment_id, quote=True)}\" "
                f"data-variant-id=\"{escape(variant_id, quote=True)}\">"
            ),
            f"<h3>{escape(variant_id)}</h3>",
            f"<div class=\"meta\">{escape(str(provider))} · {escape(str(voice))} · {escape(duration_text)}</div>",
        ]
        if audio_is_current:
            lines.extend(
                [
                    f"<audio controls preload=\"metadata\" src=\"{escape(audio_src, quote=True)}\"></audio>",
                    f"<p><a href=\"{escape(audio_src, quote=True)}\">{escape(copy['open_audio'])}</a></p>",
                ]
            )
        else:
            lines.append(f"<div class=\"missing\">{escape(copy['audio_missing'])}</div>")
        lines.extend(
            [
                f"<p class=\"note\">{escape(note)}</p>",
                "<div class=\"choose-row\">",
                (
                    f"<label class=\"choose-pill\"><input type=\"radio\" "
                    f"name=\"selection-{escape(segment_id, quote=True)}\" "
                    f"data-selection-field value=\"{escape(variant_id, quote=True)}\""
                    f"{' checked' if selected else ''}>"
                    f"<span>{escape(copy['use_this_take'])}</span></label>"
                ),
                "</div>",
                (
                    f"<textarea class=\"review-note{' is-hidden' if not selected and not review_notes else ''}\" "
                    f"data-selection-note placeholder=\"{escape(copy['notes_placeholder'], quote=True)}\">"
                    f"{escape(review_notes)}</textarea>"
                ),
                "</article>",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _tts_decision_class(decision: str) -> str:
        normalized = (decision or "UNREVIEWED").lower()
        if normalized in {"approved", "keep_reference"}:
            return "approved"
        if normalized in {"needs_review", "regenerate"}:
            return "regenerate"
        if normalized == "rejected":
            return "rejected"
        return "unreviewed"

    @staticmethod
    def _comparison_script(copy: dict[str, str]) -> str:
        script = f"""
<div class=\"toast\" data-toast><strong>{escape(copy['toast_title'])}</strong><span>{escape(copy['toast_body'])}</span></div>
<script>
(() => {{
  const storageKey = `tts-segment-lab-review:${{location.pathname}}`;
  const segmentCards = Array.from(document.querySelectorAll('[data-segment-card]'));
  const variantCards = Array.from(document.querySelectorAll('[data-variant-card]'));
  const saveButtons = Array.from(document.querySelectorAll('[data-save-review]'));
  const status = document.querySelector('[data-save-status]');
  const exportPanel = document.querySelector('[data-export-panel]');
  const exportJson = document.querySelector('[data-export-json]');
  const toast = document.querySelector('[data-toast]');
  const runId = saveButtons[0]?.dataset.runId || document.title;
  const audioPlayers = Array.from(document.querySelectorAll('audio'));

  audioPlayers.forEach((audio) => {{
    audio.addEventListener('play', () => {{
      audioPlayers.forEach((other) => {{
        if (other !== audio) {{
          other.pause();
          other.currentTime = 0;
        }}
      }});
    }});
  }});

  document.querySelector('[data-scroll-top]')?.addEventListener('click', () => {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }});

  function storeDraft(payload) {{
    try {{ localStorage.setItem(storageKey, JSON.stringify(payload)); }} catch (_) {{}}
  }}

  async function copyText(text) {{
    try {{
      if (navigator.clipboard?.writeText) {{
        await navigator.clipboard.writeText(text);
        return true;
      }}
    }} catch (_) {{}}
    try {{
      const buffer = document.createElement('textarea');
      buffer.value = text;
      buffer.setAttribute('readonly', '');
      buffer.style.position = 'fixed';
      buffer.style.left = '-9999px';
      document.body.appendChild(buffer);
      buffer.select();
      const copied = document.execCommand('copy');
      buffer.remove();
      return copied;
    }} catch (_) {{
      return false;
    }}
  }}

  function refreshSegment(segment) {{
    const selected = segment.querySelector('[data-selection-field]:checked');
    const regenerateField = segment.querySelector('[data-regenerate-all-field]');
    const regenerateBlock = segment.querySelector('[data-regenerate-all]');
    const regenerateActive = Boolean(regenerateField?.checked);
    regenerateBlock?.classList.toggle('is-active', regenerateActive);
    segment.querySelectorAll('[data-variant-card]').forEach((card) => {{
      const variantSelected = selected && card.dataset.variantId === selected.value;
      const note = card.querySelector('[data-selection-note]');
      note?.classList.toggle('is-hidden', !variantSelected);
    }});
  }}

  function collectPayload() {{
    const selections = {{}};
    const annotations = {{}};
    const segment_actions = {{}};
    segmentCards.forEach((segment) => {{
      const segmentId = segment.dataset.segmentId;
      const selected = segment.querySelector('[data-selection-field]:checked')?.value || '';
      const regenerateSelected = Boolean(segment.querySelector('[data-regenerate-all-field]:checked'));
      if (regenerateSelected) {{
        const notes = segment.querySelector('[data-segment-action-notes]')?.value.trim() || '';
        segment_actions[segmentId] = {{
          decision: 'REGENERATE',
          issue_category: 'voice_review',
          notes,
          fix_target: notes,
          requires_user_review: true,
          user_decision: ''
        }};
        return;
      }}
      if (!selected) return;
      selections[segmentId] = selected;
      const card = segment.querySelector(`[data-variant-card][data-variant-id="${{CSS.escape(selected)}}"]`);
      const notes = card?.querySelector('[data-selection-note]')?.value.trim() || '';
      const decision = notes ? 'REGENERATE' : (selected.includes('reference') ? 'KEEP_REFERENCE' : 'APPROVED');
      annotations[segmentId] = {{
        [selected]: {{
        decision,
        reviewer: 'human',
        issue_category: notes ? 'voice_review' : '',
        notes,
        fix_target: notes,
        requires_user_review: Boolean(notes),
        user_decision: ''
        }}
      }};
    }});
    return {{
      version: '1.0',
      run_id: runId,
      saved_at: new Date().toISOString(),
      selection_policy: 'one_variant_per_segment',
      selections,
      segment_actions,
      annotations
    }};
  }}

  function applyPayload(payload) {{
    if (payload.selections) {{
      Object.entries(payload.selections).forEach(([segmentId, variantId]) => {{
        const field = document.querySelector(`[data-segment-card][data-segment-id="${{CSS.escape(segmentId)}}"] [data-selection-field][value="${{CSS.escape(variantId)}}"]`);
        if (field) field.checked = true;
      }});
    }}
    if (payload.segment_actions) {{
      Object.entries(payload.segment_actions).forEach(([segmentId, action]) => {{
        const segment = document.querySelector(`[data-segment-card][data-segment-id="${{CSS.escape(segmentId)}}"]`);
        const field = segment?.querySelector('[data-regenerate-all-field]');
        if (field) field.checked = true;
        const notes = segment?.querySelector('[data-segment-action-notes]');
        if (notes) notes.value = action.notes || action.fix_target || '';
      }});
    }}
    const annotations = payload.annotations || {{}};
    Object.entries(annotations).forEach(([segmentId, variants]) => {{
      Object.entries(variants || {{}}).forEach(([variantId, annotation]) => {{
        const card = document.querySelector(`[data-variant-card][data-segment-id="${{CSS.escape(segmentId)}}"][data-variant-id="${{CSS.escape(variantId)}}"]`);
        if (!card) return;
        const notes = card.querySelector('[data-selection-note]');
        if (notes) notes.value = annotation.notes || annotation.fix_target || '';
      }});
    }});
    segmentCards.forEach((segment) => refreshSegment(segment));
  }}

  function missingSelections() {{
    const missing = [];
    segmentCards.forEach((segment) => {{
      const hasSelection = Boolean(segment.querySelector('[data-selection-field]:checked'));
      const regenerateSelected = Boolean(segment.querySelector('[data-regenerate-all-field]:checked'));
      const regenerateNotes = segment.querySelector('[data-segment-action-notes]')?.value.trim() || '';
      const regenerateBlock = segment.querySelector('[data-regenerate-all]');
      const missingSelection = !hasSelection && !regenerateSelected;
      const missingRegenerateNote = regenerateSelected && !regenerateNotes;
      segment.classList.toggle('is-missing-selection', missingSelection);
      regenerateBlock?.classList.toggle('is-missing-note', missingRegenerateNote);
      if (missingSelection || missingRegenerateNote) missing.push(segment.dataset.segmentId);
    }});
    return missing;
  }}

  try {{
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
    if (saved.selections || saved.annotations || saved.segment_actions) applyPayload(saved);
  }} catch (_) {{}}

  segmentCards.forEach((segment) => refreshSegment(segment));
  document.addEventListener('input', (event) => {{
    if (!event.target.matches('[data-selection-field], [data-selection-note], [data-regenerate-all-field], [data-segment-action-notes]')) return;
    segmentCards.forEach((segment) => refreshSegment(segment));
    storeDraft(collectPayload());
  }});
  document.addEventListener('change', (event) => {{
    if (!event.target.matches('[data-selection-field], [data-selection-note], [data-regenerate-all-field], [data-segment-action-notes]')) return;
    segmentCards.forEach((segment) => refreshSegment(segment));
    storeDraft(collectPayload());
    missingSelections();
  }});

  async function submitReview(clickedButton) {{
    const missing = missingSelections();
    if (missing.length) {{
      if (status) status.textContent = `{copy['missing_selection_prefix']} ${{missing.join(', ')}}`;
      if (toast) {{
        toast.querySelector('strong').textContent = `{copy['missing_selection_title']}`;
        toast.querySelector('span').textContent = `{copy['missing_selection_body']}`;
        toast.classList.add('is-visible');
        window.clearTimeout(toast._timer);
        toast._timer = window.setTimeout(() => toast.classList.remove('is-visible'), 4200);
      }}
      return;
    }}
    const originalTexts = new Map(saveButtons.map((button) => [button, button.textContent]));
    saveButtons.forEach((button) => {{
      button.disabled = true;
      button.textContent = button.dataset.submittedLabel || 'Submitted';
    }});
    const payload = collectPayload();
    const jsonText = JSON.stringify(payload, null, 2);
    storeDraft(payload);
    const copied = await copyText(jsonText);
    if (exportPanel && exportJson) {{
      exportJson.value = jsonText;
      exportPanel.classList.toggle('is-visible', !copied);
    }}
    if (status) status.textContent = status.dataset.submittedText || 'Review submitted.';
    if (toast) {{
      toast.querySelector('strong').textContent = `{copy['toast_title']}`;
      toast.querySelector('span').textContent = `{copy['toast_body']}`;
      toast.classList.add('is-visible');
      window.clearTimeout(toast._timer);
      toast._timer = window.setTimeout(() => {{
        toast.classList.remove('is-visible');
        saveButtons.forEach((button) => {{
          button.disabled = false;
          button.textContent = originalTexts.get(button) || button.textContent;
        }});
      }}, 5200);
    }}
  }}

  saveButtons.forEach((button) => button.addEventListener('click', () => submitReview(button)));
}})();
</script>
""".strip()
        return script

    @staticmethod
    def _html_audio_src(audio: str, html_path: Path) -> str:
        audio_path = Path(audio).expanduser().resolve()
        try:
            return audio_path.relative_to(html_path.parent.resolve()).as_posix()
        except ValueError:
            return audio_path.as_uri()

    @classmethod
    def _review_language(cls, results: dict[str, Any]) -> str:
        requested = str(results.get("review_language") or "auto").lower()
        if requested in {"zh", "zh-cn", "cn", "chinese"}:
            return "zh"
        if requested in {"en", "en-us", "english"}:
            return "en"
        text = " ".join(str(segment.get("text", "")) for segment in results.get("segments", []))
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_words = len(re.findall(r"[A-Za-z]+", text))
        return "zh" if cjk_chars >= 10 and cjk_chars >= latin_words else "en"

    @staticmethod
    def _ui_copy(language: str) -> dict[str, str]:
        if language == "zh":
            return {
                "title": "TTS 音色对比",
                "description": "同一段旁白下的不同 provider、音色和参数候选。逐段试听后，提交评审给 Agent 继续处理。",
                "project": "项目",
                "segments": "片段",
                "variants": "候选",
                "selected": "已选",
                "review_status": "评审状态",
                "review_state_unreviewed": "待评审",
                "review_state_selected": "待提交",
                "review_state_recheck": "待复审",
                "review_state_needs_changes": "有待调整",
                "review_state_approved": "已通过",
                "save_review": "提交试听评审",
                "submitted_button": "已提交",
                "save_hint": "每段旁白选择一个最终候选；如果选中的候选还需要微调，请在建议里写清楚。",
                "submit_hint": "提交后会复制评审内容，粘贴发送给 Agent 即可继续处理。",
                "submitted_hint": "试听评审已复制到剪贴板。粘贴发送给 Agent 即可继续处理。",
                "export_title": "自动复制失败",
                "export_body": "请手动复制下面的评审内容，并发送给 Agent 继续处理。",
                "toast_title": "试听评审已保存",
                "toast_body": "评审内容已复制到剪贴板。粘贴发送给 Agent 即可继续处理。",
                "back_to_top": "返回顶部",
                "use_this_take": "选用这条",
                "variant_review": "微调建议",
                "decision_empty": "未评审",
                "decision_approved": "通过",
                "decision_keep_reference": "保留参考",
                "decision_regenerate": "需要重生成",
                "decision_rejected": "不采纳",
                "notes_placeholder": "可选：需要微调就写语气、重音、发音或速度建议；留空表示直接选用。",
                "regenerate_all": "以上都不选，重新生成新的",
                "regenerate_all_placeholder": "必填：请说明为什么这些都不合适，以及希望新音频怎么调整。",
                "missing_selection_prefix": "还有片段未选择最终候选:",
                "missing_selection_title": "请选择最终候选",
                "missing_selection_body": "每段旁白都需要选一条候选，或选择重新生成并填写意见。",
                "open_audio": "打开音频",
                "audio_missing": "尚未生成音频。先运行 generate，或检查 reference 音频路径。",
                "decision": "评审",
            }
        return {
            "title": "TTS Voice Comparison",
            "description": "Audition provider, voice, and parameter variants against the same narration text. Listen by segment, then submit the review to the Agent.",
            "project": "Project",
            "segments": "Segments",
            "variants": "Variants",
            "selected": "Selected",
            "review_status": "Review",
            "review_state_unreviewed": "Unreviewed",
            "review_state_selected": "Ready to submit",
            "review_state_recheck": "Needs recheck",
            "review_state_needs_changes": "Needs changes",
            "review_state_approved": "Approved",
            "save_review": "Submit audition review",
            "submitted_button": "Submitted",
            "save_hint": "Choose one final take per segment; add optional notes if the chosen take needs refinement.",
            "submit_hint": "Submitting copies the review content. Paste it to the Agent to continue.",
            "submitted_hint": "Audition review was copied to the clipboard. Paste it to the Agent to continue.",
            "export_title": "Automatic copy failed",
            "export_body": "Manually copy the review content below and send it to the Agent.",
            "toast_title": "Audition review saved",
            "toast_body": "Review content was copied to the clipboard. Paste it to the Agent to continue.",
            "back_to_top": "Back to top",
            "use_this_take": "Use this take",
            "variant_review": "Refinement note",
            "decision_empty": "Unreviewed",
            "decision_approved": "Pass",
            "decision_keep_reference": "Keep reference",
            "decision_regenerate": "Regenerate",
            "decision_rejected": "Reject",
            "notes_placeholder": "Optional: add tone, emphasis, pronunciation, or pace tweaks. Leave blank to use this take as-is.",
            "regenerate_all": "None of these; generate a new take",
            "regenerate_all_placeholder": "Required: explain why none work and how the next take should change.",
            "missing_selection_prefix": "Segments missing a final take:",
            "missing_selection_title": "Choose final takes",
            "missing_selection_body": "Each segment needs a selected take, or a regenerate-new choice with notes.",
            "open_audio": "Open audio",
            "audio_missing": "Audio has not been generated yet. Run generate or check the reference audio path.",
            "decision": "Review",
        }
