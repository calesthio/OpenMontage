"""Parts of tools/minicut_cli.py the minicut_video tests do not reach.

A fake ``minicut`` stands in for the CLI, so no test signs in or spends.
"""

from __future__ import annotations

import subprocess

import pytest

import tools.minicut_cli as cli

APPROVAL = {"credits": 60.45, "model": "kling-4", "key": "k", "quote": "q"}


@pytest.fixture
def fake_run(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/local/bin/minicut")

    def use(fn):
        monkeypatch.setattr(cli.subprocess, "run", fn)

    return use


def test_run_reports_stderr_when_no_json(fake_run):
    fake_run(lambda argv, **kw: subprocess.CompletedProcess(argv, 10, "", "Sign in first: minicut login\n"))
    code, data = cli.run(["jobs", "--json"])

    assert code == 10
    assert cli.message(data, code) == "Sign in first: minicut login"


def test_send_timeout_keeps_approval_for_a_free_resend(fake_run):
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    fake_run(slow)
    result = cli.send(["gen", "kling-4", "out.mp4"], APPROVAL)

    assert not result.success
    assert "never charged twice" in result.error
    assert result.data == {"approval_required": False, "approval": APPROVAL}


def test_minicut_home_reads_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MINICUT_HOME", raising=False)
    monkeypatch.setenv("MH_HOME", str(tmp_path))
    assert cli.minicut_home() == tmp_path
    monkeypatch.setenv("MINICUT_HOME", str(tmp_path / "home"))
    assert cli.minicut_home() == tmp_path / "home"
