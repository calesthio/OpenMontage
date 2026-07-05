from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_reference_client_contract_state_hides_raw_commands(tmp_path):
    contract = importlib.import_module("scripts.reference_client_contract")
    project_dir = tmp_path / "project"

    state = contract.build_client_state(project_dir)
    serialized = json.dumps(state, ensure_ascii=False)

    assert state["version"] == "1.0"
    assert state["project_dir"] == str(project_dir.resolve())
    assert state["phase"] == "start"
    assert state["actions"][0]["id"] == "analyze_reference"
    assert state["actions"][0]["prepare_request"]["method"] == "POST"
    assert state["actions"][0]["prepare_request"]["path"] == "/api/reference/actions/prepare"
    assert state["actions"][0]["can_execute"] is True
    assert state["actions"][0]["execution_mode"] == "auto_execute"
    assert state["actions"][0]["disabled_reason"] is None
    assert "本地安全执行" in state["actions"][0]["execution_note"]
    assert state["actions"][0]["operator_guidance"]["summary"] == "可直接在本地安全执行。"
    assert state["actions"][0]["operator_guidance"]["next_step"] == "点击执行后会创建后台任务，并在作业列表里显示日志。"
    assert state["actions"][0]["operator_guidance"]["execute_button_label"] == "执行安全动作"
    assert state["actions"][0]["operator_guidance"]["prepare_button_label"] == "准备命令"
    assert state["actions"][0]["operator_guidance"]["confirmation_required"] is False
    assert state["actions"][0]["execute_request"]["path"] == "/api/reference/actions/execute"
    assert state["actions"][0]["execute_request"]["disabled_reason"] is None
    assert state["api_contract"]["create_project"]["path"] == "/api/reference/projects/create"
    assert state["api_contract"]["import_source"]["path"] == "/api/reference/projects/import-source"
    assert state["api_contract"]["execute_action"]["path"] == "/api/reference/actions/execute"
    assert state["api_contract"]["job_status"]["path"] == "/api/reference/jobs/status"
    assert "command" not in state["actions"][0]
    assert ".venv/bin/python" not in serialized


def test_reference_client_contract_keeps_confirmation_metadata_without_command(tmp_path):
    contract = importlib.import_module("scripts.reference_client_contract")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    state = contract.build_client_state(project_dir)

    action = next(
        action for action in state["actions"] if action["id"] == "run_one_paid_seedance_sample"
    )
    assert action["risk"] == "paid_generation"
    assert action["paid_generation"] is True
    assert action["requires_confirmation"] is True
    assert action["confirmation_phrase"] == "RUN SEEDANCE SAMPLE"
    assert action["can_execute"] is False
    assert action["execution_mode"] == "prepare_only"
    assert action["disabled_reason"] == "paid_generation_requires_confirmation"
    assert "付费生成" in action["execution_note"]
    assert action["operator_guidance"]["summary"] == "付费生成只允许准备命令，确认后由人工触发。"
    assert action["operator_guidance"]["next_step"] == "输入确认短语后只返回命令；复制到终端前请再次核对费用和样片范围。"
    assert action["operator_guidance"]["prepare_button_label"] == "输入确认并准备命令"
    assert action["operator_guidance"]["execute_button_label"] is None
    assert action["operator_guidance"]["confirmation_required"] is True
    assert action["operator_guidance"]["confirmation_phrase"] == "RUN SEEDANCE SAMPLE"
    assert action["operator_guidance"]["blocked_reason"] == "paid_generation_requires_confirmation"
    assert action["execute_request"]["disabled_reason"] == "paid_generation_requires_confirmation"
    assert "command" not in action


def test_reference_client_contract_marks_production_approval_as_prepare_only(tmp_path):
    contract = importlib.import_module("scripts.reference_client_contract")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir
        / "artifacts"
        / "reference-assets"
        / "sample-assets-bound-package.json",
        {"approval": {"status": "pending_human_review"}},
    )

    state = contract.build_client_state(project_dir)

    action = next(action for action in state["actions"] if action["id"] == "approve_for_seedance")
    assert action["risk"] == "production_approval"
    assert action["can_execute"] is False
    assert action["execution_mode"] == "prepare_only"
    assert action["disabled_reason"] == "production_approval_requires_confirmation"
    assert "生产批准" in action["execution_note"]
    assert action["operator_guidance"]["next_step"] == "输入确认短语后只返回批准命令；请先确认文案、素材授权和 Seedance 参数。"
    assert action["operator_guidance"]["prepare_button_label"] == "输入确认并准备批准命令"
    assert action["operator_guidance"]["blocked_reason"] == "production_approval_requires_confirmation"


def test_reference_client_contract_marks_manual_review_actions(tmp_path):
    contract = importlib.import_module("scripts.reference_client_contract")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-sample-result.json",
        {"status": "generated", "output_path": "sample.mp4"},
    )

    state = contract.build_client_state(project_dir)

    action = next(
        action
        for action in state["actions"]
        if action["id"] == "review_sample_before_more_generation"
    )
    assert action["risk"] == "manual_review"
    assert action["can_execute"] is False
    assert action["execution_mode"] == "manual_review"
    assert action["disabled_reason"] == "manual_review_required"
    assert "人工复核" in action["execution_note"]
    assert action["operator_guidance"]["summary"] == "需要人工复核，不能由本地队列自动执行。"
    assert action["operator_guidance"]["next_step"] == "播放或检查当前产物；确认通过后再准备下一步命令。"
    assert action["operator_guidance"]["prepare_button_label"] == "查看复核要求"
    assert action["operator_guidance"]["execute_button_label"] is None
    assert action["operator_guidance"]["blocked_reason"] == "manual_review_required"


def test_reference_client_contract_prepare_action_uses_gate(tmp_path):
    contract = importlib.import_module("scripts.reference_client_contract")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    blocked = contract.prepare_client_action(project_dir, "run_one_paid_seedance_sample")
    ready = contract.prepare_client_action(
        project_dir,
        "run_one_paid_seedance_sample",
        confirmation_phrase="RUN SEEDANCE SAMPLE",
    )

    assert blocked["status"] == "blocked"
    assert "RUN SEEDANCE SAMPLE" in blocked["error"]
    assert "command" not in blocked
    assert ready["status"] == "ready_to_execute"
    assert "--allow-paid-generation" in ready["command"]


def test_reference_client_contract_main_state_prints_json_without_secrets(
    monkeypatch, tmp_path, capsys
):
    contract = importlib.import_module("scripts.reference_client_contract")
    secret = "do-not-print-this-client-contract-secret"
    monkeypatch.setenv("DOUBAO_API_KEY", secret)
    project_dir = tmp_path / "project"

    exit_code = contract.main(["state", str(project_dir)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["phase"] == "start"
    assert secret not in json.dumps(payload, ensure_ascii=False)
