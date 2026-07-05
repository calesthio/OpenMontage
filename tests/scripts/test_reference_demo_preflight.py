from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_reference_demo_preflight_reports_ready_without_leaking_keys(monkeypatch, tmp_path):
    preflight = importlib.import_module("scripts.reference_demo_preflight")
    secret = "secret-runninghub-key"
    monkeypatch.setenv("RUNNINGHUB_API_KEY", secret)
    monkeypatch.setenv("DOUBAO_VISION_API_KEY", "secret-doubao-key")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    result = preflight.run_preflight(
        source=str(source),
        project_dir=tmp_path / "project",
        reverse_prompts=True,
        seedance_provider="runninghub",
    )

    encoded = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "ready"
    assert result["source"]["exists"] is True
    assert result["project_dir"]["writable"] is True
    assert result["providers"]["seedance"]["configured"] is True
    assert result["providers"]["vision"]["configured"] is True
    assert secret not in encoded
    assert "secret-doubao-key" not in encoded


def test_reference_demo_preflight_blocks_missing_local_source(tmp_path):
    preflight = importlib.import_module("scripts.reference_demo_preflight")

    result = preflight.run_preflight(
        source=str(tmp_path / "missing.mp4"),
        project_dir=tmp_path / "project",
    )

    assert result["status"] == "blocked"
    assert result["source"]["exists"] is False
    assert any(issue["code"] == "missing_local_source" for issue in result["issues"])


def test_reference_demo_preflight_marks_doubao_optional_when_not_requested(monkeypatch, tmp_path):
    preflight = importlib.import_module("scripts.reference_demo_preflight")
    monkeypatch.delenv("DOUBAO_VISION_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    result = preflight.run_preflight(
        source=str(source),
        project_dir=tmp_path / "project",
        reverse_prompts=False,
        root=tmp_path,
    )

    assert result["status"] in {"ready", "degraded"}
    assert result["providers"]["vision"]["required"] is False
    assert result["providers"]["vision"]["configured"] is False
    assert not any(issue["code"] == "missing_doubao_vision_key" for issue in result["issues"])


def test_reference_demo_preflight_main_prints_json(monkeypatch, tmp_path, capsys):
    preflight = importlib.import_module("scripts.reference_demo_preflight")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    exit_code = preflight.main(
        [
            str(source),
            "--project-dir",
            str(tmp_path / "project"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["source"]["input"] == str(source)
