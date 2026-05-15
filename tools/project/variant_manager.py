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
            self._review_html(review_data), encoding="utf-8"
        )
        return ToolResult(
            success=True,
            data={
                "operation": "review",
                "project_id": manifest.get("project_id"),
                "channel": channel,
                "run_id": run_id,
                "variant_count": len(variants),
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

    def _review_html(self, review_data: dict[str, Any]) -> str:
        payload = json.dumps(review_data, ensure_ascii=False)
        variants_html = "\n".join(
            self._variant_card_html(variant) for variant in review_data.get("variants", [])
        )
        project = escape(str(review_data.get("project_id") or ""))
        channel = escape(str(review_data.get("channel") or "default"))
        current = escape(str(review_data.get("current_variant_id") or "none"))
        count = len(review_data.get("variants", []))
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Variant Manager Review</title>
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
    main {{ max-width: 1180px; margin: 0 auto; padding: 36px 24px 80px; }}
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
      position: sticky;
      top: 0;
      z-index: 4;
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
    .grid {{ display: grid; gap: 18px; }}
    .card {{
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(16, 28, 45, 0.72);
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
    .new-request {{ border-color: rgba(255,209,102,.65); }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Variant Manager Review</h1>
    <p class="muted">Choose the deliverable variant for this channel. If none is good enough, request a new variant and paste the copied review JSON back to the Agent.</p>
    <div class="pills">
      <span class="pill">Project: {project}</span>
      <span class="pill">Channel: {channel}</span>
      <span class="pill">Variants: {count}</span>
      <span class="pill">Current: {current}</span>
    </div>
  </header>

  <section class="toolbar">
    <div>
      <strong>Review rule:</strong>
      <span class="muted">pick one approved variant, or request another round. Notes on a selected variant mean it needs revision before promotion.</span>
      <div id="notice" class="notice"></div>
    </div>
    <button class="submit" type="button" id="submit">Submit Review</button>
  </section>

  <section class="grid">
    {variants_html}
    <article class="card new-request">
      <h2>None of these variants</h2>
      <p class="muted">Use this when no current candidate should be promoted. Notes are required so the Agent can generate a better candidate.</p>
      <label class="choose">
        <input type="radio" name="selected_variant" value="__new_variant__" />
        Request a new variant
      </label>
      <textarea id="new_variant_notes" placeholder="Required: describe what the next variant should change."></textarea>
    </article>
  </section>
</main>
<script id="review-data" type="application/json">{escape(payload)}</script>
<script>
  const reviewData = JSON.parse(document.getElementById('review-data').textContent);
  const notice = document.getElementById('notice');
  function selectedValue() {{
    const selected = document.querySelector('input[name="selected_variant"]:checked');
    return selected ? selected.value : '';
  }}
  function copyText(text) {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      return navigator.clipboard.writeText(text);
    }}
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
    return Promise.resolve();
  }}
  function buildPayload() {{
    const selected = selectedValue();
    if (!selected) {{
      throw new Error('Please choose a variant or request a new one.');
    }}
    const now = new Date().toISOString();
    if (selected === '__new_variant__') {{
      const notes = document.getElementById('new_variant_notes').value.trim();
      if (!notes) {{
        throw new Error('Please describe what the new variant should change.');
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
    try {{
      const payload = buildPayload();
      await copyText(JSON.stringify(payload, null, 2));
      notice.textContent = 'Review copied to clipboard. Paste it back to the Agent; approved selections will be promoted, and revision/new-variant requests will start another round.';
      notice.classList.add('show');
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }} catch (err) {{
      notice.textContent = err.message || String(err);
      notice.classList.add('show');
    }}
  }});
</script>
</body>
</html>
"""

    def _variant_card_html(self, variant: dict[str, Any]) -> str:
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
  <dl>
    <dt>Video</dt><dd>{video}</dd>
    <dt>Review</dt><dd>{review_decision} {review_notes}</dd>
  </dl>
  <label class="choose">
    <input type="radio" name="selected_variant" value="{vid}" />
    Use this variant
  </label>
  <textarea data-notes-for="{vid}" placeholder="Optional: leave blank to approve and promote this variant. Add notes only if it needs revision before promotion."></textarea>
  <details>
    <summary>Inputs and outputs</summary>
    <h3>Outputs</h3>
    <pre>{outputs_json}</pre>
    <h3>Inputs</h3>
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
        else:
            next_operation = "review"

        failed = self._save_checked(path, manifest)
        if failed:
            return failed

        notes_path = path.with_name(f"{path.stem}.{channel}.review_notes.json")
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
                "current": manifest.get("current", {}),
                "review_notes": str(notes_path),
            },
            artifacts=artifacts,
        )

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
