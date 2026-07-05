#!/usr/bin/env python3
"""Local task API worker for 赤灵AI运营工作台.

This server intentionally does not execute paid/video production providers.
It persists task requests, exposes the frontend `/tasks` contract, and writes a
pipeline handoff package under `projects/` for the agent-led OpenMontage flow.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse


WORKBENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORKBENCH_DIR.parents[1]
if str(WORKBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_DIR))

from pipeline_bridge import (  # noqa: E402
    DEFAULT_PROJECTS_ROOT as DEFAULT_BRIDGE_PROJECTS_ROOT,
    DEFAULT_QUEUE_ROOT as DEFAULT_BRIDGE_QUEUE_ROOT,
    create_reference_pipeline_handoff,
)

DATA_DIR = WORKBENCH_DIR / ".worker-data"
TASKS_FILE = DATA_DIR / "tasks.json"
PROJECTS_DIR = REPO_ROOT / "projects" / "chiling-web-tasks"

STAGE_NAMES = ["解析参考", "整理文案", "生成画面", "合成字幕", "质检交付"]
STAGE_THRESHOLDS = [15, 34, 76, 92, 100]
ALLOWED_RESOLUTIONS = {"480p", "720p"}
TRAILING_SUBTITLE_PUNCTUATION = re.compile(r"[，。,.！？!?；;：:、]+$")
GENERATION_APPROVAL_PHRASE = "确认进入生产"
PRODUCTION_REQUEST_PHRASE = "确认提交生产"
PRODUCTION_SERVICE_ENABLED_ENV = "CHILING_PRODUCTION_SERVICE_ENABLED"
PRODUCTION_SERVICE_ENDPOINT_ENV = "CHILING_PRODUCTION_SERVICE_ENDPOINT"
PRODUCTION_SERVICE_EXECUTION_APPROVED_ENV = "CHILING_PRODUCTION_EXECUTION_APPROVED"


def now_ms() -> int:
    return int(time.time() * 1000)


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-")
    return normalized[:48] or "chiling-task"


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def truthy_env(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_script(text: Any) -> str:
    lines = []
    for raw_line in str(text or "").splitlines():
        line = TRAILING_SUBTITLE_PUNCTUATION.sub("", raw_line.strip())
        if line:
            lines.append(line)
    return "\n".join(lines)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    duration = clamp_int(payload.get("duration"), 1, 15, 15)
    count = clamp_int(payload.get("count"), 1, 5, 1)
    resolution = str(payload.get("resolution") or "480p")
    if resolution not in ALLOWED_RESOLUTIONS:
        resolution = "480p"

    return {
        "referenceUrl": str(payload.get("referenceUrl") or "").strip(),
        "duration": duration,
        "resolution": resolution,
        "count": count,
        "subtitleStyle": str(payload.get("subtitleStyle") or "short"),
        "script": normalize_script(payload.get("script")),
        "analysisSummary": str(payload.get("analysisSummary") or "").strip(),
        "referenceName": str(payload.get("referenceName") or "参考视频已就绪"),
        "portraitName": str(payload.get("portraitName") or "肖像图已就绪"),
    }


def task_title(payload: dict[str, Any]) -> str:
    if payload.get("referenceUrl"):
        return "参考视频复刻"

    first_line = next((line for line in payload.get("script", "").splitlines() if line.strip()), "")
    return f"{first_line[:8]} · 口播复刻" if first_line else "新建口播复刻"


def stage_state(progress: int, index: int) -> str:
    start = 0 if index == 0 else STAGE_THRESHOLDS[index - 1]
    end = STAGE_THRESHOLDS[index]
    if progress >= end:
        return "done"
    if progress >= start:
        return "active"
    return "waiting"


def stages_for(progress: int) -> list[dict[str, str]]:
    stages = []
    for index, name in enumerate(STAGE_NAMES):
        state = stage_state(progress, index)
        if state == "done":
            detail = "完成"
        elif state == "active":
            detail = f"{progress}%"
        elif index == len(STAGE_NAMES) - 1:
            detail = "预计数分钟"
        else:
            detail = "等待"
        stages.append({"name": name, "state": state, "detail": detail})
    return stages


class TaskStore:
    def __init__(
        self,
        tasks_file: Path = TASKS_FILE,
        *,
        projects_dir: Path = PROJECTS_DIR,
        bridge_projects_root: Path = DEFAULT_BRIDGE_PROJECTS_ROOT,
        bridge_queue_root: Path = DEFAULT_BRIDGE_QUEUE_ROOT,
        pipeline_handoff_factory: Callable[..., dict[str, Any]] = create_reference_pipeline_handoff,
    ) -> None:
        self.tasks_file = tasks_file
        self.projects_dir = projects_dir
        self.bridge_projects_root = bridge_projects_root
        self.bridge_queue_root = bridge_queue_root
        self.pipeline_handoff_factory = pipeline_handoff_factory
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.tasks_file.exists():
            return []
        try:
            return json.loads(self.tasks_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def save(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean_payload = validate_payload(payload)
        timestamp = now_ms()
        task_id = f"task_{timestamp}_{os.urandom(3).hex()}"
        task = {
            "id": task_id,
            "title": task_title(clean_payload),
            "status": "queued",
            "progress": 8,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "completedAt": None,
            "estimatedSeconds": max(8, clean_payload["count"] * 6),
            "payload": clean_payload,
            "workspace": str(self.projects_dir / task_id),
            "pipeline": {
                "name": "reference-video-analysis",
                "mode": "reference_pipeline_handoff",
                "paidGeneration": False,
                "requiresHumanApproval": True,
            },
        }

        pipeline_handoff = self.create_pipeline_handoff(task)
        task["pipeline_handoff"] = pipeline_handoff
        task["pipeline"] = {
            **task["pipeline"],
            "handoffStatus": pipeline_handoff["status"],
            "nextStage": pipeline_handoff["next_stage"],
            "queueItemPath": pipeline_handoff["queue_item_path"],
        }
        self.write_handoff_package(task)
        tasks = [task, *self.load()]
        self.save(tasks)
        return self.refresh(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") == task_id:
                refreshed = self.refresh(task)
                tasks[index] = refreshed
                self.save(tasks)
                return refreshed
        return None

    def list(self) -> list[dict[str, Any]]:
        tasks = [self.refresh(task) for task in self.load()]
        self.save(tasks)
        return sorted(tasks, key=lambda task: task.get("createdAt", 0), reverse=True)

    def production_queue(self) -> list[dict[str, Any]]:
        tasks = self.list()
        return [self.queue_summary(task) for task in tasks]

    def production_requests(self) -> list[dict[str, Any]]:
        tasks = self.list()
        requested = [
            self.production_request_summary(task)
            for task in tasks
            if (task.get("productionRequest") or {}).get("status") in {"production_requested", "execution_in_progress"}
        ]
        return sorted(requested, key=lambda item: item.get("requestedAt") or 0, reverse=True)

    def production_service_status(self) -> dict[str, Any]:
        return build_production_service_status()

    def production_service_configuration(self) -> dict[str, Any]:
        return build_production_service_configuration()

    def production_audit_log(self, task_id: str | None = None) -> dict[str, Any]:
        tasks = self.list()
        return build_production_audit_log(tasks, task_id)

    def task_detail(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            return {
                "status": "not_found",
                "message": "任务不存在",
                "paidGenerationStarted": False,
            }

        return build_task_detail(task, self.deliverables(task_id))

    def task_operations(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        if not task:
            return None

        return operation_panel(task)

    def review_draft(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        if not task:
            return None

        return build_review_draft(task)

    def save_review(self, task_id: str, review_payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = save_review_decision(refreshed, review_payload)
            tasks[index] = updated
            self.save(tasks)
            return result

        return {
            "status": "not_found",
            "message": "任务不存在",
            "paidGenerationStarted": False,
        }

    def approve_generation(self, task_id: str, approval_payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = approve_generation_gate(refreshed, approval_payload)
            tasks[index] = updated
            self.save(tasks)
            return result

        return {
            "status": "not_found",
            "message": "任务不存在",
            "requiredPhrase": GENERATION_APPROVAL_PHRASE,
            "paidGenerationStarted": False,
        }

    def production_prep(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            return {
                "status": "not_found",
                "message": "任务不存在",
                "paidGenerationStarted": False,
            }

        return build_production_prep(task)

    def request_production(self, task_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = request_controlled_production(refreshed, request_payload)
            tasks[index] = updated
            self.save(tasks)
            return result

        return {
            "status": "not_found",
            "message": "任务不存在",
            "requiredPhrase": PRODUCTION_REQUEST_PHRASE,
            "paidGenerationStarted": False,
        }

    def claim_production(self, task_id: str, claim_payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = claim_controlled_production(refreshed, claim_payload)
            tasks[index] = updated
            self.save(tasks)
            return result

        return {
            "status": "not_found",
            "message": "任务不存在",
            "paidGenerationStarted": False,
        }

    def complete_production(self, task_id: str, delivery_payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = complete_controlled_production(refreshed, delivery_payload)
            tasks[index] = updated
            self.save(tasks)
            if result["status"] == "completed":
                self.write_deliverable_placeholders(updated)
            return result

        return {
            "status": "not_found",
            "message": "任务不存在",
            "paidGenerationStarted": False,
        }

    def execute_production(self, task_id: str, execution_payload: dict[str, Any]) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            return {
                "status": "not_found",
                "message": "任务不存在",
                "paidGenerationStarted": False,
            }

        return execute_with_disabled_production_adapter(task, execution_payload)

    def run_operation(self, task_id: str, operation_id: str) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.get("id") != task_id:
                continue

            refreshed = self.refresh(task)
            result, updated = run_safe_operation(refreshed, operation_id)
            tasks[index] = updated
            self.save(tasks)
            return result

        return {
            "status": "not_found",
            "operationId": operation_id,
            "message": "任务不存在",
            "paidGenerationStarted": False,
        }

    def queue_summary(self, task: dict[str, Any]) -> dict[str, Any]:
        handoff = task.get("pipeline_handoff") or {}
        pipeline = task.get("pipeline") or {}
        source_state = source_state_label(str(handoff.get("status") or pipeline.get("handoffStatus") or ""))
        next_action = next_action_label(str(handoff.get("next_stage") or pipeline.get("nextStage") or ""))
        status = str(task.get("status") or "queued")

        if status == "completed":
            next_action = "查看交付"

        return {
            "id": f"queue_{task.get('id')}",
            "taskId": task.get("id"),
            "title": task.get("title") or "参考视频复刻",
            "status": status,
            "statusLabel": task_status_label(status),
            "progress": int(task.get("progress") or 0),
            "sourceState": source_state,
            "nextAction": next_action,
            "approvalRequired": bool(pipeline.get("requiresHumanApproval", True)),
            "queueItemReady": Path(str(handoff.get("queue_item_path") or "")).is_file(),
            "createdAt": task.get("createdAt"),
            "updatedAt": task.get("updatedAt"),
            "route": "delivery" if status == "completed" else "generating",
            "blockingNote": queue_blocking_note(str(handoff.get("status") or "")),
        }

    def production_request_summary(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload") or {}
        production_request = task.get("productionRequest") or {}
        execution_started = bool(production_request.get("executionStarted", False))
        status = "execution_in_progress" if execution_started else "production_requested"
        return {
            "id": f"production_{task.get('id')}",
            "taskId": task.get("id"),
            "title": task.get("title") or "参考视频复刻",
            "status": status,
            "statusLabel": "执行中" if execution_started else "等待生产",
            "nextAction": "操作员处理中" if execution_started else "操作员执行",
            "durationSeconds": payload.get("duration"),
            "resolution": payload.get("resolution"),
            "batchCount": payload.get("count"),
            "requestedAt": production_request.get("requestedAt"),
            "claimedAt": production_request.get("claimedAt"),
            "operatorName": production_request.get("operatorName") or "",
            "createdAt": task.get("createdAt"),
            "updatedAt": task.get("updatedAt"),
            "executionStarted": execution_started,
            "paidGenerationStarted": False,
            "route": "generating",
        }

    def deliverables(self, task_id: str) -> list[dict[str, str]]:
        task = self.get(task_id)
        if not task or task.get("status") != "completed":
            return []

        payload = task.get("payload") or {}
        backfill = task.get("deliveryBackfill") or {}
        duration = payload.get("duration", 15)
        resolution = payload.get("resolution", "480p")
        video_name = backfill.get("videoName") or "成品视频"
        subtitle_name = backfill.get("subtitleName") or "字幕文件"
        audit_note = backfill.get("auditNote") or "素材授权 · 肖像授权 · 文案确认"
        return [
            {
                "id": "video",
                "title": "成品视频",
                "subtitle": f"{video_name} · {resolution} · {duration}s",
                "action": "下载",
                "url": f"/worker-files/{task_id}/renders/final-placeholder.json",
            },
            {
                "id": "subtitle",
                "title": "字幕文件",
                "subtitle": f"{subtitle_name} · 句尾标点已清理",
                "action": "下载",
                "url": f"/worker-files/{task_id}/assets/subtitles.srt",
            },
            {
                "id": "audit",
                "title": "审核记录",
                "subtitle": audit_note,
                "action": "查看",
                "url": f"/worker-files/{task_id}/artifacts/audit-record.json",
            },
            {
                "id": "share",
                "title": "交付链接",
                "subtitle": "团队内部可访问",
                "action": "复制",
                "url": f"/tasks/{task_id}/deliverables",
            },
        ]

    def refresh(self, task: dict[str, Any]) -> dict[str, Any]:
        if task.get("status") == "failed":
            return {**task, "stages": stages_for(int(task.get("progress") or 0))}

        delivery_ready = (task.get("deliveryBackfill") or {}).get("status") == "delivered"
        production_delivered = (task.get("productionRequest") or {}).get("status") == "delivered"
        delivered = delivery_ready or production_delivered
        timestamp = now_ms()

        if delivered:
            progress = 100
        else:
            elapsed = max(0, timestamp - int(task.get("createdAt") or timestamp))
            estimated_ms = max(8000, int(task.get("estimatedSeconds") or 12) * 1000)
            progress = min(99, max(int(task.get("progress") or 0), round((elapsed / estimated_ms) * 100)))

        status = "completed" if delivered else "queued" if progress < 16 else "processing"
        refreshed = {
            **task,
            "status": status,
            "progress": progress,
            "updatedAt": timestamp,
            "completedAt": task.get("completedAt") or (timestamp if status == "completed" else None),
            "stages": stages_for(progress),
        }

        if status == "completed":
            self.write_deliverable_placeholders(refreshed)

        return refreshed

    def write_handoff_package(self, task: dict[str, Any]) -> None:
        workspace = Path(task["workspace"])
        artifacts_dir = workspace / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        handoff = {
            "task_id": task["id"],
            "created_at": task["createdAt"],
            "source": "chiling-workbench",
            "pipeline": task["pipeline"],
            "payload": task["payload"],
            "constraints": {
                "duration_seconds_max": 15,
                "batch_count_max": 5,
                "allowed_resolutions": sorted(ALLOWED_RESOLUTIONS),
                "ui_must_hide_provider_names": True,
                "digital_human_out_of_scope": True,
            },
            "next_agent_step": "Run OpenMontage reference-video-analysis pipeline from this approved intake package before any paid generation.",
        }
        (artifacts_dir / "web-task-request.json").write_text(
            json.dumps(handoff, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_pipeline_handoff(self, task: dict[str, Any]) -> dict[str, Any]:
        return self.pipeline_handoff_factory(
            task,
            projects_root=self.bridge_projects_root,
            queue_root=self.bridge_queue_root,
        )

    def write_deliverable_placeholders(self, task: dict[str, Any]) -> None:
        workspace = Path(task["workspace"])
        artifacts_dir = workspace / "artifacts"
        assets_dir = workspace / "assets"
        renders_dir = workspace / "renders"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)
        renders_dir.mkdir(parents=True, exist_ok=True)

        payload = task.get("payload") or {}
        (assets_dir / "subtitles.srt").write_text(script_to_srt(payload.get("script", "")), encoding="utf-8")
        (artifacts_dir / "audit-record.json").write_text(
            json.dumps(
                {
                    "task_id": task["id"],
                    "status": "approved_for_demo_delivery",
                    "checks": [
                        {"name": "素材授权", "state": "confirmed"},
                        {"name": "肖像授权", "state": "confirmed"},
                        {"name": "字幕规则", "state": "confirmed"},
                        {"name": "画面方向", "state": "pending_human_confirmation"},
                    ],
                    "note": "Local worker placeholder. Real production must run through OpenMontage pipeline approval.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (renders_dir / "final-placeholder.json").write_text(
            json.dumps(
                {
                    "task_id": task["id"],
                    "type": "placeholder",
                    "message": "真实成品视频需由 OpenMontage 生产管线生成。",
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def script_to_srt(script: str) -> str:
    lines = [line.strip() for line in str(script or "").splitlines() if line.strip()]
    if not lines:
        lines = ["请在人工审核页补充字幕文案"]

    blocks = []
    for index, line in enumerate(lines, start=1):
        start_second = index - 1
        end_second = index
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"00:00:{start_second:02d},000 --> 00:00:{end_second:02d},000",
                    line,
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def task_status_label(status: str) -> str:
    if status == "completed":
        return "已交付"
    if status == "processing":
        return "生产中"
    if status == "queued":
        return "排队中"
    if status == "failed":
        return "处理失败"
    return "待处理"


def source_state_label(status: str) -> str:
    if status == "source_imported_needs_analysis":
        return "素材已导入"
    if status == "source_needs_resolution":
        return "等待获取参考"
    return "等待提交"


def next_action_label(next_stage: str) -> str:
    if next_stage == "analyze":
        return "解析参考"
    if next_stage == "ingest":
        return "处理参考来源"
    return "等待后台处理"


def queue_blocking_note(status: str) -> str:
    if status == "source_needs_resolution":
        return "链接类参考需先由后台解析；如平台限制访问，请补充本地视频。"
    return ""


def operation_panel(task: dict[str, Any]) -> dict[str, Any]:
    status = str(task.get("status") or "queued")
    progress = int(task.get("progress") or 0)
    handoff = task.get("pipeline_handoff") or {}
    handoff_status = str(handoff.get("status") or "")
    source_ready = handoff_status == "source_imported_needs_analysis"
    source_pending = handoff_status == "source_needs_resolution"
    completed = status == "completed"
    review_approved = (task.get("review") or {}).get("status") == "approved"
    generation_ready = (task.get("generationApproval") or {}).get("status") == "ready_for_production"
    production_requested = (task.get("productionRequest") or {}).get("status") == "production_requested"

    steps = [
        operation_step(
            step_id="reference_source",
            title="参考素材",
            description="确认参考视频或链接来源，保留素材与授权记录。",
            state="done" if source_ready or completed else "ready" if source_pending else "waiting",
            action_label="已导入" if source_ready or completed else "处理参考来源",
            approval_required=False,
            can_execute=source_pending and not completed,
        ),
        operation_step(
            step_id="reference_analysis",
            title="参考解析",
            description="解析视频结构、节奏、镜头与可复用信息。",
            state=progress_state(progress, done_at=34, ready_when=source_ready, completed=completed),
            action_label="已完成" if completed or progress >= 34 else "开始解析" if source_ready else "等待素材",
            approval_required=False,
            can_execute=source_ready and progress < 34 and not completed,
        ),
        operation_step(
            step_id="copy_extract",
            title="文案提取",
            description="整理口播文案、字幕短句和人工可编辑内容。",
            state=progress_state(progress, done_at=76, ready_when=progress >= 34, completed=completed),
            action_label="已完成" if completed or progress >= 76 else "整理文案" if progress >= 34 else "等待解析",
            approval_required=False,
            can_execute=progress >= 34 and progress < 76 and not completed,
        ),
        operation_step(
            step_id="human_review",
            title="人工确认",
            description="团队确认文案、字幕、肖像授权和画面方向。",
            state="done" if completed or review_approved else "ready" if progress >= 76 else "locked",
            action_label="已完成" if completed or review_approved else "进入审核" if progress >= 76 else "等待文案",
            approval_required=True,
            can_execute=False,
        ),
        operation_step(
            step_id="generation_approval",
            title="生成审批",
            description="正式生产前进行最终确认，避免误触发付费生成。",
            state="done" if completed or generation_ready else "ready" if review_approved else "locked",
            action_label="已完成" if completed or generation_ready else "输入确认短语" if review_approved else "等待人工批准",
            approval_required=True,
            can_execute=False,
        ),
    ]

    if generation_ready or production_requested or completed:
        steps.append(
            operation_step(
                step_id="production_handoff",
                title="生产交接",
                description="把审核后的准备包提交给受控生产队列。",
                state="done" if completed or production_requested else "ready",
                action_label="已提交" if completed or production_requested else "等待提交",
                approval_required=True,
                can_execute=False,
            )
        )

    return {
        "taskId": task.get("id"),
        "title": task.get("title") or "参考视频复刻",
        "status": status,
        "statusLabel": task_status_label(status),
        "progress": progress,
        "safeAutoExecute": False,
        "operatorHint": "当前面板只展示可执行状态；正式生成仍需人工审批。",
        "steps": steps,
    }


def operation_step(
    *,
    step_id: str,
    title: str,
    description: str,
    state: str,
    action_label: str,
    approval_required: bool,
    can_execute: bool,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "description": description,
        "state": state,
        "stateLabel": operation_state_label(state),
        "actionLabel": action_label,
        "approvalRequired": approval_required,
        "canExecute": can_execute,
    }


def progress_state(progress: int, *, done_at: int, ready_when: bool, completed: bool) -> str:
    if completed or progress >= done_at:
        return "done"
    if ready_when:
        return "ready"
    return "waiting"


def operation_state_label(state: str) -> str:
    labels = {
        "done": "已完成",
        "ready": "可处理",
        "waiting": "等待中",
        "locked": "需前置确认",
    }
    return labels.get(state, "待处理")


def run_safe_operation(task: dict[str, Any], operation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if operation_id == "reference_analysis":
        return complete_safe_operation(
            task,
            operation_id=operation_id,
            progress=34,
            artifact_name="safe-reference-analysis.json",
            message="参考解析已完成，已整理视频结构、节奏和画面方向。",
            artifact_payload={
                "summary": "参考结构已完成本地整理。",
                "next_step": "整理文案",
            },
        )

    if operation_id == "copy_extract":
        if int(task.get("progress") or 0) < 34:
            return blocked_operation(task, operation_id, "请先完成参考解析。"), task
        return complete_safe_operation(
            task,
            operation_id=operation_id,
            progress=76,
            artifact_name="safe-copy-extract.json",
            message="文案提取已完成，已整理短句字幕和审核文本。",
            artifact_payload={
                "script_lines": script_lines(task),
                "subtitle_rule": "短句句尾不显示标点。",
                "next_step": "人工确认",
            },
        )

    return blocked_operation(task, operation_id, "该节点需要人工审批，当前不会自动执行。"), task


def complete_safe_operation(
    task: dict[str, Any],
    *,
    operation_id: str,
    progress: int,
    artifact_name: str,
    message: str,
    artifact_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = {
        **task,
        "status": "processing",
        "progress": max(int(task.get("progress") or 0), progress),
        "updatedAt": now_ms(),
    }
    artifact_path = write_operation_artifact(updated, operation_id, artifact_name, artifact_payload)
    result = {
        "status": "completed",
        "operationId": operation_id,
        "message": message,
        "progress": updated["progress"],
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "panel": operation_panel(updated),
    }
    return result, updated


def blocked_operation(task: dict[str, Any], operation_id: str, message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "operationId": operation_id,
        "message": message,
        "progress": int(task.get("progress") or 0),
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_operation_artifact(
    task: dict[str, Any],
    operation_id: str,
    artifact_name: str,
    payload: dict[str, Any],
) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / artifact_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "operation_id": operation_id,
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "paid_generation_started": False,
                **payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def script_lines(task: dict[str, Any]) -> list[str]:
    payload = task.get("payload") or {}
    return [line.strip() for line in str(payload.get("script") or "").splitlines() if line.strip()]


def build_review_draft(task: dict[str, Any]) -> dict[str, Any]:
    analysis = read_operation_artifact(task, "safe-reference-analysis.json")
    copy_extract = read_operation_artifact(task, "safe-copy-extract.json")
    lines = copy_extract.get("script_lines") if isinstance(copy_extract.get("script_lines"), list) else script_lines(task)
    clean_lines = [normalize_script(line) for line in lines if str(line).strip()]
    clean_lines = [line for line in clean_lines if line]

    return {
        "taskId": task.get("id"),
        "title": task.get("title") or "参考视频复刻",
        "editable": True,
        "analysisSummary": str(analysis.get("summary") or "等待参考解析后生成摘要。"),
        "scriptDraft": "\n".join(clean_lines) or normalize_script((task.get("payload") or {}).get("script")),
        "subtitleRule": str(copy_extract.get("subtitle_rule") or "短句句尾不显示标点。"),
        "reviewChecks": ["素材授权", "肖像授权", "字幕规则", "画面方向"],
        "operatorHint": "这里的摘要和文案可人工修改，确认后再进入生产。",
    }


def read_operation_artifact(task: dict[str, Any], artifact_name: str) -> dict[str, Any]:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / artifact_name
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_review_decision(
    task: dict[str, Any],
    review_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    approved = bool(review_payload.get("approved"))
    status = "approved" if approved else "saved"
    payload = dict(task.get("payload") or {})
    payload["analysisSummary"] = str(review_payload.get("analysisSummary") or payload.get("analysisSummary") or "").strip()
    payload["script"] = normalize_script(review_payload.get("script") or payload.get("script"))
    timestamp = now_ms()
    review = {
        "status": status,
        "approved": approved,
        "updatedAt": timestamp,
        "approvedAt": timestamp if approved else None,
        "checks": ["素材授权", "肖像授权", "字幕规则", "画面方向"],
    }
    updated = {
        **task,
        "payload": payload,
        "review": review,
        "progress": max(int(task.get("progress") or 0), 82 if approved else int(task.get("progress") or 0)),
        "updatedAt": timestamp,
    }
    artifact_path = write_review_artifact(updated)
    return {
        "status": status,
        "taskId": task.get("id"),
        "message": "审核已通过，等待生成审批。" if approved else "审核稿已保存。",
        "review": review,
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "panel": operation_panel(updated),
    }, updated


def write_review_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "review-approval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = task.get("payload") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": (task.get("review") or {}).get("status"),
                "approved": (task.get("review") or {}).get("approved", False),
                "analysis_summary": payload.get("analysisSummary", ""),
                "script": payload.get("script", ""),
                "paid_generation_started": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def approve_generation_gate(
    task: dict[str, Any],
    approval_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (task.get("review") or {}).get("status") != "approved":
        return blocked_generation_approval(task, "请先完成人工审核。"), task

    phrase = str(approval_payload.get("confirmationPhrase") or "").strip()
    if phrase != GENERATION_APPROVAL_PHRASE:
        return blocked_generation_approval(task, "确认短语不匹配。"), task

    timestamp = now_ms()
    generation_approval = {
        "status": "ready_for_production",
        "approvedAt": timestamp,
        "confirmationMatched": True,
        "paidGenerationStarted": False,
    }
    updated = {
        **task,
        "generationApproval": generation_approval,
        "progress": max(int(task.get("progress") or 0), 88),
        "updatedAt": timestamp,
    }
    artifact_path = write_generation_approval_artifact(updated)
    return {
        "status": "ready_for_production",
        "taskId": task.get("id"),
        "message": "生成审批已通过，等待生产准备。",
        "productionPrepared": True,
        "requiredPhrase": GENERATION_APPROVAL_PHRASE,
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "panel": operation_panel(updated),
    }, updated


def blocked_generation_approval(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "message": message,
        "productionPrepared": False,
        "requiredPhrase": GENERATION_APPROVAL_PHRASE,
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_generation_approval_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "generation-approval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = task.get("payload") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "ready_for_production",
                "analysis_summary": payload.get("analysisSummary", ""),
                "script": payload.get("script", ""),
                "duration": payload.get("duration"),
                "resolution": payload.get("resolution"),
                "count": payload.get("count"),
                "paid_generation_started": False,
                "requires_pipeline_execution": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_production_prep(task: dict[str, Any]) -> dict[str, Any]:
    if (task.get("review") or {}).get("status") != "approved":
        return blocked_production_prep(task, "请先完成人工审核。")

    if (task.get("generationApproval") or {}).get("status") != "ready_for_production":
        return blocked_production_prep(task, "请先完成生成审批确认。")

    artifact_path = write_production_prep_artifact(task)
    payload = task.get("payload") or {}
    handoff = task.get("pipeline_handoff") or {}
    return {
        "status": "ready",
        "taskId": task.get("id"),
        "title": task.get("title") or "参考视频复刻",
        "operatorHint": "生产准备包已就绪，可交给生产端继续执行；当前接口不会启动正式生成。",
        "assets": {
            "referenceName": payload.get("referenceName") or "参考视频已就绪",
            "portraitName": payload.get("portraitName") or "肖像图已就绪",
            "sourceState": source_state_label(str(handoff.get("status") or "")),
        },
        "constraints": {
            "durationSeconds": payload.get("duration"),
            "maxDurationSeconds": 15,
            "resolution": payload.get("resolution"),
            "allowedResolutions": sorted(ALLOWED_RESOLUTIONS),
            "batchCount": payload.get("count"),
            "maxBatchCount": 5,
            "subtitleRule": "短句句尾不显示标点。",
        },
        "review": {
            "analysisSummary": payload.get("analysisSummary") or "",
            "scriptLines": script_lines(task),
            "checks": ["素材授权", "肖像授权", "字幕规则", "画面方向"],
        },
        "productionRequest": {
            "status": (task.get("productionRequest") or {}).get("status") or "not_requested",
            "executionStarted": bool((task.get("productionRequest") or {}).get("executionStarted", False)),
        },
        "approval": {
            "humanReview": "approved",
            "generationApproval": "ready_for_production",
        },
        "nextActions": ["进入受控生产流程", "正式生成前再次确认"],
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
    }


def blocked_production_prep(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "title": task.get("title") or "参考视频复刻",
        "message": message,
        "paidGenerationStarted": False,
    }


def write_production_prep_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-prep.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = task.get("payload") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "ready",
                "assets": {
                    "reference_name": payload.get("referenceName") or "参考视频已就绪",
                    "portrait_name": payload.get("portraitName") or "肖像图已就绪",
                },
                "constraints": {
                    "duration_seconds": payload.get("duration"),
                    "duration_seconds_max": 15,
                    "resolution": payload.get("resolution"),
                    "allowed_resolutions": sorted(ALLOWED_RESOLUTIONS),
                    "batch_count": payload.get("count"),
                    "batch_count_max": 5,
                    "subtitle_rule": "短句句尾不显示标点。",
                },
                "review": {
                    "analysis_summary": payload.get("analysisSummary") or "",
                    "script_lines": script_lines(task),
                    "checks": ["素材授权", "肖像授权", "字幕规则", "画面方向"],
                },
                "paid_generation_started": False,
                "requires_controlled_production_flow": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def request_controlled_production(
    task: dict[str, Any],
    request_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prep = build_production_prep(task)
    if prep.get("status") != "ready":
        return blocked_production_request(task, "请先完成生产准备包。"), task

    phrase = str(request_payload.get("confirmationPhrase") or "").strip()
    if phrase != PRODUCTION_REQUEST_PHRASE:
        return blocked_production_request(task, "确认短语不匹配。"), task

    timestamp = now_ms()
    production_request = {
        "status": "production_requested",
        "requestedAt": timestamp,
        "confirmationMatched": True,
        "executionStarted": False,
        "paidGenerationStarted": False,
    }
    updated = {
        **task,
        "productionRequest": production_request,
        "progress": max(int(task.get("progress") or 0), 90),
        "updatedAt": timestamp,
    }
    artifact_path = write_production_request_artifact(updated)
    return {
        "status": "production_requested",
        "taskId": task.get("id"),
        "message": "生产请求已提交，等待受控生产流程执行。",
        "requiredPhrase": PRODUCTION_REQUEST_PHRASE,
        "executionStarted": False,
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "panel": operation_panel(updated),
        "productionPrep": build_production_prep(updated),
    }, updated


def blocked_production_request(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "message": message,
        "requiredPhrase": PRODUCTION_REQUEST_PHRASE,
        "executionStarted": False,
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_production_request_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = task.get("payload") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "production_requested",
                "title": task.get("title") or "参考视频复刻",
                "duration_seconds": payload.get("duration"),
                "resolution": payload.get("resolution"),
                "batch_count": payload.get("count"),
                "execution_started": False,
                "paid_generation_started": False,
                "requires_operator_execution": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def claim_controlled_production(
    task: dict[str, Any],
    claim_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    production_request = dict(task.get("productionRequest") or {})
    if production_request.get("status") not in {"production_requested", "execution_in_progress"}:
        return blocked_production_claim(task, "请先提交生产请求。"), task

    timestamp = now_ms()
    operator_name = str(claim_payload.get("operatorName") or "操作员").strip() or "操作员"
    updated_request = {
        **production_request,
        "status": "execution_in_progress",
        "claimedAt": production_request.get("claimedAt") or timestamp,
        "operatorName": production_request.get("operatorName") or operator_name,
        "executionStarted": True,
        "paidGenerationStarted": False,
    }
    updated = {
        **task,
        "productionRequest": updated_request,
        "progress": max(int(task.get("progress") or 0), 94),
        "updatedAt": timestamp,
    }
    artifact_path = write_production_claim_artifact(updated)
    return {
        "status": "execution_in_progress",
        "taskId": task.get("id"),
        "message": "任务已领取，已标记为执行中。",
        "operatorName": updated_request["operatorName"],
        "executionStarted": True,
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "productionRequest": updated_request,
        "panel": operation_panel(updated),
    }, updated


def blocked_production_claim(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "message": message,
        "executionStarted": False,
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_production_claim_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-claim.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    production_request = task.get("productionRequest") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "execution_in_progress",
                "operator_name": production_request.get("operatorName") or "操作员",
                "execution_started": True,
                "paid_generation_started": False,
                "requires_operator_execution": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def complete_controlled_production(
    task: dict[str, Any],
    delivery_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    production_request = dict(task.get("productionRequest") or {})
    if production_request.get("status") != "execution_in_progress":
        return blocked_production_complete(task, "请先领取任务并标记为执行中。"), task

    timestamp = now_ms()
    backfill = {
        "status": "delivered",
        "deliveredAt": timestamp,
        "videoName": str(delivery_payload.get("videoName") or "成品视频.mp4").strip() or "成品视频.mp4",
        "subtitleName": str(delivery_payload.get("subtitleName") or "字幕文件.srt").strip() or "字幕文件.srt",
        "auditNote": str(delivery_payload.get("auditNote") or "人工回填完成").strip() or "人工回填完成",
        "paidGenerationStarted": False,
    }
    updated_request = {
        **production_request,
        "status": "delivered",
        "completedAt": timestamp,
        "executionStarted": True,
        "paidGenerationStarted": False,
    }
    updated = {
        **task,
        "status": "completed",
        "progress": 100,
        "completedAt": timestamp,
        "updatedAt": timestamp,
        "productionRequest": updated_request,
        "deliveryBackfill": backfill,
    }
    artifact_path = write_production_complete_artifact(updated)
    return {
        "status": "completed",
        "taskId": task.get("id"),
        "message": "交付结果已回填，任务已进入交付区。",
        "deliveryReady": True,
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "deliveryBackfill": backfill,
    }, updated


def blocked_production_complete(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "message": message,
        "deliveryReady": False,
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_production_complete_artifact(task: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-complete.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    backfill = task.get("deliveryBackfill") or {}
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "completed",
                "video_name": backfill.get("videoName") or "成品视频.mp4",
                "subtitle_name": backfill.get("subtitleName") or "字幕文件.srt",
                "audit_note": backfill.get("auditNote") or "人工回填完成",
                "delivery_ready": True,
                "paid_generation_started": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def execute_with_disabled_production_adapter(
    task: dict[str, Any],
    execution_payload: dict[str, Any],
) -> dict[str, Any]:
    production_request = task.get("productionRequest") or {}
    if production_request.get("status") != "execution_in_progress":
        return blocked_production_execute(task, "请先领取任务并标记为执行中。")

    service_status = build_production_service_status()
    if service_status.get("executionAllowed"):
        artifact_path = write_production_preflight_artifact(task, execution_payload, service_status)
        return {
            "status": "preflight_ready",
            "taskId": task.get("id"),
            "message": "生产服务预检已通过，等待服务端执行器接管。",
            "adapterExecutionStarted": False,
            "serverExecutionQueued": False,
            "executionStarted": bool(production_request.get("executionStarted", False)),
            "artifactPath": str(artifact_path),
            "paidGenerationStarted": False,
            "nextAction": "等待服务端执行器接管",
            "panel": operation_panel(task),
        }

    artifact_path = write_production_adapter_attempt_artifact(task, execution_payload)
    return {
        "status": "disabled",
        "taskId": task.get("id"),
        "message": "真实生产服务未启用，请继续使用人工回填。",
        "adapterExecutionStarted": False,
        "executionStarted": bool(production_request.get("executionStarted", False)),
        "artifactPath": str(artifact_path),
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def blocked_production_execute(task: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "taskId": task.get("id"),
        "message": message,
        "adapterExecutionStarted": False,
        "paidGenerationStarted": False,
        "panel": operation_panel(task),
    }


def write_production_adapter_attempt_artifact(task: dict[str, Any], execution_payload: dict[str, Any]) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-adapter-attempt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "disabled",
                "operator_name": str(execution_payload.get("operatorName") or "操作员"),
                "adapter_execution_started": False,
                "paid_generation_started": False,
                "requires_manual_backfill": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_production_preflight_artifact(
    task: dict[str, Any],
    execution_payload: dict[str, Any],
    service_status: dict[str, Any],
) -> Path:
    workspace = Path(str(task.get("workspace") or PROJECTS_DIR / str(task.get("id") or "task")))
    path = workspace / "artifacts" / "production-service-preflight.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "source": "chiling-workbench",
                "task_id": task.get("id"),
                "created_at": now_ms(),
                "status": "preflight_ready",
                "operator_name": str(execution_payload.get("operatorName") or "操作员"),
                "service_status": service_status.get("status"),
                "adapter_execution_started": False,
                "server_execution_queued": False,
                "paid_generation_started": False,
                "next_action": "server_executor_handoff",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_production_service_status() -> dict[str, Any]:
    enabled = truthy_env(PRODUCTION_SERVICE_ENABLED_ENV)
    endpoint_configured = bool(str(os.environ.get(PRODUCTION_SERVICE_ENDPOINT_ENV) or "").strip())
    execution_approved = truthy_env(PRODUCTION_SERVICE_EXECUTION_APPROVED_ENV)

    if not enabled:
        return production_service_status_payload(
            status="disabled",
            status_label="未启用",
            ready=False,
            execution_allowed=False,
            summary="真实生产服务未启用，当前不会启动付费生成。",
            next_action="需要管理员开启生产服务后再执行。",
            switch_state="blocked",
            connection_state="waiting",
            connection_message="启用后检测连接配置。",
            approval_state="locked",
            approval_message="等待内部审批。",
        )

    if not endpoint_configured:
        return production_service_status_payload(
            status="missing_configuration",
            status_label="待配置",
            ready=False,
            execution_allowed=False,
            summary="真实生产服务已开启，但连接配置还不完整，不会启动付费生成。",
            next_action="请管理员补全生产服务连接配置。",
            switch_state="ok",
            connection_state="blocked",
            connection_message="等待补全连接配置。",
            approval_state="locked" if not execution_approved else "ok",
            approval_message="审批已开启。" if execution_approved else "等待内部审批。",
        )

    if execution_approved:
        return production_service_status_payload(
            status="ready",
            status_label="可连接",
            ready=True,
            execution_allowed=True,
            summary="真实生产服务配置和执行审批已就绪，等待服务端执行器接管。",
            next_action="操作员可发起生产服务预检。",
            switch_state="ok",
            connection_state="ok",
            connection_message="连接配置已就绪。",
            approval_state="ok",
            approval_message="执行审批已开启。",
        )

    return production_service_status_payload(
        status="ready",
        status_label="可连接",
        ready=True,
        execution_allowed=False,
        summary="真实生产服务配置已就绪，但执行入口仍需单独审批开启，不会启动付费生成。",
        next_action="完成内部审批后，再开启受控执行。",
        switch_state="ok",
        connection_state="ok",
        connection_message="连接配置已就绪。",
        approval_state="locked",
        approval_message="等待内部审批。",
    )


def production_service_status_payload(
    *,
    status: str,
    status_label: str,
    ready: bool,
    execution_allowed: bool,
    summary: str,
    next_action: str,
    switch_state: str,
    connection_state: str,
    connection_message: str,
    approval_state: str,
    approval_message: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "statusLabel": status_label,
        "ready": ready,
        "summary": summary,
        "nextAction": next_action,
        "executionAllowed": execution_allowed,
        "paidGenerationStarted": False,
        "executionRequiresApproval": True,
        "safeForUsers": True,
        "checks": [
            {
                "id": "manual_gate",
                "label": "人工审批闸门",
                "state": "ok",
                "message": "正式生产前必须经过人工确认。",
            },
            {
                "id": "service_switch",
                "label": "生产服务开关",
                "state": switch_state,
                "message": "已开启。" if switch_state == "ok" else "未启用。",
            },
            {
                "id": "service_connection",
                "label": "服务连接",
                "state": connection_state,
                "message": connection_message,
            },
            {
                "id": "execution_approval",
                "label": "执行审批",
                "state": approval_state,
                "message": approval_message,
            },
            {
                "id": "paid_generation_guard",
                "label": "付费生成保护",
                "state": "ok",
                "message": "当前诊断不会启动付费生成。",
            },
        ],
    }


def build_production_service_configuration() -> dict[str, Any]:
    status = build_production_service_status()
    service_enabled = status["status"] != "disabled"
    connection_ready = status["status"] == "ready"
    connection_state = "ok" if connection_ready else "blocked" if service_enabled else "waiting"
    execution_state = "ok" if status.get("executionAllowed") else "locked"

    return {
        "title": "生产服务配置",
        "editable": False,
        "secretInputAllowed": False,
        "status": status,
        "items": [
            {
                "id": "service_switch",
                "label": "服务开关",
                "state": "ok" if service_enabled else "blocked",
                "description": "控制真实生产服务是否进入可检测状态。",
            },
            {
                "id": "service_connection",
                "label": "连接配置",
                "state": connection_state,
                "description": "检查生产服务连接是否已由管理员配置完成。",
            },
            {
                "id": "execution_approval",
                "label": "执行审批",
                "state": execution_state,
                "description": "即使配置就绪，正式执行仍需单独审批开启。",
            },
            {
                "id": "secret_hosting",
                "label": "密钥托管",
                "state": "server_only",
                "description": "不在页面填写密钥；敏感配置仅服务端配置。",
            },
        ],
        "adminChecklist": [
            "在服务端开启真实生产服务",
            "补全生产服务连接配置",
            "完成内部审批后再开启受控执行",
        ],
        "guardrails": [
            "不在页面填写密钥",
            "不向普通用户展示底层供应商或模型名称",
            "配置诊断不会启动付费生成",
        ],
        "paidGenerationStarted": False,
    }


def build_production_audit_log(tasks: list[dict[str, Any]], task_id: str | None = None) -> dict[str, Any]:
    selected_tasks = [task for task in tasks if not task_id or task.get("id") == task_id]
    events: list[dict[str, Any]] = []
    for task in selected_tasks:
        events.extend(production_audit_events_for(task))

    events.sort(key=lambda event: (int(event.get("at") or 0), int(event.get("order") or 0), str(event.get("id") or "")))
    response: dict[str, Any] = {
        "events": events,
        "paidGenerationStarted": False,
        "safeForUsers": True,
    }
    if task_id:
        response["taskId"] = task_id
        response["title"] = selected_tasks[0].get("title") if selected_tasks else "参考视频复刻"
    return response


def production_audit_events_for(task: dict[str, Any]) -> list[dict[str, Any]]:
    task_id = str(task.get("id") or "")
    title = str(task.get("title") or "参考视频复刻")
    production_request = task.get("productionRequest") or {}
    delivery_backfill = task.get("deliveryBackfill") or {}
    adapter_attempt = read_operation_artifact(task, "production-adapter-attempt.json")
    preflight = read_operation_artifact(task, "production-service-preflight.json")
    events: list[dict[str, Any]] = []

    if production_request.get("requestedAt"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="production_requested",
                label="提交生产请求",
                detail="已进入受控生产队列。",
                at=production_request.get("requestedAt"),
                actor="审核员",
                state="done",
                order=10,
            )
        )

    if production_request.get("claimedAt"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="production_claimed",
                label="领取任务",
                detail="操作员已领取生产任务。",
                at=production_request.get("claimedAt"),
                actor=production_request.get("operatorName") or "操作员",
                state="done",
                order=20,
            )
        )

    if adapter_attempt.get("created_at"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="production_service_attempted",
                label="尝试执行生产服务",
                detail="真实生产服务未启用，未启动付费生成。",
                at=adapter_attempt.get("created_at"),
                actor=adapter_attempt.get("operator_name") or production_request.get("operatorName") or "操作员",
                state="blocked",
                order=30,
            )
        )

    if preflight.get("created_at"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="production_service_preflight",
                label="生产服务预检",
                detail="服务端预检已通过，等待执行器接管。",
                at=preflight.get("created_at"),
                actor=preflight.get("operator_name") or production_request.get("operatorName") or "操作员",
                state="waiting",
                order=35,
            )
        )

    if delivery_backfill.get("deliveredAt"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="delivery_backfilled",
                label="人工回填交付",
                detail=delivery_backfill.get("auditNote") or "人工回填完成",
                at=delivery_backfill.get("deliveredAt"),
                actor=production_request.get("operatorName") or "操作员",
                state="done",
                order=40,
            )
        )

    if task.get("completedAt"):
        events.append(
            audit_event(
                task_id=task_id,
                title=title,
                event_id="delivery_ready",
                label="进入交付区",
                detail="交付包已准备，可进入成品交付页。",
                at=task.get("completedAt"),
                actor="系统",
                state="done",
                order=50,
            )
        )

    return events


def audit_event(
    *,
    task_id: str,
    title: str,
    event_id: str,
    label: str,
    detail: Any,
    at: Any,
    actor: Any,
    state: str,
    order: int,
) -> dict[str, Any]:
    timestamp = int(at or 0)
    return {
        "id": f"{task_id}_{event_id}_{timestamp}",
        "taskId": task_id,
        "title": title,
        "event": event_id,
        "label": label,
        "detail": str(detail or ""),
        "at": timestamp,
        "actor": str(actor or "系统"),
        "state": state,
        "order": order,
        "paidGenerationStarted": False,
    }


def build_task_detail(task: dict[str, Any], deliverables: list[dict[str, str]]) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    payload = task.get("payload") or {}
    review = task.get("review") or {}
    audit_log = build_production_audit_log([task], task_id)
    script_preview = " / ".join(script_lines(task)[:3]) or "等待审核文案"
    prep_ready = review.get("status") == "approved" and (task.get("generationApproval") or {}).get("status") == "ready_for_production"

    sections = [
        {
            "id": "production_prep",
            "title": "生产准备包",
            "state": "ready" if prep_ready else "waiting",
            "items": [
                detail_item("生产参数", f"{payload.get('duration') or 15}s · {payload.get('resolution') or '480p'} · {payload.get('count') or 1}条"),
                detail_item("素材", f"{payload.get('referenceName') or '参考视频已就绪'} · {payload.get('portraitName') or '肖像图已就绪'}"),
                detail_item("字幕规则", "短句句尾不显示标点"),
            ],
        },
        {
            "id": "review_record",
            "title": "人工审核记录",
            "state": review.get("status") or "waiting",
            "items": [
                detail_item("解析摘要", payload.get("analysisSummary") or "等待人工确认"),
                detail_item("文案预览", script_preview),
                detail_item("审核项", "素材授权 · 肖像授权 · 字幕规则 · 画面方向"),
            ],
        },
        {
            "id": "production_audit",
            "title": "生产执行审计",
            "state": "ready" if audit_log["events"] else "waiting",
            "items": [
                detail_item(event["label"], f"{event['detail']} · {event['actor']}", event.get("state") or "done")
                for event in audit_log["events"]
            ]
            or [detail_item("暂无审计记录", "提交生产请求后开始记录", "waiting")],
        },
        {
            "id": "deliverables",
            "title": "交付物",
            "state": "ready" if deliverables else "waiting",
            "items": [
                detail_item(item.get("title") or "交付物", item.get("subtitle") or "等待交付")
                for item in deliverables
            ]
            or [detail_item("等待交付", "操作员回填后显示成品、字幕和审核记录", "waiting")],
        },
    ]

    return {
        "taskId": task_id,
        "title": task.get("title") or "参考视频复刻",
        "status": task.get("status") or "queued",
        "statusLabel": task_status_label(str(task.get("status") or "queued")),
        "progress": int(task.get("progress") or 0),
        "paidGenerationStarted": False,
        "safeForUsers": True,
        "sections": sections,
    }


def detail_item(label: Any, value: Any, state: str = "done") -> dict[str, Any]:
    return {
        "label": str(label or ""),
        "value": str(value or ""),
        "state": state,
        "paidGenerationStarted": False,
    }


class ChilingRequestHandler(BaseHTTPRequestHandler):
    store = TaskStore()

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self.send_json({"ok": True, "service": "chiling-task-worker"})
            return

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return

        if path == "/config.js":
            self.send_text(
                'window.CHILING_API_BASE = window.location.origin;\n',
                content_type="application/javascript; charset=utf-8",
            )
            return

        if path == "/tasks":
            self.send_json(self.store.list())
            return

        if path == "/pipeline-queue":
            self.send_json(self.store.production_queue())
            return

        if path == "/production-requests":
            self.send_json(self.store.production_requests())
            return

        if path == "/production-service/status":
            self.send_json(self.store.production_service_status())
            return

        if path == "/production-service/configuration":
            self.send_json(self.store.production_service_configuration())
            return

        if path == "/production-audit-log":
            self.send_json(self.store.production_audit_log())
            return

        task_id = self.extract_task_id(path)
        if task_id and path.endswith("/review-draft"):
            draft = self.store.review_draft(task_id)
            if not draft:
                self.send_error_json(HTTPStatus.NOT_FOUND, "任务不存在")
                return
            self.send_json(draft)
            return

        if task_id and path.endswith("/operations"):
            operations = self.store.task_operations(task_id)
            if not operations:
                self.send_error_json(HTTPStatus.NOT_FOUND, "任务不存在")
                return
            self.send_json(operations)
            return

        if task_id and path.endswith("/production-prep"):
            prep = self.store.production_prep(task_id)
            if prep["status"] == "not_found":
                self.send_json(prep, status=HTTPStatus.NOT_FOUND)
                return
            if prep["status"] == "blocked":
                self.send_json(prep, status=HTTPStatus.CONFLICT)
                return
            self.send_json(prep)
            return

        if task_id and path.endswith("/deliverables"):
            self.send_json(self.store.deliverables(task_id))
            return

        if task_id and path.endswith("/detail"):
            detail = self.store.task_detail(task_id)
            if detail["status"] == "not_found":
                self.send_json(detail, status=HTTPStatus.NOT_FOUND)
                return
            self.send_json(detail)
            return

        if task_id:
            task = self.store.get(task_id)
            if not task:
                self.send_error_json(HTTPStatus.NOT_FOUND, "任务不存在")
                return
            self.send_json(task)
            return

        if path.startswith("/worker-files/"):
            self.serve_worker_file(path)
            return

        self.serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        operation_task_id = self.extract_operation_action_task_id(path)
        if operation_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            operation_id = str(payload.get("operationId") or "").strip()
            if not operation_id:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "operationId 不能为空")
                return

            result = self.store.run_operation(operation_task_id, operation_id)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] == "blocked":
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        review_task_id = self.extract_review_approval_task_id(path)
        if review_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.save_review(review_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            self.send_json(result)
            return

        generation_task_id = self.extract_generation_approval_task_id(path)
        if generation_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.approve_generation(generation_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] == "blocked":
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        production_request_task_id = self.extract_production_request_task_id(path)
        if production_request_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.request_production(production_request_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] == "blocked":
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        production_claim_task_id = self.extract_production_claim_task_id(path)
        if production_claim_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.claim_production(production_claim_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] == "blocked":
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        production_execute_task_id = self.extract_production_execute_task_id(path)
        if production_execute_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.execute_production(production_execute_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] in {"blocked", "disabled"}:
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        production_complete_task_id = self.extract_production_complete_task_id(path)
        if production_complete_task_id:
            try:
                payload = self.read_json_body()
            except ValueError as error:
                self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return

            result = self.store.complete_production(production_complete_task_id, payload)
            if result["status"] == "not_found":
                self.send_json(result, status=HTTPStatus.NOT_FOUND)
                return
            if result["status"] == "blocked":
                self.send_json(result, status=HTTPStatus.CONFLICT)
                return
            self.send_json(result)
            return

        if path != "/tasks":
            self.send_error_json(HTTPStatus.NOT_FOUND, "接口不存在")
            return

        try:
            payload = self.read_json_body()
        except ValueError as error:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return

        task = self.store.create(payload)
        self.send_json(task, status=HTTPStatus.CREATED)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}

        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("JSON 请求体格式错误") from error

        if not isinstance(data, dict):
            raise ValueError("JSON 请求体必须是对象")
        return data

    def extract_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)(?:/(?:deliverables|operations|review-draft|production-prep|detail))?", path)
        return unquote(match.group(1)) if match else None

    def extract_operation_action_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/operations/actions", path)
        return unquote(match.group(1)) if match else None

    def extract_review_approval_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/review-approval", path)
        return unquote(match.group(1)) if match else None

    def extract_generation_approval_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/generation-approval", path)
        return unquote(match.group(1)) if match else None

    def extract_production_request_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/production-request", path)
        return unquote(match.group(1)) if match else None

    def extract_production_claim_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/production-claim", path)
        return unquote(match.group(1)) if match else None

    def extract_production_execute_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/production-execute", path)
        return unquote(match.group(1)) if match else None

    def extract_production_complete_task_id(self, path: str) -> str | None:
        match = re.fullmatch(r"/tasks/([^/]+)/production-complete", path)
        return unquote(match.group(1)) if match else None

    def serve_static(self, path: str) -> None:
        relative_path = "index.html" if path == "/" else unquote(path.lstrip("/"))
        target = (WORKBENCH_DIR / relative_path).resolve()

        if not self.is_safe_path(target, WORKBENCH_DIR) or not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "文件不存在")
            return

        self.send_file(target)

    def serve_worker_file(self, path: str) -> None:
        relative_path = unquote(path.removeprefix("/worker-files/"))
        if not relative_path or relative_path == path:
            self.send_error_json(HTTPStatus.NOT_FOUND, "文件不存在")
            return

        target = (PROJECTS_DIR / relative_path).resolve()
        if not self.is_safe_path(target, PROJECTS_DIR) or not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "文件不存在")
            return

        self.send_file(target)

    def send_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message, "status": int(status)}, status=status)

    def send_text(self, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def is_safe_path(target: Path, root: Path) -> bool:
        try:
            target.relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[chiling-worker] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 赤灵AI运营工作台 local task worker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5180)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ChilingRequestHandler)
    print(f"赤灵AI运营工作台 Worker running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWorker stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
