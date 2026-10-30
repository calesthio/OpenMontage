"""Pre-render narration sync gate.

This tool runs before final video rendering. It compares locked narration
segments, caption/screen text, and planned visual cues so obvious text or
timing drift can be fixed before an expensive render.
"""

from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
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


class PreRenderNarrationSyncGate(BaseTool):
    name = "pre_render_narration_sync_gate"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []
    install_instructions = "No external runtime is required."
    agent_skills = []

    capabilities = [
        "pre_render_narration_sync_review",
        "caption_text_consistency_check",
        "onscreen_text_consistency_check",
        "visual_cue_timing_check",
        "term_consistency_check",
        "agent_result_routing",
    ]
    supports = {
        "pre_render_review": True,
        "caption_text_check": True,
        "visual_timing_check": True,
        "term_consistency_check": True,
        "html_review": True,
        "automated_semantic_judgment": False,
    }
    best_for = [
        "checking locked narration against captions and planned visual cues before rendering",
        "animated UI walkthroughs and narration-led explainers",
        "catching stale script terms or visual cue timing drift before a render",
    ]
    not_good_for = [
        "post-render frame inspection",
        "automatic creative approval",
        "detecting visual content inside already-rendered frames",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["review"],
                "default": "review",
            },
            "manifest_path": {"type": "string"},
            "manifest": {"type": "object"},
            "output_dir": {"type": "string"},
        },
        "anyOf": [{"required": ["manifest_path"]}, {"required": ["manifest"]}],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "status": {"type": "string"},
            "results_path": {"type": "string"},
            "review_path": {"type": "string"},
            "review_html_path": {"type": "string"},
            "recommended_next_action": {"type": "string"},
            "finding_count": {"type": "integer"},
            "findings": {"type": "array"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20)
    idempotency_key_fields = ["operation", "manifest_path", "manifest", "output_dir"]
    side_effects = [
        "writes pre-render narration sync results.json",
        "writes review.md and review.html",
    ]
    user_visible_verification = [
        "Inspect review.html only when recommended_next_action is agent_review_required.",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs.get("operation", "review")
        start = time.time()
        try:
            if operation != "review":
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
            result = self._review(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Pre-render narration sync gate failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _review(self, inputs: dict[str, Any]) -> ToolResult:
        manifest = self._load_manifest(inputs)
        output_dir = Path(inputs.get("output_dir") or manifest["output_dir"]).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        segments = self._narration_segments(manifest)
        captions = self._caption_items(manifest)
        screen_texts = self._screen_text_items(manifest)
        visual_cues = self._visual_cues(manifest)
        term_rules = self._term_rules(manifest)
        tolerance = float(manifest.get("tolerance_seconds", 0.4))

        findings: list[dict[str, Any]] = []
        findings.extend(self._caption_findings(captions, segments))
        findings.extend(self._screen_text_findings(screen_texts, segments))
        findings.extend(self._visual_timing_findings(visual_cues, segments, default_tolerance=tolerance))
        findings.extend(self._term_findings(term_rules, captions, screen_texts, visual_cues))

        route = self._route(findings)
        results = {
            "version": self.version,
            "tool": self.name,
            "operation": "review",
            "status": route["status"],
            "project": manifest.get("project"),
            "run_id": manifest.get("run_id") or self._timestamp_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(output_dir),
            "summary": {
                "narration_segments": len(segments),
                "captions": len(captions),
                "screen_texts": len(screen_texts),
                "visual_cues": len(visual_cues),
                "finding_count": len(findings),
                "error_count": sum(1 for item in findings if item["severity"] == "error"),
                "warning_count": sum(1 for item in findings if item["severity"] == "warning"),
                "info_count": sum(1 for item in findings if item["severity"] == "info"),
            },
            "recommended_next_action": route["recommended_next_action"],
            "user_handoff_policy": route["user_handoff_policy"],
            "narration_segments": segments,
            "captions": captions,
            "screen_texts": screen_texts,
            "visual_cues": visual_cues,
            "findings": findings,
        }

        results_path = output_dir / "results.json"
        review_path = output_dir / "review.md"
        review_html_path = output_dir / "review.html"
        self._write_json(results_path, results)
        review_path.write_text(self._review_markdown(results), encoding="utf-8")
        review_html_path.write_text(self._review_html(results), encoding="utf-8")

        return ToolResult(
            success=route["status"] != "needs-revision",
            data={
                "operation": "review",
                "status": route["status"],
                "results_path": str(results_path),
                "review_path": str(review_path),
                "review_html_path": str(review_html_path),
                "recommended_next_action": route["recommended_next_action"],
                "finding_count": len(findings),
                "findings": findings,
            },
            artifacts=[str(results_path), str(review_path), str(review_html_path)],
            error=None if route["status"] != "needs-revision" else "Pre-render narration sync found issues to fix before rendering.",
        )

    def _load_manifest(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("manifest") is not None:
            manifest = deepcopy(inputs["manifest"])
        elif inputs.get("manifest_path"):
            manifest = json.loads(Path(inputs["manifest_path"]).expanduser().read_text(encoding="utf-8"))
        else:
            raise ValueError("manifest or manifest_path is required")
        if not manifest.get("output_dir"):
            raise ValueError("manifest.output_dir is required")
        return manifest

    def _narration_segments(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        items = self._load_items(manifest, ("narration_segments", "tts_segments", "segments"), path_keys=("narration_path", "tts_selection_path"))
        segments = []
        for index, item in enumerate(items):
            text = self._first_present(item, ("text", "spoken_text", "narration", "voiceover", "caption"))
            if not text:
                continue
            segment_id = str(item.get("id") or item.get("segment_id") or item.get("section_id") or f"segment-{index + 1}")
            start = self._optional_float(item, ("start_seconds", "start", "time_seconds", "timestamp_seconds"))
            end = self._optional_float(item, ("end_seconds", "end"))
            segments.append(
                {
                    "id": segment_id,
                    "section_id": item.get("section_id") or item.get("scene_id"),
                    "text": str(text),
                    "start_seconds": start,
                    "end_seconds": end,
                    "duration_seconds": self._optional_float(item, ("duration_seconds", "duration")),
                }
            )
        if not segments:
            raise ValueError("manifest needs at least one narration segment")
        return segments

    def _caption_items(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        return self._timed_text_items(manifest, ("captions", "subtitles"), path_keys=("captions_path", "subtitles_path"), item_type="caption")

    def _screen_text_items(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        return self._timed_text_items(manifest, ("screen_texts", "onscreen_texts", "visual_texts"), path_keys=("screen_texts_path",), item_type="screen_text")

    def _visual_cues(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        items = self._load_items(manifest, ("visual_cues", "cues"), path_keys=("visual_cues_path",))
        cues = []
        for index, item in enumerate(items):
            cue_id = str(item.get("id") or item.get("cue_id") or item.get("section_id") or f"cue-{index + 1}")
            timestamp = self._optional_float(item, ("timestamp_seconds", "time_seconds", "at_seconds", "start_seconds", "start"))
            cues.append(
                {
                    "id": cue_id,
                    "section_id": item.get("section_id") or item.get("scene_id"),
                    "label": item.get("label") or cue_id,
                    "timestamp_seconds": timestamp,
                    "narration_anchor": item.get("narration_anchor") or item.get("anchor_text") or item.get("text") or "",
                    "expected_state": item.get("expected_state") or item.get("expected") or "",
                    "tolerance_seconds": self._optional_float(item, ("tolerance_seconds", "tolerance")),
                    "risk": item.get("risk", ""),
                }
            )
        return cues

    def _term_rules(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        rules = manifest.get("term_rules") or manifest.get("terminology") or []
        normalized = []
        for item in rules:
            if isinstance(item, dict):
                required = item.get("required") or item.get("preferred") or item.get("term")
                forbidden = item.get("forbidden") or item.get("avoid") or []
                if isinstance(forbidden, str):
                    forbidden = [forbidden]
                if required or forbidden:
                    normalized.append({"required": str(required or ""), "forbidden": [str(value) for value in forbidden]})
        return normalized

    def _timed_text_items(
        self,
        manifest: dict[str, Any],
        keys: tuple[str, ...],
        *,
        path_keys: tuple[str, ...],
        item_type: str,
    ) -> list[dict[str, Any]]:
        items = self._load_items(manifest, keys, path_keys=path_keys)
        normalized = []
        for index, item in enumerate(items):
            text = self._first_present(item, ("text", "caption", "subtitle", "narration", "label"))
            if not text:
                continue
            normalized.append(
                {
                    "id": str(item.get("id") or item.get("section_id") or f"{item_type}-{index + 1}"),
                    "section_id": item.get("section_id") or item.get("scene_id"),
                    "text": str(text),
                    "start_seconds": self._optional_float(item, ("start_seconds", "start", "timestamp_seconds", "time_seconds")),
                    "end_seconds": self._optional_float(item, ("end_seconds", "end")),
                    "item_type": item_type,
                }
            )
        return normalized

    def _load_items(self, manifest: dict[str, Any], keys: tuple[str, ...], *, path_keys: tuple[str, ...]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key in keys:
            value = manifest.get(key)
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
        for key in path_keys:
            path = manifest.get(key)
            if path:
                loaded = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
                items.extend(self._items_from_payload(loaded))
        return items

    @staticmethod
    def _items_from_payload(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("selections", "segments", "captions", "subtitles", "cues", "items"):
                if isinstance(payload.get(key), list):
                    return [item for item in payload[key] if isinstance(item, dict)]
        return []

    def _caption_findings(self, captions: list[dict[str, Any]], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings = []
        by_id = self._segments_by_key(segments)
        for caption in captions:
            segment = by_id.get(caption["id"]) or by_id.get(str(caption.get("section_id") or ""))
            if not segment:
                findings.append(self._finding("warning", "caption_unmatched", caption["id"], "Caption has no matching narration segment."))
                continue
            if not self._texts_compatible(segment["text"], caption["text"]):
                findings.append(
                    self._finding(
                        "error",
                        "caption_text_mismatch",
                        caption["id"],
                        "Caption text differs from the locked narration text.",
                        expected=segment["text"],
                        actual=caption["text"],
                    )
                )
        return findings

    def _screen_text_findings(self, screen_texts: list[dict[str, Any]], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings = []
        by_id = self._segments_by_key(segments)
        for item in screen_texts:
            segment = by_id.get(item["id"]) or by_id.get(str(item.get("section_id") or ""))
            if not segment:
                findings.append(self._finding("info", "screen_text_unmatched", item["id"], "Screen text has no matching narration segment; agent should inspect if this is intentional."))
                continue
            if self._normal_text(item["text"]) and not self._overlap_enough(segment["text"], item["text"]):
                findings.append(
                    self._finding(
                        "warning",
                        "screen_text_drift",
                        item["id"],
                        "Screen text appears weakly related to the narration segment.",
                        expected=segment["text"],
                        actual=item["text"],
                    )
                )
        return findings

    def _visual_timing_findings(
        self,
        visual_cues: list[dict[str, Any]],
        segments: list[dict[str, Any]],
        *,
        default_tolerance: float,
    ) -> list[dict[str, Any]]:
        findings = []
        by_id = self._segments_by_key(segments)
        for cue in visual_cues:
            segment = by_id.get(cue["id"]) or by_id.get(str(cue.get("section_id") or ""))
            anchor_time = self._anchor_time(cue, segment, segments)
            timestamp = cue.get("timestamp_seconds")
            if timestamp is None:
                findings.append(self._finding("warning", "visual_cue_missing_time", cue["id"], "Visual cue has no timestamp_seconds."))
                continue
            if anchor_time is None:
                findings.append(self._finding("warning", "visual_cue_anchor_missing", cue["id"], "Could not resolve narration anchor time for visual cue."))
                continue
            tolerance = float(cue.get("tolerance_seconds") or default_tolerance)
            delta = round(float(timestamp) - float(anchor_time), 3)
            if abs(delta) > tolerance:
                findings.append(
                    self._finding(
                        "error",
                        "visual_cue_timing_mismatch",
                        cue["id"],
                        f"Visual cue is {abs(delta):.3f}s {'late' if delta > 0 else 'early'} relative to narration.",
                        expected=f"{anchor_time:.3f}s +/- {tolerance:.3f}s",
                        actual=f"{timestamp:.3f}s",
                        delta_seconds=delta,
                    )
                )
            if not cue.get("expected_state"):
                findings.append(self._finding("warning", "visual_cue_missing_expected_state", cue["id"], "Visual cue needs expected_state before review."))
        return findings

    def _term_findings(
        self,
        term_rules: list[dict[str, Any]],
        captions: list[dict[str, Any]],
        screen_texts: list[dict[str, Any]],
        visual_cues: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        findings = []
        text_items = []
        for item in captions + screen_texts:
            text_items.append((item["id"], item.get("text", "")))
        for cue in visual_cues:
            text_items.append((cue["id"], " ".join(str(cue.get(key, "")) for key in ("label", "expected_state", "narration_anchor"))))
        for rule in term_rules:
            forbidden = [value for value in rule.get("forbidden", []) if value]
            required = rule.get("required", "")
            for item_id, text in text_items:
                for forbidden_term in forbidden:
                    if forbidden_term and forbidden_term in text:
                        findings.append(
                            self._finding(
                                "error",
                                "forbidden_term",
                                item_id,
                                f"Found forbidden term {forbidden_term!r}; use {required!r} instead.",
                                expected=required,
                                actual=text,
                            )
                        )
        return findings

    def _anchor_time(self, cue: dict[str, Any], segment: dict[str, Any] | None, segments: list[dict[str, Any]]) -> float | None:
        anchor = str(cue.get("narration_anchor") or "").strip()
        if anchor:
            for candidate in segments:
                if anchor in candidate["text"] and candidate.get("start_seconds") is not None:
                    ratio = candidate["text"].find(anchor) / max(len(candidate["text"]), 1)
                    duration = self._segment_duration(candidate)
                    return float(candidate["start_seconds"]) + ratio * duration
        if segment and segment.get("start_seconds") is not None:
            return float(segment["start_seconds"])
        return None

    @staticmethod
    def _segment_duration(segment: dict[str, Any]) -> float:
        if segment.get("end_seconds") is not None and segment.get("start_seconds") is not None:
            return max(0.0, float(segment["end_seconds"]) - float(segment["start_seconds"]))
        if segment.get("duration_seconds") is not None:
            return float(segment["duration_seconds"])
        return 0.0

    @staticmethod
    def _segments_by_key(segments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        by_key = {}
        for segment in segments:
            by_key[str(segment["id"])] = segment
            if segment.get("section_id"):
                by_key[str(segment["section_id"])] = segment
        return by_key

    @classmethod
    def _texts_compatible(cls, expected: str, actual: str) -> bool:
        expected_norm = cls._normal_text(expected)
        actual_norm = cls._normal_text(actual)
        return bool(expected_norm and actual_norm and (expected_norm in actual_norm or actual_norm in expected_norm))

    @classmethod
    def _overlap_enough(cls, expected: str, actual: str) -> bool:
        expected_tokens = set(cls._tokens(expected))
        actual_tokens = set(cls._tokens(actual))
        if not expected_tokens or not actual_tokens:
            return False
        return len(expected_tokens & actual_tokens) / max(len(actual_tokens), 1) >= 0.4

    @staticmethod
    def _normal_text(text: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"[^\w\u3400-\u9fff]+", "", str(text).lower()))

    @staticmethod
    def _tokens(text: str) -> list[str]:
        cjk = list(re.findall(r"[\u3400-\u9fff]", text))
        latin = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", text.lower())
        return cjk + latin

    @staticmethod
    def _optional_float(item: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            if item.get(key) is not None:
                return float(item[key])
        return None

    @staticmethod
    def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if item.get(key):
                return item[key]
        return None

    @staticmethod
    def _finding(
        severity: str,
        kind: str,
        item_id: str,
        message: str,
        *,
        expected: Any = "",
        actual: Any = "",
        delta_seconds: float | None = None,
    ) -> dict[str, Any]:
        finding = {
            "severity": severity,
            "kind": kind,
            "item_id": item_id,
            "message": message,
            "expected": expected,
            "actual": actual,
        }
        if delta_seconds is not None:
            finding["delta_seconds"] = delta_seconds
        return finding

    @staticmethod
    def _route(findings: list[dict[str, Any]]) -> dict[str, str]:
        error_count = sum(1 for item in findings if item["severity"] == "error")
        warning_count = sum(1 for item in findings if item["severity"] == "warning")
        if error_count:
            return {
                "status": "needs-revision",
                "recommended_next_action": "revise_before_render",
                "user_handoff_policy": "Do not ask the user yet. Fix deterministic text/timing issues, rerun this gate, then render.",
            }
        if warning_count:
            return {
                "status": "needs-agent-review",
                "recommended_next_action": "agent_review_required",
                "user_handoff_policy": "Agent should inspect warnings. Ask the user only if the remaining question is semantic or creative.",
            }
        return {
            "status": "passed",
            "recommended_next_action": "ready_to_render",
            "user_handoff_policy": "No user handoff is required for this gate; proceed to render.",
        }

    @staticmethod
    def _review_markdown(results: dict[str, Any]) -> str:
        summary = results["summary"]
        lines = [
            f"# Pre-render Narration Sync Gate: {results.get('run_id', '')}",
            "",
            f"- Project: `{results.get('project', '')}`",
            f"- Status: `{results.get('status')}`",
            f"- Recommended next action: `{results.get('recommended_next_action')}`",
            f"- Findings: `{summary['finding_count']}` (`{summary['error_count']}` errors, `{summary['warning_count']}` warnings)",
            "",
            results.get("user_handoff_policy", ""),
            "",
            "## Findings",
            "",
        ]
        if not results.get("findings"):
            lines.append("No sync issues found.")
        for finding in results.get("findings", []):
            lines.extend(
                [
                    f"### {finding['severity'].upper()} {finding['kind']} - {finding['item_id']}",
                    "",
                    finding["message"],
                    "",
                    f"- Expected: {finding.get('expected') or '-'}",
                    f"- Actual: {finding.get('actual') or '-'}",
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _review_html(results: dict[str, Any]) -> str:
        summary = results["summary"]
        findings = results.get("findings", [])
        rows = "\n".join(
            "<tr>"
            f"<td>{escape(item['severity'])}</td>"
            f"<td>{escape(item['kind'])}</td>"
            f"<td>{escape(item['item_id'])}</td>"
            f"<td>{escape(item['message'])}</td>"
            f"<td>{escape(str(item.get('expected') or '-'))}</td>"
            f"<td>{escape(str(item.get('actual') or '-'))}</td>"
            "</tr>"
            for item in findings
        )
        if not rows:
            rows = '<tr><td colspan="6">No sync issues found.</td></tr>'
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pre-render Narration Sync Gate</title>
<style>
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1320; color: #edf4ff; }}
main {{ max-width: 1080px; margin: 0 auto; padding: 32px 24px 56px; }}
.summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; }}
.pill {{ border: 1px solid rgba(149,172,214,.28); border-radius: 999px; padding: 7px 12px; background: rgba(255,255,255,.06); color: #dbe8fb; }}
.policy {{ border: 1px solid rgba(98,216,255,.26); border-radius: 10px; padding: 14px 16px; background: rgba(98,216,255,.08); color: #cfeeff; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
th, td {{ border-bottom: 1px solid rgba(149,172,214,.22); padding: 10px 9px; text-align: left; vertical-align: top; }}
th {{ color: #aebbd0; font-size: 12px; text-transform: uppercase; }}
td {{ color: #edf4ff; }}
</style>
</head>
<body>
<main>
<h1>Pre-render Narration Sync Gate</h1>
<div class="summary">
<span class="pill">Project: {escape(str(results.get('project') or '-'))}</span>
<span class="pill">Status: {escape(str(results.get('status')))}</span>
<span class="pill">Next: {escape(str(results.get('recommended_next_action')))}</span>
<span class="pill">Findings: {summary['finding_count']}</span>
</div>
<div class="policy">{escape(str(results.get('user_handoff_policy') or ''))}</div>
<table>
<thead><tr><th>Severity</th><th>Kind</th><th>Item</th><th>Message</th><th>Expected</th><th>Actual</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</main>
</body>
</html>
"""

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _timestamp_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
