"""Lightweight deliverable variant registry for OpenMontage projects."""

from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

import jsonschema

from schemas.artifacts import load_schema
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


STATUSES = {"draft", "candidate", "approved", "rejected", "archived", "published"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _variant_index(manifest: dict[str, Any]) -> dict[str, int]:
    return {variant["id"]: i for i, variant in enumerate(manifest.get("variants", []))}


def _variant_summary(variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": variant["id"],
        "name": variant["name"],
        "status": variant["status"],
        "purpose": variant["purpose"],
        "created_at": variant["created_at"],
        "tags": variant.get("tags", []),
        "video": variant.get("outputs", {}).get("video"),
    }


class VariantManager(BaseTool):
    name = "variant_manager"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "project_management"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    capabilities = [
        "init_variant_manifest",
        "add_variant",
        "list_variants",
        "show_variant",
        "promote_variant",
        "archive_variant",
        "compare_variants",
        "create_variant_review_page",
        "apply_variant_review_payload",
        "validate_variant_manifest",
    ]
    best_for = [
        "tracking deliverable variants across one project",
        "recording which script/audio/caption/render inputs produced each output",
        "marking the current approved variant for named channels",
    ]
    not_good_for = [
        "storing large media blobs",
        "replacing review platforms or asset management systems",
        "automatically judging creative quality",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "manifest_path"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "init",
                    "add",
                    "list",
                    "show",
                    "promote",
                    "archive",
                    "compare",
                    "review",
                    "annotate",
                    "validate",
                ],
            },
            "manifest_path": {
                "type": "string",
                "description": "Path to variants.json or another variant manifest file.",
            },
            "project_id": {
                "type": "string",
                "description": "Project id for operation='init'.",
            },
            "overwrite": {
                "type": "boolean",
                "default": False,
                "description": "Allow init to replace an existing manifest.",
            },
            "variant": {
                "type": "object",
                "description": "Variant object for operation='add'.",
            },
            "variant_id": {
                "type": "string",
                "description": "Target variant id for show/promote/archive.",
            },
            "variant_a": {"type": "string"},
            "variant_b": {"type": "string"},
            "channel": {
                "type": "string",
                "default": "default",
                "description": "Current-channel key for promote, e.g. handoff_intro.",
            },
            "status": {
                "type": "string",
                "enum": sorted(STATUSES),
                "description": "Status filter for list or status to assign during promote.",
            },
            "purpose": {"type": "string", "description": "Purpose filter for list."},
            "tag": {"type": "string", "description": "Tag filter for list."},
            "include_archived": {
                "type": "boolean",
                "default": False,
                "description": "Include archived variants in list results.",
            },
            "update_existing": {
                "type": "boolean",
                "default": False,
                "description": "Allow add to update an existing variant id.",
            },
            "archive_reason": {"type": "string"},
            "output_dir": {
                "type": "string",
                "description": "Directory for review artifacts produced by operation='review'.",
            },
            "run_id": {
                "type": "string",
                "description": "Stable id for a review round. Defaults to project/channel/variant-review.",
            },
            "language": {
                "type": "string",
                "enum": ["auto", "en", "zh"],
                "default": "auto",
                "description": "UI language for review artifacts. auto detects from caption/subtitle artifacts.",
            },
            "review_payload": {
                "type": "object",
                "description": "Review JSON pasted back from a generated review page.",
            },
            "annotations_path": {
                "type": "string",
                "description": "Path to review JSON pasted back from a generated review page.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["operation", "manifest_path", "variant_id", "channel"]
    side_effects = [
        "writes variant manifest JSON for mutating operations",
        "writes local HTML/Markdown/JSON review artifacts for operation='review'",
    ]
    user_visible_verification = [
        "Review the manifest current channels and variant summaries before delivery",
    ]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        operation = inputs.get("operation")
        try:
            if not operation:
                result = ToolResult(success=False, error="operation is required")
            elif operation == "init":
                result = self._init(inputs)
            elif operation == "add":
                result = self._add(inputs)
            elif operation == "list":
                result = self._list(inputs)
            elif operation == "show":
                result = self._show(inputs)
            elif operation == "promote":
                result = self._promote(inputs)
            elif operation == "archive":
                result = self._archive(inputs)
            elif operation == "compare":
                result = self._compare(inputs)
            elif operation == "review":
                result = self._review(inputs)
            elif operation == "annotate":
                result = self._annotate(inputs)
            elif operation == "validate":
                result = self._validate(inputs)
            else:
                result = ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as exc:
            result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _manifest_path(self, inputs: dict[str, Any]) -> Path:
        return Path(inputs["manifest_path"]).expanduser().resolve()

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Variant manifest not found: {path}")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, path: Path, manifest: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        tmp.replace(path)

    def _check(self, manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        schema = load_schema("variant_manifest")
        try:
            jsonschema.validate(instance=manifest, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(exc.message)

        seen: set[str] = set()
        for variant in manifest.get("variants", []):
            vid = variant.get("id")
            if vid in seen:
                errors.append(f"Duplicate variant id: {vid}")
            seen.add(vid)

        for channel, variant_id in manifest.get("current", {}).items():
            if variant_id not in seen:
                errors.append(
                    f"Current channel {channel!r} points to missing variant {variant_id!r}"
                )
        return errors

    def _save_checked(self, path: Path, manifest: dict[str, Any]) -> ToolResult | None:
        errors = self._check(manifest)
        if errors:
            return ToolResult(success=False, error="; ".join(errors), data={"errors": errors})
        self._write(path, manifest)
        return None

    def _init(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        if path.exists() and not inputs.get("overwrite", False):
            return ToolResult(
                success=False,
                error=f"Manifest already exists: {path}. Pass overwrite=true to replace it.",
            )
        project_id = inputs.get("project_id")
        if not project_id:
            return ToolResult(success=False, error="project_id is required for init")
        manifest = {
            "version": "1.0",
            "project_id": project_id,
            "current": {},
            "variants": [],
        }
        self._write(path, manifest)
        return ToolResult(
            success=True,
            data={"operation": "init", "manifest_path": str(path), "manifest": manifest},
            artifacts=[str(path)],
        )

    def _add(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant = copy.deepcopy(inputs.get("variant") or {})
        if not variant:
            return ToolResult(success=False, error="variant is required for add")
        now = _now()
        variant.setdefault("status", "candidate")
        variant.setdefault("created_at", now)
        variant["updated_at"] = now
        variant.setdefault("inputs", {})
        variant.setdefault("outputs", {})
        variant.setdefault("tags", [])

        index = _variant_index(manifest)
        vid = variant.get("id")
        if not vid:
            return ToolResult(success=False, error="variant.id is required")
        if vid in index and not inputs.get("update_existing", False):
            return ToolResult(
                success=False,
                error=f"Variant {vid!r} already exists. Pass update_existing=true to replace it.",
            )

        if vid in index:
            manifest["variants"][index[vid]] = variant
            action = "updated"
        else:
            manifest.setdefault("variants", []).append(variant)
            action = "added"

        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={"operation": "add", "action": action, "variant": variant},
            artifacts=[str(path)],
        )

    def _list(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        status = inputs.get("status")
        purpose = inputs.get("purpose")
        tag = inputs.get("tag")
        include_archived = inputs.get("include_archived", False)
        variants = []
        for variant in manifest.get("variants", []):
            if (
                not include_archived
                and status != "archived"
                and variant.get("status") == "archived"
            ):
                continue
            if status and variant.get("status") != status:
                continue
            if purpose and variant.get("purpose") != purpose:
                continue
            if tag and tag not in variant.get("tags", []):
                continue
            variants.append(_variant_summary(variant))
        return ToolResult(
            success=True,
            data={
                "operation": "list",
                "project_id": manifest.get("project_id"),
                "current": manifest.get("current", {}),
                "count": len(variants),
                "variants": variants,
            },
        )

    def _get_variant(self, manifest: dict[str, Any], variant_id: str) -> dict[str, Any]:
        for variant in manifest.get("variants", []):
            if variant.get("id") == variant_id:
                return variant
        raise KeyError(f"Variant not found: {variant_id}")

    def _show(self, inputs: dict[str, Any]) -> ToolResult:
        manifest = self._read(self._manifest_path(inputs))
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for show")
        variant = self._get_variant(manifest, variant_id)
        channels = [
            channel
            for channel, current_id in manifest.get("current", {}).items()
            if current_id == variant_id
        ]
        return ToolResult(
            success=True,
            data={"operation": "show", "variant": variant, "current_channels": channels},
        )

    def _promote(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for promote")
        variant = self._get_variant(manifest, variant_id)
        restore_status = inputs.get("status")
        if variant.get("status") in {"archived", "rejected"} and restore_status not in {
            "approved",
            "published",
        }:
            return ToolResult(
                success=False,
                error=(
                    f"Variant {variant_id!r} is {variant.get('status')}; "
                    "pass status='approved' or status='published' to intentionally restore it."
                ),
            )
        channel = inputs.get("channel") or "default"
        manifest.setdefault("current", {})[channel] = variant_id
        new_status = inputs.get("status")
        if new_status:
            variant["status"] = new_status
        elif variant.get("status") in {"draft", "candidate"}:
            variant["status"] = "approved"
        variant["updated_at"] = _now()

        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={
                "operation": "promote",
                "channel": channel,
                "variant": _variant_summary(variant),
                "current": manifest["current"],
            },
            artifacts=[str(path)],
        )

    def _archive(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for archive")
        variant = self._get_variant(manifest, variant_id)
        current_channels = [
            channel
            for channel, current_id in manifest.get("current", {}).items()
            if current_id == variant_id
        ]
        if current_channels:
            return ToolResult(
                success=False,
                error=(
                    f"Variant {variant_id!r} is current for {current_channels}. "
                    "Promote another variant before archiving it."
                ),
                data={"current_channels": current_channels},
            )
        variant["status"] = "archived"
        variant["archived_at"] = _now()
        variant["updated_at"] = variant["archived_at"]
        if inputs.get("archive_reason"):
            variant["archive_reason"] = inputs["archive_reason"]
        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={"operation": "archive", "variant": _variant_summary(variant)},
            artifacts=[str(path)],
        )

    def _compare(self, inputs: dict[str, Any]) -> ToolResult:
        manifest = self._read(self._manifest_path(inputs))
        a_id = inputs.get("variant_a")
        b_id = inputs.get("variant_b")
        if not a_id or not b_id:
            return ToolResult(success=False, error="variant_a and variant_b are required")
        a = self._get_variant(manifest, a_id)
        b = self._get_variant(manifest, b_id)
        fields = ["status", "purpose", "inputs", "outputs", "review", "tags", "lineage"]
        diff: dict[str, Any] = {}
        for field in fields:
            if a.get(field) != b.get(field):
                diff[field] = {"a": a.get(field), "b": b.get(field)}
        return ToolResult(
            success=True,
            data={
                "operation": "compare",
                "variant_a": a_id,
                "variant_b": b_id,
                "changed_fields": sorted(diff),
                "diff": diff,
            },
        )

    def _filtered_variants(
        self, manifest: dict[str, Any], inputs: dict[str, Any]
    ) -> list[dict[str, Any]]:
        status = inputs.get("status")
        purpose = inputs.get("purpose")
        tag = inputs.get("tag")
        include_archived = inputs.get("include_archived", False)
        variants = []
        for variant in manifest.get("variants", []):
            if (
                not include_archived
                and status != "archived"
                and variant.get("status") == "archived"
            ):
                continue
            if status and variant.get("status") != status:
                continue
            if purpose and variant.get("purpose") != purpose:
                continue
            if tag and tag not in variant.get("tags", []):
                continue
            variants.append(variant)
        return variants

    def _review_output_dir(self, inputs: dict[str, Any], manifest_path: Path) -> Path:
        output_dir = inputs.get("output_dir")
        if output_dir:
            return Path(output_dir).expanduser().resolve()
        return manifest_path.with_name("variant-review")

    def _review_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("review_payload"):
            return copy.deepcopy(inputs["review_payload"])
        annotations_path = inputs.get("annotations_path")
        if not annotations_path:
            raise ValueError("review_payload or annotations_path is required for annotate")
        path = Path(annotations_path).expanduser().resolve()
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _review(self, inputs: dict[str, Any]) -> ToolResult:
        manifest_path = self._manifest_path(inputs)
        manifest = self._read(manifest_path)
        channel = inputs.get("channel") or "default"
        variants = self._filtered_variants(manifest, inputs)
        output_dir = self._review_output_dir(inputs, manifest_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = inputs.get("run_id") or (
            f"{manifest.get('project_id', 'project')}-{channel}-variant-review"
        )

        review_data = {
            "version": "1.0",
            "tool": self.name,
            "run_id": run_id,
            "created_at": _now(),
            "project_id": manifest.get("project_id"),
            "channel": channel,
            "language": self._detect_review_language(manifest_path, variants, inputs),
            "source_manifest": str(manifest_path),
            "current_variant_id": manifest.get("current", {}).get(channel),
            "selection_policy": "one_variant_per_channel",
            "variants": [
                {
                    "id": variant.get("id"),
                    "name": variant.get("name"),
                    "status": variant.get("status"),
                    "purpose": variant.get("purpose"),
                    "tags": variant.get("tags", []),
                    "lineage": variant.get("lineage", {}),
                    "inputs": variant.get("inputs", {}),
                    "outputs": variant.get("outputs", {}),
                    "review": variant.get("review", {}),
                    "is_current": manifest.get("current", {}).get(channel) == variant.get("id"),
                }
                for variant in variants
            ],
        }

        review_json_path = output_dir / "variant_review.json"
        review_md_path = output_dir / "variant_review.md"
        review_html_path = output_dir / "variant_review.html"
        self._write_json(review_json_path, review_data)
        review_md_path.write_text(
            self._review_markdown(review_data), encoding="utf-8"
        )
        review_html_path.write_text(
            self._review_html(review_data, manifest_path), encoding="utf-8"
        )
        return ToolResult(
            success=True,
            data={
                "operation": "review",
                "project_id": manifest.get("project_id"),
                "channel": channel,
                "run_id": run_id,
                "variant_count": len(variants),
                "language": review_data["language"],
                "current_variant_id": review_data["current_variant_id"],
                "review_json": str(review_json_path),
                "review_markdown": str(review_md_path),
                "review_html": str(review_html_path),
                "next_step": "Open review_html, choose a variant or request another variant, then paste the copied review JSON back into operation='annotate'.",
            },
            artifacts=[str(review_json_path), str(review_md_path), str(review_html_path)],
        )

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        tmp.replace(path)

    def _resolve_artifact_path(self, path_text: str, manifest_path: Path) -> Path:
        path = Path(path_text).expanduser()
        if path.is_absolute():
            return path
        candidates = [
            (manifest_path.parent / path).resolve(),
            (manifest_path.parent.parent / path).resolve(),
            (Path.cwd() / path).resolve(),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _read_text_artifact(self, path_text: str, manifest_path: Path) -> str:
        path = self._resolve_artifact_path(path_text, manifest_path)
        if not path.exists() or not path.is_file() or path.stat().st_size > 1_000_000:
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix.lower() == ".json":
                try:
                    return json.dumps(json.loads(text), ensure_ascii=False)
                except json.JSONDecodeError:
                    return text
            return text
        except OSError:
            return ""

    def _detect_review_language(
        self,
        manifest_path: Path,
        variants: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> str:
        override = str(inputs.get("language") or "auto").lower()
        if override in {"zh", "en"}:
            return override
        text_parts: list[str] = []
        subtitle_keys = {
            "caption",
            "captions",
            "srt",
            "subtitle",
            "subtitles",
            "vtt",
        }
        for variant in variants:
            for bucket_name in ("inputs", "outputs"):
                bucket = variant.get(bucket_name, {})
                if not isinstance(bucket, dict):
                    continue
                for key, value in bucket.items():
                    if key not in subtitle_keys or not isinstance(value, str):
                        continue
                    text = self._read_text_artifact(value, manifest_path)
                    if text:
                        text_parts.append(text)
        text = "\n".join(text_parts)
        cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        return "zh" if cjk_count >= 6 else "en"

    def _review_markdown(self, review_data: dict[str, Any]) -> str:
        lines = [
            "# Variant Review",
            "",
            f"- Project: `{review_data.get('project_id')}`",
            f"- Channel: `{review_data.get('channel')}`",
            f"- Run: `{review_data.get('run_id')}`",
            f"- Current: `{review_data.get('current_variant_id') or 'none'}`",
            "",
            "## Candidates",
            "",
        ]
        for variant in review_data.get("variants", []):
            outputs = variant.get("outputs", {})
            review = variant.get("review", {})
            lines.extend(
                [
                    f"### {variant.get('name')} (`{variant.get('id')}`)",
                    "",
                    f"- Status: `{variant.get('status')}`",
                    f"- Purpose: `{variant.get('purpose')}`",
                    f"- Video: `{outputs.get('video') or ''}`",
                    f"- Review: `{review.get('decision') or ''}` {review.get('notes') or ''}".rstrip(),
                    "",
                ]
            )
        lines.extend(
            [
                "## Human Review Loop",
                "",
                "Use `variant_manager` operation `annotate` with the copied review JSON.",
                "If the selected variant is approved, it is promoted for the channel.",
                "If notes request changes, the manifest records the requested revision and the workflow should render a new candidate before another review round.",
                "",
            ]
        )
        return "\n".join(lines)

    def _review_labels(self, language: str) -> dict[str, str]:
        if language == "zh":
            return {
                "title": "Variant Manager 版本评审",
                "intro": "选择这个交付渠道要使用的版本。如果没有一个合适，可以要求生成下一版，并把复制出的评审 JSON 发给 Agent。",
                "project": "项目",
                "channel": "渠道",
                "variants": "候选版本",
                "current": "当前版本",
                "review_rule": "评审规则：",
                "review_rule_text": "选择一个可交付版本；如果填写了修改意见，这个版本会进入修订，不会直接晋升。",
                "submit": "提交评审",
                "use_variant": "选用这个版本",
                "none_title": "以上版本都不选",
                "none_intro": "当当前候选都不适合作为最终版本时使用。请写清楚下一版要怎么调整。",
                "request_new": "要求生成新版本",
                "new_placeholder": "必填：说明下一版应该改什么。",
                "notes_placeholder": "可选：留空代表通过并晋升这个版本；填写意见代表需要先修订再进入下一轮评审。",
                "video": "视频",
                "review": "评审",
                "inputs_outputs": "输入和输出",
                "outputs": "输出",
                "inputs": "输入",
                "video_missing": "没有找到本地视频文件，只能显示路径。",
                "open_video": "打开视频",
                "choose_required": "请先选择一个版本，或要求生成新版本。",
                "new_notes_required": "请说明新版本应该怎么调整。",
                "copied": "评审内容已复制到剪切板。把它粘贴发给 Agent 后，Agent 会按结果晋升版本、记录修订意见，或进入下一轮新版本生成。",
                "draft_hint": "选择一个最终版本；如果选中的版本还需要微调，请在意见里写清楚。",
                "submit_hint": "提交后会复制评审内容，粘贴发送给 Agent 即可继续处理。",
                "submitted": "已提交",
                "toast_success_title": "版本评审已保存",
                "toast_error_title": "请完善评审",
                "copy_failed_title": "自动复制失败",
                "copy_failed_body": "请手动复制下面的评审内容，并发送给 Agent 继续处理。",
                "back_to_top": "返回顶部",
            }
        return {
            "title": "Variant Manager Review",
            "intro": "Choose the deliverable variant for this channel. If none is good enough, request a new variant and paste the copied review JSON back to the Agent.",
            "project": "Project",
            "channel": "Channel",
            "variants": "Variants",
            "current": "Current",
            "review_rule": "Review rule:",
            "review_rule_text": "Pick one approved variant, or request another round. Notes on a selected variant mean it needs revision before promotion.",
            "submit": "Submit Review",
            "use_variant": "Use this variant",
            "none_title": "None of these variants",
            "none_intro": "Use this when no current candidate should be promoted. Notes are required so the Agent can generate a better candidate.",
            "request_new": "Request a new variant",
            "new_placeholder": "Required: describe what the next variant should change.",
            "notes_placeholder": "Optional: leave blank to approve and promote this variant. Add notes only if it needs revision before promotion.",
            "video": "Video",
            "review": "Review",
            "inputs_outputs": "Inputs and outputs",
            "outputs": "Outputs",
            "inputs": "Inputs",
            "video_missing": "Local video file was not found; only the path can be shown.",
            "open_video": "Open video",
            "choose_required": "Please choose a variant or request a new one.",
            "new_notes_required": "Please describe what the new variant should change.",
            "copied": "Review copied to clipboard. Paste it back to the Agent; approved selections will be promoted, and revision/new-variant requests will start another round.",
            "draft_hint": "Choose one final variant. If the selected variant still needs tuning, write the request in the notes.",
            "submit_hint": "Submitting copies the review JSON; paste it back to the Agent to continue.",
            "submitted": "Submitted",
            "toast_success_title": "Variant review saved",
            "toast_error_title": "Review needs input",
            "copy_failed_title": "Automatic copy failed",
            "copy_failed_body": "Copy the review JSON below and send it to the Agent.",
            "back_to_top": "Back to top",
        }

    def _review_html(self, review_data: dict[str, Any], manifest_path: Path) -> str:
        language = review_data.get("language") or "en"
        labels = self._review_labels(language)
        payload = json.dumps(review_data, ensure_ascii=False)
        script_payload = (
            payload.replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
        variants_html = "\n".join(
            self._variant_card_html(variant, manifest_path, labels)
            for variant in review_data.get("variants", [])
        )
        project = escape(str(review_data.get("project_id") or ""))
        channel = escape(str(review_data.get("channel") or "default"))
        current = escape(str(review_data.get("current_variant_id") or "none"))
        count = len(review_data.get("variants", []))
        lang_attr = "zh-CN" if language == "zh" else "en"
        return f"""<!doctype html>
<html lang="{lang_attr}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(labels["title"])}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111f;
      --panel: #101c2d;
      --panel-2: #0b1424;
      --line: #2a3b52;
      --text: #eef6ff;
      --muted: #a9b8cc;
      --accent: #43d5ff;
      --good: #5be49b;
      --warn: #ffd166;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #12324b 0, var(--bg) 36rem);
      color: var(--text);
      font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 36px 24px 80px; }}
    header {{
      display: grid;
      gap: 18px;
      padding: 26px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: rgba(16, 28, 45, 0.78);
      box-shadow: 0 18px 60px rgba(0,0,0,.25);
    }}
    h1 {{ margin: 0; font-size: clamp(32px, 5vw, 54px); letter-spacing: 0; }}
    .muted {{ color: var(--muted); }}
    .pills {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 14px;
      background: rgba(255,255,255,.04);
      color: var(--muted);
      font-weight: 700;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 20px;
      align-items: center;
      margin: 22px 0;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(9, 18, 31, .92);
      backdrop-filter: blur(16px);
    }}
    .floating-actions {{
      position: fixed;
      right: 22px;
      bottom: 22px;
      z-index: 70;
    }}
    .scroll-top {{
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 12px 18px;
      background: rgba(16,28,45,.94);
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-weight: 900;
      box-shadow: 0 14px 34px rgba(0,0,0,.36);
    }}
    .submit {{
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 14px 24px;
      background: linear-gradient(135deg, #63ddff, #44d38d);
      color: #02111d;
      font-weight: 900;
      font-size: 18px;
      cursor: pointer;
    }}
    .notice {{
      display: none;
      margin-top: 12px;
      padding: 14px 16px;
      border: 1px solid rgba(91,228,155,.55);
      border-radius: 16px;
      background: rgba(91,228,155,.13);
      color: #dfffee;
      font-weight: 800;
    }}
    .notice.show {{ display: block; }}
    .save-status,
    .review-hint {{
      display: block;
      margin-top: 8px;
      padding: 9px 11px;
      border: 1px solid rgba(169,184,204,.18);
      border-radius: 12px;
      background: rgba(8,14,27,.36);
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }}
    .review-hint {{ border-color: rgba(67,213,255,.25); }}
    .export-panel {{
      display: none;
      margin: 0 0 22px;
      padding: 18px;
      border: 1px solid rgba(67,213,255,.32);
      border-radius: 18px;
      background: rgba(8,14,27,.72);
    }}
    .export-panel.is-visible {{ display: block; }}
    .export-panel h2 {{ margin: 0 0 8px; font-size: 20px; }}
    .export-panel p {{ margin: 0 0 12px; color: var(--muted); }}
    .export-panel textarea {{
      min-height: 220px;
      font: 13px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    .toast {{
      position: fixed;
      top: 20px;
      left: 50%;
      z-index: 80;
      display: grid;
      gap: 4px;
      max-width: min(560px, calc(100vw - 36px));
      padding: 16px 18px;
      border: 1px solid rgba(67,213,255,.42);
      border-radius: 16px;
      background: rgba(8,14,27,.96);
      box-shadow: 0 18px 48px rgba(0,0,0,.42);
      color: var(--text);
      opacity: 0;
      pointer-events: none;
      transform: translate(-50%, -12px);
      transition: opacity .18s ease, transform .18s ease;
    }}
    .toast.is-visible {{
      opacity: 1;
      transform: translate(-50%, 0);
    }}
    .toast strong {{ font-size: 16px; }}
    .toast span {{ color: var(--muted); font-size: 14px; }}
    .grid {{ display: grid; gap: 18px; }}
    .card {{
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(16, 28, 45, 0.72);
      min-width: 0;
    }}
    .card.current {{ border-color: rgba(91,228,155,.7); }}
    .card h2 {{ margin: 0 0 10px; font-size: 28px; letter-spacing: 0; }}
    .meta {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0 18px; }}
    .label {{
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,.06);
      color: var(--muted);
      font-weight: 700;
    }}
    .choose {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 18px 0 14px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      cursor: pointer;
      font-weight: 900;
      font-size: 18px;
    }}
    input[type="radio"] {{ width: 20px; height: 20px; accent-color: var(--accent); }}
    textarea {{
      width: 100%;
      min-height: 92px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      resize: vertical;
      background: var(--panel-2);
      color: var(--text);
      font: inherit;
    }}
    dl {{ display: grid; grid-template-columns: minmax(120px, 180px) 1fr; gap: 8px 14px; }}
    dt {{ color: var(--muted); font-weight: 800; }}
    dd {{ margin: 0; word-break: break-word; }}
    pre {{
      overflow: auto;
      padding: 14px;
      border-radius: 14px;
      background: rgba(0,0,0,.25);
      color: var(--muted);
    }}
    .video-shell {{
      margin: 16px 0;
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: #020711;
      width: 100%;
    }}
    video {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      max-height: 420px;
      background: #020711;
      object-fit: contain;
    }}
    .video-path {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      color: var(--muted);
      font-size: 14px;
      border-top: 1px solid var(--line);
      min-width: 0;
    }}
    .video-path span {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .video-path a {{ color: var(--accent); font-weight: 800; white-space: nowrap; }}
    .missing-video {{
      margin: 16px 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      color: var(--muted);
      background: rgba(0,0,0,.18);
      word-break: break-all;
    }}
    .new-request {{ border-color: rgba(255,209,102,.65); }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{escape(labels["title"])}</h1>
    <p class="muted">{escape(labels["intro"])}</p>
    <div class="pills">
      <span class="pill">{escape(labels["project"])}: {project}</span>
      <span class="pill">{escape(labels["channel"])}: {channel}</span>
      <span class="pill">{escape(labels["variants"])}: {count}</span>
      <span class="pill">{escape(labels["current"])}: {current}</span>
    </div>
  </header>

  <section class="toolbar">
    <div>
      <strong>{escape(labels["review_rule"])}</strong>
      <span class="muted">{escape(labels["review_rule_text"])}</span>
      <span class="save-status" data-save-status>{escape(labels["draft_hint"])}</span>
      <span class="review-hint">{escape(labels["submit_hint"])}</span>
    </div>
    <button class="submit" type="button" id="submit" data-submitted-label="{escape(labels["submitted"], quote=True)}">{escape(labels["submit"])}</button>
  </section>

  <section class="export-panel" data-export-panel>
    <h2>{escape(labels["copy_failed_title"])}</h2>
    <p>{escape(labels["copy_failed_body"])}</p>
    <textarea data-export-json readonly></textarea>
  </section>

  <section class="grid">
    {variants_html}
    <article class="card new-request">
      <h2>{escape(labels["none_title"])}</h2>
      <p class="muted">{escape(labels["none_intro"])}</p>
      <label class="choose">
        <input type="radio" name="selected_variant" value="__new_variant__" />
        {escape(labels["request_new"])}
      </label>
      <textarea id="new_variant_notes" placeholder="{escape(labels["new_placeholder"], quote=True)}"></textarea>
    </article>
  </section>

  <div class="floating-actions">
    <button class="scroll-top" type="button" data-scroll-top onclick="window.scrollTo({{top:0,behavior:'smooth'}});document.documentElement.scrollTop=0;document.body.scrollTop=0;">{escape(labels["back_to_top"])}</button>
  </div>
</main>
<div class="toast" data-toast>
  <strong></strong>
  <span></span>
</div>
<script id="review-data" type="application/json">{script_payload}</script>
<script>
  function scrollPageTop() {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
    document.documentElement.scrollTo?.({{ top: 0, behavior: 'smooth' }});
    document.body.scrollTo?.({{ top: 0, behavior: 'smooth' }});
  }}
  document.querySelector('[data-scroll-top]')?.addEventListener('click', scrollPageTop);
  const reviewData = JSON.parse(document.getElementById('review-data').textContent);
  const labels = {json.dumps(labels, ensure_ascii=False)};
  const submitButton = document.getElementById('submit');
  const status = document.querySelector('[data-save-status]');
  const toast = document.querySelector('[data-toast]');
  const exportPanel = document.querySelector('[data-export-panel]');
  const exportJson = document.querySelector('[data-export-json]');
  const storageKey = `variant-manager-review:${{reviewData.run_id}}:${{reviewData.channel}}`;
  function selectedValue() {{
    const selected = document.querySelector('input[name="selected_variant"]:checked');
    return selected ? selected.value : '';
  }}
  function showToast(title, message, timeout = 5200) {{
    if (!toast) return;
    toast.querySelector('strong').textContent = title;
    toast.querySelector('span').textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => toast.classList.remove('is-visible'), timeout);
  }}
  function storeDraft(payload) {{
    try {{
      localStorage.setItem(storageKey, JSON.stringify(payload));
    }} catch (_) {{}}
  }}
  function restoreDraft() {{
    try {{
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
      if (saved.selected_variant_id) {{
        const radio = document.querySelector(`input[name="selected_variant"][value="${{saved.selected_variant_id}}"]`);
        if (radio) radio.checked = true;
      }}
      if (saved.new_variant_notes) {{
        document.getElementById('new_variant_notes').value = saved.new_variant_notes;
      }}
      Object.entries(saved.variant_notes || {{}}).forEach(([variantId, notes]) => {{
        const field = document.querySelector(`[data-notes-for="${{variantId}}"]`);
        if (field) field.value = notes;
      }});
    }} catch (_) {{}}
  }}
  function collectDraft() {{
    const variantNotes = {{}};
    document.querySelectorAll('[data-notes-for]').forEach((field) => {{
      if (field.value.trim()) variantNotes[field.dataset.notesFor] = field.value.trim();
    }});
    return {{
      saved_at: new Date().toISOString(),
      selected_variant_id: selectedValue(),
      new_variant_notes: document.getElementById('new_variant_notes').value.trim(),
      variant_notes: variantNotes
    }};
  }}
  async function copyText(text) {{
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(text);
        return true;
      }}
    }} catch (_) {{}}
    try {{
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.left = '-9999px';
      document.body.appendChild(area);
      area.select();
      const copied = document.execCommand('copy');
      area.remove();
      return copied;
    }} catch (_) {{
      return false;
    }}
  }}
  function buildPayload() {{
    const selected = selectedValue();
    if (!selected) {{
      throw new Error(labels.choose_required);
    }}
    const now = new Date().toISOString();
    if (selected === '__new_variant__') {{
      const notes = document.getElementById('new_variant_notes').value.trim();
      if (!notes) {{
        throw new Error(labels.new_notes_required);
      }}
      return {{
        version: '1.0',
        run_id: reviewData.run_id,
        saved_at: now,
        channel: reviewData.channel,
        selection_policy: 'one_variant_per_channel',
        selected_variant_id: '',
        decision: 'REQUEST_NEW_VARIANT',
        notes,
        action: {{ decision: 'REQUEST_NEW_VARIANT', notes }}
      }};
    }}
    const notes = (document.querySelector(`[data-notes-for="${{selected}}"]`) || {{ value: '' }}).value.trim();
    return {{
      version: '1.0',
      run_id: reviewData.run_id,
      saved_at: now,
      channel: reviewData.channel,
      selection_policy: 'one_variant_per_channel',
      selected_variant_id: selected,
      decision: notes ? 'NEEDS_REVISION' : 'APPROVED',
      notes
    }};
  }}
  document.getElementById('submit').addEventListener('click', async () => {{
    const originalText = submitButton.textContent;
    try {{
      const payload = buildPayload();
      const jsonText = JSON.stringify(payload, null, 2);
      submitButton.disabled = true;
      submitButton.textContent = submitButton.dataset.submittedLabel || labels.submitted;
      storeDraft(payload);
      const copied = await copyText(jsonText);
      if (exportPanel && exportJson) {{
        exportJson.value = jsonText;
        exportPanel.classList.toggle('is-visible', !copied);
      }}
      if (status) status.textContent = labels.copied;
      showToast(labels.toast_success_title, labels.copied);
      window.setTimeout(() => {{
        submitButton.disabled = false;
        submitButton.textContent = originalText;
      }}, 1400);
    }} catch (err) {{
      const message = err.message || String(err);
      if (status) status.textContent = message;
      showToast(labels.toast_error_title, message, 4200);
      submitButton.disabled = false;
      submitButton.textContent = originalText;
    }}
  }});
  restoreDraft();
  document.querySelectorAll('input[name="selected_variant"], textarea').forEach((element) => {{
    element.addEventListener('input', () => storeDraft(collectDraft()));
    element.addEventListener('change', () => storeDraft(collectDraft()));
  }});
  document.querySelectorAll('video').forEach((video) => {{
    video.addEventListener('play', () => {{
      document.querySelectorAll('video').forEach((other) => {{
        if (other !== video) other.pause();
      }});
    }});
  }});
</script>
</body>
</html>
"""

    def _variant_video_html(
        self,
        outputs: dict[str, Any],
        manifest_path: Path,
        labels: dict[str, str],
    ) -> str:
        video = str(outputs.get("video") or "")
        if not video:
            return ""
        video_path = self._resolve_artifact_path(video, manifest_path)
        escaped_video = escape(video)
        if video_path.exists() and video_path.is_file():
            video_uri = escape(video_path.as_uri(), quote=True)
            return f"""<div class="video-shell">
    <video controls preload="metadata" src="{video_uri}" onplay="document.querySelectorAll('video').forEach((v) => {{ if (v !== this) v.pause(); }});"></video>
    <div class="video-path">
      <span>{escaped_video}</span>
      <a href="{video_uri}" target="_blank" rel="noreferrer">{escape(labels["open_video"])}</a>
    </div>
  </div>"""
        return (
            f'<div class="missing-video">{escape(labels["video_missing"])} '
            f"{escaped_video}</div>"
        )

    def _variant_card_html(
        self,
        variant: dict[str, Any],
        manifest_path: Path,
        labels: dict[str, str],
    ) -> str:
        outputs = variant.get("outputs", {})
        inputs = variant.get("inputs", {})
        review = variant.get("review", {})
        tags = " ".join(
            f'<span class="label">{escape(str(tag))}</span>'
            for tag in variant.get("tags", [])
        )
        outputs_json = escape(json.dumps(outputs, indent=2, ensure_ascii=False))
        inputs_json = escape(json.dumps(inputs, indent=2, ensure_ascii=False))
        current_class = " current" if variant.get("is_current") else ""
        current_badge = '<span class="label">current</span>' if variant.get("is_current") else ""
        vid = escape(str(variant.get("id") or ""))
        name = escape(str(variant.get("name") or vid))
        status = escape(str(variant.get("status") or ""))
        purpose = escape(str(variant.get("purpose") or ""))
        video = escape(str(outputs.get("video") or ""))
        video_preview = self._variant_video_html(outputs, manifest_path, labels)
        review_decision = escape(str(review.get("decision") or ""))
        review_notes = escape(str(review.get("notes") or ""))
        return f"""<article class="card{current_class}">
  <h2>{name}</h2>
  <div class="meta">
    <span class="label">id: {vid}</span>
    <span class="label">status: {status}</span>
    <span class="label">purpose: {purpose}</span>
    {current_badge}
    {tags}
  </div>
  {video_preview}
  <dl>
    <dt>{escape(labels["video"])}</dt><dd>{video}</dd>
    <dt>{escape(labels["review"])}</dt><dd>{review_decision} {review_notes}</dd>
  </dl>
  <label class="choose">
    <input type="radio" name="selected_variant" value="{vid}" />
    {escape(labels["use_variant"])}
  </label>
  <textarea data-notes-for="{vid}" placeholder="{escape(labels["notes_placeholder"], quote=True)}"></textarea>
  <details>
    <summary>{escape(labels["inputs_outputs"])}</summary>
    <h3>{escape(labels["outputs"])}</h3>
    <pre>{outputs_json}</pre>
    <h3>{escape(labels["inputs"])}</h3>
    <pre>{inputs_json}</pre>
  </details>
</article>"""

    def _annotate(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        payload = self._review_payload(inputs)
        channel = payload.get("channel") or inputs.get("channel") or "default"
        selected_variant_id = payload.get("selected_variant_id") or payload.get("variant_id")
        decision = str(payload.get("decision") or "").upper()
        notes = str(payload.get("notes") or "").strip()
        action = payload.get("action") or {}
        now = _now()
        artifacts = [str(path)]
        metadata = manifest.setdefault("metadata", {})
        metadata.setdefault("variant_review_history", []).append(
            {
                "run_id": payload.get("run_id"),
                "saved_at": payload.get("saved_at"),
                "applied_at": now,
                "channel": channel,
                "selected_variant_id": selected_variant_id or "",
                "decision": decision,
                "notes": notes,
            }
        )

        review_complete = False
        next_operation = "review"
        pending_variant_ids: list[str] = []
        approved_variant_id = ""
        approved_variant: dict[str, Any] | None = None

        if action.get("decision") == "REQUEST_NEW_VARIANT" or decision == "REQUEST_NEW_VARIANT":
            request_notes = str(action.get("notes") or notes).strip()
            if not request_notes:
                return ToolResult(
                    success=False,
                    error="notes are required when requesting a new variant",
                )
            metadata.setdefault("variant_review_requests", []).append(
                {
                    "run_id": payload.get("run_id"),
                    "created_at": now,
                    "channel": channel,
                    "decision": "request_new_variant",
                    "notes": request_notes,
                }
            )
            next_operation = "add_variant"
        elif selected_variant_id:
            variant = self._get_variant(manifest, selected_variant_id)
            needs_revision = decision in {
                "NEEDS_REVISION",
                "NEEDS_REVIEW",
                "REQUEST_CHANGES",
            } or bool(notes)
            if needs_revision:
                variant["review"] = {
                    "decision": "needs_revision",
                    "notes": notes or "Selected variant needs revision before promotion.",
                    "known_issues": [notes] if notes else [],
                }
                variant["updated_at"] = now
                pending_variant_ids = [selected_variant_id]
                next_operation = "revise_variant"
            else:
                if not variant.get("outputs", {}).get("video"):
                    return ToolResult(
                        success=False,
                        error=(
                            f"Variant {selected_variant_id!r} has no outputs.video; "
                            "cannot hand off to final packaging."
                        ),
                    )
                manifest.setdefault("current", {})[channel] = selected_variant_id
                if variant.get("status") in {"draft", "candidate"}:
                    variant["status"] = "approved"
                variant["review"] = {
                    "decision": "approved",
                    "notes": notes,
                    "known_issues": [],
                }
                variant["updated_at"] = now
                review_complete = True
                next_operation = "package_or_publish"
                approved_variant_id = selected_variant_id
                approved_variant = copy.deepcopy(variant)
        else:
            next_operation = "review"

        failed = self._save_checked(path, manifest)
        if failed:
            return failed

        notes_path = path.with_name(f"{path.stem}.{channel}.review_notes.json")
        package_inputs = (
            self._package_inputs(manifest, path, approved_variant, channel, notes_path)
            if approved_variant
            else {}
        )
        review_notes = {
            "version": "1.0",
            "source_payload": payload,
            "manifest_path": str(path),
            "project_id": manifest.get("project_id"),
            "channel": channel,
            "applied_at": now,
            "review_complete": review_complete,
            "next_operation": next_operation,
            "approved_variant_id": approved_variant_id,
            "pending_variant_ids": pending_variant_ids,
            "package_inputs": package_inputs,
            "current": manifest.get("current", {}),
        }
        self._write_json(notes_path, review_notes)
        artifacts.append(str(notes_path))
        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "project_id": manifest.get("project_id"),
                "channel": channel,
                "review_complete": review_complete,
                "next_operation": next_operation,
                "approved_variant_id": approved_variant_id,
                "pending_variant_ids": pending_variant_ids,
                "package_inputs": package_inputs,
                "current": manifest.get("current", {}),
                "review_notes": str(notes_path),
            },
            artifacts=artifacts,
        )

    def _package_inputs(
        self,
        manifest: dict[str, Any],
        manifest_path: Path,
        variant: dict[str, Any],
        channel: str,
        review_notes_path: Path,
    ) -> dict[str, Any]:
        package_inputs: dict[str, Any] = {
            "project_id": manifest.get("project_id"),
            "variant_id": variant.get("id"),
            "channel": channel,
        }
        video = variant.get("outputs", {}).get("video")
        if isinstance(video, str) and video:
            package_inputs["video_path"] = str(self._resolve_artifact_path(video, manifest_path))

        script = variant.get("inputs", {}).get("script")
        if isinstance(script, str) and script:
            script_path = self._resolve_artifact_path(script, manifest_path)
            if script_path.exists():
                package_inputs["script_path"] = str(script_path)

        extra_files = [{"path": str(review_notes_path), "role": "variant_review_notes"}]
        sidecar_candidates = [
            ("captions", "captions"),
            ("subtitles", "subtitles"),
            ("final_review", "final_review"),
            ("render_report", "render_report"),
        ]
        for key, role in sidecar_candidates:
            value = variant.get("inputs", {}).get(key) or variant.get("outputs", {}).get(key)
            if not isinstance(value, str) or not value:
                continue
            sidecar_path = self._resolve_artifact_path(value, manifest_path)
            if sidecar_path.exists():
                extra_files.append({"path": str(sidecar_path), "role": role})
        package_inputs["extra_files"] = extra_files
        return package_inputs

    def _validate(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        errors = self._check(manifest)
        return ToolResult(
            success=not errors,
            error=None if not errors else "; ".join(errors),
            data={
                "operation": "validate",
                "manifest_path": str(path),
                "valid": not errors,
                "errors": errors,
                "variant_count": len(manifest.get("variants", [])),
                "current": manifest.get("current", {}),
            },
        )
