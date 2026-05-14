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
            "review_notes_path": {"type": "string"},
            "annotated_review_path": {"type": "string"},
            "suggested_cues_path": {"type": "string"},
            "suggested_review_path": {"type": "string"},
            "cue_count": {"type": "integer"},
            "cues": {"type": "array"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["operation", "manifest_path", "manifest"]
    side_effects = [
        "writes cue frame images",
        "writes per-cue contact sheets",
        "writes results.json and review.md",
        "writes suggested_cues.json and suggested_cues.md in suggest_cues mode",
        "writes review_notes.json and review_annotated.md in annotate mode",
    ]
    user_visible_verification = [
        "Inspect review.md contact sheets for early, late, or wrong visual states",
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
        self._write_json(results_path, results)
        review_path.write_text(self._review_markdown(results), encoding="utf-8")
        artifacts.extend([str(results_path), str(review_path)])

        return ToolResult(
            success=True,
            data={
                "operation": results["operation"],
                "status": results["status"],
                "output_dir": str(output_dir),
                "results_path": str(results_path),
                "review_path": str(review_path),
                "cue_count": len(results["cues"]),
                "cues": results["cues"],
            },
            artifacts=artifacts,
        )

    def _annotate(self, inputs: dict[str, Any]) -> ToolResult:
        annotations = inputs.get("annotations")
        if not isinstance(annotations, dict) or not annotations:
            return ToolResult(success=False, error="annotate operation requires non-empty annotations")

        results_path = Path(inputs["results_path"]).expanduser().resolve()
        results = json.loads(results_path.read_text(encoding="utf-8"))
        valid_decisions = {"PASS", "NEEDS_REVIEW", "WRONG_EXPECTATION"}
        valid_user_decisions = {"APPROVED", "FIX_REQUESTED", "DEFERRED", "REJECTED"}
        by_id = {cue["id"]: cue for cue in results.get("cues", [])}
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

        notes = {
            "version": self.version,
            "tool": self.name,
            "operation": "annotate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_results": str(results_path),
            "project": results.get("project"),
            "run_id": results.get("run_id"),
            "annotations": [
                {
                    "cue_id": cue["id"],
                    **cue["reviewer_annotation"],
                }
                for cue in results.get("cues", [])
                if cue.get("reviewer_annotation")
            ],
        }
        output_path = Path(inputs.get("output_path") or results_path.with_name("review_notes.json")).expanduser().resolve()
        annotated_review_path = output_path.with_name("review_annotated.md")
        self._write_json(output_path, notes)
        annotated_review_path.write_text(self._review_markdown(results), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "annotate",
                "status": "completed",
                "review_notes_path": str(output_path),
                "annotated_review_path": str(annotated_review_path),
                "annotation_count": len(notes["annotations"]),
                "annotations": notes["annotations"],
            },
            artifacts=[str(output_path), str(annotated_review_path)],
        )

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
        if not extract:
            return {
                "decision": "UNREVIEWED",
                "confidence": "low",
                "issue_category": "dry_run",
                "notes": "Dry run planned cue windows but did not extract frames.",
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
            issues.append(f"{len(missing)} cue frame(s) were not extracted successfully.")

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
                )
            elif before_to_target >= active_threshold and target_to_after < quiet_threshold:
                issues.append(
                    "Most visible change happens before the target frame; the reveal may be early."
                )
            elif before_to_target < quiet_threshold and target_to_after >= active_threshold:
                issues.append(
                    "Most visible change happens after the target frame; the reveal may be late."
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
                    )

        if issues:
            return {
                "decision": "NEEDS_REVIEW",
                "confidence": "medium" if len(issues) > 1 else "low",
                "issue_category": "auto_initial_review",
                "notes": " ".join(issues),
                "fix_target": "Inspect the contact sheet and adjust cue timing, animation timing, or subtitle rendering before delivery.",
                "requires_human_review": True,
                "metrics": metrics,
            }
        return {
            "decision": "PASS",
            "confidence": "low",
            "issue_category": "auto_initial_review",
            "notes": "No obvious local heuristic issue found. Human review is still required for semantic correctness.",
            "requires_human_review": True,
            "metrics": metrics,
        }

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
