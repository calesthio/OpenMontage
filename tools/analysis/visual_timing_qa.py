"""Cue-based visual timing QA for rendered videos.

This tool runs after a video is rendered. It extracts small frame windows around
script or narration cues so a reviewer can quickly verify whether the visible
state matches the line being spoken.
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


class VisualTimingQA(BaseTool):
    name = "visual_timing_qa"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg"]

    capabilities = [
        "post_render_visual_timing_review",
        "rule_based_cue_suggestion",
        "rule_based_initial_review",
        "cue_window_frame_extraction",
        "contact_sheet_generation",
        "review_markdown_generation",
        "human_reviewer_annotation",
    ]
    supports = {
        "dry_run": True,
        "post_render_review": True,
        "cue_windows": True,
        "contact_sheets": True,
        "reviewer_annotations": True,
        "rule_based_suggest_cues": True,
        "rule_based_initial_review": True,
        "automated_semantic_judgment": False,
    }
    best_for = [
        "rendered narration-led explainers with timed visual states",
        "animated UI walkthroughs, diagrams, and text reveal timing checks",
        "human review of whether visuals match narration at key moments",
    ]
    not_good_for = [
        "fully automatic creative approval",
        "raw live-action footage review without explicit timing cues",
        "general video quality metrics such as VMAF or compression scoring",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["suggest_cues", "dry_run", "review", "annotate"],
                "default": "dry_run",
            },
            "manifest_path": {"type": "string"},
            "manifest": {"type": "object"},
            "captions_path": {"type": "string"},
            "script_path": {"type": "string"},
            "results_path": {"type": "string"},
            "annotations": {"type": "object"},
            "annotations_path": {"type": "string"},
            "output_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "project": {"type": "string"},
            "run_id": {"type": "string"},
            "speed_multiplier": {
                "type": "number",
                "default": 1.0,
                "description": "Divide source timestamps by this value when the rendered video is speed-adjusted.",
            },
            "max_cues": {"type": "integer", "default": 12},
            "per_category_limit": {"type": "integer", "default": 3},
            "auto_review": {
                "type": "boolean",
                "default": True,
                "description": "Run conservative rule-based initial review on extracted cue frames.",
            },
        },
        "anyOf": [
            {"required": ["manifest_path"]},
            {"required": ["manifest"]},
            {"required": ["results_path"]},
            {"required": ["captions_path"]},
            {"required": ["script_path"]},
        ],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "status": {"type": "string"},
            "output_dir": {"type": "string"},
            "results_path": {"type": "string"},
            "review_path": {"type": "string"},
            "review_html_path": {"type": "string"},
            "review_notes_path": {"type": "string"},
            "annotated_review_path": {"type": "string"},
            "annotated_review_html_path": {"type": "string"},
            "review_complete": {"type": "boolean"},
            "next_operation": {"type": "string"},
            "missing_review_cues": {"type": "array"},
            "pending_review_cues": {"type": "array"},
            "suggested_cues_path": {"type": "string"},
            "suggested_review_path": {"type": "string"},
            "cue_count": {"type": "integer"},
            "cues": {"type": "array"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500)
    idempotency_key_fields = [
        "operation",
        "manifest_path",
        "manifest",
        "results_path",
        "annotations",
        "annotations_path",
        "output_path",
        "output_dir",
    ]
    side_effects = [
        "writes cue frame images",
        "writes per-cue contact sheets",
        "writes results.json, review.md, and review.html",
        "writes suggested_cues.json and suggested_cues.md in suggest_cues mode",
        "writes review_notes.json, review_annotated.md, and review_annotated.html in annotate mode",
    ]
    user_visible_verification = [
        "Inspect review.html contact sheets for early, late, or wrong visual states",
    ]

    def get_status(self) -> ToolStatus:
        return super().get_status()

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs.get("operation", "dry_run")
        start = time.time()
        try:
            if operation == "suggest_cues":
                result = self._suggest_cues(inputs)
            elif operation == "annotate":
                result = self._annotate(inputs)
            elif operation in {"dry_run", "review"}:
                result = self._run(inputs, extract=operation == "review")
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as exc:
            return ToolResult(success=False, error=f"Visual Timing QA failed: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _suggest_cues(self, inputs: dict[str, Any]) -> ToolResult:
        output_dir = Path(inputs.get("output_dir") or inputs.get("manifest", {}).get("output_dir") or ".").expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        project = inputs.get("project") or inputs.get("manifest", {}).get("project")
        run_id = inputs.get("run_id") or inputs.get("manifest", {}).get("run_id") or self._timestamp_id()
        speed_multiplier = float(inputs.get("speed_multiplier", 1.0))
        max_cues = int(inputs.get("max_cues", 12))

        items = []
        if inputs.get("captions_path"):
            items.extend(self._load_caption_items(Path(inputs["captions_path"]).expanduser()))
        if inputs.get("script_path"):
            items.extend(self._load_script_items(Path(inputs["script_path"]).expanduser()))
        if inputs.get("manifest") and inputs["manifest"].get("cues"):
            items.extend(inputs["manifest"]["cues"])
        if not items:
            return ToolResult(success=False, error="suggest_cues requires captions_path, script_path, or manifest.cues")

        suggestions = self._rank_suggested_cues(
            items,
            speed_multiplier=speed_multiplier,
            max_cues=max_cues,
            per_category_limit=int(inputs.get("per_category_limit", 3)),
        )
        payload = {
            "version": self.version,
            "tool": self.name,
            "operation": "suggest_cues",
            "status": "completed",
            "project": project,
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "speed_multiplier": speed_multiplier,
            "suggestions": suggestions,
        }
        suggested_cues_path = output_dir / "suggested_cues.json"
        suggested_review_path = output_dir / "suggested_cues.md"
        self._write_json(suggested_cues_path, payload)
        suggested_review_path.write_text(self._suggestions_markdown(payload), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "suggest_cues",
                "status": "completed",
                "suggested_cues_path": str(suggested_cues_path),
                "suggested_review_path": str(suggested_review_path),
                "cue_count": len(suggestions),
                "cues": suggestions,
            },
            artifacts=[str(suggested_cues_path), str(suggested_review_path)],
        )

    def _run(self, inputs: dict[str, Any], *, extract: bool) -> ToolResult:
        manifest = self._load_manifest(inputs)
        output_dir = self._output_dir(manifest)
        output_dir.mkdir(parents=True, exist_ok=True)

        video_path = Path(manifest["video_path"]).expanduser().resolve()
        if extract and not video_path.exists():
            return ToolResult(success=False, error=f"Input video not found: {video_path}")

        duration = self._get_duration(video_path) if extract else manifest.get("duration_seconds")
        cues = self._build_cues(manifest, duration=duration)
        auto_review = bool(inputs.get("auto_review", manifest.get("auto_review", True)))

        results: dict[str, Any] = {
            "version": self.version,
            "tool": self.name,
            "operation": "review" if extract else "dry_run",
            "status": "completed",
            "project": manifest.get("project"),
            "run_id": manifest.get("run_id") or self._timestamp_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "review_language": manifest.get("review_language") or manifest.get("language") or manifest.get("ui_language"),
            "video_path": str(video_path),
            "duration_seconds": duration,
            "output_dir": str(output_dir),
            "cues": [],
        }
        artifacts: list[str] = []

        for cue in cues:
            cue_result = deepcopy(cue)
            cue_dir = output_dir / self._slug(cue["id"])
            cue_result["frames"] = []
            cue_result["contact_sheet"] = None
            if extract:
                cue_dir.mkdir(parents=True, exist_ok=True)
                cue_result["frames"] = self._extract_cue_frames(video_path, cue, cue_dir)
                sheet_path = self._write_contact_sheet(cue_result["frames"], cue_dir, cue["id"])
                if sheet_path:
                    cue_result["contact_sheet"] = str(sheet_path)
                    artifacts.append(str(sheet_path))
                artifacts.extend(frame["path"] for frame in cue_result["frames"] if frame.get("path"))
            else:
                cue_result["planned"] = True
            if auto_review:
                cue_result["initial_review"] = self._initial_review(cue_result, extract=extract)
            results["cues"].append(cue_result)

        results_path = output_dir / "results.json"
        review_path = output_dir / "review.md"
        review_html_path = output_dir / "review.html"
        self._write_json(results_path, results)
        review_path.write_text(self._review_markdown(results), encoding="utf-8")
        review_html_path.write_text(self._review_html(results, review_html_path), encoding="utf-8")
        artifacts.extend([str(results_path), str(review_path), str(review_html_path)])

        return ToolResult(
            success=True,
            data={
                "operation": results["operation"],
                "status": results["status"],
                "output_dir": str(output_dir),
                "results_path": str(results_path),
                "review_path": str(review_path),
                "review_html_path": str(review_html_path),
                "cue_count": len(results["cues"]),
                "cues": results["cues"],
            },
            artifacts=artifacts,
        )

    def _annotate(self, inputs: dict[str, Any]) -> ToolResult:
        annotations = inputs.get("annotations")
        unreviewed_policy = ""
        if not annotations and inputs.get("annotations_path"):
            annotations_payload = json.loads(Path(inputs["annotations_path"]).expanduser().read_text(encoding="utf-8"))
            unreviewed_policy = str(annotations_payload.get("unreviewed_policy", "")).upper()
            annotations = annotations_payload.get("annotations", annotations_payload)
        else:
            unreviewed_policy = str(inputs.get("unreviewed_policy", "")).upper()
        if not isinstance(annotations, dict) or not annotations:
            return ToolResult(success=False, error="annotate operation requires non-empty annotations or annotations_path")

        results_path = Path(inputs["results_path"]).expanduser().resolve()
        results = json.loads(results_path.read_text(encoding="utf-8"))
        valid_decisions = {"PASS", "NEEDS_REVIEW", "WRONG_EXPECTATION"}
        valid_user_decisions = {"APPROVED", "FIX_REQUESTED", "DEFERRED", "REJECTED"}
        by_id = {cue["id"]: cue for cue in results.get("cues", [])}
        if unreviewed_policy == "PASS":
            for cue_id in by_id:
                annotations.setdefault(cue_id, {"decision": "PASS", "reviewer": "human"})
        for cue_id, annotation in annotations.items():
            if cue_id not in by_id:
                return ToolResult(success=False, error=f"Unknown cue id: {cue_id}")
            decision = annotation.get("decision")
            if decision not in valid_decisions:
                return ToolResult(success=False, error=f"Invalid decision for {cue_id}: {decision}")
            user_decision = annotation.get("user_decision")
            if user_decision and user_decision not in valid_user_decisions:
                return ToolResult(success=False, error=f"Invalid user_decision for {cue_id}: {user_decision}")
            by_id[cue_id]["reviewer_annotation"] = {
                "decision": decision,
                "reviewer": annotation.get("reviewer", "agent"),
                "confidence": annotation.get("confidence", ""),
                "issue_category": annotation.get("issue_category", ""),
                "notes": annotation.get("notes", ""),
                "fix_target": annotation.get("fix_target", ""),
                "requires_user_review": bool(annotation.get("requires_user_review", decision != "PASS")),
                "user_decision": user_decision or "",
                "user_notes": annotation.get("user_notes", ""),
            }

        annotated_cues = [
            {
                "cue_id": cue["id"],
                **cue["reviewer_annotation"],
            }
            for cue in results.get("cues", [])
            if cue.get("reviewer_annotation")
        ]
        action_items = [
            {
                "cue_id": annotation["cue_id"],
                "decision": annotation["decision"],
                "issue_category": annotation.get("issue_category", ""),
                "notes": annotation.get("notes", ""),
                "fix_target": annotation.get("fix_target", ""),
            }
            for annotation in annotated_cues
            if annotation.get("decision") != "PASS" or annotation.get("requires_user_review")
        ]
        completion = self._review_completion(results, action_items)
        notes = {
            "version": self.version,
            "tool": self.name,
            "operation": "annotate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "summary": {
                "annotation_count": len(annotated_cues),
                "pass_count": sum(1 for annotation in annotated_cues if annotation.get("decision") == "PASS"),
                "action_item_count": len(action_items),
            },
            "completion": completion,
            "action_items": action_items,
            "annotations": annotated_cues,
        }
        output_path = Path(inputs.get("output_path") or results_path.with_name("review_notes.json")).expanduser().resolve()
        annotated_review_path = output_path.with_name("review_annotated.md")
        annotated_review_html_path = output_path.with_name("review_annotated.html")
        self._write_json(output_path, notes)
        annotated_review_path.write_text(self._review_markdown(results), encoding="utf-8")
        annotated_review_html_path.write_text(self._review_html(results, annotated_review_html_path), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "status": "completed",
                "review_notes_path": str(output_path),
                "annotated_review_path": str(annotated_review_path),
                "annotated_review_html_path": str(annotated_review_html_path),
                "annotation_count": len(notes["annotations"]),
                "review_complete": completion["review_complete"],
                "next_operation": completion["next_operation"],
                "missing_review_cues": completion["missing_review_cues"],
                "pending_review_cues": completion["pending_review_cues"],
                "action_item_count": len(action_items),
                "action_items": action_items,
                "annotations": notes["annotations"],
            },
            artifacts=[str(output_path), str(annotated_review_path), str(annotated_review_html_path)],
        )

    @staticmethod
    def _review_completion(results: dict[str, Any], action_items: list[dict[str, Any]]) -> dict[str, Any]:
        annotated = {
            str(cue.get("id"))
            for cue in results.get("cues", [])
            if cue.get("reviewer_annotation", {}).get("decision")
        }
        all_cue_ids = [str(cue.get("id")) for cue in results.get("cues", [])]
        missing_review_cues = [cue_id for cue_id in all_cue_ids if cue_id not in annotated]
        pending_review_cues = sorted(
            {
                str(item.get("cue_id"))
                for item in action_items
                if item.get("cue_id")
            }
        )
        review_complete = not missing_review_cues and not pending_review_cues
        if review_complete:
            next_operation = "complete"
        elif pending_review_cues:
            next_operation = "revise_and_rerun_review"
        else:
            next_operation = "annotate"
        return {
            "review_complete": review_complete,
            "next_operation": next_operation,
            "missing_review_cues": missing_review_cues,
            "pending_review_cues": pending_review_cues,
        }

    def _load_manifest(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("manifest") is not None:
            manifest = deepcopy(inputs["manifest"])
        elif inputs.get("manifest_path"):
            manifest = json.loads(Path(inputs["manifest_path"]).read_text(encoding="utf-8"))
        else:
            raise ValueError("manifest or manifest_path is required")
        if not manifest.get("video_path"):
            raise ValueError("manifest.video_path is required")
        if not manifest.get("output_dir"):
            raise ValueError("manifest.output_dir is required")
        if not manifest.get("cues"):
            raise ValueError("manifest.cues must contain at least one cue")
        return manifest

    def _load_caption_items(self, path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_items = payload.get("cues") or payload.get("captions") or payload.get("segments") or []
        elif isinstance(payload, list):
            raw_items = payload
        else:
            raw_items = []
        items = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            text = item.get("word") or item.get("text") or item.get("caption") or item.get("narration")
            timestamp = self._item_timestamp_seconds(item)
            if text and timestamp is not None:
                items.append(
                    {
                        "id": item.get("id") or item.get("section_id") or f"caption-{index + 1}",
                        "section_id": item.get("section_id"),
                        "text": str(text),
                        "timestamp_seconds": timestamp,
                        "source_type": "caption",
                        "source_index": index,
                    }
                )
        return items

    def _load_script_items(self, path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_items = payload.get("sections") or payload.get("script") or payload.get("scenes") or payload.get("segments") or []
        elif isinstance(payload, list):
            raw_items = payload
        else:
            raw_items = []
        items = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("narration") or item.get("voiceover")
            timestamp = self._item_timestamp_seconds(item)
            if text and timestamp is not None:
                items.append(
                    {
                        "id": item.get("id") or item.get("section_id") or item.get("scene_id") or f"script-{index + 1}",
                        "section_id": item.get("section_id") or item.get("scene_id") or item.get("id"),
                        "text": str(text),
                        "timestamp_seconds": timestamp,
                        "source_type": "script",
                        "source_index": index,
                    }
                )
        return items

    @staticmethod
    def _item_timestamp_seconds(item: dict[str, Any]) -> float | None:
        for key in ("timestamp_seconds", "time_seconds", "start_seconds", "at_seconds", "start"):
            if key in item:
                return float(item[key])
        for key in ("startMs", "start_ms", "startMilliseconds"):
            if key in item:
                return float(item[key]) / 1000.0
        return None

    def _rank_suggested_cues(
        self,
        items: list[dict[str, Any]],
        *,
        speed_multiplier: float,
        max_cues: int,
        per_category_limit: int,
    ) -> list[dict[str, Any]]:
        scored = []
        seen_texts = set()
        for item in items:
            text = item.get("text", "")
            normalized_text = re.sub(r"\s+", "", text.lower())
            if not normalized_text or normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            score, reasons, category = self._cue_score(text)
            if score <= 0:
                continue
            timestamp = float(item["timestamp_seconds"]) / speed_multiplier if speed_multiplier else float(item["timestamp_seconds"])
            cue_id = self._slug(item.get("id") or text[:32])
            scored.append(
                {
                    "id": cue_id,
                    "section_id": item.get("section_id"),
                    "label": self._suggested_label(text, category),
                    "timestamp_seconds": round(timestamp, 3),
                    "narration": text,
                    "expected_state": "",
                    "risk": f"Rule-based candidate: {', '.join(reasons)}.",
                    "review_questions": [
                        "Does the visible state match this spoken cue?",
                        "Is the reveal early, late, or visually crowded?",
                    ],
                    "score": score,
                    "category": category,
                    "reasons": reasons,
                    "source_type": item.get("source_type"),
                    "source_index": item.get("source_index"),
                }
            )
        scored.sort(key=lambda cue: (-cue["score"], cue["timestamp_seconds"]))
        selected = []
        per_category: dict[str, int] = {}
        for cue in scored:
            category = cue.get("category", "visual-timing")
            if per_category.get(category, 0) >= per_category_limit:
                continue
            selected.append(cue)
            per_category[category] = per_category.get(category, 0) + 1
            if len(selected) >= max_cues:
                break
        return selected

    @staticmethod
    def _cue_score(text: str) -> tuple[int, list[str], str]:
        groups = [
            ("self-check", 7, ["doctor", "自检", "检查环境", "权限", "通过自检"]),
            ("system-api", 6, ["接口", "真实系统", "真实业务数据", "Open API", "业务数据"]),
            ("ecosystem", 6, ["数字花园", "资产", "连接", "生态"]),
            ("feedback", 5, ["反馈", "问题", "处理", "状态", "评估"]),
            ("next-version", 5, ["下一版", "升级", "更新", "回到", "Agent 手里"]),
            ("installation", 4, ["安装", "升级", "Skill", "目录", "配置"]),
            ("question-hook", 3, ["谁来", "怎么", "从哪里", "为什么", "答案"]),
            ("visual-reveal", 3, ["出现", "点亮", "展示", "流程", "节点"]),
        ]
        reasons = []
        category = ""
        score = 0
        for name, weight, keywords in groups:
            hits = [keyword for keyword in keywords if keyword.lower() in text.lower()]
            if hits:
                score += weight + min(len(hits), 3)
                if name == "ecosystem" and any(hit in {"数字花园", "连接"} for hit in hits):
                    score += 4
                reasons.append(f"{name} ({'/'.join(hits[:3])})")
                category = category or name
        return score, reasons, category or "visual-timing"

    @staticmethod
    def _suggested_label(text: str, category: str) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) > 28:
            clean = clean[:28] + "..."
        return f"{category}: {clean}" if category else clean

    def _output_dir(self, manifest: dict[str, Any]) -> Path:
        return Path(manifest["output_dir"]).expanduser().resolve()

    def _build_cues(self, manifest: dict[str, Any], *, duration: float | None) -> list[dict[str, Any]]:
        default_offsets = manifest.get("offsets_seconds", [-0.5, 0.0, 0.5])
        default_tolerance = float(manifest.get("tolerance_seconds", 0.5))
        cues = []
        for raw_cue in manifest.get("cues", []):
            cue = deepcopy(raw_cue)
            cue_id = str(cue.get("id") or cue.get("section_id") or f"cue-{len(cues) + 1}")
            timestamp = self._cue_timestamp(cue)
            offsets = cue.get("offsets_seconds", default_offsets)
            frame_points = []
            for offset in offsets:
                ts = float(timestamp) + float(offset)
                frame_points.append(
                    {
                        "offset_seconds": float(offset),
                        "timestamp_seconds": self._clamp_timestamp(ts, duration),
                    }
                )
            cues.append(
                {
                    "id": cue_id,
                    "section_id": cue.get("section_id"),
                    "label": cue.get("label", cue_id),
                    "timestamp_seconds": float(timestamp),
                    "tolerance_seconds": float(cue.get("tolerance_seconds", default_tolerance)),
                    "narration": cue.get("narration") or cue.get("line") or cue.get("text", ""),
                    "subtitle": cue.get("subtitle") or cue.get("caption") or cue.get("caption_text", ""),
                    "expected_state": cue.get("expected_state") or cue.get("expected") or "",
                    "risk": cue.get("risk", ""),
                    "review_questions": cue.get("review_questions", []),
                    "frame_points": frame_points,
                }
            )
        return cues

    @staticmethod
    def _cue_timestamp(cue: dict[str, Any]) -> float:
        for key in ("timestamp_seconds", "time_seconds", "start_seconds", "at_seconds"):
            if key in cue:
                return float(cue[key])
        if "start" in cue:
            return float(cue["start"])
        raise ValueError(f"Cue {cue.get('id', '<unknown>')} needs timestamp_seconds or start_seconds")

    @staticmethod
    def _clamp_timestamp(value: float, duration: float | None) -> float:
        ts = max(0.0, value)
        if duration is not None and duration > 0:
            ts = min(ts, max(duration - 0.05, 0.0))
        return round(ts, 3)

    def _extract_cue_frames(
        self,
        video_path: Path,
        cue: dict[str, Any],
        cue_dir: Path,
    ) -> list[dict[str, Any]]:
        frames = []
        for index, point in enumerate(cue["frame_points"]):
            offset = point["offset_seconds"]
            ts = point["timestamp_seconds"]
            label = self._offset_label(offset)
            frame_path = cue_dir / f"{index:02d}_{label}_{ts:.3f}s.jpg"
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(ts),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ]
            frame_record = {
                "offset_seconds": offset,
                "timestamp_seconds": ts,
                "label": label,
                "path": str(frame_path),
            }
            try:
                self.run_command(cmd)
                if not frame_path.exists():
                    frame_record["error"] = "Frame extraction did not create a file"
            except Exception as exc:
                frame_record["error"] = str(exc)
            frames.append(frame_record)
        return frames

    def _write_contact_sheet(
        self,
        frames: list[dict[str, Any]],
        cue_dir: Path,
        cue_id: str,
    ) -> Path | None:
        existing = [Path(frame["path"]) for frame in frames if frame.get("path") and Path(frame["path"]).exists()]
        if not existing:
            return None
        sheet_path = cue_dir / f"{self._slug(cue_id)}_contact_sheet.jpg"
        inputs: list[str] = []
        filter_parts: list[str] = []
        labels: list[str] = []
        for index, path in enumerate(existing):
            inputs.extend(["-i", str(path)])
            filter_parts.append(f"[{index}:v]scale=480:-1[v{index}]")
            labels.append(f"[v{index}]")
        filter_complex = ";".join(filter_parts + [f"{''.join(labels)}hstack=inputs={len(existing)}[out]"])
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            str(sheet_path),
        ]
        try:
            self.run_command(cmd)
            return sheet_path if sheet_path.exists() else None
        except Exception:
            return None

    def _initial_review(self, cue: dict[str, Any], *, extract: bool) -> dict[str, Any]:
        """Conservative local first pass for obvious cue review risks.

        This is intentionally not semantic video understanding. It only flags
        conditions that should stop the agent from treating contact sheets as
        reviewed: missing frames, no visible change around a reveal cue,
        changes that appear before/after the target timestamp, and subtitle-like
        cues whose lower frame band looks visually empty.
        """
        language = self._cue_language(cue)
        zh = language == "zh"
        if not extract:
            return {
                "decision": "UNREVIEWED",
                "confidence": "low",
                "issue_category": "dry_run",
                "notes": "Dry run planned cue windows but did not extract frames."
                if not zh
                else "Dry run 只规划了检查窗口，尚未抽取截图。",
                "requires_human_review": True,
            }

        frames = cue.get("frames", [])
        issues: list[str] = []
        metrics: dict[str, Any] = {}

        missing = [
            frame for frame in frames
            if frame.get("error") or not frame.get("path") or not Path(frame["path"]).exists()
        ]
        if missing:
            issues.append(
                f"{len(missing)} cue frame(s) were not extracted successfully."
                if not zh
                else f"{len(missing)} 张 cue 截图没有成功抽取。"
            )

        diffs = self._frame_diffs(frames)
        if diffs:
            metrics["frame_diffs"] = diffs
        text = " ".join(
            str(cue.get(key, ""))
            for key in ("narration", "expected_state", "risk", "label")
        ).lower()
        reveal_sensitive = any(
            token in text
            for token in (
                "highlight",
                "highlighted",
                "reveal",
                "visible",
                "appear",
                "node",
                "flow",
                "点亮",
                "亮起",
                "出现",
                "展示",
                "流程",
                "节点",
                "字幕",
                "caption",
                "subtitle",
            )
        )
        if reveal_sensitive and len(diffs) >= 2:
            before_to_target = diffs[0]["mean_abs_diff"]
            target_to_after = diffs[1]["mean_abs_diff"]
            quiet_threshold = 2.0
            active_threshold = 7.0
            if max(before_to_target, target_to_after) < quiet_threshold:
                issues.append(
                    "Little visible change was detected across the cue window; verify the expected reveal/state is actually present."
                    if not zh
                    else "cue 窗口内可见变化很小，请确认期望的画面状态或点亮效果是否真的出现。"
                )
            elif before_to_target >= active_threshold and target_to_after < quiet_threshold:
                issues.append(
                    "Most visible change happens before the target frame; the reveal may be early."
                    if not zh
                    else "主要画面变化发生在目标帧之前，点亮或切换可能偏早。"
                )
            elif before_to_target < quiet_threshold and target_to_after >= active_threshold:
                issues.append(
                    "Most visible change happens after the target frame; the reveal may be late."
                    if not zh
                    else "主要画面变化发生在目标帧之后，点亮或切换可能偏晚。"
                )

        subtitle_sensitive = any(
            token in text for token in ("字幕", "caption", "captions", "subtitle", "subtitles")
        )
        if subtitle_sensitive:
            subtitle_metrics = self._subtitle_band_metrics(frames)
            if subtitle_metrics:
                metrics["subtitle_band"] = subtitle_metrics
                if subtitle_metrics.get("max_edge_density", 0.0) < 0.015:
                    issues.append(
                        "Subtitle/caption cue has very low lower-frame edge density; subtitles may be missing or too faint."
                        if not zh
                        else "字幕 cue 的画面下方边缘密度很低，字幕可能缺失或太淡。"
                    )

        if issues:
            return {
                "decision": "NEEDS_REVIEW",
                "confidence": "medium" if len(issues) > 1 else "low",
                "issue_category": "auto_initial_review",
                "notes": " ".join(issues),
                "fix_target": "Inspect the contact sheet and adjust cue timing, animation timing, or subtitle rendering before delivery."
                if not zh
                else "请查看截图窗口，并在交付前调整 cue 时间点、动画时间或字幕渲染。",
                "requires_human_review": True,
                "metrics": metrics,
            }
        return {
            "decision": "PASS",
            "confidence": "low",
            "issue_category": "auto_initial_review",
            "notes": "No obvious local heuristic issue found. Human review is still required for semantic correctness."
            if not zh
            else "本地启发式检查没有发现明显问题，但仍需要人工确认语义是否对齐。",
            "requires_human_review": True,
            "metrics": metrics,
        }

    @classmethod
    def _cue_language(cls, cue: dict[str, Any]) -> str:
        text = " ".join(
            str(cue.get(key, ""))
            for key in ("subtitle", "narration", "text", "caption", "expected_state", "risk", "label")
        )
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_words = len(re.findall(r"[A-Za-z]+", text))
        return "zh" if cjk_chars >= 2 and cjk_chars >= latin_words * 0.2 else "en"

    @staticmethod
    def _frame_diffs(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            from PIL import Image, ImageChops, ImageStat
        except Exception:
            return []

        images = []
        for frame in frames:
            path = frame.get("path")
            if not path or not Path(path).exists() or frame.get("error"):
                continue
            try:
                image = Image.open(path).convert("L").resize((96, 54))
                images.append((frame, image))
            except Exception:
                continue
        diffs = []
        for index in range(1, len(images)):
            prev_frame, prev_image = images[index - 1]
            curr_frame, curr_image = images[index]
            diff = ImageChops.difference(prev_image, curr_image)
            mean_abs = ImageStat.Stat(diff).mean[0]
            diffs.append(
                {
                    "from_offset_seconds": prev_frame.get("offset_seconds"),
                    "to_offset_seconds": curr_frame.get("offset_seconds"),
                    "mean_abs_diff": round(float(mean_abs), 3),
                }
            )
        return diffs

    @staticmethod
    def _subtitle_band_metrics(frames: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            from PIL import Image, ImageFilter, ImageStat
        except Exception:
            return {}

        densities = []
        for frame in frames:
            path = frame.get("path")
            if not path or not Path(path).exists() or frame.get("error"):
                continue
            try:
                image = Image.open(path).convert("L")
                width, height = image.size
                band_top = int(height * 0.72)
                band = image.crop((0, band_top, width, height))
                edges = band.filter(ImageFilter.FIND_EDGES)
                stat = ImageStat.Stat(edges)
                edge_density = float(stat.mean[0]) / 255.0
                densities.append(round(edge_density, 4))
            except Exception:
                continue
        if not densities:
            return {}
        return {
            "edge_density_by_frame": densities,
            "max_edge_density": max(densities),
        }

    def _get_duration(self, video_path: Path) -> float:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]
        result = self.run_command(cmd)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))

    @staticmethod
    def _review_markdown(results: dict[str, Any]) -> str:
        lines = [
            f"# Visual Timing QA Review: {results.get('run_id', '')}",
            "",
            f"- Project: `{results.get('project', '')}`",
            f"- Video: `{results.get('video_path', '')}`",
            f"- Created: `{results.get('created_at', '')}`",
            f"- Status: `{results.get('status', '')}`",
            "",
            "Use this review to decide whether each key line is early, late, or visually correct.",
            "",
        ]
        lines.extend(VisualTimingQA._summary_lines(results))
        for cue in results.get("cues", []):
            lines.extend(
                [
                    f"## {cue.get('label') or cue['id']}",
                    "",
                    f"- Cue id: `{cue['id']}`",
                    f"- Section id: `{cue.get('section_id') or ''}`",
                    f"- Target time: `{cue.get('timestamp_seconds', 0):.3f}s`",
                    f"- Tolerance: `+/-{cue.get('tolerance_seconds', 0.5):.3f}s`",
                    f"- Narration: {cue.get('narration', '')}",
                    f"- Expected visual state: {cue.get('expected_state', '')}",
                ]
            )
            if cue.get("risk"):
                lines.append(f"- Risk: {cue['risk']}")
            if cue.get("initial_review"):
                initial = cue["initial_review"]
                lines.extend(
                    [
                        "- Initial auto review:",
                        f"  - Decision: `{initial.get('decision', '')}`",
                        f"  - Confidence: `{initial.get('confidence', '')}`",
                        f"  - Category: `{initial.get('issue_category', '')}`",
                        f"  - Notes: {initial.get('notes', '')}",
                    ]
                )
                if initial.get("fix_target"):
                    lines.append(f"  - Fix target: {initial['fix_target']}")
            if cue.get("review_questions"):
                lines.append("- Review questions:")
                for question in cue["review_questions"]:
                    lines.append(f"  - {question}")
            lines.extend(
                [
                    "",
                    "Reviewer decision:",
                    *VisualTimingQA._decision_lines(cue.get("reviewer_annotation")),
                ]
            )
            if cue.get("contact_sheet"):
                lines.extend(["", f"![contact sheet]({cue['contact_sheet']})"])
            if cue.get("frames"):
                lines.extend(["", "| Offset | Timestamp | Frame |", "|---:|---:|---|"])
                for frame in cue["frames"]:
                    link = f"[jpg]({frame.get('path')})" if frame.get("path") else "-"
                    if frame.get("error"):
                        link = f"{link} - ERROR"
                    lines.append(
                        f"| {frame.get('offset_seconds', 0):.3f}s | "
                        f"{frame.get('timestamp_seconds', 0):.3f}s | {link} |"
                    )
            else:
                planned = ", ".join(
                    f"{point['timestamp_seconds']:.3f}s"
                    for point in cue.get("frame_points", [])
                )
                lines.extend(["", f"- Planned frame timestamps: `{planned}`"])
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def _review_html(cls, results: dict[str, Any], html_path: Path) -> str:
        language = cls._review_language(results)
        copy = cls._ui_copy(language)
        title = f"{copy['title']}: {results.get('run_id', '')}".strip()
        summary = cls._summary_counts(results)

        css = """
