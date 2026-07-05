from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_reference_action_gate_requires_paid_seedance_confirmation(tmp_path):
    gate = importlib.import_module("scripts.reference_action_gate")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    with pytest.raises(ValueError, match="RUN SEEDANCE SAMPLE"):
        gate.prepare_action(project_dir, "run_one_paid_seedance_sample")

    result = gate.prepare_action(
        project_dir,
        "run_one_paid_seedance_sample",
        confirmation_phrase="RUN SEEDANCE SAMPLE",
    )

    assert result["status"] == "ready_to_execute"
    assert result["action_id"] == "run_one_paid_seedance_sample"
    assert result["risk"] == "paid_generation"
    assert result["paid_generation"] is True
    assert "--allow-paid-generation" in result["command"]


def test_reference_action_gate_requires_delivery_confirmation(tmp_path):
    gate = importlib.import_module("scripts.reference_action_gate")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(output_path),
        },
    )

    with pytest.raises(ValueError, match="APPROVE FINAL DELIVERY"):
        gate.prepare_action(
            project_dir,
            "export_delivery_package",
            confirmation_phrase="wrong phrase",
        )

    result = gate.prepare_action(
        project_dir,
        "export_delivery_package",
        confirmation_phrase="APPROVE FINAL DELIVERY",
    )

    assert result["status"] == "ready_to_execute"
    assert result["risk"] == "delivery_export"
    assert result["paid_generation"] is False
    assert "scripts/export_reference_delivery.py" in result["command"]


def test_reference_action_gate_allows_local_action_without_confirmation(tmp_path):
    gate = importlib.import_module("scripts.reference_action_gate")
    project_dir = tmp_path / "project"

    result = gate.prepare_action(project_dir, "analyze_reference")

    assert result["status"] == "ready_to_execute"
    assert result["risk"] == "local"
    assert result["requires_confirmation"] is False
    assert result["command"].startswith(".venv/bin/python")


def test_reference_action_gate_rejects_unknown_action(tmp_path):
    gate = importlib.import_module("scripts.reference_action_gate")

    with pytest.raises(ValueError, match="Unknown action"):
        gate.prepare_action(tmp_path / "project", "missing_action")


def test_reference_action_gate_main_prints_json_and_does_not_leak_env(monkeypatch, tmp_path, capsys):
    gate = importlib.import_module("scripts.reference_action_gate")
    secret = "do-not-print-this-action-gate-secret"
    monkeypatch.setenv("RUNNINGHUB_API_KEY", secret)
    project_dir = tmp_path / "project"

    exit_code = gate.main([str(project_dir), "analyze_reference"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["action_id"] == "analyze_reference"
    assert payload["status"] == "ready_to_execute"
    assert secret not in json.dumps(payload, ensure_ascii=False)
