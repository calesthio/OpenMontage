"""Segment-level TTS audition lab.

This tool sits before final narration generation. It creates controlled
voiceover samples for high-risk script segments, records the parameters used,
and writes a selection file that later asset generation can reuse.
"""

from __future__ import annotations

import json
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
                "enum": ["dry_run", "generate", "analyze", "annotate", "select"],
                "default": "dry_run",
            },
            "manifest_path": {"type": "string"},
            "manifest": {"type": "object"},
            "results_path": {"type": "string"},
            "analysis_options": {"type": "object"},
            "annotations": {"type": ["object", "array"]},
            "selections": {"type": "object"},
            "output_path": {"type": "string"},
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
            "segments": {"type": "array"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True)
    idempotency_key_fields = ["operation", "manifest_path", "manifest", "analysis_options", "annotations", "selections"]
    side_effects = [
        "writes TTS audition audio samples",
        "writes per-variant provider metadata",
        "writes results.json, review.md, and compare.html",
        "writes audio_profile.json and analysis.md in analyze mode",
        "writes review_notes.json and review_annotated.md in annotate mode",
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
        annotations = inputs.get("annotations")
        if not annotations:
            return ToolResult(success=False, error="annotate operation requires non-empty annotations")

        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        annotated_results = deepcopy(results)
        by_segment = self._segment_lookup(annotated_results)
        applied_annotations = []

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

        summary = self._review_summary(annotated_results)
        review_notes = {
            "version": self.version,
            "tool": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "summary": summary,
            "annotations": applied_annotations,
        }

        output_path = Path(inputs.get("output_path") or results_path.with_name("review_notes.json"))
        review_path = output_path.with_name("review_annotated.md")
        annotated_results_path = output_path.with_name("results_annotated.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, review_notes)
        self._write_json(annotated_results_path, annotated_results)
        review_path.write_text(self._review_markdown(annotated_results), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "status": "completed",
                "results_path": str(annotated_results_path),
                "review_path": str(review_path),
                "review_notes_path": str(output_path),
                "summary": summary,
                "annotations": applied_annotations,
            },
            artifacts=[str(output_path), str(annotated_results_path), str(review_path)],
        )

    def _select(self, inputs: dict[str, Any]) -> ToolResult:
        selections = inputs.get("selections")
        if not isinstance(selections, dict) or not selections:
            return ToolResult(success=False, error="select operation requires non-empty selections mapping")

        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        by_segment = self._segment_lookup(results)

        selected_items = []
        for segment_key, variant_id in selections.items():
            segment = by_segment.get(segment_key)
            if not segment:
                return ToolResult(success=False, error=f"Unknown segment/section selection key: {segment_key}")
            variant = next((item for item in segment.get("variants", []) if item.get("id") == variant_id), None)
            if not variant:
                return ToolResult(success=False, error=f"Unknown variant {variant_id!r} for segment {segment_key!r}")
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

        selection = {
            "version": self.version,
            "tool": self.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "selections": selected_items,
        }
        output_path = Path(inputs.get("output_path") or results_path.with_name("selection.json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, selection)

        return ToolResult(
            success=True,
            data={
                "operation": "select",
                "status": "completed",
                "selection_path": str(output_path),
                "selection_count": len(selected_items),
                "selections": selected_items,
            },
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _segment_lookup(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
        by_segment: dict[str, dict[str, Any]] = {}
        for segment in results.get("segments", []):
            by_segment[segment["id"]] = segment
            if segment.get("section_id"):
                by_segment[segment["section_id"]] = segment
        return by_segment

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
.pill {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 999px;
  padding: 6px 12px;
  color: #dbe7fb;
  font-size: 13px;
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
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.missing {
  border: 1px dashed rgba(149,172,214,.28);
  color: #94a7c4;
  border-radius: 9px;
  padding: 10px 12px;
  font-size: 14px;
}
@media (max-width: 720px) {
  main { padding: 28px 16px 46px; }
  h1 { font-size: 25px; }
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
            f"<span class=\"pill\">{escape(copy['status'])}: {escape(str(results.get('status') or '-'))}</span>",
            "</div>",
            "</header>",
        ]

        for segment in results.get("segments", []):
            lines.extend(
                [
                    "<section class=\"segment\">",
                    f"<h2>{escape(str(segment.get('label') or segment.get('id') or ''))}</h2>",
                    f"<div class=\"text\">{escape(str(segment.get('text') or ''))}</div>",
                    "<div class=\"grid\">",
                ]
            )
            for variant in segment.get("variants", []):
                lines.append(cls._comparison_card_html(variant, html_path, copy))
            lines.extend(["</div>", "</section>"])

        lines.extend(["</main>", "</body>", "</html>"])
        return "\n".join(lines) + "\n"

    @classmethod
    def _comparison_card_html(cls, variant: dict[str, Any], html_path: Path, copy: dict[str, str]) -> str:
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
        decision = (variant.get("review") or {}).get("decision", "UNREVIEWED")

        lines = [
            "<article class=\"card\">",
            f"<h3>{escape(str(variant.get('id') or 'variant'))}</h3>",
            f"<div class=\"meta\">{escape(str(provider))} · {escape(str(voice))} · {escape(duration_text)}</div>",
        ]
        if audio and Path(audio).expanduser().exists():
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
                f"<div class=\"meta\">{escape(copy['decision'])}: {escape(str(decision))}</div>",
                "</article>",
            ]
        )
        return "\n".join(lines)

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
                "description": "同一段旁白下的不同 provider、音色和参数候选。逐段试听后，再把最终选择写入 selection.json。",
                "project": "项目",
                "segments": "片段",
                "variants": "候选",
                "status": "状态",
                "open_audio": "打开音频",
                "audio_missing": "尚未生成音频。先运行 generate，或检查 reference 音频路径。",
                "decision": "评审",
            }
        return {
            "title": "TTS Voice Comparison",
            "description": "Audition provider, voice, and parameter variants against the same narration text. Listen by segment before writing final choices to selection.json.",
            "project": "Project",
            "segments": "Segments",
            "variants": "Variants",
            "status": "Status",
            "open_audio": "Open audio",
            "audio_missing": "Audio has not been generated yet. Run generate or check the reference audio path.",
            "decision": "Review",
        }
