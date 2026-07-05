from __future__ import annotations

import importlib.util
import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKER_PATH = ROOT / "web" / "chiling-workbench" / "worker.py"


def _load_worker():
    spec = importlib.util.spec_from_file_location("chiling_worker", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _http_json(port: int, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read().decode("utf-8")
    connection.close()
    return response.status, json.loads(data) if data else {}


def _http_raw(port: int, method: str, path: str) -> tuple[int, bytes, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path)
    response = connection.getresponse()
    data = response.read()
    content_type = response.getheader("Content-Type", "")
    connection.close()
    return response.status, data, content_type


def test_chiling_worker_create_writes_reference_pipeline_handoff(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")

    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create(
        {
            "referenceUrl": str(reference),
            "duration": 20,
            "resolution": "1080p",
            "count": 9,
            "script": "第一句。\n第二句，",
        }
    )

    handoff = task["pipeline_handoff"]
    queue_payload = json.loads(Path(handoff["queue_item_path"]).read_text(encoding="utf-8"))

    assert task["payload"]["duration"] == 15
    assert task["payload"]["resolution"] == "480p"
    assert task["payload"]["count"] == 5
    assert task["payload"]["script"] == "第一句\n第二句"
    assert task["pipeline"]["mode"] == "reference_pipeline_handoff"
    assert handoff["pipeline_type"] == "reference-video-analysis"
    assert handoff["status"] == "source_imported_needs_analysis"
    assert Path(handoff["reference_project_dir"]).is_dir()
    assert Path(handoff["source_artifact_path"]).is_file()
    assert queue_payload["task_id"] == task["id"]
    assert queue_payload["next_stage"] == "analyze"
    assert queue_payload["paid_generation_allowed"] is False


def test_chiling_worker_lists_user_safe_production_queue(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    queue = store.production_queue()
    serialized = json.dumps(queue, ensure_ascii=False)

    assert len(queue) == 1
    assert queue[0]["taskId"] == task["id"]
    assert queue[0]["title"] == "参考视频复刻"
    assert queue[0]["sourceState"] == "素材已导入"
    assert queue[0]["nextAction"] == "解析参考"
    assert queue[0]["approvalRequired"] is True
    assert queue[0]["queueItemReady"] is True
    assert "reference-video-analysis" not in serialized
    assert "pipeline_type" not in serialized
    assert "command" not in serialized


def test_chiling_worker_returns_user_safe_operation_panel(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    panel = store.task_operations(task["id"])
    serialized = json.dumps(panel, ensure_ascii=False)

    assert panel["taskId"] == task["id"]
    assert panel["title"] == "参考视频复刻"
    assert [step["title"] for step in panel["steps"]] == [
        "参考素材",
        "参考解析",
        "文案提取",
        "人工确认",
        "生成审批",
    ]
    assert panel["steps"][0]["state"] == "done"
    assert panel["steps"][1]["state"] == "ready"
    assert panel["steps"][1]["actionLabel"] == "开始解析"
    assert panel["steps"][3]["approvalRequired"] is True
    assert panel["steps"][4]["state"] == "locked"
    assert panel["steps"][4]["approvalRequired"] is True
    assert panel["safeAutoExecute"] is False
    assert "reference-video-analysis" not in serialized
    assert "pipeline_type" not in serialized
    assert "command" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_runs_safe_local_operation_actions(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。\n第二句。"})

    analysis = store.run_operation(task["id"], "reference_analysis")
    copy_extract = store.run_operation(task["id"], "copy_extract")
    blocked = store.run_operation(task["id"], "generation_approval")
    panel = store.task_operations(task["id"])
    serialized = json.dumps([analysis, copy_extract, blocked, panel], ensure_ascii=False)

    assert analysis["status"] == "completed"
    assert analysis["operationId"] == "reference_analysis"
    assert analysis["paidGenerationStarted"] is False
    assert Path(analysis["artifactPath"]).is_file()
    assert copy_extract["status"] == "completed"
    assert copy_extract["operationId"] == "copy_extract"
    assert copy_extract["progress"] >= 76
    assert Path(copy_extract["artifactPath"]).is_file()
    assert blocked["status"] == "blocked"
    assert blocked["operationId"] == "generation_approval"
    assert blocked["paidGenerationStarted"] is False
    assert panel["steps"][1]["state"] == "done"
    assert panel["steps"][2]["state"] == "done"
    assert panel["steps"][4]["state"] == "locked"
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_builds_editable_review_draft_from_safe_artifacts(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。\n第二句。"})
    store.run_operation(task["id"], "reference_analysis")
    store.run_operation(task["id"], "copy_extract")

    draft = store.review_draft(task["id"])
    serialized = json.dumps(draft, ensure_ascii=False)

    assert draft["taskId"] == task["id"]
    assert draft["editable"] is True
    assert draft["analysisSummary"] == "参考结构已完成本地整理。"
    assert draft["scriptDraft"] == "第一句\n第二句"
    assert draft["subtitleRule"] == "短句句尾不显示标点。"
    assert draft["reviewChecks"] == ["素材授权", "肖像授权", "字幕规则", "画面方向"]
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_saves_approved_review_without_generation(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "旧文案。"})
    result = store.save_review(
        task["id"],
        {
            "analysisSummary": "人工改后的解析摘要",
            "script": "第一句。\n第二句，",
            "approved": True,
        },
    )
    saved = store.get(task["id"])
    panel = store.task_operations(task["id"])
    serialized = json.dumps([result, panel], ensure_ascii=False)

    assert result["status"] == "approved"
    assert result["paidGenerationStarted"] is False
    assert Path(result["artifactPath"]).is_file()
    assert saved["payload"]["analysisSummary"] == "人工改后的解析摘要"
    assert saved["payload"]["script"] == "第一句\n第二句"
    assert saved["review"]["status"] == "approved"
    assert panel["steps"][3]["state"] == "done"
    assert panel["steps"][4]["state"] == "ready"
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_requires_phrase_for_generation_approval_gate(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    before_review = store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    wrong_phrase = store.approve_generation(task["id"], {"confirmationPhrase": "确认"})
    approved = store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    saved = store.get(task["id"])
    panel = store.task_operations(task["id"])
    serialized = json.dumps([before_review, wrong_phrase, approved, panel], ensure_ascii=False)

    assert before_review["status"] == "blocked"
    assert before_review["requiredPhrase"] == "确认进入生产"
    assert wrong_phrase["status"] == "blocked"
    assert wrong_phrase["paidGenerationStarted"] is False
    assert approved["status"] == "ready_for_production"
    assert approved["productionPrepared"] is True
    assert approved["paidGenerationStarted"] is False
    assert Path(approved["artifactPath"]).is_file()
    assert saved["generationApproval"]["status"] == "ready_for_production"
    assert panel["steps"][4]["state"] == "done"
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_builds_safe_production_prep_after_approval(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create(
        {
            "referenceUrl": str(reference),
            "duration": 12,
            "resolution": "720p",
            "count": 3,
            "referenceName": "团队参考.mp4",
            "portraitName": "授权肖像.png",
            "script": "第一句。\n第二句，",
        }
    )
    blocked = store.production_prep(task["id"])
    store.save_review(
        task["id"],
        {"analysisSummary": "人工确认后的解析摘要", "script": "第一句。\n第二句，", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})

    prep = store.production_prep(task["id"])
    serialized = json.dumps(prep, ensure_ascii=False)

    assert blocked["status"] == "blocked"
    assert blocked["paidGenerationStarted"] is False
    assert prep["status"] == "ready"
    assert prep["taskId"] == task["id"]
    assert prep["constraints"]["durationSeconds"] == 12
    assert prep["constraints"]["maxDurationSeconds"] == 15
    assert prep["constraints"]["resolution"] == "720p"
    assert prep["constraints"]["batchCount"] == 3
    assert prep["constraints"]["maxBatchCount"] == 5
    assert prep["review"]["analysisSummary"] == "人工确认后的解析摘要"
    assert prep["review"]["scriptLines"] == ["第一句", "第二句"]
    assert prep["assets"]["referenceName"] == "团队参考.mp4"
    assert prep["assets"]["portraitName"] == "授权肖像.png"
    assert prep["paidGenerationStarted"] is False
    assert Path(prep["artifactPath"]).is_file()
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_requires_phrase_for_controlled_production_request(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    before_ready = store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    wrong_phrase = store.request_production(task["id"], {"confirmationPhrase": "确认"})
    requested = store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    saved = store.get(task["id"])
    prep = store.production_prep(task["id"])
    panel = store.task_operations(task["id"])
    serialized = json.dumps([before_ready, wrong_phrase, requested, prep, panel], ensure_ascii=False)

    assert before_ready["status"] == "blocked"
    assert before_ready["requiredPhrase"] == "确认提交生产"
    assert wrong_phrase["status"] == "blocked"
    assert wrong_phrase["paidGenerationStarted"] is False
    assert requested["status"] == "production_requested"
    assert requested["requiredPhrase"] == "确认提交生产"
    assert requested["executionStarted"] is False
    assert requested["paidGenerationStarted"] is False
    assert Path(requested["artifactPath"]).is_file()
    assert saved["productionRequest"]["status"] == "production_requested"
    assert prep["productionRequest"]["status"] == "production_requested"
    assert panel["steps"][-1]["title"] == "生产交接"
    assert panel["steps"][-1]["state"] == "done"
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_lists_operator_production_requests(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create(
        {
            "referenceUrl": str(reference),
            "duration": 10,
            "resolution": "480p",
            "count": 2,
            "script": "第一句。",
        }
    )
    assert store.production_requests() == []

    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})

    queue = store.production_requests()
    serialized = json.dumps(queue, ensure_ascii=False)

    assert len(queue) == 1
    assert queue[0]["taskId"] == task["id"]
    assert queue[0]["title"] == "参考视频复刻"
    assert queue[0]["status"] == "production_requested"
    assert queue[0]["statusLabel"] == "等待生产"
    assert queue[0]["nextAction"] == "操作员执行"
    assert queue[0]["durationSeconds"] == 10
    assert queue[0]["resolution"] == "480p"
    assert queue[0]["batchCount"] == 2
    assert queue[0]["executionStarted"] is False
    assert queue[0]["paidGenerationStarted"] is False
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_claims_production_request_without_generation(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    before_request = store.claim_production(task["id"], {"operatorName": "小王"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})

    claimed = store.claim_production(task["id"], {"operatorName": "小王"})
    saved = store.get(task["id"])
    queue = store.production_requests()
    serialized = json.dumps([before_request, claimed, queue], ensure_ascii=False)

    assert before_request["status"] == "blocked"
    assert before_request["paidGenerationStarted"] is False
    assert claimed["status"] == "execution_in_progress"
    assert claimed["operatorName"] == "小王"
    assert claimed["executionStarted"] is True
    assert claimed["paidGenerationStarted"] is False
    assert Path(claimed["artifactPath"]).is_file()
    assert saved["productionRequest"]["status"] == "execution_in_progress"
    assert saved["productionRequest"]["executionStarted"] is True
    assert queue[0]["status"] == "execution_in_progress"
    assert queue[0]["statusLabel"] == "执行中"
    assert queue[0]["nextAction"] == "操作员处理中"
    assert queue[0]["executionStarted"] is True
    assert queue[0]["paidGenerationStarted"] is False
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_production_adapter_is_disabled_by_default(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    before_claim = store.execute_production(task["id"], {"operatorName": "小王"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.claim_production(task["id"], {"operatorName": "小王"})

    attempt = store.execute_production(task["id"], {"operatorName": "小王"})
    saved = store.get(task["id"])
    queue = store.production_requests()
    serialized = json.dumps([before_claim, attempt, queue], ensure_ascii=False)

    assert before_claim["status"] == "blocked"
    assert before_claim["paidGenerationStarted"] is False
    assert attempt["status"] == "disabled"
    assert attempt["adapterExecutionStarted"] is False
    assert attempt["paidGenerationStarted"] is False
    assert Path(attempt["artifactPath"]).is_file()
    assert saved["status"] != "completed"
    assert "deliveryBackfill" not in saved
    assert saved["productionRequest"]["status"] == "execution_in_progress"
    assert queue[0]["status"] == "execution_in_progress"
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_reports_user_safe_production_service_status(tmp_path, monkeypatch):
    worker = _load_worker()
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    monkeypatch.delenv("CHILING_PRODUCTION_SERVICE_ENABLED", raising=False)
    monkeypatch.delenv("CHILING_PRODUCTION_SERVICE_ENDPOINT", raising=False)
    disabled = store.production_service_status()

    monkeypatch.setenv("CHILING_PRODUCTION_SERVICE_ENABLED", "true")
    monkeypatch.delenv("CHILING_PRODUCTION_SERVICE_ENDPOINT", raising=False)
    missing_configuration = store.production_service_status()

    monkeypatch.setenv("CHILING_PRODUCTION_SERVICE_ENDPOINT", "https://internal.example.invalid/run")
    ready = store.production_service_status()
    serialized = json.dumps([disabled, missing_configuration, ready], ensure_ascii=False)

    assert disabled["status"] == "disabled"
    assert disabled["statusLabel"] == "未启用"
    assert disabled["ready"] is False
    assert disabled["executionAllowed"] is False
    assert disabled["paidGenerationStarted"] is False
    assert "不会启动付费生成" in disabled["summary"]
    assert missing_configuration["status"] == "missing_configuration"
    assert missing_configuration["statusLabel"] == "待配置"
    assert missing_configuration["ready"] is False
    assert missing_configuration["executionAllowed"] is False
    assert ready["status"] == "ready"
    assert ready["statusLabel"] == "可连接"
    assert ready["ready"] is True
    assert ready["executionAllowed"] is False
    assert ready["paidGenerationStarted"] is False
    assert "真实生产服务" in ready["summary"]
    assert "CHILING_PRODUCTION_SERVICE" not in serialized
    assert "RUNNINGHUB" not in serialized
    assert "DOUBAO" not in serialized
    assert "ARK" not in serialized
    assert "API" not in serialized
    assert "https://internal.example.invalid" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_preflights_production_service_only_after_server_approval(tmp_path, monkeypatch):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.claim_production(task["id"], {"operatorName": "小王"})

    monkeypatch.setenv("CHILING_PRODUCTION_SERVICE_ENABLED", "true")
    monkeypatch.setenv("CHILING_PRODUCTION_SERVICE_ENDPOINT", "https://internal.example.invalid/run")
    monkeypatch.delenv("CHILING_PRODUCTION_EXECUTION_APPROVED", raising=False)

    not_approved = store.execute_production(task["id"], {"operatorName": "小王"})
    status_before_approval = store.production_service_status()

    monkeypatch.setenv("CHILING_PRODUCTION_EXECUTION_APPROVED", "true")
    preflight = store.execute_production(task["id"], {"operatorName": "小王"})
    audit_log = store.production_audit_log(task["id"])
    serialized = json.dumps([not_approved, status_before_approval, preflight, audit_log], ensure_ascii=False)

    assert status_before_approval["status"] == "ready"
    assert status_before_approval["executionAllowed"] is False
    assert not_approved["status"] == "disabled"
    assert not_approved["adapterExecutionStarted"] is False
    assert not_approved["paidGenerationStarted"] is False
    assert preflight["status"] == "preflight_ready"
    assert preflight["adapterExecutionStarted"] is False
    assert preflight["serverExecutionQueued"] is False
    assert preflight["paidGenerationStarted"] is False
    assert preflight["nextAction"] == "等待服务端执行器接管"
    assert Path(preflight["artifactPath"]).is_file()
    assert "生产服务预检" in [event["label"] for event in audit_log["events"]]
    assert "command" not in serialized
    assert "CHILING_PRODUCTION_SERVICE" not in serialized
    assert "https://internal.example.invalid" not in serialized
    assert "RUNNINGHUB" not in serialized
    assert "DOUBAO" not in serialized
    assert "ARK" not in serialized
    assert "API" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_returns_user_safe_production_service_configuration(tmp_path, monkeypatch):
    worker = _load_worker()
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    monkeypatch.setenv("CHILING_PRODUCTION_SERVICE_ENABLED", "true")
    monkeypatch.delenv("CHILING_PRODUCTION_SERVICE_ENDPOINT", raising=False)

    configuration = store.production_service_configuration()
    serialized = json.dumps(configuration, ensure_ascii=False)

    assert configuration["title"] == "生产服务配置"
    assert configuration["editable"] is False
    assert configuration["secretInputAllowed"] is False
    assert configuration["paidGenerationStarted"] is False
    assert configuration["status"]["status"] == "missing_configuration"
    assert configuration["status"]["executionAllowed"] is False
    assert [item["label"] for item in configuration["items"]] == [
        "服务开关",
        "连接配置",
        "执行审批",
        "密钥托管",
    ]
    assert configuration["items"][0]["state"] == "ok"
    assert configuration["items"][1]["state"] == "blocked"
    assert configuration["items"][2]["state"] == "locked"
    assert configuration["items"][3]["state"] == "server_only"
    assert configuration["adminChecklist"] == [
        "在服务端开启真实生产服务",
        "补全生产服务连接配置",
        "完成内部审批后再开启受控执行",
    ]
    assert "CHILING_PRODUCTION_SERVICE" not in serialized
    assert "RUNNINGHUB" not in serialized
    assert "DOUBAO" not in serialized
    assert "ARK" not in serialized
    assert "API" not in serialized
    assert "密钥值" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_does_not_auto_complete_before_delivery_backfill(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。", "count": 1})
    stale_task = {
        **task,
        "createdAt": task["createdAt"] - 120_000,
        "estimatedSeconds": 1,
        "progress": 8,
    }
    store.save([stale_task])

    refreshed = store.get(task["id"])

    assert refreshed["status"] != "completed"
    assert refreshed["progress"] < 100
    assert store.deliverables(task["id"]) == []


def test_chiling_worker_completes_delivery_backfill_after_claim(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。", "duration": 9})
    before_claim = store.complete_production(
        task["id"],
        {"videoName": "成品.mp4", "subtitleName": "字幕.srt", "auditNote": "人工回填完成"},
    )
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.claim_production(task["id"], {"operatorName": "小王"})

    completed = store.complete_production(
        task["id"],
        {"videoName": "成品.mp4", "subtitleName": "字幕.srt", "auditNote": "人工回填完成"},
    )
    saved = store.get(task["id"])
    queue = store.production_requests()
    deliverables = store.deliverables(task["id"])
    serialized = json.dumps([before_claim, completed, deliverables], ensure_ascii=False)

    assert before_claim["status"] == "blocked"
    assert before_claim["paidGenerationStarted"] is False
    assert completed["status"] == "completed"
    assert completed["deliveryReady"] is True
    assert completed["paidGenerationStarted"] is False
    assert Path(completed["artifactPath"]).is_file()
    assert saved["status"] == "completed"
    assert saved["progress"] == 100
    assert saved["productionRequest"]["status"] == "delivered"
    assert saved["deliveryBackfill"]["videoName"] == "成品.mp4"
    assert queue == []
    assert deliverables[0]["title"] == "成品视频"
    assert "成品.mp4" in deliverables[0]["subtitle"]
    assert deliverables[1]["title"] == "字幕文件"
    assert "字幕.srt" in deliverables[1]["subtitle"]
    assert "command" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_builds_user_safe_production_audit_log(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.claim_production(task["id"], {"operatorName": "小王"})
    store.execute_production(task["id"], {"operatorName": "小王"})
    store.complete_production(
        task["id"],
        {"videoName": "成品.mp4", "subtitleName": "字幕.srt", "auditNote": "人工回填完成"},
    )

    audit_log = store.production_audit_log()
    task_audit_log = store.production_audit_log(task["id"])
    serialized = json.dumps([audit_log, task_audit_log], ensure_ascii=False)

    assert audit_log["paidGenerationStarted"] is False
    assert audit_log["safeForUsers"] is True
    assert task_audit_log["taskId"] == task["id"]
    assert [event["label"] for event in task_audit_log["events"]] == [
        "提交生产请求",
        "领取任务",
        "尝试执行生产服务",
        "人工回填交付",
        "进入交付区",
    ]
    assert all(event["paidGenerationStarted"] is False for event in task_audit_log["events"])
    assert task_audit_log["events"][1]["actor"] == "小王"
    assert task_audit_log["events"][2]["state"] == "blocked"
    assert task_audit_log["events"][3]["detail"] == "人工回填完成"
    assert "command" not in serialized
    assert "artifactPath" not in serialized
    assert "production-adapter" not in serialized
    assert "RUNNINGHUB" not in serialized
    assert "DOUBAO" not in serialized
    assert "ARK" not in serialized
    assert "API" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_returns_user_safe_task_detail(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )

    task = store.create({"referenceUrl": str(reference), "script": "第一句。", "duration": 8, "resolution": "480p"})
    store.save_review(
        task["id"],
        {"analysisSummary": "已人工确认", "script": "第一句。", "approved": True},
    )
    store.approve_generation(task["id"], {"confirmationPhrase": "确认进入生产"})
    store.request_production(task["id"], {"confirmationPhrase": "确认提交生产"})
    store.claim_production(task["id"], {"operatorName": "小王"})
    store.execute_production(task["id"], {"operatorName": "小王"})
    store.complete_production(
        task["id"],
        {"videoName": "成品.mp4", "subtitleName": "字幕.srt", "auditNote": "人工回填完成"},
    )

    detail = store.task_detail(task["id"])
    missing = store.task_detail("missing")
    serialized = json.dumps(detail, ensure_ascii=False)

    assert missing["status"] == "not_found"
    assert detail["taskId"] == task["id"]
    assert detail["title"] == "参考视频复刻"
    assert detail["paidGenerationStarted"] is False
    assert [section["title"] for section in detail["sections"]] == [
        "生产准备包",
        "人工审核记录",
        "生产执行审计",
        "交付物",
    ]
    assert detail["sections"][0]["items"][0]["label"] == "生产参数"
    assert "8s" in detail["sections"][0]["items"][0]["value"]
    assert detail["sections"][1]["items"][0]["label"] == "解析摘要"
    assert detail["sections"][1]["items"][0]["value"] == "已人工确认"
    assert "尝试执行生产服务" in [item["label"] for item in detail["sections"][2]["items"]]
    assert "成品视频" in [item["label"] for item in detail["sections"][3]["items"]]
    assert "command" not in serialized
    assert "artifactPath" not in serialized
    assert "queue_item_path" not in serialized
    assert "RUNNINGHUB" not in serialized
    assert "DOUBAO" not in serialized
    assert "ARK" not in serialized
    assert "API" not in serialized
    assert "reference-video-analysis" not in serialized
    assert "seedance" not in serialized.lower()


def test_chiling_worker_http_smoke_runs_full_delivery_flow(tmp_path):
    worker = _load_worker()
    reference = tmp_path / "reference.mp4"
    reference.write_bytes(b"fake mp4")
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )
    original_store = worker.ChilingRequestHandler.store
    worker.ChilingRequestHandler.store = store
    try:
        server = worker.ThreadingHTTPServer(("127.0.0.1", 0), worker.ChilingRequestHandler)
    except PermissionError:
        worker.ChilingRequestHandler.store = original_store
        pytest.skip("local socket binding is not permitted in this sandbox")
    port = int(server.server_address[1])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, health = _http_json(port, "GET", "/health")
        assert status == 200
        assert health["ok"] is True

        status, service_status = _http_json(port, "GET", "/production-service/status")
        service_serialized = json.dumps(service_status, ensure_ascii=False)
        assert status == 200
        assert service_status["status"] == "disabled"
        assert service_status["executionAllowed"] is False
        assert service_status["paidGenerationStarted"] is False
        assert "seedance" not in service_serialized.lower()

        status, service_configuration = _http_json(port, "GET", "/production-service/configuration")
        configuration_serialized = json.dumps(service_configuration, ensure_ascii=False)
        assert status == 200
        assert service_configuration["title"] == "生产服务配置"
        assert service_configuration["secretInputAllowed"] is False
        assert service_configuration["paidGenerationStarted"] is False
        assert "seedance" not in configuration_serialized.lower()

        status, empty_audit = _http_json(port, "GET", "/production-audit-log")
        assert status == 200
        assert empty_audit["events"] == []
        assert empty_audit["paidGenerationStarted"] is False

        status, task = _http_json(
            port,
            "POST",
            "/tasks",
            {
                "referenceUrl": str(reference),
                "script": "第一句。\n第二句，",
                "duration": 9,
                "resolution": "480p",
                "count": 1,
            },
        )
        assert status == 201
        task_id = task["id"]

        status, analysis = _http_json(port, "POST", f"/tasks/{task_id}/operations/actions", {"operationId": "reference_analysis"})
        assert status == 200
        assert analysis["paidGenerationStarted"] is False

        status, copy_extract = _http_json(port, "POST", f"/tasks/{task_id}/operations/actions", {"operationId": "copy_extract"})
        assert status == 200
        assert copy_extract["paidGenerationStarted"] is False

        status, review = _http_json(
            port,
            "POST",
            f"/tasks/{task_id}/review-approval",
            {"analysisSummary": "人工确认摘要", "script": "第一句。\n第二句，", "approved": True},
        )
        assert status == 200
        assert review["status"] == "approved"

        status, blocked_generation = _http_json(port, "POST", f"/tasks/{task_id}/generation-approval", {"confirmationPhrase": "确认"})
        assert status == 409
        assert blocked_generation["paidGenerationStarted"] is False

        status, generation = _http_json(port, "POST", f"/tasks/{task_id}/generation-approval", {"confirmationPhrase": "确认进入生产"})
        assert status == 200
        assert generation["status"] == "ready_for_production"
        assert generation["paidGenerationStarted"] is False

        status, prep = _http_json(port, "GET", f"/tasks/{task_id}/production-prep")
        assert status == 200
        assert prep["status"] == "ready"

        status, production_request = _http_json(port, "POST", f"/tasks/{task_id}/production-request", {"confirmationPhrase": "确认提交生产"})
        assert status == 200
        assert production_request["status"] == "production_requested"
        assert production_request["paidGenerationStarted"] is False

        status, request_queue = _http_json(port, "GET", "/production-requests")
        assert status == 200
        assert request_queue[0]["status"] == "production_requested"

        status, claim = _http_json(port, "POST", f"/tasks/{task_id}/production-claim", {"operatorName": "小王"})
        assert status == 200
        assert claim["status"] == "execution_in_progress"
        assert claim["paidGenerationStarted"] is False

        status, adapter_attempt = _http_json(port, "POST", f"/tasks/{task_id}/production-execute", {"operatorName": "小王"})
        assert status == 409
        assert adapter_attempt["status"] == "disabled"
        assert adapter_attempt["adapterExecutionStarted"] is False
        assert adapter_attempt["paidGenerationStarted"] is False

        status, running_queue = _http_json(port, "GET", "/production-requests")
        assert status == 200
        assert running_queue[0]["status"] == "execution_in_progress"

        status, complete = _http_json(
            port,
            "POST",
            f"/tasks/{task_id}/production-complete",
            {"videoName": "成品.mp4", "subtitleName": "字幕.srt", "auditNote": "人工回填完成"},
        )
        assert status == 200
        assert complete["status"] == "completed"
        assert complete["paidGenerationStarted"] is False

        status, audit_log = _http_json(port, "GET", "/production-audit-log")
        assert status == 200
        assert "尝试执行生产服务" in [event["label"] for event in audit_log["events"]]
        assert audit_log["paidGenerationStarted"] is False

        status, detail = _http_json(port, "GET", f"/tasks/{task_id}/detail")
        assert status == 200
        assert detail["taskId"] == task_id
        assert "生产执行审计" in [section["title"] for section in detail["sections"]]
        assert detail["paidGenerationStarted"] is False

        status, deliverables = _http_json(port, "GET", f"/tasks/{task_id}/deliverables")
        assert status == 200
        assert deliverables[0]["title"] == "成品视频"
        assert "成品.mp4" in deliverables[0]["subtitle"]

        status, empty_queue = _http_json(port, "GET", "/production-requests")
        assert status == 200
        assert empty_queue == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        worker.ChilingRequestHandler.store = original_store


def test_chiling_worker_serves_favicon_without_console_404(tmp_path):
    worker = _load_worker()
    store = worker.TaskStore(
        tasks_file=tmp_path / "worker-data" / "tasks.json",
        projects_dir=tmp_path / "web-projects",
        bridge_projects_root=tmp_path / "reference-projects",
        bridge_queue_root=tmp_path / "pipeline-queue",
    )
    original_store = worker.ChilingRequestHandler.store
    worker.ChilingRequestHandler.store = store
    try:
        server = worker.ThreadingHTTPServer(("127.0.0.1", 0), worker.ChilingRequestHandler)
    except PermissionError:
        worker.ChilingRequestHandler.store = original_store
        pytest.skip("local socket binding is not permitted in this sandbox")
    port = int(server.server_address[1])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, body, content_type = _http_raw(port, "GET", "/favicon.ico")

        assert status == 204
        assert body == b""
        assert "image" not in content_type.lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        worker.ChilingRequestHandler.store = original_store
