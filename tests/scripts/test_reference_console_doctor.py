from __future__ import annotations

import importlib
import json


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._payload


def test_reference_console_doctor_reports_running_service(monkeypatch):
    doctor = importlib.import_module("scripts.reference_console_doctor")

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://127.0.0.1:8765/api/reference/health"
        assert timeout == 0.5
        return _FakeResponse({"status": "ok", "service": "reference_local_api"})

    monkeypatch.setattr(doctor.request, "urlopen", fake_urlopen)

    result = doctor.probe_console(timeout=0.5)

    assert result["status"] == "running"
    assert result["service_running"] is True
    assert result["console_url"] == "http://127.0.0.1:8765/"
    assert result["health"]["service"] == "reference_local_api"
    assert result["recommended_action"] == "open_console"


def test_reference_console_doctor_reports_stopped_service(monkeypatch):
    doctor = importlib.import_module("scripts.reference_console_doctor")

    def fake_urlopen(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(doctor.request, "urlopen", fake_urlopen)

    result = doctor.probe_console(timeout=0.5)

    assert result["status"] == "stopped"
    assert result["service_running"] is False
    assert result["health"] is None
    assert result["recommended_action"] == "start_console"
    assert ".venv/bin/python scripts/reference_local_api.py" in result["start_command"]


def test_reference_console_doctor_main_prints_json(monkeypatch, capsys):
    doctor = importlib.import_module("scripts.reference_console_doctor")

    def fake_urlopen(request, timeout):
        return _FakeResponse({"status": "ok", "service": "reference_local_api"})

    monkeypatch.setattr(doctor.request, "urlopen", fake_urlopen)

    exit_code = doctor.main(["--timeout", "0.5"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "running"
    assert payload["open_command"] == "open http://127.0.0.1:8765/"
