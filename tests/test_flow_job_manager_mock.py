"""Mock tests for Google Flow MCP checks — run without a real browser.

These tests verify that the Job Manager correctly handles MCP responses
using mocked subprocess, so they don't require a real Chrome/gflow session.
Real integration tests remain in test_flow_job_manager.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.flow_job_manager import (  # noqa: E402
    GFLOW_READ_ONLY_TOOLS,
    FlowJobManager,
    check_gflow_auth,
    check_gflow_credits,
    get_manager,
)


# ---------------------------------------------------------------------------
# Mock helper
# ---------------------------------------------------------------------------


class _FakeProc:
    """Fake subprocess.Popen result for MCP tests."""

    def __init__(self, stdout_lines: list[str], returncode: int = 0):
        self.stdout = "\n".join(stdout_lines) + "\n"
        self.stderr = ""
        self.returncode = returncode

    def communicate(self, input=None, timeout=None):
        return self.stdout, self.stderr

    def kill(self):
        pass


def _mcp_result(tool_name: str, payload: dict) -> str:
    """Build a fake MCP JSON-RPC result line for id=2."""
    return json.dumps(
        {"jsonrpc": "2.0", "id": 2, "result": payload}
    )


# ---------------------------------------------------------------------------
# Mocked MCP tests
# ---------------------------------------------------------------------------


def test_gflow_auth_check_mock(monkeypatch):
    """gflow_auth_status returns verified session (mocked)."""
    fake_stdout = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        _mcp_result("gflow_auth_status", {"verified": True, "profile": "flow_remote"}),
    ]

    with patch("lib.flow_job_manager.subprocess.Popen", return_value=_FakeProc(fake_stdout)):
        result = check_gflow_auth()
        assert result["ok"] is True


def test_gflow_auth_check_failed_mock(monkeypatch):
    """gflow_auth_status returns failure (mocked)."""
    fake_stdout = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        _mcp_result("gflow_auth_status", {"verified": False, "error": "no session"}),
    ]

    with patch("lib.flow_job_manager.subprocess.Popen", return_value=_FakeProc(fake_stdout)):
        result = check_gflow_auth()
        assert result["ok"] is False


def test_gflow_credits_check_mock(monkeypatch):
    """gflow_get_credits returns balance (mocked)."""
    fake_stdout = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        _mcp_result("gflow_get_credits", {"credits": 100.5, "profile": "flow_remote"}),
    ]

    with patch("lib.flow_job_manager.subprocess.Popen", return_value=_FakeProc(fake_stdout)):
        result = check_gflow_credits()
        assert result["ok"] is True


def test_gflow_mcp_error_mock(monkeypatch):
    """gflow MCP returns JSON-RPC error (mocked)."""
    fake_stdout = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32000, "message": "Connection closed"},
            }
        ),
    ]

    with patch("lib.flow_job_manager.subprocess.Popen", return_value=_FakeProc(fake_stdout)):
        with pytest.raises(RuntimeError, match="MCP gflow_auth_status error"):
            check_gflow_auth()


def test_gflow_read_only_tools_no_generation():
    """Generation tools are NOT in the read-only set (security check)."""
    assert "gflow_generate_image" not in GFLOW_READ_ONLY_TOOLS
    assert "gflow_generate_video" not in GFLOW_READ_ONLY_TOOLS
    # All permitted tools are read-only
    for tool in GFLOW_READ_ONLY_TOOLS:
        assert "generate" not in tool.lower()


def test_job_manager_read_only_mode():
    """Job Manager enforces READ_ONLY_MODE by default."""
    from lib.flow_job_manager import READ_ONLY_MODE, assert_read_only

    assert READ_ONLY_MODE is True

    # Should not raise in read-only mode
    assert_read_only("test operation")

    # Cannot be re-enabled without explicit change
    # (test that the constant exists and is True)


def test_fail_from_any_state(tmp_path):
    """fail() can be called from any non-terminal state."""
    import shutil
    import lib.flow_job_manager as fjm

    # Isolated directories
    fjm.JOBS_DIR = tmp_path / "jobs"
    fjm.FLOW_QUEUE_DIR = tmp_path / "flow_queue"
    fjm.FLOW_RESULTS_DIR = tmp_path / "flow_results"
    fjm.QUEUE_DB = tmp_path / "flow_queue" / "queue.db"
    for d in (fjm.JOBS_DIR, fjm.FLOW_QUEUE_DIR, fjm.FLOW_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    mgr = FlowJobManager()
    mgr.add_job(
        job_id="fail-test-001",
        project="test",
        scene="scene",
        prompt="A test prompt for validation purposes only",
    )

    # fail() from DRAFT should work (error state)
    job = mgr.fail("fail-test-001", "simulated failure")
    assert job.state == "FAILED"
    assert job.error == "simulated failure"

    # Cannot fail an already-failed job
    with pytest.raises(ValueError, match="already terminal"):
        mgr.fail("fail-test-001", "again")

    # Cleanup
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_fail_from_validated(tmp_path):
    """fail() works from VALIDATED state too."""
    import shutil
    import lib.flow_job_manager as fjm

    fjm.JOBS_DIR = tmp_path / "jobs2"
    fjm.FLOW_QUEUE_DIR = tmp_path / "flow_queue2"
    fjm.FLOW_RESULTS_DIR = tmp_path / "flow_results2"
    fjm.QUEUE_DB = tmp_path / "flow_queue2" / "queue.db"
    for d in (fjm.JOBS_DIR, fjm.FLOW_QUEUE_DIR, fjm.FLOW_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    mgr = FlowJobManager()
    mgr.add_job(
        job_id="fail-test-002",
        project="test",
        scene="scene",
        prompt="A test prompt for validation purposes only",
    )
    mgr.validate_job("fail-test-002")
    assert mgr.get_job("fail-test-002").state == "VALIDATED"

    job = mgr.fail("fail-test-002", "validation rejected")
    assert job.state == "FAILED"

    shutil.rmtree(tmp_path, ignore_errors=True)