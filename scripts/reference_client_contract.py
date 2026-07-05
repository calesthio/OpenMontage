"""Expose a frontend-safe contract for reference-video project controls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_action_gate import prepare_action
from scripts.reference_project_snapshot import build_snapshot

ACTION_PREPARE_PATH = "/api/reference/actions/prepare"
ACTION_EXECUTE_PATH = "/api/reference/actions/execute"
JOB_STATUS_PATH = "/api/reference/jobs/status"
JOB_LIST_PATH = "/api/reference/jobs/list"


def _execution_metadata(
    action: dict[str, Any],
    *,
    can_execute: bool,
) -> dict[str, str | None]:
    if can_execute:
        return {
            "execution_mode": "auto_execute",
            "disabled_reason": None,
            "execution_note": "可直接在本地安全执行。",
        }

    if action.get("enabled") is False:
        return {
            "execution_mode": "prepare_only",
            "disabled_reason": "action_disabled",
            "execution_note": "当前阶段暂不可执行，请先完成前置步骤。",
        }

    risk = str(action.get("risk") or "")
    if risk == "manual_review" or action.get("script") == "manual_review":
        return {
            "execution_mode": "manual_review",
            "disabled_reason": "manual_review_required",
            "execution_note": "需要人工复核，不能由本地队列自动执行。",
        }
    if risk == "paid_generation":
        return {
            "execution_mode": "prepare_only",
            "disabled_reason": "paid_generation_requires_confirmation",
            "execution_note": "付费生成只允许准备命令，确认后由人工触发。",
        }
    if risk == "production_approval":
        return {
            "execution_mode": "prepare_only",
            "disabled_reason": "production_approval_requires_confirmation",
            "execution_note": "生产批准只允许准备命令，必须人工确认后继续。",
        }
    if risk == "delivery_export":
        return {
            "execution_mode": "prepare_only",
            "disabled_reason": "delivery_export_requires_confirmation",
            "execution_note": "最终交付导出只允许准备命令，必须人工确认后继续。",
        }
    if action.get("requires_confirmation"):
        return {
            "execution_mode": "prepare_only",
            "disabled_reason": "confirmation_required",
            "execution_note": "该动作需要确认短语，只允许准备命令。",
        }
    return {
        "execution_mode": "prepare_only",
        "disabled_reason": "not_safe_for_auto_execute",
        "execution_note": "该动作不在本地安全自动执行范围内，只允许准备命令。",
    }


def _operator_guidance(
    action: dict[str, Any],
    execution: dict[str, str | None],
    *,
    can_execute: bool,
) -> dict[str, Any]:
    risk = str(action.get("risk") or "")
    confirmation_phrase = action.get("confirmation_phrase")
    disabled_reason = execution["disabled_reason"]
    base = {
        "summary": execution["execution_note"],
        "confirmation_required": bool(action.get("requires_confirmation")),
        "confirmation_phrase": confirmation_phrase,
        "blocked_reason": disabled_reason,
        "execute_button_label": "执行安全动作" if can_execute else None,
        "prepare_button_label": "准备命令",
    }
    if can_execute:
        return {
            **base,
            "next_step": "点击执行后会创建后台任务，并在作业列表里显示日志。",
        }
    if risk == "manual_review" or action.get("script") == "manual_review":
        return {
            **base,
            "next_step": "播放或检查当前产物；确认通过后再准备下一步命令。",
            "prepare_button_label": "查看复核要求",
        }
    if risk == "paid_generation":
        return {
            **base,
            "next_step": "输入确认短语后只返回命令；复制到终端前请再次核对费用和样片范围。",
            "prepare_button_label": "输入确认并准备命令",
        }
    if risk == "production_approval":
        return {
            **base,
            "next_step": "输入确认短语后只返回批准命令；请先确认文案、素材授权和 Seedance 参数。",
            "prepare_button_label": "输入确认并准备批准命令",
        }
    if risk == "delivery_export":
        return {
            **base,
            "next_step": "输入确认短语后只返回交付导出命令；请先播放最终 MP4 并确认业务批准。",
            "prepare_button_label": "输入确认并准备交付命令",
        }
    if action.get("requires_confirmation"):
        return {
            **base,
            "next_step": "输入确认短语后只返回命令；请人工核对后再决定是否执行。",
            "prepare_button_label": "输入确认并准备命令",
        }
    return {
        **base,
        "next_step": "查看准备结果并按项目流程人工处理。",
    }


def _status_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status.get("status"),
        "current_artifact_path": status.get("current_artifact_path"),
        "production_plan_path": status.get("production_plan_path"),
        "approval_status": status.get("approval_status"),
        "target_mode": status.get("target_mode"),
        "paid_generation_started": bool(status.get("paid_generation_started")),
        "render_output_path": status.get("render_output_path"),
        "render_output_exists": status.get("render_output_exists"),
        "burned_subtitles": status.get("burned_subtitles"),
        "mixed_audio": status.get("mixed_audio"),
        "mixed_audio_path": status.get("mixed_audio_path"),
        "delivery_dir": status.get("delivery_dir"),
        "delivery_video_path": status.get("delivery_video_path"),
    }


def _client_action(action: dict[str, Any]) -> dict[str, Any]:
    action_id = str(action.get("id") or "")
    can_execute = (
        action.get("risk") == "local"
        and action.get("requires_confirmation") is not True
        and action.get("script") != "manual_review"
        and action.get("enabled") is not False
    )
    execution = _execution_metadata(action, can_execute=can_execute)
    guidance = _operator_guidance(action, execution, can_execute=can_execute)
    return {
        "id": action_id,
        "label": action.get("label"),
        "script": action.get("script"),
        "risk": action.get("risk"),
        "paid_generation": bool(action.get("paid_generation")),
        "requires_confirmation": bool(action.get("requires_confirmation")),
        "confirmation_phrase": action.get("confirmation_phrase"),
        "can_execute": can_execute,
        "enabled": action.get("enabled") is not False,
        "execution_mode": execution["execution_mode"],
        "disabled_reason": execution["disabled_reason"],
        "execution_note": execution["execution_note"],
        "operator_guidance": guidance,
        "prepare_request": {
            "method": "POST",
            "path": ACTION_PREPARE_PATH,
            "body": {
                "action_id": action_id,
                "confirmation_phrase_required": bool(action.get("requires_confirmation")),
            },
        },
        "execute_request": {
            "method": "POST",
            "path": ACTION_EXECUTE_PATH,
            "body": {
                "action_id": action_id,
            },
            "enabled": can_execute,
            "disabled_reason": execution["disabled_reason"],
        },
    }


def build_client_state(project_dir: str | Path) -> dict[str, Any]:
    """Return a frontend-safe state payload with raw shell commands removed."""

    snapshot = build_snapshot(project_dir)
    return {
        "version": "1.0",
        "project_dir": snapshot["project_dir"],
        "phase": snapshot["phase"],
        "status": _status_summary(snapshot.get("status") or {}),
        "artifacts": snapshot.get("artifacts") or {},
        "approval": snapshot.get("approval") or {},
        "media": snapshot.get("media") or {},
        "delivery": snapshot.get("delivery"),
        "actions": [
            _client_action(action)
            for action in snapshot.get("ui_actions") or []
        ],
        "api_contract": {
            "state": {
                "method": "GET",
                "path": "/api/reference/state",
            },
            "create_project": {
                "method": "POST",
                "path": "/api/reference/projects/create",
            },
            "import_source": {
                "method": "POST",
                "path": "/api/reference/projects/import-source",
            },
            "prepare_action": {
                "method": "POST",
                "path": ACTION_PREPARE_PATH,
            },
            "execute_action": {
                "method": "POST",
                "path": ACTION_EXECUTE_PATH,
            },
            "job_status": {
                "method": "GET",
                "path": JOB_STATUS_PATH,
            },
            "job_list": {
                "method": "GET",
                "path": JOB_LIST_PATH,
            },
        },
        "safety": snapshot.get("safety") or {},
    }


def prepare_client_action(
    project_dir: str | Path,
    action_id: str,
    *,
    confirmation_phrase: str | None = None,
) -> dict[str, Any]:
    """Prepare an action for a client, returning blocked payloads instead of raising."""

    try:
        return prepare_action(
            project_dir,
            action_id,
            confirmation_phrase=confirmation_phrase,
        )
    except ValueError as error:
        return {
            "version": "1.0",
            "status": "blocked",
            "project_dir": str(Path(project_dir).expanduser().resolve()),
            "action_id": action_id,
            "error": str(error),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    state_parser = subparsers.add_parser("state", help="Print frontend-safe project state.")
    state_parser.add_argument("project_dir")

    prepare_parser = subparsers.add_parser(
        "prepare-action",
        help="Validate and return a command for a specific action.",
    )
    prepare_parser.add_argument("project_dir")
    prepare_parser.add_argument("action_id")
    prepare_parser.add_argument("--confirmation-phrase")

    args = parser.parse_args(argv)
    if args.command == "state":
        payload = build_client_state(args.project_dir)
        exit_code = 0
    else:
        payload = prepare_client_action(
            args.project_dir,
            args.action_id,
            confirmation_phrase=args.confirmation_phrase,
        )
        exit_code = 0 if payload.get("status") == "ready_to_execute" else 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