:root {
  color-scheme: dark;
  --bg: #09111e;
  --panel: rgba(255,255,255,.06);
  --panel-strong: rgba(255,255,255,.1);
  --border: rgba(150,176,220,.24);
  --text: #eef5ff;
  --muted: #a8b7d0;
  --accent: #62d8ff;
  --ok: #4ade80;
  --warn: #facc15;
  --bad: #fb7185;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 18% 0%, rgba(98,216,255,.18), transparent 30rem),
    linear-gradient(145deg, #07101d 0%, var(--bg) 58%, #0f1626 100%);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", sans-serif;
  line-height: 1.5;
}
main { max-width: 1180px; margin: 0 auto; padding: 34px 28px 64px; }
header { margin-bottom: 24px; }
h1 { margin: 0 0 10px; font-size: 30px; letter-spacing: 0; }
p { color: var(--muted); }
.summary { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.review-toolbar {
  align-items: flex-end;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.045);
  border-radius: 12px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  margin-top: 18px;
  padding: 14px;
}
.filter-controls {
  align-items: flex-end;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.filter-control {
  color: var(--muted);
  display: grid;
  gap: 6px;
  font-size: 12px;
}
.filter-control select,
.review-form textarea {
  background: rgba(0,0,0,.24);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: var(--text);
  font: inherit;
  padding: 8px 10px;
  width: 100%;
}
.filter-control select { min-width: 170px; }
.review-action {
  align-items: flex-end;
  display: grid;
  gap: 6px;
  justify-items: end;
  max-width: 360px;
}
.review-action .hint { color: var(--muted); font-size: 13px; text-align: right; }
.pill {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 999px;
  padding: 6px 12px;
  color: #dbe8fb;
  font-size: 13px;
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
.primary-action:hover,
.primary-action:focus-visible {
  background: linear-gradient(135deg, rgba(129,230,255,1), rgba(94,234,148,.86));
  color: #06111f;
}
.floating-actions {
  bottom: 22px;
  display: grid;
  gap: 10px;
  position: fixed;
  right: 22px;
  z-index: 45;
}
.floating-actions .pill {
  backdrop-filter: blur(12px);
  box-shadow: 0 14px 34px rgba(0,0,0,.26);
}
button.pill {
  cursor: pointer;
  font: inherit;
}
button.pill:hover,
button.pill:focus-visible,
button.pill.is-active {
  background: rgba(98,216,255,.16);
  border-color: rgba(98,216,255,.62);
  color: var(--text);
  outline: none;
}
.cue.is-hidden { display: none; }
.save-row {
  align-items: center;
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.save-status { color: var(--muted); font-size: 13px; }
.cue {
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 14px;
  padding: 22px;
  margin: 22px 0;
  box-shadow: 0 20px 52px rgba(0,0,0,.24);
}
.cue-head { display: flex; gap: 12px; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; }
.cue h2 { margin: 0; font-size: 22px; letter-spacing: 0; }
.badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
  border: 1px solid var(--border);
  background: rgba(8,14,27,.72);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  color: #dbe8fb;
}
.pass { border-color: rgba(74,222,128,.45); color: var(--ok); }
.needs { border-color: rgba(250,204,21,.5); color: var(--warn); }
.wrong, .rejected { border-color: rgba(251,113,133,.5); color: var(--bad); }
.unreviewed { color: var(--muted); }
.meta { color: #94a7c4; font-size: 13px; margin: 10px 0; }
.text-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
.box {
  border: 1px solid rgba(255,255,255,.07);
  background: rgba(0,0,0,.2);
  border-radius: 10px;
  padding: 12px 14px;
}
.box-title { color: var(--muted); font-size: 12px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .04em; }
.review-note { color: #dbe8fb; }
.questions { margin: 12px 0 0; color: var(--muted); }
.review-form {
  border: 1px solid rgba(98,216,255,.18);
  background: rgba(8,14,27,.54);
  border-radius: 10px;
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding: 12px;
}
.review-form label {
  color: var(--muted);
  display: grid;
  gap: 6px;
  font-size: 12px;
}
.review-options {
  border: 0;
  margin: 0;
  padding: 0;
}
.review-options legend {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.radio-row {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.radio-pill {
  align-items: center;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.22);
  border-radius: 999px;
  color: #dbe8fb;
  cursor: pointer;
  display: grid;
  gap: 8px;
  grid-template-columns: 18px 1fr;
  justify-items: start;
  min-height: 42px;
  padding: 8px 12px;
  text-align: left;
  width: 100%;
}
.radio-pill input {
  accent-color: var(--accent);
  margin: 0;
  place-self: center;
}
.radio-pill span {
  align-self: center;
  min-width: 0;
  white-space: nowrap;
}
.radio-pill:has(input:checked) {
  background: rgba(98,216,255,.16);
  border-color: rgba(98,216,255,.68);
  color: var(--text);
}
.review-form textarea { min-height: 74px; resize: vertical; }
.review-form .conditional-note.is-hidden { display: none; }
.warning-note {
  border: 1px solid rgba(250,204,21,.32);
  background: rgba(250,204,21,.08);
  border-radius: 8px;
  color: #fde68a;
  display: none;
  font-size: 13px;
  padding: 8px 10px;
}
.warning-note.is-visible { display: block; }
.form-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr;
}
.sheet { margin-top: 14px; }
.sheet-action {
  align-items: center;
  display: inline-flex;
  gap: 8px;
  min-height: 38px;
  padding: 8px 12px;
  width: auto;
}
.frames {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.frame {
  border: 1px solid rgba(255,255,255,.08);
  background: rgba(8,14,27,.66);
  border-radius: 10px;
  padding: 10px;
}
.image-open {
  appearance: none;
  background: rgba(0,0,0,.22);
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 8px;
  color: inherit;
  cursor: zoom-in;
  display: block;
  font: inherit;
  overflow: hidden;
  padding: 0;
  text-align: left;
  width: 100%;
}
.image-open:hover,
.image-open:focus-visible {
  border-color: rgba(98,216,255,.7);
  box-shadow: 0 0 0 3px rgba(98,216,255,.16);
  outline: none;
}
.image-open img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: 8px;
  background: rgba(0,0,0,.28);
}
.frame .meta { margin: 7px 0 0; }
.lightbox-open { overflow: hidden; }
.lightbox {
  align-items: center;
  background: rgba(2,7,15,.92);
  display: none;
  inset: 0;
  justify-content: center;
  padding: 70px 72px 34px;
  position: fixed;
  z-index: 50;
}
.lightbox.is-open { display: flex; }
.lightbox-main {
  align-items: center;
  display: flex;
  height: 100%;
  justify-content: center;
  width: 100%;
}
.lightbox img {
  background: rgba(0,0,0,.3);
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 10px;
  box-shadow: 0 24px 72px rgba(0,0,0,.45);
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
.lightbox-bar {
  align-items: center;
  display: flex;
  gap: 10px;
  left: 22px;
  position: absolute;
  right: 22px;
  top: 18px;
}
.lightbox-title {
  color: #dbe8fb;
  flex: 1;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lightbox-btn {
  appearance: none;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 999px;
  color: var(--text);
  cursor: pointer;
  font: inherit;
  min-height: 36px;
  padding: 7px 12px;
}
.lightbox-btn:hover,
.lightbox-btn:focus-visible {
  background: rgba(98,216,255,.18);
  border-color: rgba(98,216,255,.62);
  outline: none;
}
.lightbox-btn:disabled {
  cursor: not-allowed;
  opacity: .32;
}
.lightbox-btn:disabled:hover {
  background: rgba(255,255,255,.08);
  border-color: rgba(255,255,255,.18);
}
.lightbox-arrow {
  border-radius: 999px;
  font-size: 30px;
  height: 52px;
  line-height: 1;
  padding: 0;
  position: absolute;
  top: calc(50% - 26px);
  width: 52px;
}
.lightbox-prev { left: 14px; }
.lightbox-next { right: 14px; }
.lightbox-counter { color: var(--muted); min-width: 54px; text-align: center; }
.toast {
  align-items: center;
  background: rgba(9,17,30,.96);
  border: 1px solid rgba(98,216,255,.72);
  border-radius: 16px;
  box-shadow: 0 18px 48px rgba(0,0,0,.42);
  color: var(--text);
  display: none;
  gap: 12px;
  left: 50%;
  max-width: min(560px, calc(100vw - 36px));
  padding: 18px 20px;
  position: fixed;
  top: 90px;
  transform: translateX(-50%);
  width: max-content;
  z-index: 60;
}
.toast.is-visible { display: flex; }
.toast::before {
  align-items: center;
  background: rgba(74,222,128,.16);
  border: 1px solid rgba(74,222,128,.48);
  border-radius: 999px;
  color: var(--ok);
  content: "✓";
  display: flex;
  flex: 0 0 auto;
  font-weight: 700;
  height: 34px;
  justify-content: center;
  width: 34px;
}
.toast strong { display: block; margin-bottom: 4px; }
.toast span { color: var(--muted); font-size: 13px; }
.export-panel {
  border: 1px solid rgba(98,216,255,.28);
  background: rgba(8,14,27,.72);
  border-radius: 12px;
  display: none;
  margin-top: 14px;
  padding: 14px;
}
.export-panel.is-visible { display: block; }
.export-panel h2 { font-size: 18px; margin: 0 0 8px; }
.export-panel p { margin: 0 0 10px; }
.export-panel textarea {
  background: rgba(0,0,0,.28);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  color: var(--text);
  font: 12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  min-height: 180px;
  padding: 10px;
  width: 100%;
}
.empty {
  border: 1px dashed rgba(150,176,220,.26);
  color: var(--muted);
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 14px;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
@media (max-width: 760px) {
  main { padding: 28px 16px 46px; }
  h1 { font-size: 25px; }
  .review-toolbar { align-items: stretch; flex-direction: column; }
  .review-action { justify-items: start; max-width: none; }
  .review-action .hint { text-align: left; }
  .text-grid { grid-template-columns: 1fr; }
  .form-grid { grid-template-columns: 1fr; }
  .floating-actions {
    bottom: 14px;
    left: 14px;
    right: 14px;
    grid-template-columns: 1fr 1fr;
  }
  .lightbox { padding: 62px 14px 22px; }
  .lightbox-arrow { bottom: 18px; top: auto; }
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
            f"<span class=\"pill\">{escape(copy['cues'])}: {summary['total']}</span>",
            "</div>",
            "<div class=\"review-toolbar\">",
            "<div class=\"filter-controls\">",
            "<label class=\"filter-control\">",
            f"{escape(copy['initial_filter'])}",
            (
                "<select data-initial-filter>"
                f"<option value=\"all\">{escape(copy['filter_all'])}</option>"
                f"<option value=\"pass\">{escape(copy['initial_pass'])}: {summary['initial_pass']}</option>"
                f"<option value=\"needs\">{escape(copy['initial_failed'])}: {summary['initial_needs_review']}</option>"
                "</select>"
            ),
            "</label>",
            "<label class=\"filter-control\">",
            f"{escape(copy['review_filter'])}",
            (
                "<select data-review-filter>"
                f"<option value=\"all\">{escape(copy['filter_all'])}</option>"
                f"<option value=\"reviewed\">{escape(copy['reviewed'])}: {summary['reviewed']}</option>"
                f"<option value=\"unreviewed\">{escape(copy['unreviewed'])}: {summary['unreviewed']}</option>"
                "</select>"
            ),
            "</label>",
            "</div>",
            "<div class=\"review-action\">",
            (
                f"<button type=\"button\" class=\"pill primary-action\" data-save-review "
                f"data-submitted-label=\"{escape(copy['submitted_button'], quote=True)}\" "
                f"data-run-id=\"{escape(str(results.get('run_id') or 'visual-timing-review'), quote=True)}\">"
                f"{escape(copy['save_review'])}</button>"
            ),
            (
                f"<span class=\"save-status\" data-save-status "
                f"data-submitted-text=\"{escape(copy['submitted_hint'], quote=True)}\">"
                f"{escape(copy['save_hint'])}</span>"
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

        for cue in results.get("cues", []):
            lines.append(cls._cue_html(cue, html_path, copy))

        lines.extend(
            [
                "</main>",
                cls._lightbox_html(copy),
                "</body>",
                "</html>",
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _filter_button(label: str, count: int, filter_name: str, *, active: bool = False) -> str:
        active_class = " is-active" if active else ""
        return (
            f"<button type=\"button\" class=\"pill filter-pill{active_class}\" "
            f"data-filter=\"{escape(filter_name, quote=True)}\">"
            f"{escape(label)}: {int(count)}</button>"
        )

    @classmethod
    def _cue_html(cls, cue: dict[str, Any], html_path: Path, copy: dict[str, str]) -> str:
        initial = cue.get("initial_review") or {}
        annotation = cue.get("reviewer_annotation") or {}
        initial_decision = initial.get("decision", "UNREVIEWED")
        reviewer_decision = annotation.get("decision", "UNREVIEWED")
        badge_initial = cls._decision_class(initial_decision)
        badge_reviewer = cls._decision_class(reviewer_decision)
        target = cue.get("timestamp_seconds", 0)
        tolerance = cue.get("tolerance_seconds", 0.5)
        requires_reviewer = (
            reviewer_decision in {"NEEDS_REVIEW", "WRONG_EXPECTATION"}
            or bool(annotation.get("requires_user_review"))
        )

        lines = [
            (
                f"<section class=\"cue\" data-cue-card "
                f"data-initial-decision=\"{escape(str(initial_decision), quote=True)}\" "
                f"data-reviewer-decision=\"{escape(str(reviewer_decision), quote=True)}\" "
                f"data-reviewer-needs=\"{'true' if requires_reviewer else 'false'}\" "
                f"data-reviewed=\"{'true' if annotation.get('decision') else 'false'}\">"
            ),
            "<div class=\"cue-head\">",
            f"<h2>{escape(str(cue.get('label') or cue.get('id') or ''))}</h2>",
            "<div class=\"badges\">",
            f"<span class=\"badge {badge_initial}\">{escape(copy['auto'])}: {escape(str(initial_decision))}</span>",
            f"<span class=\"badge {badge_reviewer}\">{escape(copy['reviewer'])}: {escape(str(reviewer_decision))}</span>",
            "</div>",
            "</div>",
            (
                f"<div class=\"meta\">{escape(copy['cue_id'])}: {escape(str(cue.get('id') or ''))} · "
                f"{escape(copy['section'])}: {escape(str(cue.get('section_id') or '-'))} · "
                f"{escape(copy['time'])}: {float(target):.3f}s · "
                f"{escape(copy['tolerance'])}: +/-{float(tolerance):.3f}s</div>"
            ),
            "<div class=\"text-grid\">",
            cls._html_box(copy["narration"], cue.get("narration", "")),
            cls._html_box(copy["expected"], cue.get("expected_state", "")),
            "</div>",
        ]
        if cue.get("risk"):
            lines.append(cls._html_box(copy["risk"], cue.get("risk", "")))
        if initial:
            lines.append(cls._html_box(copy["auto_notes"], initial.get("notes", ""), class_name="review-note"))
            if initial.get("fix_target"):
                lines.append(cls._html_box(copy["fix_target"], initial.get("fix_target", "")))
        if annotation:
            review_text = annotation.get("notes") or annotation.get("fix_target") or ""
            lines.append(cls._html_box(copy["review_notes"], review_text))
            if annotation.get("user_decision") or annotation.get("user_notes"):
                lines.append(
                    cls._html_box(
                        copy["user_decision"],
                        f"{annotation.get('user_decision', '')} {annotation.get('user_notes', '')}".strip(),
                    )
                )
        if cue.get("review_questions"):
            lines.append("<div class=\"questions\"><strong>" + escape(copy["questions"]) + "</strong><ul>")
            for question in cue["review_questions"]:
                lines.append(f"<li>{escape(str(question))}</li>")
            lines.append("</ul></div>")

        lines.append(cls._review_form_html(cue, copy))

        if cue.get("frames"):
            lines.append("<div class=\"frames\">")
            for frame in cue["frames"]:
                lines.append(cls._frame_html(frame, html_path, copy, group=str(cue.get("id") or "cue")))
            lines.append("</div>")
        else:
            planned = ", ".join(f"{point['timestamp_seconds']:.3f}s" for point in cue.get("frame_points", []))
            lines.append(f"<div class=\"empty\">{escape(copy['planned_frames'])}: {escape(planned)}</div>")

        lines.append("</section>")
        return "\n".join(lines)

    @staticmethod
    def _review_form_html(cue: dict[str, Any], copy: dict[str, str]) -> str:
        cue_id = str(cue.get("id") or "")
        annotation = cue.get("reviewer_annotation") or {}
        decision = str(annotation.get("decision") or "")
        notes = str(annotation.get("notes") or "")
        option_specs = [
            ("", copy["decision_empty"]),
            ("PASS", copy["decision_pass"]),
            ("NEEDS_REVIEW", copy["decision_needs"]),
            ("WRONG_EXPECTATION", copy["decision_wrong"]),
        ]

        def radios(specs: list[tuple[str, str]], selected: str) -> str:
            return "".join(
                (
                    f"<label class=\"radio-pill\">"
                    f"<input type=\"radio\" name=\"decision-{escape(cue_id, quote=True)}\" "
                    f"data-review-field=\"decision\" value=\"{escape(value, quote=True)}\""
                    f"{' checked' if value == selected else ''}>"
                    f"<span>{escape(label)}</span>"
                    f"</label>"
                )
                for value, label in specs
            )

        return "\n".join(
            [
                f"<form class=\"review-form\" data-review-form data-cue-id=\"{escape(cue_id, quote=True)}\">",
                "<div class=\"form-grid\">",
                "<fieldset class=\"review-options\">",
                f"<legend>{escape(copy['review_decision'])}</legend>",
                f"<div class=\"radio-row\">{radios(option_specs, decision)}</div>",
                "</fieldset>",
                f"<label class=\"conditional-note{' is-hidden' if decision not in {'NEEDS_REVIEW', 'WRONG_EXPECTATION'} else ''}\">",
                f"{escape(copy['review_notes_field'])}",
                f"<textarea data-review-field=\"notes\">{escape(notes)}</textarea>",
                "</label>",
                "</div>",
                f"<div class=\"warning-note{' is-visible' if decision == 'WRONG_EXPECTATION' else ''}\" data-wrong-warning>{escape(copy['wrong_warning'])}</div>",
                "</form>",
            ]
        )

    @staticmethod
    def _lightbox_html(copy: dict[str, str]) -> str:
        script = """
(() => {
  const items = Array.from(document.querySelectorAll('[data-lightbox-src]')).map((button) => ({
    src: button.dataset.lightboxSrc,
    title: button.dataset.lightboxTitle || button.querySelector('img')?.alt || '',
    group: button.dataset.lightboxGroup || 'default'
  }));
  if (!items.length) return;
  const groups = new Map();
  items.forEach((item) => {
    if (!groups.has(item.group)) groups.set(item.group, []);
    groups.get(item.group).push(item);
  });
  const modal = document.querySelector('[data-lightbox]');
  const image = modal.querySelector('[data-lightbox-image]');
  const title = modal.querySelector('[data-lightbox-title]');
  const counter = modal.querySelector('[data-lightbox-counter]');
  const prevButton = modal.querySelector('[data-lightbox-prev]');
  const nextButton = modal.querySelector('[data-lightbox-next]');
  let activeItems = items;
  let index = 0;

  function show(nextIndex) {
    index = Math.max(0, Math.min(nextIndex, activeItems.length - 1));
    image.src = activeItems[index].src;
    image.alt = activeItems[index].title;
    title.textContent = activeItems[index].title;
    counter.textContent = `${index + 1} / ${activeItems.length}`;
    prevButton.disabled = index === 0;
    nextButton.disabled = index === activeItems.length - 1;
  }

  function open(buttonIndex) {
    const item = items[buttonIndex];
    activeItems = groups.get(item.group) || [item];
    show(activeItems.indexOf(item));
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('lightbox-open');
    modal.querySelector('[data-lightbox-close]').focus();
  }

  function close() {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('lightbox-open');
    image.removeAttribute('src');
  }

  document.querySelectorAll('[data-lightbox-src]').forEach((button, buttonIndex) => {
    button.addEventListener('click', () => open(buttonIndex));
  });
  prevButton.addEventListener('click', () => show(index - 1));
  nextButton.addEventListener('click', () => show(index + 1));
  modal.querySelector('[data-lightbox-close]').addEventListener('click', close);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener('keydown', (event) => {
    if (!modal.classList.contains('is-open')) return;
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowLeft' && index > 0) show(index - 1);
    if (event.key === 'ArrowRight' && index < activeItems.length - 1) show(index + 1);
  });

  const initialFilter = document.querySelector('[data-initial-filter]');
  const reviewFilter = document.querySelector('[data-review-filter]');
  const cueCards = Array.from(document.querySelectorAll('[data-cue-card]'));
  function matchesFilters(card) {
    const initial = initialFilter?.value || 'all';
    const review = reviewFilter?.value || 'all';
    const initialOk =
      initial === 'all' ||
      (initial === 'pass' && card.dataset.initialDecision === 'PASS') ||
      (initial === 'needs' && card.dataset.initialDecision === 'NEEDS_REVIEW');
    const reviewOk =
      review === 'all' ||
      (review === 'reviewed' && card.dataset.reviewed === 'true') ||
      (review === 'unreviewed' && card.dataset.reviewed !== 'true');
    return initialOk && reviewOk;
  }
  function applyFilters() {
    cueCards.forEach((card) => card.classList.toggle('is-hidden', !matchesFilters(card)));
  }
  initialFilter?.addEventListener('change', applyFilters);
  reviewFilter?.addEventListener('change', applyFilters);

  const storageKey = `visual-timing-review:${location.pathname}`;
  const forms = Array.from(document.querySelectorAll('[data-review-form]'));
  const status = document.querySelector('[data-save-status]');
  const saveButtons = Array.from(document.querySelectorAll('[data-save-review]'));
  const runId = saveButtons[0]?.dataset.runId || document.title;
  const toast = document.querySelector('[data-toast]');
  const exportPanel = document.querySelector('[data-export-panel]');
  const exportJson = document.querySelector('[data-export-json]');
  document.querySelector('[data-scroll-top]')?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  function storeDraft(payload) {
    try {
      localStorage.setItem(storageKey, JSON.stringify(payload));
    } catch (_) {}
  }
  async function copyText(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {}
    try {
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
    } catch (_) {
      return false;
    }
  }
  function refreshForm(form) {
    const decision = form.querySelector('[data-review-field="decision"]:checked')?.value || '';
    form.querySelector('.conditional-note')?.classList.toggle('is-hidden', !['NEEDS_REVIEW', 'WRONG_EXPECTATION'].includes(decision));
    form.querySelector('[data-wrong-warning]')?.classList.toggle('is-visible', decision === 'WRONG_EXPECTATION');
    const card = form.closest('[data-cue-card]');
    if (card) {
      card.dataset.reviewed = decision ? 'true' : 'false';
      card.dataset.reviewerDecision = decision || 'UNREVIEWED';
      card.dataset.reviewerNeeds = decision && decision !== 'PASS' ? 'true' : 'false';
    }
    applyFilters();
  }
  function collectAnnotations({ includeImplicitPass = false } = {}) {
    const annotations = {};
    forms.forEach((form) => {
      const cueId = form.dataset.cueId;
      const fields = {};
      form.querySelectorAll('[data-review-field]').forEach((field) => {
        const name = field.dataset.reviewField;
        if (field.type === 'radio') {
          if (field.checked) fields[name] = field.value.trim();
        } else {
          fields[name] = field.value.trim();
        }
      });
      const decision = fields.decision || (includeImplicitPass ? 'PASS' : '');
      if (decision) {
        const needsAdjustment = decision !== 'PASS';
        annotations[cueId] = {
          decision,
          reviewer: 'human',
          confidence: '',
          issue_category: decision === 'WRONG_EXPECTATION' ? 'cue_expectation' : '',
          notes: fields.notes || '',
          fix_target: needsAdjustment ? (fields.notes || '') : '',
          requires_user_review: needsAdjustment,
          user_decision: '',
          user_notes: ''
        };
      }
    });
    return annotations;
  }
  function applyAnnotations(annotations) {
    forms.forEach((form) => {
      const annotation = annotations[form.dataset.cueId];
      if (!annotation) return;
      form.querySelectorAll('[data-review-field]').forEach((field) => {
        const name = field.dataset.reviewField;
        if (!(name in annotation)) return;
        if (field.type === 'radio') field.checked = field.value === (annotation[name] || '');
        else field.value = annotation[name] || '';
      });
      refreshForm(form);
    });
  }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
    if (saved.annotations) applyAnnotations(saved.annotations);
  } catch (_) {}
  forms.forEach((form) => {
    refreshForm(form);
    form.addEventListener('input', () => {
      refreshForm(form);
      const payload = { saved_at: new Date().toISOString(), annotations: collectAnnotations() };
      storeDraft(payload);
      if (status) status.textContent = status.dataset.draftText || status.textContent;
    });
    form.addEventListener('change', () => {
      refreshForm(form);
      const payload = { saved_at: new Date().toISOString(), annotations: collectAnnotations() };
      storeDraft(payload);
      if (status) status.textContent = status.dataset.draftText || status.textContent;
    });
  });
  if (status) status.dataset.draftText = status.textContent;
  async function submitReview(clickedButton) {
      const originalTexts = new Map(saveButtons.map((button) => [button, button.textContent]));
      saveButtons.forEach((button) => {
        button.disabled = true;
        button.textContent = button.dataset.submittedLabel || 'Submitted';
      });
      const annotations = collectAnnotations({ includeImplicitPass: true });
      const payload = {
        version: '1.0',
        run_id: runId,
        saved_at: new Date().toISOString(),
        unreviewed_policy: 'PASS',
        annotations
      };
      const jsonText = JSON.stringify(payload, null, 2);
      storeDraft(payload);
      const copied = await copyText(jsonText);
      try {
        const blob = new Blob([jsonText], { type: 'application/json' });
        const link = document.createElement('a');
        const safeRun = (payload.run_id || 'visual-timing-review').replace(/[^a-zA-Z0-9_-]+/g, '-');
        link.href = URL.createObjectURL(blob);
        link.download = `${safeRun}-review-notes.json`;
        document.body.appendChild(link);
        link.click();
        URL.revokeObjectURL(link.href);
        link.remove();
      } catch (_) {}
      if (exportPanel && exportJson) {
        exportJson.value = jsonText;
        exportPanel.classList.toggle('is-visible', !copied);
      }
      if (status) status.textContent = status.dataset.submittedText || 'Review submitted.';
      if (toast) {
        toast.classList.add('is-visible');
        window.clearTimeout(toast._timer);
        toast._timer = window.setTimeout(() => {
          toast.classList.remove('is-visible');
          saveButtons.forEach((button) => {
            button.disabled = false;
            button.textContent = originalTexts.get(button) || button.textContent;
          });
        }, 5200);
      } else {
        window.setTimeout(() => {
          saveButtons.forEach((button) => {
            button.disabled = false;
            button.textContent = originalTexts.get(button) || button.textContent;
          });
        }, 1800);
      }
  }
  saveButtons.forEach((button) => button.addEventListener('click', () => submitReview(button)));
})();
""".strip()
        return "\n".join(
            [
                "<div class=\"lightbox\" data-lightbox aria-hidden=\"true\" role=\"dialog\" aria-modal=\"true\">",
                "<div class=\"lightbox-bar\">",
                f"<div class=\"lightbox-title\" data-lightbox-title>{escape(copy['image_preview'])}</div>",
                "<div class=\"lightbox-counter\" data-lightbox-counter></div>",
                f"<button type=\"button\" class=\"lightbox-btn\" data-lightbox-close>{escape(copy['close'])}</button>",
                "</div>",
                f"<button type=\"button\" class=\"lightbox-btn lightbox-arrow lightbox-prev\" data-lightbox-prev aria-label=\"{escape(copy['previous'], quote=True)}\">‹</button>",
                "<div class=\"lightbox-main\"><img data-lightbox-image alt=\"\"></div>",
                f"<button type=\"button\" class=\"lightbox-btn lightbox-arrow lightbox-next\" data-lightbox-next aria-label=\"{escape(copy['next'], quote=True)}\">›</button>",
                "</div>",
                f"<script>{script}</script>",
                "<div class=\"toast\" data-toast>",
                f"<strong>{escape(copy['toast_title'])}</strong>",
                f"<span>{escape(copy['toast_body'])}</span>",
                "</div>",
            ]
        )

    @staticmethod
    def _html_box(title: str, value: Any, *, class_name: str = "") -> str:
        return (
            "<div class=\"box\">"
            f"<div class=\"box-title\">{escape(str(title))}</div>"
            f"<div class=\"{escape(class_name)}\">{escape(str(value or '-'))}</div>"
            "</div>"
        )

    @classmethod
    def _frame_html(cls, frame: dict[str, Any], html_path: Path, copy: dict[str, str], *, group: str) -> str:
        path = frame.get("path")
        offset = frame.get("offset_seconds", 0)
        ts = frame.get("timestamp_seconds", 0)
        if path and Path(path).expanduser().exists() and not frame.get("error"):
            src = cls._html_asset_src(path, html_path)
            title = f"{copy['frame']}: {float(offset):+.3f}s / {float(ts):.3f}s"
            media = (
                f"<button type=\"button\" class=\"image-open\" "
                f"data-lightbox-src=\"{escape(src, quote=True)}\" "
                f"data-lightbox-group=\"{escape(group, quote=True)}\" "
                f"data-lightbox-title=\"{escape(title, quote=True)}\">"
                f"<img src=\"{escape(src, quote=True)}\" alt=\"{escape(title, quote=True)}\" loading=\"lazy\">"
                "</button>"
            )
        else:
            media = f"<div class=\"empty\">{escape(copy['frame_missing'])}</div>"
        error = f" · {escape(str(frame.get('error')))}" if frame.get("error") else ""
        return (
            "<article class=\"frame\">"
            f"{media}"
            f"<div class=\"meta\">{float(offset):+.3f}s · {float(ts):.3f}s{error}</div>"
            "</article>"
        )

    @staticmethod
    def _html_asset_src(path: str, html_path: Path) -> str:
        asset_path = Path(path).expanduser().resolve()
        try:
            return asset_path.relative_to(html_path.parent.resolve()).as_posix()
        except ValueError:
            return asset_path.as_uri()

    @staticmethod
    def _decision_class(decision: str) -> str:
        normalized = (decision or "UNREVIEWED").lower()
        if normalized == "pass":
            return "pass"
        if normalized in {"needs_review", "fix_requested"}:
            return "needs"
        if normalized in {"wrong_expectation", "rejected"}:
            return "wrong"
        return "unreviewed"

    @classmethod
    def _summary_counts(cls, results: dict[str, Any]) -> dict[str, Any]:
        counts = {
            "total": len(results.get("cues", [])),
            "initial_needs_review": 0,
            "initial_pass": 0,
            "reviewer_needs_review": 0,
            "reviewed": 0,
            "unreviewed": 0,
            "initial_queue": [],
        }
        for cue in results.get("cues", []):
            initial = cue.get("initial_review") or {}
            annotation = cue.get("reviewer_annotation") or {}
            if initial.get("decision") == "NEEDS_REVIEW":
                counts["initial_needs_review"] += 1
                counts["initial_queue"].append(cue)
            if initial.get("decision") == "PASS":
                counts["initial_pass"] += 1
            decision = annotation.get("decision")
            if decision in {"NEEDS_REVIEW", "WRONG_EXPECTATION"} or annotation.get("requires_user_review"):
                counts["reviewer_needs_review"] += 1
            if decision:
                counts["reviewed"] += 1
            else:
                counts["unreviewed"] += 1
        return counts

    @classmethod
    def _review_language(cls, results: dict[str, Any]) -> str:
        explicit_language = str(results.get("review_language") or "").lower()
        if explicit_language.startswith("zh"):
            return "zh"
        if explicit_language.startswith("en"):
            return "en"
        subtitle_text = " ".join(str(cue.get("subtitle", "")) for cue in results.get("cues", []))
        narration_text = " ".join(str(cue.get("narration", "")) for cue in results.get("cues", []))
        if cls._looks_chinese(f"{subtitle_text} {narration_text}"):
            return "zh"
        text = " ".join(
            " ".join(str(cue.get(key, "")) for key in ("label", "subtitle", "narration", "expected_state", "risk"))
            for cue in results.get("cues", [])
        )
        if cls._looks_chinese(text):
            return "zh"
        return "en"

    @staticmethod
    def _looks_chinese(text: str) -> bool:
        cjk_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_words = len(re.findall(r"[A-Za-z]+", text))
        return cjk_chars >= 10 and cjk_chars >= latin_words * 0.35

    @staticmethod
    def _ui_copy(language: str) -> dict[str, str]:
        if language == "zh":
            return {
                "title": "Visual Timing QA 审片",
                "description": "逐个检查旁白时间点附近的画面状态、截图窗口和自动初审结果。",
                "project": "项目",
                "cues": "检查点",
                "initial_needs": "自动初审待看",
                "initial_pass": "自动初审通过",
                "initial_failed": "初审未通过",
                "initial_filter": "初审状态",
                "review_filter": "评审状态",
                "filter_all": "全部",
                "reviewed": "已评审",
                "reviewer_needs": "人工待看",
                "unreviewed": "未评审",
                "save_review": "提交评审",
                "submitted_button": "已提交",
                "back_to_top": "返回顶部",
                "save_hint": "只标需要调整的项即可；提交时未评审项会按通过记录。",
                "submitted_hint": "评审内容已复制到剪贴板。粘贴发送给 Agent 后，Agent 会按评审结果调整和记录；未评审项按通过处理。",
                "toast_title": "评审已保存",
                "toast_body": "评审内容已复制到剪贴板。粘贴发送给 Agent 即可处理；未评审项会按通过记录。",
                "export_title": "评审记录已生成",
                "export_body": "自动复制失败时才会显示这里的 JSON；请复制后发送给 Agent。未评审项会按通过记录。",
                "initial_queue": "自动初审队列",
                "auto": "自动初审",
                "reviewer": "人工评审",
                "cue_id": "Cue",
                "section": "段落",
                "time": "时间",
                "tolerance": "容差",
                "narration": "旁白",
                "expected": "期望画面",
                "risk": "风险",
                "auto_notes": "自动初审说明",
                "review_notes": "人工评审说明",
                "review_decision": "人工结论",
                "review_notes_field": "评审意见",
                "wrong_warning": "选择“检查点不准确”表示这个检查点本身可能需要调整，会触发对 QA 检查点设计或抓取逻辑的复盘，请谨慎使用。",
                "fix_target": "修复目标",
                "user_decision": "用户决定",
                "user_notes": "补充说明",
                "requires_user_review": "需要继续人工确认",
                "decision_empty": "未评审",
                "decision_pass": "通过",
                "decision_needs": "需要调整",
                "decision_wrong": "检查点不准确",
                "user_decision_empty": "无需用户决定",
                "user_approved": "确认通过",
                "user_fix_requested": "要求调整",
                "user_deferred": "稍后再看",
                "user_rejected": "不采纳",
                "questions": "检查问题",
                "contact_sheet": "拼图概览",
                "open_contact_sheet": "打开拼图概览",
                "frame": "截图",
                "image_preview": "图片预览",
                "previous": "上一张",
                "next": "下一张",
                "close": "关闭",
                "planned_frames": "计划抽帧时间",
                "frame_missing": "截图缺失",
            }
        return {
            "title": "Visual Timing QA Review",
            "description": "Review nearby frames, expected visual states, and initial auto-review results for each narration cue.",
            "project": "Project",
            "cues": "Cues",
            "initial_needs": "Auto needs review",
            "initial_pass": "Auto pass",
            "initial_failed": "Auto failed",
            "initial_filter": "Auto-review status",
            "review_filter": "Review status",
            "filter_all": "All",
            "reviewed": "Reviewed",
            "reviewer_needs": "Reviewer needs review",
            "unreviewed": "Unreviewed",
            "save_review": "Submit review",
            "submitted_button": "Submitted",
            "back_to_top": "Back to top",
            "save_hint": "Mark only items that need changes; unreviewed items are recorded as passed on submit.",
            "submitted_hint": "Review content was copied to the clipboard. Paste it to the Agent so it can adjust and record the results; unreviewed items are treated as passed.",
            "toast_title": "Review saved",
            "toast_body": "Review content was copied to the clipboard. Paste it to the Agent; unreviewed items are recorded as passed.",
            "export_title": "Review notes generated",
            "export_body": "This JSON is shown only if automatic copy fails. Copy it to the Agent; unreviewed items are recorded as passed.",
            "initial_queue": "Initial auto-review queue",
            "auto": "Auto",
            "reviewer": "Reviewer",
            "cue_id": "Cue",
            "section": "Section",
            "time": "Time",
            "tolerance": "Tolerance",
            "narration": "Narration",
            "expected": "Expected visual state",
            "risk": "Risk",
            "auto_notes": "Auto-review notes",
            "review_notes": "Reviewer notes",
            "review_decision": "Reviewer decision",
            "review_notes_field": "Review notes",
            "wrong_warning": "Choosing Wrong expectation means this cue itself may need framework or cue-selection changes. Use it sparingly.",
            "fix_target": "Fix target",
            "user_decision": "User decision",
            "user_notes": "Additional notes",
            "requires_user_review": "Needs further human review",
            "decision_empty": "Unreviewed",
            "decision_pass": "Pass",
            "decision_needs": "Needs adjustment",
            "decision_wrong": "Wrong expectation",
            "user_decision_empty": "No user decision",
            "user_approved": "Approved",
            "user_fix_requested": "Fix requested",
            "user_deferred": "Deferred",
            "user_rejected": "Rejected",
            "questions": "Review questions",
            "contact_sheet": "Contact sheet",
            "open_contact_sheet": "Open contact sheet",
            "frame": "Frame",
            "image_preview": "Image preview",
            "previous": "Previous",
            "next": "Next",
            "close": "Close",
            "planned_frames": "Planned frame timestamps",
            "frame_missing": "Frame missing",
        }

    @staticmethod
    def _suggestions_markdown(payload: dict[str, Any]) -> str:
        lines = [
            f"# Suggested Visual Timing Cues: {payload.get('run_id', '')}",
            "",
            f"- Project: `{payload.get('project', '')}`",
            f"- Created: `{payload.get('created_at', '')}`",
            f"- Speed multiplier: `{payload.get('speed_multiplier', 1.0)}`",
            f"- Candidate count: `{len(payload.get('suggestions', []))}`",
            "",
            "These are rule-based candidates. Confirm or edit `expected_state` before running `review`.",
            "",
            "| Score | Time | Cue id | Label | Reasons |",
            "|---:|---:|---|---|---|",
        ]
        for cue in payload.get("suggestions", []):
            lines.append(
                f"| {cue.get('score', 0)} | {cue.get('timestamp_seconds', 0):.3f}s | "
                f"`{cue.get('id', '')}` | {cue.get('label', '')} | {', '.join(cue.get('reasons', []))} |"
            )
        lines.extend(["", "## Manifest Draft", "", "```json"])
        draft = {
            "offsets_seconds": [-0.6, 0, 0.6],
            "tolerance_seconds": 0.5,
            "cues": [
                {
                    "id": cue["id"],
                    "section_id": cue.get("section_id"),
                    "label": cue.get("label"),
                    "timestamp_seconds": cue.get("timestamp_seconds"),
                    "narration": cue.get("narration"),
                    "expected_state": cue.get("expected_state", ""),
                    "risk": cue.get("risk", ""),
                    "review_questions": cue.get("review_questions", []),
                }
                for cue in payload.get("suggestions", [])
            ],
        }
        lines.append(json.dumps(draft, ensure_ascii=False, indent=2))
        lines.extend(["```", ""])
        return "\n".join(lines)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _decision_lines(annotation: dict[str, Any] | None) -> list[str]:
        decision = annotation.get("decision") if annotation else None
        notes = annotation.get("notes", "") if annotation else ""
        fix_target = annotation.get("fix_target", "") if annotation else ""
        reviewer = annotation.get("reviewer", "") if annotation else ""
        confidence = annotation.get("confidence", "") if annotation else ""
        issue_category = annotation.get("issue_category", "") if annotation else ""
        requires_user_review = annotation.get("requires_user_review") if annotation else None
        user_decision = annotation.get("user_decision", "") if annotation else ""
        user_notes = annotation.get("user_notes", "") if annotation else ""

        lines = [
            f"- [{'x' if decision == 'PASS' else ' '}] PASS - visual timing and state match the cue",
            f"- [{'x' if decision == 'NEEDS_REVIEW' else ' '}] NEEDS_REVIEW - timing or layout needs another look",
            f"- [{'x' if decision == 'WRONG_EXPECTATION' else ' '}] WRONG_EXPECTATION - cue expectation does not match the approved creative direction",
            f"- Issue category: {issue_category}",
            f"- Notes: {notes}",
            f"- Fix target: {fix_target}",
        ]
        if annotation:
            lines.extend(
                [
                    f"- Reviewer: {reviewer}",
                    f"- Confidence: {confidence}",
                    f"- Requires user review: {requires_user_review}",
                    f"- User decision: {user_decision}",
                    f"- User notes: {user_notes}",
                ]
            )
        return lines

    @staticmethod
    def _summary_lines(results: dict[str, Any]) -> list[str]:
        cues = results.get("cues", [])
        counts = {"PASS": 0, "NEEDS_REVIEW": 0, "WRONG_EXPECTATION": 0, "UNREVIEWED": 0}
        initial_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "UNREVIEWED": 0}
        user_review = []
        initial_review_queue = []
        for cue in cues:
            annotation = cue.get("reviewer_annotation") or {}
            decision = annotation.get("decision")
            initial = cue.get("initial_review") or {}
            initial_decision = initial.get("decision")
            if initial_decision in initial_counts:
                initial_counts[initial_decision] += 1
            if decision in counts:
                counts[decision] += 1
            else:
                counts["UNREVIEWED"] += 1
            if annotation.get("requires_user_review") or decision in {"NEEDS_REVIEW", "WRONG_EXPECTATION"}:
                user_review.append(cue)
            if initial_decision == "NEEDS_REVIEW":
                initial_review_queue.append(cue)

        lines = [
            "## Summary",
            "",
            f"- Total cues: `{len(cues)}`",
            f"- Initial auto PASS: `{initial_counts['PASS']}`",
            f"- Initial auto NEEDS_REVIEW: `{initial_counts['NEEDS_REVIEW']}`",
            f"- Initial auto UNREVIEWED: `{initial_counts['UNREVIEWED']}`",
            f"- PASS: `{counts['PASS']}`",
            f"- NEEDS_REVIEW: `{counts['NEEDS_REVIEW']}`",
            f"- WRONG_EXPECTATION: `{counts['WRONG_EXPECTATION']}`",
            f"- UNREVIEWED: `{counts['UNREVIEWED']}`",
            "",
        ]
        if initial_review_queue:
            lines.append("Initial auto-review queue:")
            for cue in initial_review_queue:
                initial = cue.get("initial_review") or {}
                lines.append(
                    f"- `{cue['id']}` - {initial.get('notes', '')}"
                )
            lines.append("")
        if user_review:
            lines.append("Reviewer queue:")
            for cue in user_review:
                annotation = cue.get("reviewer_annotation") or {}
                lines.append(
                    f"- `{cue['id']}` - {annotation.get('decision', 'UNREVIEWED')}: "
                    f"{annotation.get('fix_target') or annotation.get('notes', '')}"
                )
            lines.append("")
        else:
            lines.extend(["Reviewer queue: none", ""])
        return lines

    @staticmethod
    def _offset_label(offset: float) -> str:
        if offset == 0:
            return "at"
        prefix = "plus" if offset > 0 else "minus"
        return f"{prefix}{abs(offset):.3f}".replace(".", "_")

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip()).strip("-")
        return slug or "cue"

    @staticmethod
    def _timestamp_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
