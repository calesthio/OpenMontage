"""Publish-stage final package helper for OpenMontage projects."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from tools.analysis.audio_probe import probe_duration
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _copy_file(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _as_file_uri(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).expanduser().resolve().as_uri()


def _human_size(size_bytes: Any) -> str:
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(size_bytes)} B"


class PublishPackager(BaseTool):
    name = "publish_packager"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publishing"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffprobe"]
    install_instructions = (
        "Install FFmpeg (includes ffprobe). FFmpeg itself is only required when "
        "cover_mode='replace_first_frame'."
    )

    capabilities = [
        "package_final_video",
        "copy_cover_asset",
        "replace_video_first_frame_with_cover",
        "write_final_package_manifest",
        "create_final_package_review_page",
        "verify_duration_delta",
        "verify_audio_is_not_silent",
        "verify_timing_qa_reference",
    ]
    best_for = [
        "turning an approved render into a publish-ready final package",
        "recording checksums and source paths for final deliverables",
        "making a cover image become the first visible frame without shifting audio",
    ]
    not_good_for = [
        "deciding the creative concept for a cover",
        "publishing to external platforms",
        "replacing project or version tracking",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["package", "review", "annotate"],
                "default": "package",
                "description": "package creates the final package; review creates a local confirmation page; annotate optionally records explicit package review JSON.",
            },
            "video_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "manifest_path": {
                "type": "string",
                "description": "Path to final_package_manifest.json for review/annotate operations.",
            },
            "review_output_dir": {
                "type": "string",
                "description": "Directory for final package review artifacts.",
            },
            "run_id": {"type": "string"},
            "language": {
                "type": "string",
                "enum": ["auto", "en", "zh"],
                "default": "auto",
                "description": "Review UI language. auto detects from script, captions, and package metadata.",
            },
            "review_payload": {
                "type": "object",
                "description": "Review JSON pasted back from the generated review page.",
            },
            "annotations_path": {
                "type": "string",
                "description": "Path to review JSON pasted back from the generated review page.",
            },
            "review_notes_output_path": {
                "type": "string",
                "description": "Optional output path for recorded review notes.",
            },
            "project_id": {"type": "string"},
            "variant_id": {"type": "string"},
            "channel": {"type": "string"},
            "cover_path": {
                "type": "string",
                "description": "Optional poster/cover image to copy into the package.",
            },
            "cover_source_kind": {
                "type": "string",
                "enum": [
                    "rendered_frame",
                    "generated_image",
                    "generated_video_frame",
                    "source_footage_frame",
                    "manual_design",
                    "unknown",
                ],
                "default": "unknown",
                "description": "Where the cover asset came from; useful for model-generated or manual covers.",
            },
            "cover_generator": {
                "type": "object",
                "description": "Optional cover provenance, such as provider/model/prompt id.",
            },
            "cover_mode": {
                "type": "string",
                "enum": ["none", "replace_first_frame"],
                "default": "none",
                "description": "replace_first_frame swaps only the first video frame and keeps original audio timing.",
            },
            "script_path": {
                "type": "string",
                "description": "Optional script JSON. cover_direction is copied from it when present.",
            },
            "extra_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "role"],
                    "properties": {
                        "path": {"type": "string"},
                        "role": {"type": "string"},
                        "label": {
                            "type": "string",
                            "description": "Optional human-friendly label for the package review page.",
                        },
                    },
                    "additionalProperties": False,
                },
                "description": "Optional sidecar files, such as subtitles, review notes, or metadata.",
            },
            "reference_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "role"],
                    "properties": {
                        "path": {"type": "string"},
                        "role": {"type": "string"},
                        "label": {
                            "type": "string",
                            "description": "Optional human-friendly label for the package review page.",
                        },
                    },
                    "additionalProperties": False,
                },
                "description": "Optional local reference pages/files that should remain at their original path, such as HTML review pages with adjacent assets.",
            },
            "duration_tolerance_seconds": {
                "type": "number",
                "default": 0.15,
                "description": "Allowed duration delta after packaging.",
            },
            "audio_min_mean_volume_db": {
                "type": "number",
                "default": -60.0,
                "description": "Minimum allowed mean volume when an audio stream exists. Lower values are treated as effectively silent.",
            },
            "require_timing_qa": {
                "type": "boolean",
                "default": False,
                "description": "Require a visual timing QA reference file/page before final packaging can pass.",
            },
            "overwrite": {"type": "boolean", "default": False},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = [
        "video_path",
        "output_dir",
        "cover_path",
        "cover_mode",
        "variant_id",
    ]
    side_effects = ["writes final package files and manifest JSON"]
    user_visible_verification = [
        "Open the packaged video or final package review page and confirm the first frame, subtitles, audio sync, and included sidecars.",
        "If the package contents are wrong, tell the agent what to fix and rerun packaging.",
    ]

    def get_status(self) -> ToolStatus:
        if shutil.which("ffprobe"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "package")
        if operation == "review":
            manifest_path = self._manifest_path(inputs)
            review_dir = self._review_output_dir(inputs, manifest_path)
            return {
                "tool": self.name,
                "operation": operation,
                "estimated_cost_usd": 0.0,
                "estimated_runtime_seconds": 1.0,
                "status": self.get_status().value,
                "would_execute": True,
                "would_write": [
                    str(review_dir / "final_package_review.json"),
                    str(review_dir / "final_package_review.md"),
                    str(review_dir / "final_package_review.html"),
                ],
            }
        if operation == "annotate":
            manifest_path = self._manifest_path(inputs)
            return {
                "tool": self.name,
                "operation": operation,
                "estimated_cost_usd": 0.0,
                "estimated_runtime_seconds": 1.0,
                "status": self.get_status().value,
                "would_execute": True,
                "would_write": [
                    str(self._review_notes_output_path(inputs, manifest_path)),
                ],
            }
        cover_mode = inputs.get("cover_mode", "none")
        return {
            "tool": self.name,
            "operation": operation,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
            "would_write": [
                str(Path(inputs["output_dir"]).expanduser() / "video" / Path(inputs["video_path"]).name),
                str(Path(inputs["output_dir"]).expanduser() / "final_package_manifest.json"),
            ],
            "requires_ffmpeg": cover_mode == "replace_first_frame",
        }

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0 if inputs.get("cover_mode") == "replace_first_frame" else 2.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            operation = inputs.get("operation", "package")
            if operation == "package":
                result = self._package(inputs)
            elif operation == "review":
                result = self._review(inputs)
            elif operation == "annotate":
                result = self._annotate(inputs)
            else:
                result = ToolResult(success=False, error=f"Unsupported operation: {operation}")
        except Exception as exc:
            result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _package(self, inputs: dict[str, Any]) -> ToolResult:
        if not inputs.get("video_path"):
            return ToolResult(success=False, error="video_path is required for package")
        if not inputs.get("output_dir"):
            return ToolResult(success=False, error="output_dir is required for package")
        video_path = Path(inputs["video_path"]).expanduser().resolve()
        output_dir = Path(inputs["output_dir"]).expanduser().resolve()
        cover_path = (
            Path(inputs["cover_path"]).expanduser().resolve()
            if inputs.get("cover_path")
            else None
        )
        cover_direction, cover_policy = self._cover_metadata(inputs.get("script_path"))
        cover_mode = inputs.get("cover_mode") or (
            cover_policy or {}
        ).get("first_frame_mode", "none")
        overwrite = bool(inputs.get("overwrite", False))
        tolerance = float(inputs.get("duration_tolerance_seconds", 0.15))
        audio_threshold = float(inputs.get("audio_min_mean_volume_db", -60.0))
        require_timing_qa = bool(inputs.get("require_timing_qa", False))

        if not video_path.exists():
            return ToolResult(success=False, error=f"Video not found: {video_path}")
        if cover_mode == "replace_first_frame" and not cover_path:
            return ToolResult(
                success=False,
                error="cover_path is required when cover_mode='replace_first_frame'",
            )
        if cover_path and not cover_path.exists():
            return ToolResult(success=False, error=f"Cover not found: {cover_path}")
        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            return ToolResult(
                success=False,
                error=f"Output directory is not empty: {output_dir}. Pass overwrite=true.",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        video_out = output_dir / "video" / video_path.name
        cover_out = output_dir / "cover" / cover_path.name if cover_path else None

        source_duration = probe_duration(video_path)
        if cover_mode == "replace_first_frame":
            video_out = video_out.with_name(f"{video_out.stem}-cover-first-frame{video_out.suffix}")
            self._replace_first_frame(video_path, cover_path, video_out)
        else:
            _copy_file(video_path, video_out)

        if cover_path and cover_out:
            _copy_file(cover_path, cover_out)

        files = [_file_entry(video_out, "video")]
        if cover_out:
            files.append(_file_entry(cover_out, "cover"))

        for item in inputs.get("extra_files", []) or []:
            src = Path(item["path"]).expanduser().resolve()
            if not src.exists():
                return ToolResult(success=False, error=f"Extra file not found: {src}")
            dst = output_dir / "sidecars" / src.name
            _copy_file(src, dst)
            entry = _file_entry(dst, item["role"])
            if item.get("label"):
                entry["label"] = item["label"]
            files.append(entry)

        references = []
        for item in inputs.get("reference_files", []) or []:
            src = Path(item["path"]).expanduser().resolve()
            if not src.exists():
                return ToolResult(success=False, error=f"Reference file not found: {src}")
            entry = _file_entry(src, item["role"])
            if item.get("label"):
                entry["label"] = item["label"]
            references.append(entry)

        package_duration = probe_duration(video_out)
        duration_delta = (
            round(package_duration - source_duration, 3)
            if package_duration is not None and source_duration is not None
            else None
        )
        warnings: list[str] = []
        if duration_delta is not None and abs(duration_delta) > tolerance:
            warnings.append(
                f"Duration delta {duration_delta}s exceeds tolerance {tolerance}s"
            )
        audio_check = self._audio_loudness_check(video_out, audio_threshold)
        if audio_check.get("status") == "failed":
            warnings.append(str(audio_check.get("message") or "Audio loudness check failed"))
        timing_qa_check = self._timing_qa_check(
            files,
            references,
            required=require_timing_qa,
        )
        if timing_qa_check.get("status") == "missing_required":
            warnings.append(str(timing_qa_check["message"]))

        manifest: dict[str, Any] = {
            "version": "1.0",
            "created_at": _now(),
            "package_dir": str(output_dir),
            "video": {
                "source_path": str(video_path),
                "package_path": str(video_out),
                "duration_seconds": package_duration,
                "source_duration_seconds": source_duration,
                "duration_delta_seconds": duration_delta,
                "cover_first_frame": cover_mode == "replace_first_frame",
                "cover_mode": cover_mode,
                "first_frame_verified": None,
            },
            "files": files,
            "references": references,
            "verification": {
                "duration_tolerance_seconds": tolerance,
                "audio_min_mean_volume_db": audio_threshold,
                "audio": audio_check,
                "timing_qa": timing_qa_check,
                "passed": not warnings,
                "warnings": warnings,
            },
        }
        for key in ("project_id", "variant_id", "channel"):
            if inputs.get(key):
                manifest[key] = inputs[key]
        if cover_direction:
            manifest["cover_direction"] = cover_direction
        if cover_policy:
            manifest["cover_policy"] = cover_policy
        if cover_out:
            manifest["cover"] = {
                "source_path": str(cover_path),
                "package_path": str(cover_out),
                "role": (
                    "poster_and_first_frame"
                    if cover_mode == "replace_first_frame"
                    else "poster"
                ),
                "source_kind": inputs.get("cover_source_kind", "unknown"),
            }
            if inputs.get("cover_generator"):
                manifest["cover"]["generator"] = inputs["cover_generator"]

        summary_path = output_dir / "FINAL_PACKAGE.md"
        summary_path.write_text(self._package_summary_markdown(manifest), encoding="utf-8")
        files.append(_file_entry(summary_path, "final_package_summary"))
        manifest["files"] = files

        manifest_path = output_dir / "final_package_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return ToolResult(
            success=not warnings,
            data=manifest,
            artifacts=[str(output_dir), str(manifest_path)],
            error="; ".join(warnings) if warnings else None,
        )

    def _package_summary_markdown(self, manifest: dict[str, Any]) -> str:
        lines = [
            "# Final Package",
            "",
            f"- Project: `{manifest.get('project_id') or ''}`",
            f"- Variant: `{manifest.get('variant_id') or ''}`",
            f"- Channel: `{manifest.get('channel') or ''}`",
            f"- Package directory: `{manifest.get('package_dir') or ''}`",
            f"- Created at: `{manifest.get('created_at') or ''}`",
            "",
            "## Video",
            "",
            f"- Source: `{(manifest.get('video') or {}).get('source_path') or ''}`",
            f"- Packaged: `{(manifest.get('video') or {}).get('package_path') or ''}`",
            f"- Duration: `{(manifest.get('video') or {}).get('duration_seconds')}`",
            f"- Cover frame written in package: `{(manifest.get('video') or {}).get('cover_first_frame')}`",
            "",
        ]
        cover = manifest.get("cover") or {}
        if cover:
            lines.extend(
                [
                    "## Cover",
                    "",
                    f"- Source: `{cover.get('source_path') or ''}`",
                    f"- Packaged: `{cover.get('package_path') or ''}`",
                    f"- Role: `{cover.get('role') or ''}`",
                    f"- Source kind: `{cover.get('source_kind') or ''}`",
                    "",
                ]
            )
        lines.extend(["## Files", ""])
        for item in manifest.get("files") or []:
            lines.append(
                f"- `{item.get('role')}` `{item.get('path')}` "
                f"({item.get('size_bytes')} bytes, sha256 `{item.get('sha256')}`)"
            )
        references = manifest.get("references") or []
        if references:
            lines.extend(["", "## Reference Pages", ""])
            for item in references:
                lines.append(
                    f"- `{item.get('role')}` `{item.get('path')}` "
                    f"({item.get('size_bytes')} bytes, sha256 `{item.get('sha256')}`)"
                )
        warnings = (manifest.get("verification") or {}).get("warnings") or []
        lines.extend(
            [
                "",
                "## Verification",
                "",
                f"- Passed: `{(manifest.get('verification') or {}).get('passed')}`",
                f"- Warnings: `{'; '.join(warnings) if warnings else 'none'}`",
            ]
        )
        audio = (manifest.get("verification") or {}).get("audio") or {}
        if audio:
            lines.extend(
                [
                    f"- Audio check: `{audio.get('status')}`",
                    f"- Audio mean volume: `{audio.get('mean_volume_db')}`",
                    f"- Audio max volume: `{audio.get('max_volume_db')}`",
                ]
            )
        timing_qa = (manifest.get("verification") or {}).get("timing_qa") or {}
        if timing_qa:
            lines.extend(
                [
                    f"- Timing QA: `{timing_qa.get('status')}`",
                    f"- Timing QA references: `{timing_qa.get('reference_count')}`",
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def _manifest_path(self, inputs: dict[str, Any]) -> Path:
        if inputs.get("manifest_path"):
            return Path(inputs["manifest_path"]).expanduser().resolve()
        if inputs.get("output_dir"):
            return (
                Path(inputs["output_dir"]).expanduser().resolve()
                / "final_package_manifest.json"
            )
        raise ValueError("manifest_path or output_dir is required")

    def _review_output_dir(self, inputs: dict[str, Any], manifest_path: Path) -> Path:
        if inputs.get("review_output_dir"):
            return Path(inputs["review_output_dir"]).expanduser().resolve()
        return manifest_path.parent / "final-package-review"

    def _review_notes_output_path(
        self, inputs: dict[str, Any], manifest_path: Path
    ) -> Path:
        if inputs.get("review_notes_output_path"):
            return Path(inputs["review_notes_output_path"]).expanduser().resolve()
        return manifest_path.with_name("final_package_review_notes.json")

    def _read_manifest(self, manifest_path: Path) -> dict[str, Any]:
        if not manifest_path.exists():
            raise FileNotFoundError(f"Final package manifest not found: {manifest_path}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _review_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("review_payload"):
            return dict(inputs["review_payload"])
        if inputs.get("annotations_path"):
            path = Path(inputs["annotations_path"]).expanduser().resolve()
            return json.loads(path.read_text(encoding="utf-8"))
        raise ValueError("review_payload or annotations_path is required for annotate")

    def _review(self, inputs: dict[str, Any]) -> ToolResult:
        manifest_path = self._manifest_path(inputs)
        manifest = self._read_manifest(manifest_path)
        review_dir = self._review_output_dir(inputs, manifest_path)
        review_dir.mkdir(parents=True, exist_ok=True)
        language = self._detect_review_language(manifest, inputs)
        run_id = inputs.get("run_id") or self._default_review_run_id(manifest)
        review_data = {
            "version": "1.0",
            "operation": "review",
            "run_id": run_id,
            "created_at": _now(),
            "language": language,
            "manifest_path": str(manifest_path),
            "package_dir": manifest.get("package_dir"),
            "project_id": manifest.get("project_id"),
            "variant_id": manifest.get("variant_id"),
            "channel": manifest.get("channel"),
            "video": manifest.get("video", {}),
            "cover": manifest.get("cover", {}),
            "files": manifest.get("files", []),
            "references": manifest.get("references", []),
            "verification": manifest.get("verification", {}),
            "cover_direction": manifest.get("cover_direction"),
            "cover_policy": manifest.get("cover_policy"),
            "review_state": self._review_state(manifest),
        }
        json_path = review_dir / "final_package_review.json"
        md_path = review_dir / "final_package_review.md"
        html_path = review_dir / "final_package_review.html"
        json_path.write_text(
            json.dumps(review_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        md_path.write_text(self._review_markdown(review_data), encoding="utf-8")
        html_path.write_text(self._review_html(review_data), encoding="utf-8")
        return ToolResult(
            success=True,
            data={
                "operation": "review",
                "run_id": run_id,
                "language": language,
                "review_json": str(json_path),
                "review_markdown": str(md_path),
                "review_html": str(html_path),
                "next_step": "Open final_package_review.html. If the package is wrong, tell the agent what to adjust and rerun packaging.",
            },
            artifacts=[str(json_path), str(md_path), str(html_path)],
        )

    def _annotate(self, inputs: dict[str, Any]) -> ToolResult:
        payload = self._review_payload(inputs)
        manifest_path = (
            Path(payload.get("manifest_path")).expanduser().resolve()
            if payload.get("manifest_path")
            else self._manifest_path(inputs)
        )
        manifest = self._read_manifest(manifest_path)
        decision = str(payload.get("decision") or "UNREVIEWED").upper()
        notes = str(payload.get("notes") or "")
        review_complete = decision == "APPROVED"
        if decision == "APPROVED":
            next_operation = "deliver_or_publish"
        elif decision == "WRONG_PACKAGE":
            next_operation = "rebuild_package_inputs"
        else:
            next_operation = "repackage_final"

        review_notes = {
            "version": "1.0",
            "run_id": payload.get("run_id") or self._default_review_run_id(manifest),
            "saved_at": _now(),
            "manifest_path": str(manifest_path),
            "project_id": manifest.get("project_id"),
            "variant_id": manifest.get("variant_id"),
            "channel": manifest.get("channel"),
            "decision": decision,
            "notes": notes,
            "reviewer": "human",
            "review_complete": review_complete,
            "next_operation": next_operation,
            "package": {
                "package_dir": manifest.get("package_dir"),
                "video_path": (manifest.get("video") or {}).get("package_path"),
                "cover_path": (manifest.get("cover") or {}).get("package_path"),
                "verification_passed": (manifest.get("verification") or {}).get("passed"),
            },
            "package_manifest": str(manifest_path),
            "review_payload": payload,
        }
        output_path = self._review_notes_output_path(inputs, manifest_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(review_notes, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        md_path = output_path.with_suffix(".md")
        md_path.write_text(self._annotated_markdown(review_notes), encoding="utf-8")
        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "decision": decision,
                "review_complete": review_complete,
                "next_operation": next_operation,
                "review_notes": str(output_path),
                "review_markdown": str(md_path),
                "package_manifest": str(manifest_path),
            },
            artifacts=[str(output_path), str(md_path)],
        )

    def _default_review_run_id(self, manifest: dict[str, Any]) -> str:
        parts = [
            manifest.get("project_id") or "project",
            manifest.get("channel") or "default",
            manifest.get("variant_id") or "final",
            "package-review",
        ]
        return "-".join(self._slug(str(part)) for part in parts if part)

    @staticmethod
    def _slug(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or "item"

    def _review_state(self, manifest: dict[str, Any]) -> dict[str, Any]:
        verification = manifest.get("verification") or {}
        warnings = verification.get("warnings") or []
        if warnings or verification.get("passed") is False:
            state = "needs_check"
        else:
            state = "ready_for_review"
        return {
            "state": state,
            "file_count": len(manifest.get("files") or []),
            "has_cover": bool(manifest.get("cover")),
            "cover_first_frame": bool((manifest.get("video") or {}).get("cover_first_frame")),
            "verification_passed": verification.get("passed"),
            "warning_count": len(warnings),
        }

    def _detect_review_language(
        self, manifest: dict[str, Any], inputs: dict[str, Any]
    ) -> str:
        requested = str(inputs.get("language") or "auto").lower()
        if requested in {"zh", "en"}:
            return requested
        text_parts = [
            manifest.get("project_id") or "",
            manifest.get("variant_id") or "",
            manifest.get("channel") or "",
            json.dumps(manifest.get("cover_direction") or {}, ensure_ascii=False),
            json.dumps(manifest.get("cover_policy") or {}, ensure_ascii=False),
        ]
        for file_info in (manifest.get("files") or []) + (manifest.get("references") or []):
            role = str(file_info.get("role") or "").lower()
            if role in {"captions", "subtitles", "script", "transcript", "narration_map"}:
                path = Path(str(file_info.get("path") or "")).expanduser()
                if path.exists() and path.stat().st_size <= 1024 * 1024:
                    try:
                        text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
                    except OSError:
                        pass
        merged = "\n".join(text_parts)
        return "zh" if re.search(r"[\u4e00-\u9fff]", merged) else "en"

    def _review_labels(self, language: str) -> dict[str, str]:
        if language == "zh":
            return {
                "title": "最终交付包确认",
                "description": "检查最终视频、封面、附属文件和校验结果。如果内容不对，直接告诉 Agent 需要调整哪里。",
                "project": "项目",
                "variant": "版本",
                "channel": "渠道",
                "state": "状态",
                "video": "最终视频",
                "cover": "封面",
                "files": "交付文件",
                "references": "相关页面",
                "verification": "校验结果",
                "cover_policy": "封面策略",
                "confirm_title": "打包内容确认",
                "wrong_package": "打包目标不准确",
                "confirm_hint": "如果发现视频、封面或附属文件不对，直接告诉 Agent 需要调整哪里，它会重新打包。",
                "back_top": "返回顶部",
                "path": "路径",
                "copy_path": "复制路径",
                "path_copied": "路径已复制",
                "role": "角色",
                "size": "大小",
                "sha": "SHA-256",
                "passed": "通过",
                "duration": "时长",
                "cover_first_frame": "封面帧",
                "warnings": "警告",
                "audio": "音频",
                "audio_mean": "平均音量",
                "timing_qa": "Timing QA",
                "none": "无",
                "no_cover_policy": "未记录封面策略。若脚本 JSON 提供 cover_policy 或 cover_direction，后续会在这里展示。",
                "yes": "是",
                "no": "否",
                "ready_for_review": "待确认",
                "needs_check": "需检查",
            }
        return {
            "title": "Final Package Confirmation",
            "description": "Check the final video, cover, sidecar files, and verification result. If anything is wrong, tell the Agent what to adjust.",
            "project": "Project",
            "variant": "Variant",
            "channel": "Channel",
            "state": "State",
            "video": "Final video",
            "cover": "Cover",
                "files": "Package files",
                "references": "Reference pages",
                "verification": "Verification",
            "cover_policy": "Cover policy",
            "confirm_title": "Package content check",
            "wrong_package": "Wrong package target",
            "confirm_hint": "If the video, cover, or sidecar files are wrong, tell the Agent what to adjust and it will repackage.",
            "back_top": "Back to top",
            "path": "Path",
            "copy_path": "Copy path",
            "path_copied": "Path copied",
            "role": "Role",
            "size": "Size",
            "sha": "SHA-256",
            "passed": "Passed",
            "duration": "Duration",
            "cover_first_frame": "Cover frame",
            "warnings": "Warnings",
            "audio": "Audio",
            "audio_mean": "Mean volume",
            "timing_qa": "Timing QA",
            "none": "None",
            "no_cover_policy": "No cover policy was recorded. Future packages will show cover_policy or cover_direction here when the script JSON provides it.",
            "yes": "Yes",
            "no": "No",
            "ready_for_review": "Ready for review",
            "needs_check": "Needs check",
        }

    def _role_label(self, role: str, language: str) -> str:
        labels = {
            "zh": {
                "video": "最终视频",
                "cover": "封面",
                "captions": "字幕",
                "subtitles": "字幕",
                "script": "脚本",
                "transcript": "文稿",
                "visual_timing_review": "Timing QA",
                "narration_map": "旁白记录",
                "archive_manifest": "归档说明",
                "final_package_summary": "交付包说明",
                "visual_timing_review_page": "Timing QA 页面",
                "tts_segment_review_page": "旁白试听页面",
                "narration_review_page": "旁白页面",
                "variant_review_notes": "版本评审",
                "final_package_review_notes": "交付评审",
            },
            "en": {
                "video": "Video",
                "cover": "Cover",
                "captions": "Captions",
                "subtitles": "Subtitles",
                "script": "Script",
                "transcript": "Transcript",
                "visual_timing_review": "Timing QA",
                "narration_map": "Narration map",
                "archive_manifest": "Archive manifest",
                "final_package_summary": "Package summary",
                "visual_timing_review_page": "Timing QA page",
                "tts_segment_review_page": "Narration audition page",
                "narration_review_page": "Narration page",
                "variant_review_notes": "Variant review",
                "final_package_review_notes": "Package review",
            },
        }
        return labels.get(language, labels["en"]).get(role, role)

    def _state_label(self, state: str, labels: dict[str, str]) -> str:
        return labels.get(state, state)

    def _bool_label(self, value: Any, labels: dict[str, str]) -> str:
        if value is True:
            return labels["yes"]
        if value is False:
            return labels["no"]
        return labels["none"]

    def _review_markdown(self, review_data: dict[str, Any]) -> str:
        lines = [
            f"# {self._review_labels(review_data.get('language', 'en'))['title']}: {review_data.get('run_id')}",
            "",
            f"- Project: `{review_data.get('project_id') or ''}`",
            f"- Variant: `{review_data.get('variant_id') or ''}`",
            f"- Channel: `{review_data.get('channel') or ''}`",
            f"- Manifest: `{review_data.get('manifest_path')}`",
            "",
            "## Files",
        ]
        for item in review_data.get("files") or []:
            lines.append(
                f"- `{item.get('role')}`: `{item.get('path')}` ({item.get('size_bytes')} bytes)"
            )
        references = review_data.get("references") or []
        if references:
            lines.extend(["", "## References"])
            for item in references:
                lines.append(
                    f"- `{item.get('role')}`: `{item.get('path')}` ({item.get('size_bytes')} bytes)"
                )
        verification = review_data.get("verification") or {}
        timing_qa = verification.get("timing_qa") or {}
        lines.extend(
            [
                "",
                "## Verification",
                f"- Passed: `{verification.get('passed')}`",
                f"- Warnings: `{'; '.join(verification.get('warnings') or []) or 'none'}`",
                f"- Timing QA: `{timing_qa.get('status') or 'none'}`",
                "",
                "If the package contents are wrong, tell the agent what to adjust and rerun packaging.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _annotated_markdown(self, review_notes: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# Final Package Review Notes: {review_notes.get('run_id')}",
                "",
                f"- Decision: `{review_notes.get('decision')}`",
                f"- Review complete: `{review_notes.get('review_complete')}`",
                f"- Next operation: `{review_notes.get('next_operation')}`",
                f"- Package manifest: `{review_notes.get('package_manifest')}`",
                "",
                "## Notes",
                review_notes.get("notes") or "",
                "",
            ]
        )

    def _review_html(self, review_data: dict[str, Any]) -> str:
        language = review_data.get("language") or "en"
        labels = self._review_labels(language)
        payload = json.dumps(review_data, ensure_ascii=False)
        script_payload = (
            payload.replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )
        video = review_data.get("video") or {}
        cover = review_data.get("cover") or {}
        verification = review_data.get("verification") or {}
        video_src = _as_file_uri(video.get("package_path"))
        cover_src = _as_file_uri(cover.get("package_path"))
        warnings = verification.get("warnings") or []
        warning_text = "; ".join(str(item) for item in warnings) or labels["none"]
        audio = verification.get("audio") or {}
        timing_qa = verification.get("timing_qa") or {}
        audio_status = str(audio.get("status") or labels["none"])
        timing_qa_status = str(timing_qa.get("status") or labels["none"])
        mean_volume = audio.get("mean_volume_db")
        audio_mean_text = (
            f"{float(mean_volume):.1f} dB"
            if isinstance(mean_volume, (int, float))
            else labels["none"]
        )
        files_html = "\n".join(
            self._file_row_html(item, labels) for item in review_data.get("files") or []
        )
        references_html = "\n".join(
            self._file_row_html(item, labels) for item in review_data.get("references") or []
        )
        cover_policy = review_data.get("cover_policy") or {}
        cover_direction = review_data.get("cover_direction") or {}
        policy_text = json.dumps(
            {"cover_policy": cover_policy, "cover_direction": cover_direction},
            ensure_ascii=False,
            indent=2,
        )
        if not cover_policy and not cover_direction:
            policy_text = labels["no_cover_policy"]
        duration = video.get("duration_seconds")
        duration_text = f"{float(duration):.2f}s" if isinstance(duration, (int, float)) else labels["none"]
        return f"""<!doctype html>
