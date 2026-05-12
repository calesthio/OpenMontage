"""Segment-level TTS audition lab.

This tool sits before final narration generation. It creates controlled
voiceover samples for high-risk script segments, records the parameters used,
and writes a selection file that later asset generation can reuse.
"""

from __future__ import annotations

import json
import re
import time
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
        "voice_variant_selection",
    ]
    supports = {
        "dry_run": True,
        "provider_comparison": True,
        "selection_manifest": True,
        "timestamps_when_provider_supports_them": True,
    }
    best_for = [
        "auditioning narration before final asset generation",
        "comparing TTS providers and voices for sensitive script lines",
        "recording chosen voiceover variants for production reuse",
    ]
    not_good_for = [
        "objective speech-quality benchmarking",
        "large-scale MOS listening studies",
        "subtitle generation after narration is locked",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["dry_run", "generate", "select"], "default": "dry_run"},
            "manifest_path": {"type": "string"},
            "manifest": {"type": "object"},
            "results_path": {"type": "string"},
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
            "selection_path": {"type": "string"},
            "segments": {"type": "array"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True)
    idempotency_key_fields = ["operation", "manifest_path", "manifest", "selections"]
    side_effects = [
        "writes TTS audition audio samples",
        "writes per-variant provider metadata",
        "writes results.json and review.md",
        "writes selection.json in select mode",
        "calls configured TTS providers in generate mode",
    ]
    user_visible_verification = [
        "Listen to generated samples in review.md",
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
        self._write_json(results_path, results)
        review_path.write_text(self._review_markdown(results), encoding="utf-8")
        artifacts.extend([str(results_path), str(review_path)])

        return ToolResult(
            success=results["status"] != "completed-with-errors",
            data={
                "operation": results["operation"],
                "status": results["status"],
                "output_dir": str(output_dir),
                "results_path": str(results_path),
                "review_path": str(review_path),
                "segments": results["segments"],
            },
            artifacts=artifacts,
            error=None if results["status"] == "completed" else "One or more variants failed.",
        )

    def _select(self, inputs: dict[str, Any]) -> ToolResult:
        selections = inputs.get("selections")
        if not isinstance(selections, dict) or not selections:
            return ToolResult(success=False, error="select operation requires non-empty selections mapping")

        results_path = self._results_path(inputs)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        by_segment: dict[str, dict[str, Any]] = {}
        for segment in results.get("segments", []):
            by_segment[segment["id"]] = segment
            if segment.get("section_id"):
                by_segment[segment["section_id"]] = segment

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

    @staticmethod
    def _review_markdown(results: dict[str, Any]) -> str:
        lines = [
            f"# TTS Segment Lab Review: {results.get('run_id', '')}",
            "",
            f"- Project: `{results.get('project', '')}`",
            f"- Created: `{results.get('created_at', '')}`",
            f"- Status: `{results.get('status', '')}`",
            "",
        ]
        for segment in results.get("segments", []):
            lines.extend(
                [
                    f"## {segment.get('label') or segment['id']}",
                    "",
                    f"- Segment id: `{segment['id']}`",
                    f"- Section id: `{segment.get('section_id') or ''}`",
                    f"- Text: {segment.get('text', '')}",
                    "",
                    "| Variant | Provider | Duration | Audio | Note | Key Params |",
                    "|---|---|---:|---|---|---|",
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
                lines.append(
                    f"| `{variant['id']}` | `{provider}` | {duration_text} | {audio_link} | "
                    f"{variant.get('note', '')} | {key_params} |"
                )
            lines.append("")
        return "\n".join(lines)