<html lang="{escape(language)}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(labels["title"])}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #07111f;
  --panel: #101b2b;
  --panel2: #0b1423;
  --line: #29405f;
  --text: #eef6ff;
  --muted: #aab8cd;
  --cyan: #45d7ff;
  --green: #55d99f;
  --warn: #ffce4a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: radial-gradient(circle at 30% 0%, rgba(69,215,255,.13), transparent 34%), var(--bg);
  color: var(--text);
}}
main {{ width: min(1120px, calc(100vw - 48px)); margin: 0 auto; padding: 36px 0 80px; }}
.hero, .card {{
  border: 1px solid var(--line);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(18,31,49,.95), rgba(10,18,31,.94));
  box-shadow: 0 18px 60px rgba(0,0,0,.28);
}}
.hero {{ padding: 28px; margin-bottom: 24px; }}
h1 {{ margin: 0 0 10px; font-size: clamp(32px, 5vw, 54px); letter-spacing: 0; }}
p {{ color: var(--muted); line-height: 1.65; }}
.pills {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 22px; }}
.pill {{
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 10px 14px;
  color: var(--muted);
  background: rgba(255,255,255,.03);
}}
.pill strong {{ color: var(--text); }}
.grid {{ display: grid; grid-template-columns: 1.45fr .9fr; gap: 20px; align-items: start; }}
.card {{ padding: 22px; margin-bottom: 20px; }}
h2 {{ margin: 0 0 16px; font-size: 24px; letter-spacing: 0; }}
video, img.cover {{
  width: 100%;
  display: block;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,.12);
  background: #020712;
}}
video {{ max-height: 64vh; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
.metric {{
  min-height: 86px;
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 16px;
  padding: 14px;
  background: rgba(255,255,255,.035);
}}
.metric span {{
  display: block;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.35;
  margin-bottom: 10px;
}}
.metric strong {{
  display: block;
  color: var(--text);
  font-size: 22px;
  line-height: 1.2;
  overflow-wrap: anywhere;
}}
.metric.ok strong {{ color: var(--green); }}
.metric.warn strong {{ color: var(--warn); }}
table {{ width: 100%; border-collapse: collapse; color: var(--muted); }}
th, td {{ padding: 11px 8px; border-bottom: 1px solid rgba(255,255,255,.08); text-align: left; vertical-align: top; }}
th {{ color: var(--text); font-weight: 700; }}
td.path {{ overflow-wrap: anywhere; max-width: 420px; }}
pre {{
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--muted);
  background: rgba(0,0,0,.22);
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 14px;
  padding: 16px;
}}
button {{
  border: 0;
  border-radius: 999px;
  padding: 15px 24px;
  color: #06111f;
  font-weight: 800;
  font-size: 18px;
  background: linear-gradient(135deg, #62dcff, #54d68f);
  cursor: pointer;
}}
.hint {{ color: var(--muted); }}
.confirm-note {{
  border: 1px solid rgba(69,215,255,.32);
  border-radius: 16px;
  padding: 14px 16px;
  background: rgba(69,215,255,.1);
  color: var(--muted);
  line-height: 1.6;
}}
.copy-path {{
  margin-left: 8px;
  width: 30px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  border: 1px solid rgba(69,215,255,.28);
  border-radius: 50%;
  padding: 0;
  color: var(--cyan);
  background: rgba(69,215,255,.08);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  vertical-align: middle;
}}
.copy-path:hover {{
  border-color: rgba(69,215,255,.62);
  background: rgba(69,215,255,.16);
}}
.top-button {{
  position: fixed;
  right: 24px;
  bottom: 24px;
  display: none;
  z-index: 10;
}}
.top-button.show {{ display: inline-flex; }}
@media (max-width: 860px) {{
  main {{ width: min(100vw - 28px, 1120px); padding-top: 22px; }}
  .grid {{ grid-template-columns: 1fr; }}
  .metric-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<main id="top">
  <section class="hero">
    <h1>{escape(labels["title"])}</h1>
    <p>{escape(labels["description"])}</p>
    <div class="pills">
      <span class="pill">{escape(labels["project"])}: <strong>{escape(str(review_data.get("project_id") or ""))}</strong></span>
      <span class="pill">{escape(labels["variant"])}: <strong>{escape(str(review_data.get("variant_id") or ""))}</strong></span>
      <span class="pill">{escape(labels["channel"])}: <strong>{escape(str(review_data.get("channel") or ""))}</strong></span>
    </div>
  </section>

  <section class="grid">
    <div>
      <section class="card">
        <h2>{escape(labels["video"])}</h2>
        <video controls preload="metadata" src="{escape(video_src, quote=True)}"></video>
      </section>
      <section class="card">
        <h2>{escape(labels["files"])}</h2>
        <table>
          <thead><tr><th>{escape(labels["role"])}</th><th>{escape(labels["path"])}</th><th>{escape(labels["size"])}</th><th>{escape(labels["sha"])}</th></tr></thead>
          <tbody>{files_html}</tbody>
        </table>
      </section>
      {f'''<section class="card">
        <h2>{escape(labels["references"])}</h2>
        <table>
          <thead><tr><th>{escape(labels["role"])}</th><th>{escape(labels["path"])}</th><th>{escape(labels["size"])}</th><th>{escape(labels["sha"])}</th></tr></thead>
          <tbody>{references_html}</tbody>
        </table>
      </section>''' if references_html else ""}
    </div>
    <div>
      <section class="card">
        <h2>{escape(labels["cover"])}</h2>
        {f'<img class="cover" src="{escape(cover_src, quote=True)}" alt="cover" />' if cover_src else f'<p>{escape(labels["none"])}</p>'}
      </section>
      <section class="card">
        <h2>{escape(labels["verification"])}</h2>
        <div class="metric-grid">
          <div class="metric ok"><span>{escape(labels["passed"])}</span><strong>{escape(self._bool_label(verification.get("passed"), labels))}</strong></div>
          <div class="metric"><span>{escape(labels["duration"])}</span><strong>{escape(duration_text)}</strong></div>
          <div class="metric"><span>{escape(labels["cover_first_frame"])}</span><strong>{escape(self._bool_label(video.get("cover_first_frame"), labels))}</strong></div>
          <div class="metric"><span>{escape(labels["audio"])}</span><strong>{escape(audio_status)}</strong></div>
          <div class="metric"><span>{escape(labels["audio_mean"])}</span><strong>{escape(audio_mean_text)}</strong></div>
          <div class="metric"><span>{escape(labels["timing_qa"])}</span><strong>{escape(timing_qa_status)}</strong></div>
          <div class="metric warn"><span>{escape(labels["warnings"])}</span><strong>{escape(warning_text)}</strong></div>
        </div>
      </section>
      <section class="card">
        <h2>{escape(labels["cover_policy"])}</h2>
        <pre>{escape(policy_text)}</pre>
      </section>
      <section class="card">
        <h2>{escape(labels["confirm_title"])}</h2>
        <p class="confirm-note">{escape(labels["confirm_hint"])}</p>
      </section>
    </div>
  </section>
</main>
<button type="button" class="top-button" id="top-button">{escape(labels["back_top"])}</button>
<script id="review-data" type="application/json">{script_payload}</script>
<script>
(() => {{
  const reviewData = JSON.parse(document.getElementById('review-data').textContent);
  const pathCopied = {json.dumps(labels["path_copied"], ensure_ascii=False)};
  document.querySelectorAll('[data-copy-path]').forEach((button) => {{
    button.addEventListener('click', async () => {{
      const value = button.getAttribute('data-copy-path') || '';
      const original = button.textContent;
      try {{
        await navigator.clipboard.writeText(value);
        button.setAttribute('aria-label', pathCopied);
        button.textContent = '✓';
        setTimeout(() => {{
          button.textContent = original;
          button.setAttribute('aria-label', original);
        }}, 1400);
      }} catch (error) {{
        window.prompt('Copy path', value);
      }}
    }});
  }});
  const topButton = document.getElementById('top-button');
  window.addEventListener('scroll', () => {{
    topButton.classList.toggle('show', window.scrollY > 600);
  }});
  topButton.addEventListener('click', () => window.scrollTo({{ top: 0, behavior: 'smooth' }}));
}})();
</script>
</body>
</html>
"""

    def _file_row_html(self, item: dict[str, Any], labels: dict[str, str]) -> str:
        path = str(item.get("path") or "")
        uri = _as_file_uri(path) if path else ""
        file_name = Path(path).name if path else labels["none"]
        path_html = (
            f'<a href="{escape(uri, quote=True)}" title="{escape(path, quote=True)}">{escape(file_name)}</a>'
            f'<button type="button" class="copy-path" data-copy-path="{escape(path, quote=True)}" aria-label="{escape(labels["copy_path"], quote=True)}" title="{escape(labels["copy_path"], quote=True)}">⧉</button>'
            if uri
            else escape(file_name)
        )
        sha = str(item.get("sha256") or "")
        language = "zh" if labels.get("yes") == "是" else "en"
        role = str(item.get("role") or "")
        role_label = str(item.get("label") or self._role_label(role, language))
        return (
            "<tr>"
            f"<td>{escape(role_label)}</td>"
            f"<td class=\"path\">{path_html}</td>"
            f"<td>{escape(_human_size(item.get('size_bytes') or 0))}</td>"
            f"<td>{escape(sha[:12])}</td>"
            "</tr>"
        )

    def _cover_metadata(
        self, script_path: str | None
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if not script_path:
            return None, None
        path = Path(script_path).expanduser().resolve()
        if not path.exists():
            return None, None
        try:
            script = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None, None
        return script.get("cover_direction"), script.get("cover_policy")

    def _audio_loudness_check(self, video_path: Path, min_mean_volume_db: float) -> dict[str, Any]:
        ffprobe = shutil.which("ffprobe")
        ffmpeg = shutil.which("ffmpeg")
        if not ffprobe or not ffmpeg:
            return {
                "status": "skipped",
                "reason": "ffprobe or ffmpeg not found",
                "threshold_mean_volume_db": min_mean_volume_db,
            }

        try:
            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-select_streams",
                    "a",
                    "-show_streams",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            streams = json.loads(probe.stdout or "{}").get("streams") or []
        except Exception:
            return {
                "status": "skipped",
                "reason": "audio stream probe failed",
                "threshold_mean_volume_db": min_mean_volume_db,
            }
        if not streams:
            return {
                "status": "skipped",
                "reason": "no audio stream",
                "has_audio_stream": False,
                "threshold_mean_volume_db": min_mean_volume_db,
            }

        try:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-i",
                    str(video_path),
                    "-af",
                    "volumedetect",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "skipped",
                "reason": "volumedetect timed out",
                "has_audio_stream": True,
                "threshold_mean_volume_db": min_mean_volume_db,
            }

        stderr = result.stderr or ""
        mean_match = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", stderr)
        max_match = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", stderr)
        if not mean_match:
            return {
                "status": "skipped",
                "reason": "volumedetect did not report mean volume",
                "has_audio_stream": True,
                "threshold_mean_volume_db": min_mean_volume_db,
            }

        mean_volume = float(mean_match.group(1))
        max_volume = float(max_match.group(1)) if max_match else None
        passed = mean_volume > min_mean_volume_db
        check = {
            "status": "passed" if passed else "failed",
            "has_audio_stream": True,
            "mean_volume_db": mean_volume,
            "max_volume_db": max_volume,
            "threshold_mean_volume_db": min_mean_volume_db,
        }
        if not passed:
            check["message"] = (
                f"Audio mean volume {mean_volume} dB is at or below "
                f"threshold {min_mean_volume_db} dB; the packaged video may be silent."
            )
        return check

    def _timing_qa_check(
        self,
        files: list[dict[str, Any]],
        references: list[dict[str, Any]],
        *,
        required: bool,
    ) -> dict[str, Any]:
        timing_roles = {
            "visual_timing_review",
            "visual_timing_review_page",
            "visual_timing_annotated_review",
            "visual_timing_notes",
            "timing_qa",
            "timing_qa_page",
            "timing_qa_notes",
        }
        matches = [
            item
            for item in [*files, *references]
            if str(item.get("role") or "").lower() in timing_roles
        ]
        if matches:
            return {
                "status": "passed",
                "required": required,
                "reference_count": len(matches),
                "roles": [str(item.get("role") or "") for item in matches],
                "paths": [str(item.get("path") or "") for item in matches],
            }
        if required:
            return {
                "status": "missing_required",
                "required": True,
                "reference_count": 0,
                "message": "Timing QA reference is required before final packaging can pass.",
            }
        return {
            "status": "not_provided",
            "required": False,
            "reference_count": 0,
            "message": "No Timing QA reference was attached to this final package.",
        }

    def _replace_first_frame(self, video_path: Path, cover_path: Path, output_path: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")
        width, height, fps = self._video_info(video_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frame_seconds = 1 / fps
        filter_complex = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"trim=duration={frame_seconds},setpts=PTS-STARTPTS[cover];"
            f"[0:v]trim=start={frame_seconds},setpts=PTS-STARTPTS[tail];"
            f"[cover][tail]concat=n=2:v=1:a=0[v]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-loop",
            "1",
            "-i",
            str(cover_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)

    def _video_info(self, video_path: Path) -> tuple[int, int, float]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError("ffprobe not found on PATH")
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-select_streams",
                "v:0",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        width = int(stream.get("width") or 1920)
        height = int(stream.get("height") or 1080)
        fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
        try:
            numerator, denominator = fps_raw.split("/", 1)
            fps = float(numerator) / float(denominator)
        except Exception:
            fps = 30.0
        if fps <= 0:
            fps = 30.0
        return width, height, fps
